from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.models import StandupEntry
from app.models.automations import AutomationRun
from app.models.standups import StandupPromotionRequest
from app.security.execution_authorization import sign_execution_payload
from app.services import standup_truth_service
from app.services.standup_relevance_service import (
    build_standup_relevance_plan,
    effective_feezie_meeting_participants,
    validate_standup_relevance_plan,
)
from app.services.standup_truth_service import (
    ASYNC_ROLE_CONTRIBUTION_SCHEMA_VERSION,
    ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION,
    MEETING_EVIDENCE_SCHEMA_VERSION,
    MEETING_PHASES,
    PARTICIPANT_REPORT_AUTOMATION_ID,
    PARTICIPANT_REPORT_PROVENANCE,
    PARTICIPANT_REPORT_SCHEMA_VERSION,
    async_role_contribution_id,
    async_role_contribution_truth,
    canonical_promotion_claims,
    classify_standup,
    meeting_record_truth,
    promotion_payload_sha256,
    remote_standup_pm_update,
    remote_standup_promotion_payload,
    remote_standup_report_content,
    semantic_sha256,
)
from app.services.workspace_runtime_contract_service import (
    standup_participants_for,
)


NOW = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
MEETING_AT = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


def test_remote_promotion_projection_keeps_private_goal_and_excerpt_context_local() -> None:
    private_goal = (
        "Privately advance the exact workspace strategy through its canonical "
        "evidence and owner-governed phase boundary."
    )
    private_excerpt = (
        "This is a deliberately private multi-line workspace excerpt whose exact wording "
        "must remain on the Mac.\nIt includes a second sentence so the historical Yoda "
        "180-character synthesized prefix cannot evade exact-literal redaction."
    )
    normalized_excerpt = " ".join(private_excerpt.split())
    truncated_excerpt = normalized_excerpt[:179].rstrip() + "…"
    second_sentence = normalized_excerpt.split(". ", 1)[1]
    middle_slice = normalized_excerpt[58:154]
    local_path = "/" + "Users" + "/operator/project/workspaces/private/brief.md"
    promotion = {
        "meeting_id": "meeting-private-projection",
        "prep_id": "prep-private-projection",
        "workspace_key": "fusion-os",
        "cycle_id": "daily-private-projection",
        "standup_kind": "workspace_sync",
        "participants": ["Jean-Claude", "Fusion Systems Operator"],
        "summary": f"Evaluation against {private_goal}",
        "discussion_rounds": [
            {
                "round": 1,
                "speaker": "Fusion Systems Operator",
                "note": f"Grounding brief: {truncated_excerpt}",
                "provenance": "synthesized_role_lens",
            },
            {
                "round": 2,
                "speaker": "Jean-Claude",
                "note": f"Second sentence copied alone: {second_sentence}",
                "provenance": "synthesized_role_lens",
            },
            {
                "round": 3,
                "speaker": "Fusion Systems Operator",
                "note": f"Middle slice copied alone: {middle_slice}",
                "provenance": "synthesized_role_lens",
            },
        ],
        "strategy_context": {
            "display_name": "Fusion OS",
            "goal_contract_status": "available_private_authority",
            "goal_contract": {
                "schema_version": "workspace_goal_contract/v1",
                "goal": private_goal,
                "progress_signals": ["Private progress signal."],
                "phase_gate": "Private phase gate.",
                "no_action_trigger": "Private no-action trigger.",
                "safe_internal_boundary": ["Private automatic boundary."],
                "owner_required_boundary": ["Private owner boundary."],
                "authority_refs": [local_path],
            },
            "inferred_excerpt": private_excerpt,
            "goal_contract_source_path": local_path,
        },
        "recursion": {
            "goal": {"goal": private_goal},
            "no_action": {
                "selected": True,
                "reason": "No eligible change was selected.",
                "future_trigger": "Private no-action trigger.",
            },
        },
        "conversation_path": local_path,
        "source_paths": [local_path],
        "memory_promotions": [private_excerpt],
        "pm_updates": [
            {
                "workspace_key": "fusion-os",
                "scope": "workspace",
                "owner_agent": "fusion-operator",
                "title": "Prepare one bounded internal packet",
                "status": "todo",
                "reason": "Selected by the bounded local cycle.",
                "payload": {
                    "goal_contract": {"goal": private_goal},
                    "strategy_context": {"inferred_excerpt": private_excerpt},
                    "dream_lineage": {
                        "findings": [private_excerpt],
                        "recommendation": private_excerpt,
                    },
                    "instructions": [
                        f"Use {local_path} without copying {private_goal} remotely.",
                        f"Do not persist this middle slice: {middle_slice}",
                    ],
                    "reference_artifacts": [local_path],
                },
            }
        ],
    }

    projected = remote_standup_promotion_payload(promotion)
    claims = canonical_promotion_claims(promotion)
    projected_pm = remote_standup_pm_update(promotion["pm_updates"][0])
    projected_report = remote_standup_report_content(
        {
            "note": f"Copied second sentence: {second_sentence}",
            "evidence_refs": ["bounded:test"],
            "position": "challenge",
            "risks": [f"Copied middle slice: {middle_slice}"],
            "recommended_next_step": f"Avoid copying {middle_slice}",
            "owner_decision_required": False,
        },
        promotion_payload=promotion,
        private_contexts=(promotion["strategy_context"],),
    )
    serialized = "\n".join(
        json.dumps(value, sort_keys=True)
        for value in (projected, claims, projected_pm, projected_report)
    )

    assert private_goal not in serialized
    assert private_excerpt not in serialized
    assert normalized_excerpt[:179] not in serialized
    assert second_sentence not in serialized
    assert middle_slice not in serialized
    assert "/" + "Users" + "/" not in serialized
    assert "safe_internal_boundary" not in serialized
    assert "owner_required_boundary" not in serialized
    assert "authority_refs" not in serialized
    assert '"goal_contract":' not in serialized
    assert "progress_signals" not in serialized
    assert "phase_gate" not in serialized
    assert "no_action_trigger" not in serialized
    assert projected["conversation_path"] is None
    assert projected["source_paths"] == []
    assert projected["memory_promotions"] == []
    assert projected["strategy_context"] == {
        "display_name": "Fusion OS",
        "goal_contract_status": "available_private_authority",
    }


def _structural_projection_fixture(
    *,
    workspace_key: str,
    standup_kind: str,
    participants: list[str],
    standup_relevance: dict | None = None,
) -> dict:
    private_goal = (
        "sep-2-private-proof binds "
        f"{workspace_key} {standup_kind} {' '.join(participants)}"
    )
    relevance = dict(standup_relevance or {})
    goal_contract = {
        "goal": private_goal,
        "workspace_key": workspace_key,
        "standup_kind": standup_kind,
        "participants": participants,
    }
    if relevance:
        goal_contract["policy_version"] = relevance["policy_version"]
    return {
        "meeting_id": f"meeting-{workspace_key}-{standup_kind}",
        "prep_id": f"prep-{workspace_key}-{standup_kind}",
        "workspace_key": workspace_key,
        "cycle_id": "daily-2026-09-02@20260902T101500000000Z",
        "standup_kind": standup_kind,
        "owner": "Jean-Claude",
        "source": "standup_prep",
        "participants": participants,
        "summary": f"Copied private authority: {private_goal}",
        "agenda": ["Evaluate the bounded current state."],
        "blockers": [],
        "commitments": [],
        "needs": [],
        "audience_response": [],
        "decisions": [],
        "owners": [],
        "artifact_deltas": [],
        "standup_sections": {},
        "pm_snapshot": {},
        "strategy_context": {
            "display_name": workspace_key,
            "goal_contract_status": "available_private_authority",
            "goal_contract": goal_contract,
        },
        "standup_relevance": relevance,
        "discussion_rounds": [
            {
                "round": index,
                "speaker": participant,
                "note": "Bounded public-safe structural regression note.",
            }
            for index, participant in enumerate(participants, start=1)
        ],
        "source_paths": [],
        "memory_promotions": [],
        "prior_standup": {},
        "continuity": {},
        "recursion": {
            "planned_participants": participants,
            "closing_participant": "Jean-Claude",
        },
        "recommendation_path": None,
        "pm_updates": [],
    }


@pytest.mark.parametrize(
    "workspace_key",
    (
        "fusion-os",
        "easyoutfitapp",
        "ai-swag-store",
        "agc",
        "work-life-tools",
    ),
)
def test_sep2_project_structural_identifiers_survive_private_projection(
    workspace_key: str,
) -> None:
    participants = standup_participants_for(workspace_key, "workspace_sync")
    promotion = _structural_projection_fixture(
        workspace_key=workspace_key,
        standup_kind="workspace_sync",
        participants=participants,
    )

    projected = remote_standup_promotion_payload(promotion)
    replayed = remote_standup_promotion_payload(projected)
    validated = StandupPromotionRequest.model_validate(replayed)

    assert validated.workspace_key == workspace_key
    assert validated.standup_kind == "workspace_sync"
    assert validated.participants == participants
    assert [item["speaker"] for item in validated.discussion_rounds] == participants
    assert validated.recursion["planned_participants"] == participants
    assert "sep-2-private-proof" not in json.dumps(replayed, sort_keys=True)
    assert "[private-workspace-context]" in replayed["summary"]


@pytest.mark.parametrize(
    "standup_kind",
    ("executive_ops", "operations", "weekly_review", "saturday_vision"),
)
def test_sep2_shared_ops_structural_identifiers_survive_private_projection(
    standup_kind: str,
) -> None:
    participants = ["Jean-Claude", "Neo", "Yoda"]
    promotion = _structural_projection_fixture(
        workspace_key="shared_ops",
        standup_kind=standup_kind,
        participants=participants,
    )

    projected = remote_standup_promotion_payload(promotion)
    replayed = remote_standup_promotion_payload(projected)
    validated = StandupPromotionRequest.model_validate(replayed)

    assert validated.workspace_key == "shared_ops"
    assert validated.standup_kind == standup_kind
    assert validated.participants == participants
    assert [item["speaker"] for item in validated.discussion_rounds] == participants
    assert "sep-2-private-proof" not in json.dumps(replayed, sort_keys=True)


@pytest.mark.parametrize(
    "tags",
    (
        ["execution_or_lifecycle"],
        ["owner_intent_or_approval", "strategy_or_positioning"],
    ),
)
def test_sep2_feezie_relevance_authority_survives_private_projection(
    tags: list[str],
) -> None:
    relevance = build_standup_relevance_plan(
        [
            {
                "id": "sep2-feezie-structural-regression",
                "title": "Evaluate one bounded FEEZIE agenda item",
                "workspace_key": "feezie-os",
                "source_ids": ["bounded-source-1"],
                "observed_at": "2026-09-02T10:15:00Z",
                "tags": tags,
            }
        ],
        now=datetime(2026, 9, 2, 10, 15, tzinfo=timezone.utc),
    )
    participants = (
        effective_feezie_meeting_participants(relevance)
        if relevance["disposition"] == "run"
        else [
            str(item["display_name"])
            for item in relevance["participant_plan"]
        ]
    )
    promotion = _structural_projection_fixture(
        workspace_key="feezie-os",
        standup_kind="workspace_sync",
        participants=participants,
        standup_relevance=relevance,
    )

    projected = remote_standup_promotion_payload(promotion)
    replayed = remote_standup_promotion_payload(projected)
    validated = StandupPromotionRequest.model_validate(replayed)
    validated_relevance = validate_standup_relevance_plan(
        validated.standup_relevance
    )

    assert validated.workspace_key == "feezie-os"
    assert validated.standup_kind == "workspace_sync"
    assert validated.participants == participants
    assert validated_relevance["policy_version"] == relevance["policy_version"]
    assert validated_relevance["selected_roles"] == relevance["selected_roles"]
    assert [
        item["display_name"] for item in validated_relevance["participant_plan"]
    ] == [item["display_name"] for item in relevance["participant_plan"]]
    assert "sep-2-private-proof" not in json.dumps(replayed, sort_keys=True)


@pytest.mark.parametrize("workspace_key", ("fusion os", "unknown-workspace"))
def test_remote_projection_rejects_noncanonical_workspace_identifiers(
    workspace_key: str,
) -> None:
    promotion = _structural_projection_fixture(
        workspace_key=workspace_key,
        standup_kind="workspace_sync",
        participants=["Jean-Claude", "Fusion Systems Operator"],
    )

    with pytest.raises(ValueError, match="canonical workspace_key"):
        remote_standup_promotion_payload(promotion)


def test_remote_projection_rejects_tampered_feezie_policy_before_preservation() -> None:
    relevance = build_standup_relevance_plan(
        [
            {
                "id": "sep2-feezie-tamper",
                "title": "Evaluate a bounded execution issue",
                "workspace_key": "feezie-os",
                "source_ids": ["bounded-source-1"],
                "observed_at": "2026-09-02T10:15:00Z",
                "tags": ["execution_or_lifecycle"],
            }
        ],
        now=datetime(2026, 9, 2, 10, 15, tzinfo=timezone.utc),
    )
    relevance["policy_version"] = "untrusted-policy/v0"
    promotion = _structural_projection_fixture(
        workspace_key="feezie-os",
        standup_kind="workspace_sync",
        participants=["Jean-Claude"],
        standup_relevance=relevance,
    )

    with pytest.raises(ValueError, match="policy version is not authoritative"):
        remote_standup_promotion_payload(promotion)


def _standup(**overrides) -> StandupEntry:
    return StandupEntry(
        id=overrides.pop("id", "standup-1"),
        owner=overrides.pop("owner", "Jean-Claude"),
        workspace_key=overrides.pop("workspace_key", "shared_ops"),
        status=overrides.pop("status", "completed"),
        blockers=overrides.pop("blockers", []),
        commitments=overrides.pop("commitments", []),
        needs=overrides.pop("needs", []),
        source=overrides.pop("source", "standup_prep"),
        conversation_path=None,
        payload=overrides.pop("payload", {"summary": "Current operating decision.", "decisions": ["Proceed."]}),
        created_at=overrides.pop("created_at", NOW - timedelta(hours=2)),
        **overrides,
    )


def _participant_key(display_name: str) -> str:
    return "-".join(
        part
        for part in "".join(
            character.lower() if character.isalnum() else "-"
            for character in display_name
        ).split("-")
        if part
    )


def _signed_meeting_fixture(monkeypatch, participants=None):
    monkeypatch.setenv("CONTROL_PLANE_JOB_SIGNING_SECRET", "meeting-integrity-test-secret")
    participants = list(participants or ["Jean-Claude", "Neo", "Yoda"])
    synthetic_identity_digests = {
        participant: semantic_sha256(
            {
                "fixture": "public-safe-canonical-identity-pack",
                "workspace_key": "shared_ops",
                "participant": participant,
            }
        )
        for participant in participants
    }
    monkeypatch.setattr(
        standup_truth_service,
        "canonical_identity_pack_sha256",
        lambda _workspace, participant: synthetic_identity_digests.get(participant),
    )
    meeting_id = "meeting-shared-ops-20260826T180000Z"
    cycle_id = "daily-2026-08-26@20260826T180000000000Z"
    standup_kind = "executive_ops"
    promotion = {
        "meeting_id": meeting_id,
        "prep_id": "prep-shared-ops-20260826T180000Z",
        "workspace_key": "shared_ops",
        "cycle_id": cycle_id,
        "standup_kind": standup_kind,
        "owner": "Jean-Claude",
        "source": "standup_prep",
        "participants": participants,
        "summary": "Run one independently receipted executive meeting.",
        "agenda": ["Review current evidence", "Resolve the next bounded action"],
        "blockers": [],
        "commitments": ["Carry verified outcomes into the next cycle."],
        "needs": [],
        "audience_response": [],
        "decisions": ["Proceed only from canonical participant reports."],
        "owners": ["Jean-Claude"],
        "artifact_deltas": [],
        "standup_sections": {},
        "pm_snapshot": {},
        "strategy_context": {},
        "standup_relevance": {},
        "source_paths": [],
        "memory_promotions": [],
        "prior_standup": {},
        "continuity": {},
        "recursion": {},
        "recommendation_path": None,
        "pm_updates": [],
    }
    promotion_sha = promotion_payload_sha256(promotion)
    participant_run_id = lambda phase_index, participant: (  # noqa: E731
        f"standup-participant::{meeting_id}::{phase_index}::{_participant_key(participant)}"
    )
    resolution_run_ids = [participant_run_id(3, participant) for participant in participants[1:]]
    runs: list[AutomationRun] = []
    discussion: list[dict] = []
    global_round = 0
    for phase_index, phase in MEETING_PHASES:
        phase_participants = (
            [*participants[1:], participants[0]]
            if phase == "commitments_resolution"
            else participants
        )
        for participant in phase_participants:
            global_round += 1
            run_id = participant_run_id(phase_index, participant)
            is_closing_report = phase_index == 3 and participant == participants[0]
            report_content = {
                "note": f"{participant} supplied the {phase} report.",
                "evidence_refs": [f"evidence-{phase_index}-{_participant_key(participant)}"],
                "position": "affirm",
                "risks": [],
                "recommended_next_step": "Continue the exact bounded proposal or retain its trigger.",
                "owner_decision_required": False,
            }
            if is_closing_report:
                report_content.update(
                    {
                        "proposal_disposition": "ratify_exact",
                        "ratification_reason": "Every signed resolution supports the exact bounded proposal.",
                    }
                )
            metadata = {
                "schema_version": PARTICIPANT_REPORT_SCHEMA_VERSION,
                "meeting_id": meeting_id,
                "cycle_id": cycle_id,
                "standup_kind": standup_kind,
                "workspace_key": "shared_ops",
                "phase": phase,
                "phase_index": phase_index,
                "participant_key": _participant_key(participant),
                "display_name": participant,
                "identity_pack_sha256": synthetic_identity_digests[participant],
                "input_sha256": semantic_sha256(
                    {"meeting_id": meeting_id, "phase": phase, "participant": participant}
                ),
                "meeting_packet_sha256": semantic_sha256(
                    {"meeting_id": meeting_id, "promotion": promotion_sha}
                ),
                "role_context_schema_version": "standup_role_context/v1",
                "role_context_sha256": semantic_sha256(
                    {"participant": participant, "role_context": "bounded"}
                ),
                "closing_participant": participants[0],
                "is_closing_report": is_closing_report,
                "resolution_reports_considered": (
                    resolution_run_ids if is_closing_report else []
                ),
                "promotion_payload_sha256": promotion_sha,
                "report_content": report_content,
                "report_sha256": semantic_sha256(report_content),
                "generated_at": MEETING_AT.isoformat().replace("+00:00", "Z"),
                "provenance": PARTICIPANT_REPORT_PROVENANCE,
            }
            runs.append(
                AutomationRun(
                    id=run_id,
                    automation_id=PARTICIPANT_REPORT_AUTOMATION_ID,
                    automation_name="Standup Participant Report",
                    source="local_launchd_registry",
                    runtime="codex_exec",
                    status="completed",
                    run_at=MEETING_AT,
                    finished_at=MEETING_AT,
                    owner_agent=participant,
                    scope="shared_ops",
                    workspace_key="shared_ops",
                    action_required=False,
                    metadata=sign_execution_payload(run_id, metadata),
                )
            )
            discussion.append(
                {
                    "round": global_round,
                    "phase": phase,
                    "phase_index": phase_index,
                    "speaker": participant,
                    "note": report_content["note"],
                    "position": report_content["position"],
                    "risks": report_content["risks"],
                    "recommended_next_step": report_content["recommended_next_step"],
                    "owner_decision_required": report_content["owner_decision_required"],
                    **(
                        {
                            "proposal_disposition": report_content["proposal_disposition"],
                            "ratification_reason": report_content["ratification_reason"],
                        }
                        if is_closing_report
                        else {}
                    ),
                    "participant_report_run_id": run_id,
                    "provenance": PARTICIPANT_REPORT_PROVENANCE,
                }
            )
    evidence = {
        "schema_version": MEETING_EVIDENCE_SCHEMA_VERSION,
        "meeting_id": meeting_id,
        "participant_report_run_ids": [run.id for run in runs],
    }
    body = {
        "workspace_key": "shared_ops",
        "standup_kind": standup_kind,
        "cycle_id": cycle_id,
        "meeting_id": meeting_id,
        "record_kind": "standup",
        "meeting_held": True,
        "evaluation_only": False,
        "participants": participants,
        "discussion": discussion,
        "meeting_evidence": evidence,
        "promotion_claims": canonical_promotion_claims(promotion),
    }
    monkeypatch.setattr(standup_truth_service, "list_runs", lambda **_kwargs: runs)
    return body, runs


def test_shared_ops_standup_has_tighter_freshness_window() -> None:
    truth = classify_standup(_standup(created_at=NOW - timedelta(hours=13)), now=NOW)

    assert truth["freshness_limit_hours"] == 12
    assert truth["freshness"] == "degraded"
    assert truth["age_hours"] == 13.0


def test_standup_freshness_rejects_naive_evaluation_time() -> None:
    with pytest.raises(ValueError, match="ai_clone_utc timezone offset"):
        classify_standup(_standup(), now=datetime(2026, 7, 25, 16, 0))


def test_legacy_feezie_identity_uses_feezie_freshness_contract() -> None:
    truth = classify_standup(
        _standup(workspace_key="linkedin-os", created_at=NOW - timedelta(hours=30)),
        now=NOW,
    )

    assert truth["workspace_key"] == "feezie-os"
    assert truth["freshness"] == "degraded"
    assert truth["freshness_degraded"] is True


def test_standup_freshness_uses_semantic_observation_not_late_persistence() -> None:
    truth = classify_standup(
        _standup(
            created_at=NOW,
            payload={
                "summary": "A late persistence of an older cycle.",
                "recursion": {
                    "observed_at": (NOW - timedelta(hours=20)).isoformat(),
                    "clock": {
                        "authority": "ai_clone_utc",
                        "observed_at": (NOW - timedelta(hours=20)).isoformat(),
                    },
                },
            },
        ),
        now=NOW,
    )

    assert truth["freshness"] == "stale"
    assert truth["freshness_clock"] == "semantic_observed_at"
    assert truth["freshness_degraded"] is False


def test_conflicting_semantic_standup_clocks_fail_closed() -> None:
    truth = classify_standup(
        _standup(
            created_at=NOW,
            payload={
                "summary": "Conflicting observations cannot be fresh.",
                "observed_at": NOW.isoformat(),
                "recursion": {
                    "observed_at": (NOW - timedelta(hours=1)).isoformat(),
                },
            },
        ),
        now=NOW,
    )

    assert truth["freshness"] == "invalid"
    assert truth["observed_at"] is None
    assert truth["freshness_clock"] == "conflicting_semantic_observation"


def test_cycle_id_microseconds_do_not_conflict_with_second_precision_observation() -> None:
    truth = classify_standup(
        _standup(
            created_at=NOW,
            payload={
                "summary": "The explicit observation remains one clock.",
                "cycle_id": "daily-2026-07-25@20260725T160000123456Z",
                "recursion": {
                    "observed_at": "2026-07-25T16:00:00Z",
                    "clock": {
                        "authority": "ai_clone_utc",
                        "observed_at": "2026-07-25T16:00:00Z",
                    },
                },
            },
        ),
        now=NOW,
    )

    assert truth["freshness"] == "current"
    assert truth["freshness_clock"] == "semantic_observed_at"


def test_noncanonical_clock_authority_cannot_mark_standup_current() -> None:
    truth = classify_standup(
        _standup(
            created_at=NOW,
            payload={
                "summary": "Only the canonical AI Clone UTC clock is valid.",
                "recursion": {
                    "observed_at": "2026-07-25T16:00:00Z",
                    "clock": {
                        "authority": "host_local_time",
                        "observed_at": "2026-07-25T16:00:00Z",
                    },
                },
            },
        ),
        now=NOW,
    )

    assert truth["freshness"] == "invalid"
    assert truth["freshness_clock"] == "invalid_semantic_clock_authority"


def test_commitment_heavy_standup_without_decision_is_marked_ceremonial() -> None:
    truth = classify_standup(
        _standup(
            commitments=["One", "Two", "Three", "Four", "Five"],
            payload={"summary": "Continue all current commitments."},
        ),
        now=NOW,
    )

    assert truth["quality"] == "ceremonial"
    assert truth["has_decision_output"] is False


def test_pm_handoff_makes_standup_actionable() -> None:
    truth = classify_standup(
        _standup(
            commitments=["One", "Two", "Three", "Four"],
            payload={"summary": "Route one priority.", "pm_updates": [{"title": "Ship it"}]},
        ),
        now=NOW,
    )

    assert truth["quality"] == "actionable"
    assert truth["decision_yield"] == 1


def test_signed_canonical_phase_receipts_verify_real_meeting(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)

    truth = meeting_record_truth(
        body,
        source="standup_prep",
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is True
    assert truth["reason"] == "signed_canonical_participant_reports_verified"
    assert len(truth["canonical_meeting_evidence"]["participant_reports"]) == 9
    assert truth["canonical_discussion"] == body["discussion"]
    assert truth["canonical_ratification"]["proposal_disposition"] == "ratify_exact"
    assert truth["canonical_ratification"]["recommendations_authorized"] is True


@pytest.mark.parametrize(
    ("tag", "participant"),
    (
        ("owner_intent_or_approval", "Neo"),
        ("strategy_or_positioning", "Yoda"),
    ),
)
def test_signed_async_role_receipt_verifies_without_meeting_or_authority_transfer(
    monkeypatch,
    tag: str,
    participant: str,
) -> None:
    monkeypatch.setenv(
        "CONTROL_PLANE_JOB_SIGNING_SECRET",
        "async-role-contribution-test-secret",
    )
    observed_at = datetime(2026, 8, 27, 15, tzinfo=timezone.utc)
    relevance = build_standup_relevance_plan(
        [
            {
                "id": f"one-role-{participant.lower()}",
                "title": "Evaluate one bounded FEEZIE issue",
                "workspace_key": "feezie-os",
                "source_ids": ["bounded-source-1"],
                "observed_at": observed_at,
                "tags": [tag],
            }
        ],
        now=observed_at,
    )
    promotion = {
        "prep_id": f"prep-{participant.lower()}",
        "workspace_key": "feezie-os",
        "standup_kind": "workspace_sync",
        "cycle_id": "daily-2026-08-27@20260827T150000000000Z",
        "owner": "Jean-Claude",
        "source": "standup_prep",
        "participants": [participant],
        "summary": "Evaluate one bounded proposal.",
        "agenda": ["Evaluate one bounded proposal."],
        "blockers": [],
        "commitments": [],
        "needs": [],
        "audience_response": [],
        "decisions": [],
        "owners": [],
        "artifact_deltas": [],
        "standup_sections": {},
        "pm_snapshot": {},
        "strategy_context": {},
        "standup_relevance": relevance,
        "source_paths": [],
        "memory_promotions": [],
        "prior_standup": {},
        "continuity": {},
        "recursion": {},
        "recommendation_path": None,
        "pm_updates": [],
    }
    contribution_id = async_role_contribution_id(
        promotion,
        display_name=participant,
    )
    run_id = str(
        uuid5(
            NAMESPACE_URL,
            f"ai-clone:standup-async-role-report:{contribution_id}",
        )
    )
    report_content = {
        "note": f"{participant} supplied one independently bounded role assessment.",
        "evidence_refs": ["bounded-source-1"],
        "position": "affirm",
        "risks": [],
        "recommended_next_step": "Route only through the existing bounded PM authority.",
        "owner_decision_required": False,
    }
    metadata = {
        "schema_version": ASYNC_ROLE_CONTRIBUTION_SCHEMA_VERSION,
        "contribution_id": contribution_id,
        "cycle_id": promotion["cycle_id"],
        "workspace_key": "feezie-os",
        "standup_kind": "workspace_sync",
        "participant_key": participant.lower(),
        "display_name": participant,
        "relevance_fingerprint": relevance["input_fingerprint"],
        "identity_pack_sha256": "a" * 64,
        "input_sha256": "b" * 64,
        "role_context_schema_version": "standup_role_context/v1",
        "role_context_sha256": "c" * 64,
        "canonical_pm_execution_authority": "Jean-Claude",
        "participant_is_canonical_pm_execution_authority": False,
        "pm_execution_authority_transferred": False,
        "authority_scope": "independent_role_lens_only",
        "promotion_payload_sha256": promotion_payload_sha256(promotion),
        "report_content": report_content,
        "report_sha256": semantic_sha256(report_content),
        "generated_at": observed_at.isoformat().replace("+00:00", "Z"),
        "provenance": PARTICIPANT_REPORT_PROVENANCE,
    }
    run = AutomationRun(
        id=run_id,
        automation_id=PARTICIPANT_REPORT_AUTOMATION_ID,
        automation_name="Standup Participant Report",
        source="local_launchd_registry",
        runtime="codex_exec",
        status="completed",
        run_at=observed_at,
        finished_at=observed_at,
        owner_agent=participant,
        scope="workspace",
        workspace_key="feezie-os",
        action_required=False,
        metadata=sign_execution_payload(run_id, metadata),
    )
    monkeypatch.setattr(
        standup_truth_service,
        "list_runs",
        lambda **_kwargs: [run],
    )
    evidence = {
        "schema_version": ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION,
        "contribution_id": contribution_id,
        "participant_report_run_id": run_id,
        "display_name": participant,
        "canonical_pm_execution_authority": "Jean-Claude",
        "pm_execution_authority_transferred": False,
        "meeting_held": False,
    }

    truth = async_role_contribution_truth(
        evidence,
        promotion_payload=promotion,
    )

    assert truth["valid"] is True
    assert truth["state"] == "verified_signed_async_role_contribution"
    canonical = truth["canonical_evidence"]
    assert canonical["display_name"] == participant
    assert canonical["meeting_held"] is False
    assert canonical["canonical_pm_execution_authority"] == "Jean-Claude"
    assert canonical["pm_execution_authority_transferred"] is False
    assert canonical["authority_scope"] == "independent_role_lens_only"

    rejected = async_role_contribution_truth(
        {**evidence, "pm_execution_authority_transferred": True},
        promotion_payload=promotion,
    )
    assert rejected == {
        "valid": False,
        "state": "invalid_async_role_evidence",
        "reason": "async_role_evidence_identity_invalid",
    }


def test_signed_neo_yoda_reports_cannot_replace_jean_claude_as_closer(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch, participants=["Neo", "Yoda"])

    truth = meeting_record_truth(
        body,
        source="standup_prep",
        expected_participants=["Neo", "Yoda"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "canonical_jean_claude_closer_missing"


def test_local_ledger_timestamp_does_not_break_purpose_signature(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    for run in runs:
        run.metadata["locally_recorded_at"] = "2026-08-26T18:00:01Z"

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is True


def test_blocked_resolution_requires_canonical_closer_to_withhold(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    yoda_resolution = next(
        run
        for run in runs
        if run.owner_agent == "Yoda" and run.metadata.get("phase") == "commitments_resolution"
    )
    yoda_content = dict(yoda_resolution.metadata["report_content"])
    yoda_content["position"] = "block"
    yoda_resolution.metadata = sign_execution_payload(
        yoda_resolution.id,
        {
            **yoda_resolution.metadata,
            "report_content": yoda_content,
            "report_sha256": semantic_sha256(yoda_content),
        },
    )
    yoda_round = next(
        item
        for item in body["discussion"]
        if item["speaker"] == "Yoda" and item["phase"] == "commitments_resolution"
    )
    yoda_round["position"] = "block"

    rejected = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )
    assert rejected["is_meeting"] is False
    assert rejected["reason"] == "blocked_resolution_cannot_be_ratified"

    closer = next(
        run
        for run in runs
        if run.owner_agent == "Jean-Claude"
        and run.metadata.get("phase") == "commitments_resolution"
    )
    closer_content = dict(closer.metadata["report_content"])
    closer_content.update(
        {
            "proposal_disposition": "withhold",
            "ratification_reason": "Yoda's signed block withholds this exact proposal from dispatch.",
        }
    )
    closer.metadata = sign_execution_payload(
        closer.id,
        {
            **closer.metadata,
            "report_content": closer_content,
            "report_sha256": semantic_sha256(closer_content),
        },
    )
    closer_round = next(
        item
        for item in body["discussion"]
        if item["speaker"] == "Jean-Claude"
        and item["phase"] == "commitments_resolution"
    )
    closer_round.update(
        {
            "proposal_disposition": "withhold",
            "ratification_reason": closer_content["ratification_reason"],
        }
    )

    verified = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )
    assert verified["is_meeting"] is True
    assert verified["canonical_ratification"]["recommendations_authorized"] is False
    assert verified["canonical_ratification"]["blocked_by"] == ["Yoda"]


def test_challenge_and_owner_requirement_remain_visible_when_closer_ratifies(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    neo_resolution = next(
        run
        for run in runs
        if run.owner_agent == "Neo" and run.metadata.get("phase") == "commitments_resolution"
    )
    neo_content = dict(neo_resolution.metadata["report_content"])
    neo_content.update({"position": "challenge", "owner_decision_required": True})
    neo_resolution.metadata = sign_execution_payload(
        neo_resolution.id,
        {
            **neo_resolution.metadata,
            "report_content": neo_content,
            "report_sha256": semantic_sha256(neo_content),
        },
    )
    neo_round = next(
        item
        for item in body["discussion"]
        if item["speaker"] == "Neo" and item["phase"] == "commitments_resolution"
    )
    neo_round.update({"position": "challenge", "owner_decision_required": True})

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is True
    assert truth["canonical_ratification"]["recommendations_authorized"] is True
    assert truth["canonical_ratification"]["automatic_dispatch_authorized"] is False
    assert truth["canonical_ratification"]["owner_decision_routing_required"] is True
    assert truth["canonical_ratification"]["recommendation_routing"] == "owner_decision_required"
    assert truth["canonical_ratification"]["owner_decision_required_by"] == ["Neo"]
    neo_position = next(
        item
        for item in truth["canonical_ratification"]["resolution_positions"]
        if item["participant"] == "Neo"
    )
    assert neo_position["position"] == "challenge"
    assert neo_position["owner_decision_required"] is True
    challenge_disposition = truth["canonical_ratification"]["challenge_dispositions"][0]
    assert challenge_disposition["participant"] == "Neo"
    assert challenge_disposition["report_run_id"] == neo_resolution.id
    assert challenge_disposition["disposition"] == "overridden_by_exact_ratification"
    assert challenge_disposition["closed_by"] == "Jean-Claude"
    assert challenge_disposition["reason"] == truth["canonical_ratification"]["ratification_reason"]


def test_plain_challenge_is_explicitly_disposed_by_closer_not_silently_ignored(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    yoda_resolution = next(
        run
        for run in runs
        if run.owner_agent == "Yoda" and run.metadata.get("phase") == "commitments_resolution"
    )
    yoda_content = dict(yoda_resolution.metadata["report_content"])
    yoda_content["position"] = "challenge"
    yoda_resolution.metadata = sign_execution_payload(
        yoda_resolution.id,
        {
            **yoda_resolution.metadata,
            "report_content": yoda_content,
            "report_sha256": semantic_sha256(yoda_content),
        },
    )
    yoda_round = next(
        item
        for item in body["discussion"]
        if item["speaker"] == "Yoda" and item["phase"] == "commitments_resolution"
    )
    yoda_round["position"] = "challenge"

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is True
    ratification = truth["canonical_ratification"]
    assert ratification["recommendations_authorized"] is True
    assert ratification["automatic_dispatch_authorized"] is True
    assert ratification["challenged_by"] == ["Yoda"]
    assert ratification["challenge_dispositions"] == [
        {
            "participant": "Yoda",
            "report_run_id": yoda_resolution.id,
            "disposition": "overridden_by_exact_ratification",
            "closed_by": "Jean-Claude",
            "closing_report_run_id": ratification["closing_report_run_id"],
            "reason": ratification["ratification_reason"],
        }
    ]


def test_closer_owner_requirement_cannot_authorize_automatic_dispatch(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    closer = next(
        run
        for run in runs
        if run.owner_agent == "Jean-Claude"
        and run.metadata.get("phase") == "commitments_resolution"
    )
    closer_content = dict(closer.metadata["report_content"])
    closer_content["owner_decision_required"] = True
    closer.metadata = sign_execution_payload(
        closer.id,
        {
            **closer.metadata,
            "report_content": closer_content,
            "report_sha256": semantic_sha256(closer_content),
        },
    )
    closer_round = next(
        item
        for item in body["discussion"]
        if item["speaker"] == "Jean-Claude"
        and item["phase"] == "commitments_resolution"
    )
    closer_round["owner_decision_required"] = True

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is True
    ratification = truth["canonical_ratification"]
    assert ratification["proposal_disposition"] == "ratify_exact"
    assert ratification["recommendations_authorized"] is True
    assert ratification["automatic_dispatch_authorized"] is False
    assert ratification["owner_decision_routing_required"] is True
    assert ratification["owner_decision_required_by"] == ["Jean-Claude"]


def test_fake_64_hex_caller_reports_cannot_self_certify_attendance(monkeypatch) -> None:
    monkeypatch.setattr(standup_truth_service, "list_runs", lambda **_kwargs: [])
    body = {
        "workspace_key": "shared_ops",
        "standup_kind": "executive_ops",
        "cycle_id": "cycle-fake",
        "meeting_id": "meeting-fake",
        "record_kind": "standup",
        "meeting_held": True,
        "participants": ["Jean-Claude", "Neo", "Yoda"],
        "discussion": [
            {
                "round": index,
                "speaker": participant,
                "note": "Caller-shaped dialogue.",
                "participant_report_id": f"fake-{index}",
                "provenance": "independent_agent",
            }
            for index, participant in enumerate(["Jean-Claude", "Neo", "Yoda"], start=1)
        ],
        "meeting_evidence": {
            "schema_version": MEETING_EVIDENCE_SCHEMA_VERSION,
            "meeting_id": "meeting-fake",
            "participant_reports": [
                {
                    "schema_version": PARTICIPANT_REPORT_SCHEMA_VERSION,
                    "report_id": f"fake-{index}",
                    "agent_run_id": f"fake-run-{index}",
                    "display_name": participant,
                    "identity_pack_sha256": "a" * 64,
                    "report_sha256": "b" * 64,
                    "generated_at": "2026-08-26T18:00:00Z",
                    "provenance": "independent_agent",
                }
                for index, participant in enumerate(["Jean-Claude", "Neo", "Yoda"], start=1)
            ],
            "transcript_sha256": "c" * 64,
        },
        "promotion_claims": canonical_promotion_claims(
            {
                "meeting_id": "meeting-fake",
                "workspace_key": "shared_ops",
                "cycle_id": "cycle-fake",
                "standup_kind": "executive_ops",
                "participants": ["Jean-Claude", "Neo", "Yoda"],
            }
        ),
    }

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "participant_report_run_references_invalid"


def test_caller_cannot_replace_server_resolved_receipt_hashes(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    body["meeting_evidence"]["participant_reports"] = [
        {
            "agent_run_id": run_id,
            "identity_pack_sha256": "f" * 64,
            "report_sha256": "e" * 64,
        }
        for run_id in body["meeting_evidence"]["participant_report_run_ids"]
    ]

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "caller_supplied_report_receipt_mismatch"


def test_meeting_evidence_must_bind_exact_cycle_workspace_kind_and_meeting(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    body["meeting_evidence"]["cycle_id"] = "different-cycle"

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "meeting_evidence_binding_mismatch"


def test_signed_receipt_is_rejected_after_report_content_tamper(monkeypatch) -> None:
    body, runs = _signed_meeting_fixture(monkeypatch)
    runs[0].metadata["report_content"] = {"note": "Tampered after signing."}

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "participant_report_signature_invalid"


def test_real_report_ids_cannot_be_reused_for_mutated_promotion_claims(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    mutated_claims = dict(body["promotion_claims"])
    mutated_claims["summary"] = "Caller replaced the summary after every report completed."

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
        promotion_payload=mutated_claims,
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "participant_report_authority_binding_invalid"


def test_transcript_round_must_equal_canonical_report_content(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    body["discussion"][0]["note"] = "Caller rewrote the signed report."

    truth = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert truth["is_meeting"] is False
    assert truth["reason"] == "transcript_round_not_bound_to_canonical_report"


def test_later_identity_pack_change_does_not_erase_signed_historical_meeting(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    original = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )
    assert original["is_meeting"] is True
    original_digest = original["canonical_meeting_evidence"]["participant_reports"][0][
        "identity_pack_sha256"
    ]

    monkeypatch.setattr(
        standup_truth_service,
        "canonical_identity_pack_sha256",
        lambda _workspace, _participant: "f" * 64,
    )
    historical = meeting_record_truth(
        {
            **body,
            "discussion": original["canonical_discussion"],
            "meeting_evidence": original["canonical_meeting_evidence"],
        },
        expected_participants=body["participants"],
        workspace_key="shared_ops",
    )

    assert historical["is_meeting"] is True
    assert (
        historical["canonical_meeting_evidence"]["participant_reports"][0][
            "identity_pack_sha256"
        ]
        == original_digest
    )

    promotion_check = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
        verify_current_identity_pack=True,
    )
    assert promotion_check["is_meeting"] is False
    assert promotion_check["reason"] == "participant_report_authority_binding_invalid"


def test_missing_current_identity_binding_fails_closed_for_new_promotion(monkeypatch) -> None:
    body, _runs = _signed_meeting_fixture(monkeypatch)
    monkeypatch.setattr(
        standup_truth_service,
        "canonical_identity_pack_sha256",
        lambda _workspace, _participant: None,
    )

    promotion_check = meeting_record_truth(
        body,
        expected_participants=body["participants"],
        workspace_key="shared_ops",
        verify_current_identity_pack=True,
    )

    assert promotion_check["is_meeting"] is False
    assert promotion_check["reason"] == "participant_report_authority_binding_invalid"


def test_digest_only_deployment_projection_binds_every_canonical_participant_pack(
    monkeypatch,
) -> None:
    pairs = [
        ("*", "Jean-Claude", "shared_ops"),
        ("*", "Neo", "shared_ops"),
        ("*", "Yoda", "shared_ops"),
        ("fusion-os", "Fusion Systems Operator", "fusion-os"),
        ("easyoutfitapp", "Easy Outfit App Operator Agent", "easyoutfitapp"),
        ("ai-swag-store", "AI Swag Store Operator Agent", "ai-swag-store"),
        ("agc", "AGC Operator Agent", "agc"),
        ("work-life-tools", "Work Life Tools Operator Agent", "work-life-tools"),
    ]
    projected = standup_truth_service._projected_identity_pack_digests()
    assert projected is not None
    assert set(projected) == {(scope, name) for scope, name, _lookup in pairs}

    for scope, display_name, lookup_workspace in pairs:
        canonical_digest = standup_truth_service.canonical_identity_pack_sha256(
            lookup_workspace,
            display_name,
        )
        assert canonical_digest == projected[(scope, display_name)]
        local_digest = standup_truth_service._local_identity_pack_sha256(
            lookup_workspace,
            display_name,
        )
        if local_digest is not None:
            assert local_digest == canonical_digest

    monkeypatch.setattr(
        standup_truth_service,
        "_local_identity_pack_sha256",
        lambda _workspace, _participant: None,
    )
    monkeypatch.setattr(
        standup_truth_service,
        "_private_identity_pack_authority_present",
        lambda: False,
    )
    assert (
        standup_truth_service.canonical_identity_pack_sha256(
            "shared_ops",
            "Jean-Claude",
        )
        == projected[("*", "Jean-Claude")]
    )
