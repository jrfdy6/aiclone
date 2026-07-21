from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.pm_board import PMCard, PMExecutionGateBackfillRequest
from app.routes.pm_board import router
from app.security.execution_authorization import sign_execution_payload
from app.services import pm_card_service
from app.services.execution_gate_service import apply_execution_gate, grant_execution_approval


SAFE_ID = "11111111-1111-4111-8111-111111111111"
RISKY_ID = "22222222-2222-4222-8222-222222222222"


def _safe_payload() -> dict:
    return {
        "workspace_key": "work-life-tools",
        "instructions": ["Improve the internal validation flow inside Work Life Tools."],
        "acceptance_criteria": ["Focused tests pass and the PM result is written back."],
        "artifacts_expected": ["updated tests"],
        "completion_contract": {
            "source": "codex_native_remote_queue",
            "autostart": True,
            "done_when": ["Focused tests pass."],
        },
        "execution": {
            "state": "queued",
            "execution_mode": "delegated",
            "target_agent": "Work Life Tools Operator Agent",
            "capability_id": "codex.bounded_project_work/v1",
        },
    }


def _card(
    *,
    card_id: str = SAFE_ID,
    title: str = "Improve internal validation",
    source: str = "codex_native:remote_queue",
    payload: dict | None = None,
    status: str = "todo",
) -> PMCard:
    now = datetime.now(timezone.utc)
    return PMCard(
        id=card_id,
        title=title,
        owner="Neo",
        status=status,
        source=source,
        link_type=None,
        link_id=None,
        payload=deepcopy(payload if payload is not None else _safe_payload()),
        created_at=now,
        updated_at=now,
    )


def _request(mode: str = "preview") -> PMExecutionGateBackfillRequest:
    if mode == "apply":
        return PMExecutionGateBackfillRequest(mode="apply", confirmed=True, limit=25)
    return PMExecutionGateBackfillRequest(mode="preview", limit=25)


def test_preview_classifies_safe_card_without_writing_or_signing_secret(monkeypatch) -> None:
    monkeypatch.delenv("CONTROL_PLANE_JOB_SIGNING_SECRET", raising=False)
    card = _card()
    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill") as persist,
    ):
        result = pm_card_service.backfill_execution_gates(_request())

    persist.assert_not_called()
    assert result.mode == "preview"
    assert result.candidate_count == 1
    assert result.classified_auto_execute_count == 1
    assert result.would_become_runnable_count == 1
    assert result.items[0].action == "would_update"


def test_apply_persists_safe_gate_without_changing_execution_intent(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "backfill-test-secret")
    card = _card()
    captured: dict = {}

    def persist(_card: PMCard, payload: dict) -> PMCard:
        captured.update(payload)
        return _card.model_copy(update={"payload": sign_execution_payload(_card.id, payload)})

    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill", side_effect=persist),
    ):
        result = pm_card_service.backfill_execution_gates(_request("apply"))

    assert result.updated_count == 1
    assert result.items[0].action == "updated"
    assert result.items[0].would_become_runnable is True
    assert captured["execution"] == card.payload["execution"]
    assert captured["completion_contract"] == card.payload["completion_contract"]
    assert "execution_approval" not in captured
    assert captured["execution_gate"]["decision"] == "AUTO_EXECUTE"


def test_apply_persists_consequential_card_as_require_approval(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "backfill-test-secret")
    card = _card(card_id=RISKY_ID, title="Publish the LinkedIn post")
    captured: dict = {}

    def persist(_card: PMCard, payload: dict) -> PMCard:
        captured.update(payload)
        return _card.model_copy(update={"payload": sign_execution_payload(_card.id, payload)})

    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill", side_effect=persist),
    ):
        result = pm_card_service.backfill_execution_gates(_request("apply"))

    assert result.updated_count == 1
    assert result.classified_require_approval_count == 1
    assert result.would_become_runnable_count == 0
    assert "PUBLICATION" in result.items[0].risk_factors
    assert captured["execution_gate"]["approval_state"] == "missing"
    assert "execution_approval" not in captured


def test_benign_openclaw_legacy_card_remains_fail_closed() -> None:
    payload = _safe_payload()
    payload["completion_contract"]["source"] = "legacy_remote_queue"
    card = _card(source="openclaw:thin-trigger", payload=payload)
    with patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)):
        result = pm_card_service.backfill_execution_gates(_request())

    item = result.items[0]
    assert item.decision == "REQUIRE_APPROVAL"
    assert "UNKNOWN_EFFECT" in item.risk_factors
    assert item.would_become_runnable is False


def test_apply_requires_signing_configuration(monkeypatch) -> None:
    monkeypatch.delenv("CONTROL_PLANE_JOB_SIGNING_SECRET", raising=False)
    with (
        patch("app.security.execution_authorization.Path.read_text", side_effect=OSError),
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards") as scan,
    ):
        with pytest.raises(RuntimeError, match="signing is not configured"):
            pm_card_service.backfill_execution_gates(_request("apply"))
    scan.assert_not_called()


def test_current_signed_gate_is_idempotently_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "backfill-test-secret")
    card = _card()
    gated = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key="work-life-tools",
        payload=card.payload,
    )
    card = card.model_copy(update={"payload": sign_execution_payload(card.id, gated)})
    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill") as persist,
    ):
        result = pm_card_service.backfill_execution_gates(_request("apply"))

    persist.assert_not_called()
    assert result.already_current_count == 1
    assert result.items[0].action == "unchanged"


def test_active_claim_and_unpersisted_exact_approval_are_not_reactivated(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "backfill-test-secret")
    active_payload = _safe_payload()
    active_payload["execution"].update(
        {
            "state": "running",
            "executor_status": "running",
            "claim_id": "33333333-3333-4333-8333-333333333333",
            "executor_worker_id": "macbook-codex",
        }
    )
    active = _card(payload=active_payload)

    risky = _card(card_id=RISKY_ID, title="Publish the LinkedIn post")
    approved = grant_execution_approval(
        card_id=risky.id,
        title=risky.title,
        source=risky.source,
        workspace_key="work-life-tools",
        payload=risky.payload,
        approved_by="Neo",
    )
    approved.pop("execution_gate", None)
    risky = risky.model_copy(update={"payload": approved})

    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([active, risky], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill") as persist,
    ):
        result = pm_card_service.backfill_execution_gates(_request("apply"))

    persist.assert_not_called()
    assert result.active_claim_skipped_count == 1
    assert result.manual_reapproval_count == 1
    assert [item.action for item in result.items] == ["skipped_active_claim", "skipped_manual_reapproval"]


def test_cas_miss_does_not_report_activation(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "backfill-test-secret")
    card = _card()
    with (
        patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], False)),
        patch.object(pm_card_service, "_persist_execution_gate_backfill", return_value=None),
    ):
        result = pm_card_service.backfill_execution_gates(_request("apply"))

    assert result.cas_miss_count == 1
    assert result.updated_count == 0
    assert result.would_become_runnable_count == 0
    assert result.items[0].action == "cas_miss"


def test_backfill_request_requires_explicit_apply_confirmation() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/pm/admin/execution-gates/backfill",
        json={"mode": "apply", "limit": 25},
    )
    assert response.status_code == 422


def test_backfill_route_maps_missing_signing_configuration_to_503() -> None:
    app = FastAPI()
    app.include_router(router)
    with patch.object(pm_card_service, "backfill_execution_gates", side_effect=RuntimeError("signing unavailable")):
        response = TestClient(app).post(
            "/api/pm/admin/execution-gates/backfill",
            json={"mode": "apply", "confirmed": True, "limit": 25},
        )
    assert response.status_code == 503
    assert "signing unavailable" in response.json()["detail"]


def test_result_cursor_is_stable_uuid() -> None:
    card = _card()
    request = PMExecutionGateBackfillRequest(mode="preview", limit=1)
    with patch.object(pm_card_service, "_list_execution_gate_backfill_cards", return_value=([card], True)):
        result = pm_card_service.backfill_execution_gates(request)

    assert result.has_more is True
    assert result.next_after_card_id == UUID(SAFE_ID)
