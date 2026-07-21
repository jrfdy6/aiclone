from __future__ import annotations

from copy import deepcopy

import pytest

from app.services import execution_gate_service as service


def _safe_payload(**updates):
    payload = {
        "workspace_key": "work-life-tools",
        "goal": "Improve the calculator's internal validation flow.",
        "instructions": ["Update the validation code only inside the Work Life Tools workspace."],
        "acceptance_criteria": ["Focused tests pass and the result is written back to PM."],
        "artifacts_expected": ["updated tests"],
        "completion_contract": {
            "source": "codex_native_remote_queue",
            "autostart": True,
            "done_when": ["Focused tests pass."],
        },
        "execution": {
            "execution_mode": "delegated",
            "target_agent": "Work Life Tools Operator Agent",
            "capability_id": service.BOUNDED_PROJECT_CAPABILITY,
        },
    }
    payload.update(updates)
    return payload


def _evaluate(payload=None, *, title="Improve internal validation", source="codex_native:remote_queue"):
    return service.evaluate_execution_gate(
        card_id="card-1",
        title=title,
        source=source,
        workspace_key="work-life-tools",
        payload=payload or _safe_payload(),
    )


def test_bounded_internal_project_work_auto_executes() -> None:
    gate = _evaluate()

    assert gate["decision"] == service.AUTO_EXECUTE
    assert gate["risk_factors"] == []
    assert gate["approval_state"] == "not_required"
    assert service.execution_gate_allows_run(gate)


@pytest.mark.parametrize(
    ("title", "risk"),
    [
        ("Merge pull request #42 into main", "CODE_MERGE"),
        ("Deploy the app to Railway production", "DEPLOYMENT"),
        ("Publish the LinkedIn post", "PUBLICATION"),
        ("Send the customer an email reply", "EXTERNAL_COMMUNICATION"),
        ("Purchase a paid subscription with the business card", "FINANCIAL"),
        ("Delete the production database records", "DESTRUCTIVE_OR_IRREVERSIBLE"),
        ("Rotate the API key credential", "ACCESS_OR_PERMISSION_CHANGE"),
        ("Promote these traits into persona canon", "OWNER_JUDGMENT_REQUIRED"),
    ],
)
def test_consequential_action_requires_approval(title: str, risk: str) -> None:
    gate = _evaluate(title=title)

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert risk in gate["risk_factors"]
    assert not service.execution_gate_allows_run(gate)


def test_unknown_capability_fails_closed_even_from_signed_shape() -> None:
    payload = _safe_payload()
    payload["execution"]["capability_id"] = "producer.claims.this.is.safe/v1"

    gate = _evaluate(payload)

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert "UNKNOWN_CAPABILITY" in gate["risk_factors"]


def test_editorial_low_risk_fields_cannot_override_external_action() -> None:
    payload = _safe_payload(
        risk_level="low",
        approval_status="approved",
        publish_posture="safe",
    )

    gate = _evaluate(payload, title="Publish this post publicly on LinkedIn")

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert "PUBLICATION" in gate["risk_factors"]


def test_exact_approval_allows_approvable_risk_and_intent_edit_invalidates_it() -> None:
    payload = _safe_payload()
    approved = service.grant_execution_approval(
        card_id="card-1",
        title="Deploy the app to Railway production",
        source="codex_native:remote_queue",
        workspace_key="work-life-tools",
        payload=payload,
        approved_by="Neo",
    )

    assert approved["execution_gate"]["decision"] == service.REQUIRE_APPROVAL
    assert approved["execution_gate"]["approval_state"] == "approved"
    assert service.execution_gate_allows_run(approved)

    edited = deepcopy(approved)
    edited["instructions"] = ["Deploy to Railway production and then publish the launch post."]
    stale_gate = service.evaluate_execution_gate(
        card_id="card-1",
        title="Deploy the app to Railway production",
        source="codex_native:remote_queue",
        workspace_key="work-life-tools",
        payload=edited,
    )

    assert stale_gate["approval_state"] == "stale"
    assert not service.execution_gate_allows_run(stale_gate)


def test_credential_like_value_is_not_approval_overridable() -> None:
    payload = _safe_payload(context="Use token: sk-this-looks-like-a-secret-value-123456789")

    with pytest.raises(ValueError, match="cannot be approved"):
        service.grant_execution_approval(
            card_id="card-1",
            title="Update integration settings",
            source="codex_native:remote_queue",
            workspace_key="work-life-tools",
            payload=payload,
            approved_by="Neo",
        )


def test_brain_route_to_persona_canon_requires_owner_judgment() -> None:
    payload = {
        "workspace_key": "shared_ops",
        "brain_local_action": {
            "action": "signal_route",
            "parameters": {"route": {"route": "persona_canon"}},
        },
        "execution": {"execution_mode": "brain_local_action", "target_agent": "Brain Local Action"},
    }

    gate = service.evaluate_execution_gate(
        card_id="brain-card",
        title="Brain: route local signal",
        source="brain_local_action:signal_route",
        workspace_key="shared_ops",
        payload=payload,
    )

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert "OWNER_JUDGMENT_REQUIRED" in gate["risk_factors"]


def test_safe_brain_ingestion_uses_deterministic_local_runner() -> None:
    payload = {
        "workspace_key": "shared_ops",
        "brain_local_action": {"action": "youtube_watchlist_ingest", "parameters": {"request": {}}},
        "execution": {"execution_mode": "brain_local_action", "target_agent": "Brain Local Action"},
    }

    gate = service.evaluate_execution_gate(
        card_id="brain-card",
        title="Brain: ingest YouTube source locally",
        source="brain_local_action:youtube_watchlist_ingest",
        workspace_key="shared_ops",
        payload=payload,
    )

    assert gate["decision"] == service.AUTO_EXECUTE
    assert gate["runner_profile"] == "deterministic_local"


@pytest.mark.parametrize(
    "title",
    [
        "Draft a LinkedIn post for owner review",
        "Draft an email reply for owner review",
    ],
)
def test_private_draft_artifacts_do_not_count_as_external_delivery(title: str) -> None:
    gate = _evaluate(title=title)

    assert gate["decision"] == service.AUTO_EXECUTE
    assert "PUBLICATION" not in gate["risk_factors"]
    assert "EXTERNAL_COMMUNICATION" not in gate["risk_factors"]


def test_negated_external_actions_do_not_create_false_positive() -> None:
    payload = _safe_payload(
        instructions=["Create a private draft only. Do not publish, post, schedule, or send it."],
        acceptance_criteria=["The private draft is ready for owner review."],
    )

    gate = _evaluate(payload, title="Prepare a private response draft")

    assert gate["decision"] == service.AUTO_EXECUTE


@pytest.mark.parametrize(
    ("title", "risk"),
    [
        ("Restart the Railway production service", "DEPLOYMENT"),
        ("Roll back the production deployment", "DEPLOYMENT"),
        ("Run the current owner-review packet and record decisions", "OWNER_JUDGMENT_REQUIRED"),
        ("Upload the finished video to YouTube", "PUBLICATION"),
        ("Invite Casey as a production administrator", "ACCESS_OR_PERMISSION_CHANGE"),
        ("Reveal the API key in the result memo", "CREDENTIAL_ACCESS_REQUEST"),
        ("Update canonical identity claims", "OWNER_JUDGMENT_REQUIRED"),
        ("Delete the outdated story from story bank", "OWNER_JUDGMENT_REQUIRED"),
    ],
)
def test_additional_consequential_actions_fail_closed(title: str, risk: str) -> None:
    gate = _evaluate(title=title)

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert risk in gate["risk_factors"]


@pytest.mark.parametrize("workspace_key", ["linkedin-os", "feezie-os"])
def test_publication_classification_does_not_depend_on_workspace_alias(workspace_key: str) -> None:
    payload = _safe_payload(workspace_key=workspace_key)
    gate = service.evaluate_execution_gate(
        card_id="feezie-card",
        title="Schedule approved FEEZIE draft - FEEZIE-002",
        source="codex_native:remote_queue",
        workspace_key=workspace_key,
        payload=payload,
    )

    assert gate["decision"] == service.REQUIRE_APPROVAL
    assert "PUBLICATION" in gate["risk_factors"]
    assert gate["allowed_roots"] == ["workspaces/linkedin-content-os"]


def test_approval_risk_set_must_match_current_classification() -> None:
    approved = service.grant_execution_approval(
        card_id="card-1",
        title="Publish the LinkedIn post",
        source="codex_native:remote_queue",
        workspace_key="work-life-tools",
        payload=_safe_payload(),
        approved_by="Neo",
    )
    approved["execution_approval"]["approved_risk_factors"] = []

    gate = service.evaluate_execution_gate(
        card_id="card-1",
        title="Publish the LinkedIn post",
        source="codex_native:remote_queue",
        workspace_key="work-life-tools",
        payload=approved,
    )

    assert gate["approval_state"] == "stale"
    assert not service.execution_gate_allows_run(gate)


def test_credential_access_request_cannot_be_approved_into_codex() -> None:
    with pytest.raises(ValueError, match="cannot be approved"):
        service.grant_execution_approval(
            card_id="card-1",
            title="Reveal the API key in the result memo",
            source="codex_native:remote_queue",
            workspace_key="work-life-tools",
            payload=_safe_payload(),
            approved_by="Neo",
        )
