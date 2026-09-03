from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import PurePosixPath
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ops_workspace_goal_projection_service
from app.services import ops_standup_projection_service
from app.services import workspace_registry_service
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.integrated_memory_readiness_service import IntegratedMemoryReadinessService
from app.services.ops_standup_projection_service import (
    LEGACY_PROJECTION_SCHEMA,
    PROJECTION_SCHEMA,
    _MISSING_SHARED_OPS_RECONCILIATION_REASON,
    OpsStandupProjectionError,
    _bounded_workspace_cycle_evaluations,
    build_ops_standup_projection,
    ops_projection_semantic_sha256,
    unavailable_ops_standup_projection,
    validate_ops_standup_projection,
)
from app.services.ops_workspace_goal_projection_service import (
    OpsWorkspaceGoalProjectionError,
    build_ops_workspace_goal_projection,
    ops_workspace_goal_projection_semantic_sha256,
    unavailable_ops_workspace_goal_projection,
    validate_ops_workspace_goal_projection,
)
from app.services.portfolio_cycle_service import PortfolioCycleService
from app.services.workspace_snapshot_store import upsert_snapshot
from app.services.workspace_registry_service import (
    ACTIVE_PORTFOLIO_WORKSPACE_STATUSES,
    workspace_registry_entries,
)


def _ready(store: IntegratedSystemStore, *, cycle_id: str = "ops-projection-memory") -> str:
    receipt = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id=cycle_id,
        retrieval_refresh=lambda: {"schema_version": "codex_memory_index/v1", "status": "ok", "files": 1, "last_sync_at": "2026-08-20T06:15:00+00:00"},
        recall_search=lambda _query: [{"path": "memory"}],
        now=datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc),
    )
    return receipt["readiness_id"]


def _active_workspace_recursion() -> list[dict]:
    return [
        {
            "workspace_key": str(entry["key"]),
            "display_name": str(entry["display_name"]),
            "goal": {
                "schema_version": "workspace_goal_contract/v1",
                "goal": "Advance bounded private workspace evidence.",
                "progress_signals": ["A verified result exists."],
                "phase_gate": "External action remains owner controlled.",
                "no_action_trigger": "New eligible evidence arrives.",
            },
            "changes_since_prior": [],
            "system_decisions": [],
            "actions_taken": [],
            "completed_work": [],
            "failed_work": [],
            "carried_forward": [],
            "owner_decisions": [],
            "blocked": [],
            "no_action": [],
            "recommendations": [],
            "reference_only": [],
            "next_cycle_inputs": [],
            "recommendation_resolutions": [],
        }
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace"
        and entry.get("portfolio_visible") is True
        and entry.get("status") in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
    ]


def _goal_projection_authority_entries() -> tuple[dict, ...]:
    """Provide a bounded authority fixture without reading private workspace files."""

    entries: list[dict] = []
    for entry in workspace_registry_entries():
        if (
            entry.get("kind") != "workspace"
            or entry.get("portfolio_visible") is not True
            or entry.get("status") not in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
        ):
            continue
        workspace_key = str(entry["key"])
        entries.append(
            {
                **entry,
                "goal_contract_status": "available_private_authority",
                "goal_contract_observed_at": "2026-08-20T06:15:00Z",
                "goal_contract_authority_sha256": "4" * 64,
                "goal_contract": {
                    "schema_version": "workspace_goal_contract/v1",
                    "goal": (
                        f"Advance {workspace_key} only from verified bounded evidence."
                    ),
                    "progress_signals": [
                        "One verified goal-aligned change is durably recorded."
                    ],
                    "phase_gate": (
                        "The current bounded phase has verified completion evidence."
                    ),
                    "no_action_trigger": (
                        "New eligible evidence or a governed lifecycle change arrives."
                    ),
                    "safe_internal_boundary": [
                        "Analyze approved evidence and maintain bounded internal work."
                    ],
                    "owner_required_boundary": [
                        "External, irreversible, or strategic action requires the owner."
                    ],
                    "authority_refs": ["SOURCE_OF_TRUTH.md"],
                },
            }
        )
    return tuple(entries)


@pytest.fixture
def workspace_goal_projection(monkeypatch) -> dict:
    """Build ready projection data from an explicit public-safe test fixture."""

    monkeypatch.setattr(
        ops_workspace_goal_projection_service,
        "_active_project_entries",
        _goal_projection_authority_entries,
    )
    return build_ops_workspace_goal_projection()


def _semantic_projection(
    *,
    observed_at: str = "2026-08-20T06:15:00Z",
    generated_at: str = "2026-08-20T06:16:00Z",
    attempt_number: int = 1,
    attempt_payload_sha256: str | None = None,
    ops_conclusion_id: str = "ops-clock-test",
) -> dict:
    parsed_observation = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    cycle_stamp = parsed_observation.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    projection = unavailable_ops_standup_projection("test_fixture")
    projection.update(
        {
            "generated_at": generated_at,
            "state": "ready",
            "reason_codes": [],
            "ops_conclusion_id": ops_conclusion_id,
            "ops_conclusion_attempt_id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ai-clone:ops-attempt:{ops_conclusion_id}:{attempt_number}",
                )
            ),
            "ops_conclusion_attempt_number": attempt_number,
            "ops_conclusion_attempt_payload_sha256": (
                attempt_payload_sha256 or f"{attempt_number:064x}"
            ),
            "portfolio_cycle_id": (
                f"daily-{parsed_observation.astimezone(timezone.utc).date().isoformat()}"
                f"@{cycle_stamp}"
            ),
            "cycle_date": parsed_observation.astimezone(timezone.utc).date().isoformat(),
            "observed_at": observed_at,
            "clock": {
                "schema_version": "ai_clone_clock/v1",
                "authority": "ai_clone_utc",
                "timezone": "UTC",
                "observed_at": observed_at,
            },
            "status": "complete",
            "workspace_recursion": _active_workspace_recursion(),
            "shared_ops_reconciliation": {
                "display_name": "Executive Standup",
                "role": "portfolio_reconciler",
                "summary": "Shared Ops reconciled the exact active project scope.",
                "goal": {
                    "schema_version": "workspace_goal_contract/v1",
                    "goal": "Keep the active portfolio legible and reconcile cross-workspace dependencies.",
                    "progress_signals": ["Every material signal has an evidenced disposition."],
                    "phase_gate": "No dependency is silently absorbed by Shared Ops.",
                    "no_action_trigger": "New evidence changes a workspace dependency or priority.",
                },
                "evaluated": [],
                "system_decisions": [],
                "actions_taken": [
                    {
                        "kind": "portfolio_reconciliation",
                        "summary": "Reconciled six project conclusions without executing project work.",
                    }
                ],
                "owner_calls": [],
                "blocked": [],
                "no_action": [],
                "recommendations": [],
                "reference_only": [],
                "next_cycle_inputs": [
                    {
                        "kind": "canonical_ops_reconciliation_receipt",
                        "summary": "The next Dream consolidation consumes this bounded receipt.",
                    }
                ],
            },
        }
    )
    return validate_ops_standup_projection(projection)


def _store_semantic_ops_payload(
    tmp_path,
    *,
    workspace_recursion: list[dict],
) -> IntegratedSystemStore:
    projection = _semantic_projection()
    store = IntegratedSystemStore(tmp_path / "active-coverage.sqlite3")
    store.migrate()
    payload = {
        "schema_version": "ops_standup_summary_conclusion/v3",
        "portfolio_cycle_id": projection["portfolio_cycle_id"],
        "cycle_date": projection["cycle_date"],
        "observed_at": projection["observed_at"],
        "clock": projection["clock"],
        "status": "complete",
        "workspace_recursion": workspace_recursion,
        "shared_ops_reconciliation": projection["shared_ops_reconciliation"],
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with store.connection() as connection:
        connection.execute(
            "INSERT INTO portfolio_cycles(portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json) VALUES (?,?,?,?,?,?,?)",
            (
                projection["portfolio_cycle_id"],
                projection["cycle_date"],
                "complete",
                len(_active_workspace_recursion()),
                projection["observed_at"],
                "active-coverage-cycle",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO ops_conclusions(ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key) VALUES (?,?,?,?,?,?)",
            (
                projection["ops_conclusion_id"],
                projection["portfolio_cycle_id"],
                payload_json,
                "complete",
                projection["observed_at"],
                "active-coverage-conclusion",
            ),
        )
        connection.execute(
            "INSERT INTO ops_conclusion_attempts(attempt_id,ops_conclusion_id,attempt_number,payload_json,status,created_at) VALUES (?,?,?,?,?,?)",
            (
                projection["ops_conclusion_attempt_id"],
                projection["ops_conclusion_id"],
                1,
                payload_json,
                "complete",
                projection["observed_at"],
            ),
        )
        connection.commit()
    return store


def test_workspace_cycle_projection_preserves_governed_authority_and_terminal_states():
    raw = {
        "workspace_key": "feezie-os",
        "standup_kind": "workspace_sync",
        "status": "async_contribution",
        "reason": "new_cycle_observation",
        "cycle_id": "daily-2026-09-03@20260903T101500590123Z",
        "observed_at": "2026-09-03T10:15:00Z",
        "evaluation_schema_version": "workspace_cycle_evaluation/v1",
        "cycle_evaluation_only": True,
        "meeting_held": False,
        "promotion_suppressed": False,
        "owner_decision_count": 1,
        "created_standup_id": "bounded-coordination-row",
        "async_role_contribution_id": "bounded-contribution",
        "async_role_participant_report_run_id": "bounded-run",
        "async_role_display_name": "Neo",
        "canonical_pm_execution_authority": "Jean-Claude",
        "pm_execution_authority_transferred": False,
        "canonical_update_accepted": True,
        "async_recommendation_terminal_dispositions": [
            {
                "state": "bounded_owner_decision",
                "request_sha256": "private-lineage-is-not-owner-guidance",
            },
            {
                "state": "placed_in_execution_queue",
                "card_id": "private-card-id",
            },
        ],
        "goal": {"goal": "Private authority must come from recursion."},
        "promotion_error": "/private/provider/body",
    }

    projected = _bounded_workspace_cycle_evaluations([raw])

    assert len(projected) == 1
    evaluation = projected[0]
    assert evaluation["canonical_update_accepted"] is True
    assert evaluation["canonical_pm_execution_authority"] == "Jean-Claude"
    assert evaluation["pm_execution_authority_transferred"] is False
    assert evaluation["owner_decision_count"] == 1
    assert evaluation["async_recommendation_terminal_dispositions"] == [
        {"state": "bounded_owner_decision"},
        {"state": "placed_in_execution_queue"},
    ]
    assert "goal" not in evaluation
    assert "promotion_error" not in evaluation
    assert "request_sha256" not in json.dumps(projected)
    projection = _semantic_projection()
    projection["workspace_cycle_evaluations"] = projected
    assert validate_ops_standup_projection(projection) == projection


def _daily_cycle_clock_run(
    *,
    cycle_id: str,
    observed_at: str = "2026-08-20T06:15:00Z",
    clock: dict | None = None,
    run_id: str = "daily-integrated-cycle-clock-evidence",
) -> dict:
    return {
        "id": run_id,
        "automation_id": "daily_integrated_cycle",
        "automation_name": "Daily Integrated Cycle",
        "source": "codex_launchd_registry",
        "runtime": "launchd",
        "status": "failed",
        "metadata": {
            "cycle_id": cycle_id,
            "observed_at": observed_at,
            "clock": clock
            or {
                "schema_version": "ai_clone_clock/v1",
                "authority": "ai_clone_utc",
                "timezone": "UTC",
                "observed_at": observed_at,
            },
        },
    }


def _write_clock_ledger(path, *rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_ready_projection_covers_each_structural_active_project_once():
    projection = _semantic_projection()
    expected = [
        str(entry["key"])
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace"
        and entry.get("portfolio_visible") is True
        and entry.get("status") in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
    ]

    assert [
        row["workspace_key"] for row in projection["workspace_recursion"]
    ] == expected
    assert len(expected) == len(set(expected))
    assert len(expected) == 6
    assert "shared_ops" not in expected
    assert projection["shared_ops_reconciliation"]["role"] == "portfolio_reconciler"


def test_workspace_recommendations_and_reference_evidence_are_bounded_separate_lanes(
    tmp_path,
):
    recursion = _active_workspace_recursion()
    recursion[0]["recommendations"] = [
        {
            "summary": "Prepare one bounded internal research packet.",
            "private_notes": "must not project",
        }
    ]
    recursion[0]["reference_only"] = [
        {
            "summary": "Prior plan retained for comparison only.",
            "ref": "workspace-evidence:prior-plan",
            "body": "must not project",
        }
    ]
    store = _store_semantic_ops_payload(
        tmp_path,
        workspace_recursion=recursion,
    )

    projection = build_ops_standup_projection(store=store)
    first = projection["workspace_recursion"][0]

    assert first["recommendations"] == [
        {"summary": "Prepare one bounded internal research packet."}
    ]
    assert first["reference_only"] == [
        {
            "summary": "Prior plan retained for comparison only.",
            "ref": "workspace-evidence:prior-plan",
        }
    ]
    assert first["actions_taken"] == []


def test_shared_ops_summary_is_reconciler_only_and_private_material_fails_closed():
    projection = _semantic_projection()
    assert len(projection["workspace_recursion"]) == 6
    assert all(
        row["workspace_key"] != "shared_ops"
        for row in projection["workspace_recursion"]
    )

    forged = copy.deepcopy(projection)
    private_path_canary = str(
        PurePosixPath("/", "Users", "synthetic-owner", "private", "ops.md")
    )
    forged["shared_ops_reconciliation"]["reference_only"] = [
        {"summary": f"Leaked {private_path_canary}"}
    ]
    with pytest.raises(
        OpsStandupProjectionError,
        match="private or oversized material",
    ):
        validate_ops_standup_projection(forged)


def test_exact_prior_v3_shape_is_losslessly_degraded_for_additive_reconciler_truth():
    prior_v3 = _semantic_projection()
    prior_v3.pop("shared_ops_reconciliation")
    for row in prior_v3["workspace_recursion"]:
        row.pop("recommendations")
        row.pop("reference_only")

    upgraded = validate_ops_standup_projection(prior_v3)

    assert upgraded["schema_version"] == PROJECTION_SCHEMA
    assert upgraded["state"] == "degraded"
    assert upgraded["shared_ops_reconciliation"] is None
    assert _MISSING_SHARED_OPS_RECONCILIATION_REASON in upgraded["reason_codes"]
    assert all(
        row["recommendations"] == [] and row["reference_only"] == []
        for row in upgraded["workspace_recursion"]
    )


def test_active_project_scope_is_structural_not_name_or_route_based(monkeypatch):
    monkeypatch.setattr(
        ops_standup_projection_service,
        "workspace_registry_entries",
        lambda: (
            {
                "key": "live-project",
                "kind": "workspace",
                "portfolio_visible": True,
                "status": "live",
            },
            {
                "key": "standing-project",
                "kind": "workspace",
                "portfolio_visible": True,
                "status": "standing_up",
            },
            {
                "key": "planned-project",
                "kind": "workspace",
                "portfolio_visible": True,
                "status": "planned",
            },
            {
                "key": "hidden-project",
                "kind": "workspace",
                "portfolio_visible": False,
                "status": "live",
            },
            {
                "key": "shared_ops",
                "kind": "executive",
                "portfolio_visible": True,
                "status": "live",
            },
        ),
    )

    assert ops_standup_projection_service._active_project_workspace_keys() == (
        "live-project",
        "standing-project",
    )


def test_ready_projection_rejects_missing_active_project_without_degraded_truth():
    projection = _semantic_projection()
    projection["workspace_recursion"].pop()

    with pytest.raises(OpsStandupProjectionError, match="incoherent ready"):
        validate_ops_standup_projection(projection)

    projection.update(
        state="degraded",
        reason_codes=["unrelated_warning"],
    )
    with pytest.raises(
        OpsStandupProjectionError,
        match="missing active workspace recursion requires its reason code",
    ):
        validate_ops_standup_projection(projection)

    projection["reason_codes"] = [
        "ops_conclusion_missing_active_workspace_recursion"
    ]
    assert validate_ops_standup_projection(projection) == projection


@pytest.mark.parametrize(
    ("defect", "error"),
    [
        ("duplicate", "duplicate workspace recursion key"),
        (
            "shared_ops",
            "unexpected workspace recursion key outside the active project registry",
        ),
    ],
)
def test_sync_boundary_rejects_duplicate_or_reconciler_recursion(
    defect,
    error,
    monkeypatch,
):
    projection = _semantic_projection()
    extra = copy.deepcopy(projection["workspace_recursion"][0])
    if defect == "shared_ops":
        extra["workspace_key"] = "shared_ops"
        extra["display_name"] = "Executive Standup"
    projection["workspace_recursion"].append(extra)

    with pytest.raises(OpsStandupProjectionError, match=error):
        validate_ops_standup_projection(projection)
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: pytest.fail(
            "invalid workspace coverage reached storage"
        ),
    )
    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("defect", "reason_code", "warning_text"),
    [
        (
            "duplicate",
            "ops_conclusion_duplicate_workspace_recursion",
            "repeated workspace recursion rows",
        ),
        (
            "shared_ops",
            "ops_conclusion_unexpected_workspace_recursion",
            "out-of-scope recursion rows",
        ),
        (
            "missing_key",
            "ops_conclusion_unexpected_workspace_recursion",
            "out-of-scope recursion rows",
        ),
    ],
)
def test_canonical_builder_degrades_and_bounds_duplicate_or_reconciler_rows(
    tmp_path,
    defect,
    reason_code,
    warning_text,
):
    recursion = _active_workspace_recursion()
    if defect == "missing_key":
        recursion.append({"summary": "Malformed canonical recursion row."})
    else:
        extra = copy.deepcopy(recursion[0])
        if defect == "shared_ops":
            extra["workspace_key"] = "shared_ops"
            extra["display_name"] = "Executive Standup"
        recursion.append(extra)
    store = _store_semantic_ops_payload(
        tmp_path,
        workspace_recursion=recursion,
    )

    projection = build_ops_standup_projection(store=store)

    assert projection["state"] == "degraded"
    assert projection["status"] == "complete"
    assert reason_code in projection["reason_codes"]
    projected_keys = [
        row["workspace_key"] for row in projection["workspace_recursion"]
    ]
    assert projected_keys == [
        row["workspace_key"] for row in _active_workspace_recursion()
    ]
    assert "shared_ops" not in projected_keys
    assert any(
        warning_text in warning
        for warning in projection["degraded_system_warnings"]
    )


def test_structural_active_coverage_survives_absent_private_goal_authority(
    tmp_path,
    monkeypatch,
):
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(
                workspace_registry_service,
                "WORKSPACE_GOAL_CONTRACT_AUTHORITY_PATH",
                tmp_path / "public-runtime-has-no-private-goal-authority.json",
            )
            workspace_registry_service.clear_workspace_registry_caches()
            entries = workspace_registry_entries()
            assert all(
                entry["goal_contract_status"] == "private_authority_unavailable"
                for entry in entries
            )

            projection = _semantic_projection()
            assert projection["state"] == "ready"
            expected = [
                str(entry["key"])
                for entry in entries
                if entry.get("kind") == "workspace"
                and entry.get("portfolio_visible") is True
                and entry.get("status")
                in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
            ]
            assert [
                row["workspace_key"]
                for row in projection["workspace_recursion"]
            ] == expected
            assert "shared_ops" not in expected
    finally:
        workspace_registry_service.clear_workspace_registry_caches()


def test_builds_bounded_final_ops_projection(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="p",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os"],
        readiness_id=_ready(store, cycle_id="p"),
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="p",
        workspace_key="feezie-os",
        conclusion_kind="conclusion",
        provenance_kind="independent_agent",
        payload={
            "summary": "Content reviewed",
            "goal": {
                "schema_version": "workspace_goal_contract/v1",
                "goal": "Advance truthful private content evidence without publishing.",
                "progress_signals": ["A bounded draft has a verified result receipt."],
                "phase_gate": "Owner review remains required before publication.",
                "no_action_trigger": "Reevaluate when eligible evidence or an owner decision arrives.",
                "safe_internal_boundary": ["Prepare and review bounded private drafts."],
                "owner_required_boundary": ["Publication requires the owner."],
                "authority_refs": ["SOURCE_OF_TRUTH.md"],
            },
            "changes_since_prior": [{"summary": "A new eligible source cleared review."}],
            "system_decisions": [{"summary": "Use the safe internal drafting lane."}],
            "actions_taken": [
                {
                    "summary": "Queued and completed the bounded draft.",
                    "raw_body": "must never project",
                    "notes": "api_key=secret-value /private/var/private-run.json",
                }
            ],
            "completed_work": [{"summary": "Draft ready"}],
            "failed_work": [{"summary": "One critic pass failed safely.", "retryable": True}],
            "carried_forward": [{"summary": "Carry owner review forward."}],
            "blockers": [{"summary": "Publication is owner gated."}],
            "owner_decisions": [{"summary": "Approve or reject the exact draft."}],
            "no_action": [
                {
                    "summary": "No public action is eligible.",
                    "trigger": "An explicit owner publication decision.",
                }
            ],
            "recommendation_resolutions": [
                {
                    "title": "Prepare the private draft",
                    "state": "executed_automatically",
                    "explanation": "A verified internal result exists.",
                    "future_trigger": "Owner review may now proceed.",
                }
            ],
            "next_cycle_inputs": [{"summary": "Consume the verified draft receipt."}],
            "recommended_next_actions": [
                {
                    "summary": "Review the exact private draft.",
                    "resolution_state": "bounded_owner_decision",
                }
            ],
            "evidence_links": [{"url": "https://example.com/evidence"}],
        },
        idempotency_key="w",
    )
    service.conclude_ops(
        portfolio_cycle_id="p",
        system_health={
            "api": {"status": "healthy", "debug": "/private/var/raw-health.json"},
            "backup_recovery": "not_verified",
        },
        recommended_next_actions=["Review draft"],
        observed_at=datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc),
        workspace_cycle_evaluations=[
            {
                "workspace_key": "feezie-os",
                "standup_kind": "workspace_sync",
                "status": "decision_record",
                "reason": "stale",
                "cycle_evaluation_only": True,
                "evaluation_schema_version": "workspace_cycle_evaluation/v1",
                "meeting_held": False,
                "decision_record_schema_version": "standup_decision_record/v1",
            }
        ],
    )
    projection = build_ops_standup_projection(store=store)
    assert projection["schema_version"] == PROJECTION_SCHEMA
    assert projection["state"] == "degraded"
    assert (
        "ops_conclusion_missing_active_workspace_recursion"
        in projection["reason_codes"]
    )
    assert any(
        "missing active workspace recursion rows" in warning
        for warning in projection["degraded_system_warnings"]
    )
    assert projection["workspace_updates"][0]["provenance_kind"] == "independent_agent"
    recursion = projection["workspace_recursion"][0]
    assert recursion["workspace_key"] == "feezie-os"
    assert recursion["display_name"] == "FEEZIE OS"
    assert recursion["goal"]["goal"] == "Advance truthful private content evidence without publishing."
    assert "private_notes" not in recursion["goal"]
    assert recursion["changes_since_prior"][0]["summary"] == "A new eligible source cleared review."
    assert recursion["system_decisions"][0]["summary"] == "Use the safe internal drafting lane."
    assert recursion["actions_taken"][0] == {
        "summary": "Queued and completed the bounded draft.",
        "route": "ops",
    }
    assert recursion["completed_work"][0]["summary"] == "Draft ready"
    assert recursion["failed_work"][0]["retryable"] is True
    assert recursion["carried_forward"][0]["summary"] == "Carry owner review forward."
    assert recursion["owner_decisions"][0]["summary"] == "Approve or reject the exact draft."
    assert recursion["blocked"][0]["summary"] == "Publication is owner gated."
    assert len(recursion["blocked"]) == 1
    assert recursion["no_action"][0]["trigger"] == "An explicit owner publication decision."
    assert recursion["next_cycle_inputs"][0]["summary"] == "Consume the verified draft receipt."
    assert recursion["recommendation_resolutions"][0]["state"] == "executed_automatically"
    assert projection["completed_work"][0]["summary"] == "Draft ready"
    assert projection["ai_clone_process_updates"]["memory_readiness"]["status"] == "ready"
    assert projection["supporting_evidence_links"][0]["url"] == "https://example.com/evidence"
    assert projection["observed_at"] == "2026-08-20T06:15:00Z"
    assert projection["clock"] == {
        "schema_version": "ai_clone_clock/v1",
        "authority": "ai_clone_utc",
        "timezone": "UTC",
        "observed_at": "2026-08-20T06:15:00Z",
    }
    assert projection["workspace_cycle_evaluations"][0]["status"] == "decision_record"
    assert projection["workspace_cycle_evaluations"][0]["cycle_evaluation_only"] is True
    assert projection["workspace_cycle_evaluations"][0]["meeting_held"] is False
    assert (
        projection["workspace_cycle_evaluations"][0]["evaluation_schema_version"]
        == "workspace_cycle_evaluation/v1"
    )
    assert projection["decision_readiness"]["state"] == "ready"
    assert projection["decision_readiness"]["clock_authority"] == "ai_clone_utc"
    assert projection["decision_readiness"]["blocking_reason_codes"] == []
    assert "backup_recovery" in projection["decision_readiness"]["context_warnings"][0]
    assert projection["recommended_next_actions"][0]["summary"] == "Review the exact private draft."
    assert "must never project" not in str(projection)
    assert "secret-value" not in str(projection)
    assert "/private/" not in str(projection)
    assert projection["endpoint_and_subsystem_health"] == {
        "api": "healthy",
        "backup_recovery": "not_verified",
    }
    assert validate_ops_standup_projection(projection) == projection


def test_projection_prefers_newer_semantic_observation_over_later_backfill_write(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="newer-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os"],
        readiness_id=_ready(store, cycle_id="newer-cycle"),
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="newer-cycle",
        workspace_key="feezie-os",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload={
            "summary": "Newer semantic state.",
            "goal": {
                "schema_version": "workspace_goal_contract/v1",
                "goal": "Advance truthful private content evidence without publishing.",
                "progress_signals": ["A bounded draft has a verified result receipt."],
                "phase_gate": "Owner review remains required before publication.",
                "no_action_trigger": "Reevaluate when eligible evidence or an owner decision arrives.",
                "safe_internal_boundary": ["Prepare and review bounded private drafts."],
                "owner_required_boundary": ["Publication requires the owner."],
                "authority_refs": ["SOURCE_OF_TRUTH.md"],
            },
            "no_action": [
                {
                    "selected": True,
                    "reason": "No new eligible content evidence was observed.",
                    "future_trigger": "Eligible evidence or an owner decision arrives.",
                }
            ],
        },
        idempotency_key="newer-semantic-workspace",
    )
    service.conclude_ops(
        portfolio_cycle_id="newer-cycle",
        system_health={"api": "healthy"},
    )
    with store.connection() as connection:
        current = connection.execute(
            "SELECT payload_json FROM ops_conclusions WHERE portfolio_cycle_id='newer-cycle'"
        ).fetchone()
        older_payload = json.loads(current["payload_json"])
        older_payload.update(
            {
                "portfolio_cycle_id": "older-backfill",
                "observed_at": "2026-08-20T05:00:00+00:00",
                "workspace_updates": [
                    {
                        "workspace_key": "feezie-os",
                        "state": "healthy_no_change",
                        "summary": "Older backfilled state.",
                        "provenance_kind": "deterministic_policy",
                    }
                ],
            }
        )
        connection.execute(
            "INSERT INTO portfolio_cycles(portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json) VALUES (?,?,?,?,?,?,?)",
            (
                "older-backfill",
                "2026-08-20",
                "complete",
                1,
                "2026-08-30T00:00:00+00:00",
                "portfolio-cycle:older-backfill",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO ops_conclusions(ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key) VALUES (?,?,?,?,?,?)",
            (
                "ops-older-backfill",
                "older-backfill",
                json.dumps(older_payload, sort_keys=True, separators=(",", ":")),
                "complete",
                "2026-08-30T00:00:00+00:00",
                "ops-conclusion:older-backfill",
            ),
        )
        malformed_payload = {
            **older_payload,
            "portfolio_cycle_id": "naive-newer-write",
            "observed_at": "2026-09-01T12:00:00",
        }
        connection.execute(
            "INSERT INTO portfolio_cycles(portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json) VALUES (?,?,?,?,?,?,?)",
            (
                "naive-newer-write",
                "2026-09-01",
                "complete",
                1,
                "2026-09-01T12:30:00+00:00",
                "portfolio-cycle:naive-newer-write",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO ops_conclusions(ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key) VALUES (?,?,?,?,?,?)",
            (
                "ops-naive-newer-write",
                "naive-newer-write",
                json.dumps(malformed_payload, sort_keys=True, separators=(",", ":")),
                "complete",
                "2026-09-01T12:30:00+00:00",
                "ops-conclusion:naive-newer-write",
            ),
        )
        connection.commit()

    projection = build_ops_standup_projection(store=store)

    assert projection["portfolio_cycle_id"] == "newer-cycle"
    assert projection["observed_at"] == "2026-08-20T06:15:00Z"


def test_goal_authority_blocker_and_future_trigger_survive_bounded_projection(tmp_path):
    store = IntegratedSystemStore(tmp_path / "goal-block.sqlite3")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="goal-block-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["fusion-os"],
        readiness_id=_ready(store, cycle_id="goal-block-cycle"),
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="goal-block-cycle",
        workspace_key="fusion-os",
        conclusion_kind="conclusion",
        provenance_kind="deterministic_policy",
        payload={
            "summary": "Goal-directed evaluation was blocked.",
            "goal": {},
        },
        idempotency_key="goal-block-workspace",
    )
    service.conclude_ops(
        portfolio_cycle_id="goal-block-cycle",
        system_health={"api": "healthy"},
    )

    projection = build_ops_standup_projection(store=store)
    blocker = projection["workspace_recursion"][0]["blocked"][0]

    assert projection["state"] == "degraded"
    assert projection["status"] == "degraded"
    assert blocker["reason_code"] == "workspace_goal_authority_blocked"
    assert blocker["reason"]
    assert blocker["future_trigger"]


def test_stored_v1_projection_is_closed_field_upgraded_to_v3(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    projection = build_ops_standup_projection(store=store)
    legacy = copy.deepcopy(projection)
    legacy["schema_version"] = LEGACY_PROJECTION_SCHEMA
    legacy["state"] = "ready"
    legacy["status"] = "complete"
    legacy["reason_codes"] = []
    legacy.pop("workspace_recursion")
    legacy["ai_clone_process_updates"] = {
        "memory_readiness": {
            "status": "ready",
            "raw_body": "api_key=legacy-secret",
            "local_path": "/private/var/legacy.json",
        },
        "arbitrary_mapping": {"body": "must not survive"},
    }
    legacy["workspace_updates"] = [
        {
            "workspace_key": "feezie-os",
            "summary": "A safe summary",
            "notes": "api_key=legacy-secret /private/var/legacy.json",
        }
    ]
    legacy["canonical_decisions"] = [
        {
            "decision_id": "decision-legacy",
            "decision_type": "owner approval",
            "status": "open",
            "title": "Review the bounded decision",
            "state_version": 1,
            "interaction_mode": "simple",
            "route": "ops",
            "resolution": {},
            "session_ref": None,
            "updated_at": "2026-08-20T00:00:00+00:00",
            "links": [],
        }
    ]

    upgraded = validate_ops_standup_projection(legacy)

    assert upgraded["schema_version"] == PROJECTION_SCHEMA
    assert upgraded["state"] == "degraded"
    assert upgraded["reason_codes"] == [
        "legacy_projection_missing_workspace_recursion",
        "legacy_projection_missing_clock_receipt",
        "ops_conclusion_missing_shared_ops_reconciliation",
    ]
    assert upgraded["observed_at"] is None
    assert upgraded["clock"] is None
    assert upgraded["workspace_recursion"] == []
    assert upgraded["workspace_updates"] == [
        {"workspace_key": "feezie-os", "summary": "A safe summary"}
    ]
    assert upgraded["ai_clone_process_updates"] == {
        "memory_readiness": {"status": "ready"}
    }
    assert upgraded["canonical_decisions"][0]["decision_type"] == "owner approval"
    assert "legacy-secret" not in str(upgraded)
    assert "/private/" not in str(upgraded)


def test_legacy_projection_with_partial_duplicate_and_shared_ops_rows_degrades_cleanly():
    legacy = _semantic_projection()
    legacy["schema_version"] = LEGACY_PROJECTION_SCHEMA
    legacy["workspace_recursion"].pop()
    legacy["workspace_recursion"].append(
        copy.deepcopy(legacy["workspace_recursion"][0])
    )
    shared_ops = copy.deepcopy(legacy["workspace_recursion"][0])
    shared_ops.update(
        workspace_key="shared_ops",
        display_name="Executive Standup",
    )
    legacy["workspace_recursion"].append(shared_ops)

    upgraded = validate_ops_standup_projection(legacy)

    assert upgraded["state"] == "degraded"
    assert "ops_conclusion_attempt_missing" in upgraded["reason_codes"]
    assert (
        "ops_conclusion_missing_active_workspace_recursion"
        in upgraded["reason_codes"]
    )
    assert (
        "ops_conclusion_duplicate_workspace_recursion"
        in upgraded["reason_codes"]
    )
    assert (
        "ops_conclusion_unexpected_workspace_recursion"
        in upgraded["reason_codes"]
    )
    projected_keys = [
        row["workspace_key"] for row in upgraded["workspace_recursion"]
    ]
    assert len(projected_keys) == len(set(projected_keys))
    assert "shared_ops" not in projected_keys


@pytest.mark.parametrize("state", ["empty", "error"])
def test_legacy_projection_without_conclusion_preserves_coherent_empty_state(state):
    legacy = unavailable_ops_standup_projection(
        f"legacy_{state}",
        state=state,
    )
    legacy["schema_version"] = LEGACY_PROJECTION_SCHEMA

    upgraded = validate_ops_standup_projection(legacy)

    assert upgraded["state"] == state
    assert upgraded["status"] == state
    assert upgraded["ops_conclusion_id"] is None
    assert upgraded["workspace_recursion"] == []
    assert "legacy_projection_missing_clock_receipt" in upgraded["reason_codes"]


def test_canonical_ops_attempt_recovers_exact_daily_cycle_clock_evidence(
    tmp_path,
    monkeypatch,
):
    store = _store_semantic_ops_payload(
        tmp_path,
        workspace_recursion=_active_workspace_recursion(),
    )
    with store.connection() as connection:
        row = connection.execute(
            "SELECT ops_conclusion_id,payload_json FROM ops_conclusions LIMIT 1"
        ).fetchone()
        legacy_payload = json.loads(row["payload_json"])
        cycle_id = legacy_payload["portfolio_cycle_id"]
        legacy_payload["observed_at"] = "2026-08-20T06:15:00+00:00"
        legacy_payload.pop("clock")
        encoded = json.dumps(legacy_payload, sort_keys=True, separators=(",", ":"))
        connection.execute(
            "UPDATE ops_conclusions SET payload_json=? WHERE ops_conclusion_id=?",
            (encoded, row["ops_conclusion_id"]),
        )
        connection.execute(
            "UPDATE ops_conclusion_attempts SET payload_json=? WHERE ops_conclusion_id=?",
            (encoded, row["ops_conclusion_id"]),
        )
        connection.commit()
    ledger = tmp_path / "runs" / "all.jsonl"
    _write_clock_ledger(
        ledger,
        _daily_cycle_clock_run(cycle_id=cycle_id),
    )
    monkeypatch.setattr(
        ops_standup_projection_service,
        "CODEX_RUN_LEDGER_PATH",
        ledger,
    )

    projection = build_ops_standup_projection(store=store)

    assert projection["observed_at"] == "2026-08-20T06:15:00Z"
    assert projection["clock"] == {
        "schema_version": "ai_clone_clock/v1",
        "authority": "ai_clone_utc",
        "timezone": "UTC",
        "observed_at": "2026-08-20T06:15:00Z",
    }
    assert "ops_conclusion_clock_unverified" not in projection["reason_codes"]


def test_legacy_clock_bridge_ignores_same_cycle_retries_without_exact_observation(
    tmp_path,
):
    cycle_id = "daily-2026-08-26"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-26",
        "observed_at": "2026-08-26T18:02:39+00:00",
    }
    missing_observation = _daily_cycle_clock_run(
        cycle_id=cycle_id,
        run_id="daily-retry-without-observation",
    )
    missing_observation["metadata"].pop("observed_at")
    missing_observation["metadata"].pop("clock")
    different_observation = _daily_cycle_clock_run(
        cycle_id=cycle_id,
        observed_at="2026-08-26T06:15:00Z",
        run_id="daily-retry-different-observation",
    )
    different_observation["metadata"].pop("clock")
    exact_observation = _daily_cycle_clock_run(
        cycle_id=cycle_id,
        observed_at="2026-08-26T18:02:39Z",
        run_id="daily-exact-clock-evidence",
    )
    ledger = tmp_path / "runs.jsonl"
    _write_clock_ledger(
        ledger,
        missing_observation,
        different_observation,
        exact_observation,
    )

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=ledger,
        )
    )

    assert recovered["observed_at"] == "2026-08-26T18:02:39Z"
    assert recovered["clock"] == exact_observation["metadata"]["clock"]


@pytest.mark.parametrize(
    "receipt_cycle_id,receipt_observed_at,clock",
    [
        ("daily-2026-08-20", "2026-08-20T06:15:01Z", None),
        ("daily-2026-08-21", "2026-08-20T06:15:00Z", None),
        ("daily-2026-08-20", "2026-08-20T02:15:00-04:00", None),
        (
            "daily-2026-08-20",
            "2026-08-20T06:15:00Z",
            {
                "schema_version": "ai_clone_clock/v1",
                "authority": "browser_local",
                "timezone": "UTC",
                "observed_at": "2026-08-20T06:15:00Z",
            },
        ),
        (
            "daily-2026-08-20",
            "2026-08-20T06:15:00Z",
            {
                "schema_version": "ai_clone_clock/v1",
                "authority": "ai_clone_utc",
                "timezone": "UTC",
                "observed_at": "2026-08-20T06:15:01Z",
            },
        ),
    ],
)
def test_legacy_clock_bridge_fails_closed_for_mismatch_or_invalid_receipt(
    tmp_path,
    receipt_cycle_id,
    receipt_observed_at,
    clock,
):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
        "generated_at": receipt_observed_at,
    }
    ledger = tmp_path / "runs.jsonl"
    _write_clock_ledger(
        ledger,
        _daily_cycle_clock_run(
            cycle_id=receipt_cycle_id,
            observed_at=receipt_observed_at,
            clock=clock,
        ),
    )

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=ledger,
        )
    )

    assert recovered == payload
    assert "clock" not in recovered
    assert recovered["observed_at"].endswith("+00:00")


def test_legacy_clock_bridge_rejects_conflicting_same_cycle_receipts(tmp_path):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
    }
    ledger = tmp_path / "runs.jsonl"
    _write_clock_ledger(
        ledger,
        _daily_cycle_clock_run(cycle_id=cycle_id, run_id="daily-clock-a"),
        _daily_cycle_clock_run(
            cycle_id=cycle_id,
            observed_at="2026-08-20T06:15:00.000000Z",
            run_id="daily-clock-b",
        ),
    )

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=ledger,
        )
    )

    assert recovered == payload
    assert "clock" not in recovered


def test_legacy_clock_bridge_streams_past_old_ledger_bounds_before_recovery(
    tmp_path,
):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
    }
    ledger = tmp_path / "large-runs.jsonl"
    filler_line = json.dumps(
        {
            "automation_id": "unrelated_bounded_worker",
            "padding": "x" * 900,
        },
        sort_keys=True,
    ) + "\n"
    matching_line = json.dumps(
        _daily_cycle_clock_run(cycle_id=cycle_id),
        sort_keys=True,
    ) + "\n"
    ledger.write_text(filler_line * 10_001 + matching_line, encoding="utf-8")
    assert ledger.stat().st_size > 8 * 1024 * 1024
    with ledger.open(encoding="utf-8") as handle:
        assert sum(1 for _line in handle) > 10_000

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=ledger,
        )
    )

    assert recovered["observed_at"] == "2026-08-20T06:15:00Z"
    assert recovered["clock"]["authority"] == "ai_clone_utc"


def test_legacy_clock_bridge_fails_closed_beyond_configured_whole_file_bound(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
    }
    ledger = tmp_path / "bounded-runs.jsonl"
    _write_clock_ledger(ledger, _daily_cycle_clock_run(cycle_id=cycle_id))
    monkeypatch.setattr(
        ops_standup_projection_service,
        "_LEGACY_CLOCK_LEDGER_MAX_BYTES",
        ledger.stat().st_size - 1,
    )

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=ledger,
        )
    )

    assert recovered == payload
    assert "clock" not in recovered


def test_legacy_clock_bridge_rejects_symlinked_ledger(tmp_path):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
    }
    target = tmp_path / "real-runs.jsonl"
    linked = tmp_path / "linked-runs.jsonl"
    _write_clock_ledger(target, _daily_cycle_clock_run(cycle_id=cycle_id))
    linked.symlink_to(target)

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=linked,
        )
    )

    assert recovered == payload
    assert "clock" not in recovered


def test_legacy_clock_bridge_rejects_malformed_ledger_and_preserves_clocked_payload(
    tmp_path,
):
    cycle_id = "daily-2026-08-20"
    payload = {
        "portfolio_cycle_id": cycle_id,
        "cycle_date": "2026-08-20",
        "observed_at": "2026-08-20T06:15:00+00:00",
    }
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("{not-json}\n", encoding="utf-8")

    recovered = (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            payload,
            ledger_path=malformed,
        )
    )

    assert recovered == payload
    assert "clock" not in recovered

    clocked = _semantic_projection()
    conflicting = tmp_path / "conflicting.jsonl"
    _write_clock_ledger(
        conflicting,
        _daily_cycle_clock_run(
            cycle_id=clocked["portfolio_cycle_id"],
            observed_at="2026-08-20T06:15:01Z",
        ),
    )
    assert (
        ops_standup_projection_service._recover_legacy_ops_clock_from_run_ledger(
            clocked,
            ledger_path=conflicting,
        )
        is clocked
    )


def test_v2_projection_rejects_unknown_item_fields(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    projection = build_ops_standup_projection(store=store)
    projection["workspace_updates"] = [
        {"summary": "Safe", "notes": "api_key=do-not-project"}
    ]

    with pytest.raises(OpsStandupProjectionError, match="workspace_updates item"):
        validate_ops_standup_projection(projection)


def test_pre_recursion_canonical_ops_conclusion_projects_degraded_not_ready(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    store.migrate()
    observed_at = "2026-08-20T06:15:00+00:00"
    underlying = {
        "schema_version": "ops_standup_summary_conclusion/v1",
        "portfolio_cycle_id": "legacy-cycle",
        "cycle_date": "2026-08-20",
        "observed_at": observed_at,
        "status": "complete",
        "workspace_updates": [],
        "workspace_cycle_evaluations": [],
        "ai_clone_process_updates": {},
        "endpoint_and_subsystem_health": {},
        "work_underway": [],
        "completed_work": [],
        "blockers": [],
        "urgent_escalations": [],
        "workspace_decisions": [],
        "ops_decisions": [],
        "owner_calls": [],
        "degraded_system_warnings": [],
        "supporting_evidence_links": [],
        "recommended_next_actions": [],
    }
    with store.connection() as connection:
        connection.execute(
            "INSERT INTO portfolio_cycles(portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json) VALUES (?,?,?,?,?,?,?)",
            ("legacy-cycle", "2026-08-20", "complete", 0, observed_at, "legacy-cycle", "{}"),
        )
        connection.execute(
            "INSERT INTO ops_conclusions(ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key) VALUES (?,?,?,?,?,?)",
            (
                "legacy-ops",
                "legacy-cycle",
                json.dumps(underlying, sort_keys=True, separators=(",", ":")),
                "complete",
                observed_at,
                "legacy-ops",
            ),
        )
        connection.commit()

    projection = build_ops_standup_projection(store=store)

    assert projection["state"] == "degraded"
    assert projection["reason_codes"] == [
        "ops_conclusion_missing_workspace_recursion",
        "ops_conclusion_missing_active_workspace_recursion",
        "ops_conclusion_clock_unverified",
        "ops_conclusion_attempt_missing",
        "ops_conclusion_missing_shared_ops_reconciliation",
    ]
    assert projection["observed_at"] is None
    assert projection["clock"] is None
    assert projection["workspace_recursion"] == []
    assert projection["decision_readiness"]["state"] == "ready"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda projection: projection["canonical_decisions"].append(
            {
                "decision_id": "decision-1",
                "decision_type": "owner approval",
                "status": "resolved",
                "title": "Bounded title",
                "state_version": 1,
                "interaction_mode": "simple",
                "route": "ops",
                "resolution": {"choice": {"raw_body": "nested leak"}},
                "session_ref": None,
                "updated_at": "2026-08-20T00:00:00+00:00",
                "links": [],
            }
        ),
        lambda projection: projection["decision_readiness"].update(
            checked_at={"raw_body": "nested leak"}
        ),
        lambda projection: projection["supporting_evidence_links"].append(
            {"url": "https://example.com/evidence?session=opaque"}
        ),
        lambda projection: projection["workspace_updates"].append(
            {"count": float("nan")}
        ),
    ],
)
def test_v2_sync_boundary_rejects_nested_query_and_nonfinite_values(tmp_path, mutate):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    projection = build_ops_standup_projection(store=store)
    mutate(projection)

    with pytest.raises(OpsStandupProjectionError):
        validate_ops_standup_projection(projection)


def test_workspace_route_is_honestly_degraded_without_sync(monkeypatch):
    monkeypatch.setattr("app.routes.workspace.get_snapshot_payload", lambda *_: None)
    response = TestClient(app).get("/api/workspace/ops-standup")
    assert response.status_code == 200
    assert response.json()["state"] == "degraded"
    assert response.json()["reason_codes"] == ["projection_not_synced"]


def test_workspace_route_can_read_canonical_ops_only_when_local_fallback_is_explicit(monkeypatch):
    expected = {"schema_version": "ops_standup_summary/v1", "state": "ready"}
    monkeypatch.setenv("AI_CLONE_LOCAL_CANONICAL_PROJECTION", "true")
    monkeypatch.setattr("app.routes.workspace.get_snapshot_payload", lambda *_: None)
    monkeypatch.setattr("app.routes.workspace.build_ops_standup_projection", lambda: expected)
    response = TestClient(app).get("/api/workspace/ops-standup")
    assert response.status_code == 200
    assert response.json() == expected


def test_workspace_goal_projection_covers_every_active_project_from_one_authority(
    workspace_goal_projection,
):
    projection = workspace_goal_projection

    assert projection["schema_version"] == "ops_workspace_goal_projection/v1"
    assert projection["state"] == "ready"
    assert projection["clock"]["authority"] == "ai_clone_utc"
    assert len(projection["authority_sha256"]) == 64
    assert len(projection["projected_contracts_sha256"]) == 64
    assert [item["workspace_key"] for item in projection["workspaces"]] == [
        "feezie-os",
        "fusion-os",
        "easyoutfitapp",
        "ai-swag-store",
        "agc",
        "work-life-tools",
    ]
    assert all(
        set(item["goal"])
        == {
            "schema_version",
            "goal",
            "progress_signals",
            "phase_gate",
            "no_action_trigger",
        }
        for item in projection["workspaces"]
    )
    serialized = json.dumps(projection)
    assert "safe_internal_boundary" not in serialized
    assert "owner_required_boundary" not in serialized
    assert "authority_refs" not in serialized
    assert "/Users/" not in serialized


def test_workspace_goal_projection_rejects_partial_or_tampered_portfolio(
    workspace_goal_projection,
):
    partial = copy.deepcopy(workspace_goal_projection)
    partial["workspaces"] = partial["workspaces"][:-1]
    with pytest.raises(OpsWorkspaceGoalProjectionError, match="exact active"):
        validate_ops_workspace_goal_projection(partial)

    tampered = copy.deepcopy(workspace_goal_projection)
    tampered["workspaces"][0]["goal"]["goal"] = "Changed without a new projection digest."
    with pytest.raises(OpsWorkspaceGoalProjectionError, match="digest mismatch"):
        validate_ops_workspace_goal_projection(tampered)


def test_workspace_goal_projection_fails_closed_without_private_authority(monkeypatch):
    unavailable_entries = tuple(
        {
            **entry,
            "goal_contract_status": "private_authority_unavailable",
            "goal_contract_observed_at": None,
            "goal_contract_authority_sha256": None,
            "goal_contract": {},
        }
        for entry in _goal_projection_authority_entries()
    )
    monkeypatch.setattr(
        ops_workspace_goal_projection_service,
        "_active_project_entries",
        lambda: unavailable_entries,
    )

    with pytest.raises(OpsWorkspaceGoalProjectionError, match="authority is unavailable"):
        build_ops_workspace_goal_projection()


def test_workspace_goal_projection_unavailable_state_claims_no_authority():
    projection = unavailable_ops_workspace_goal_projection(
        "workspace_goal_projection_not_synced"
    )

    assert validate_ops_workspace_goal_projection(projection) == projection
    assert projection["state"] == "unavailable"
    assert projection["observed_at"] is None
    assert projection["workspaces"] == []


def test_workspace_goal_route_reads_the_independent_goal_projection(
    monkeypatch,
    workspace_goal_projection,
):
    projection = workspace_goal_projection
    monkeypatch.setattr(
        "app.routes.workspace.get_snapshot_payload",
        lambda workspace, snapshot_type: projection
        if snapshot_type == "ops_workspace_goal_contracts"
        else None,
    )

    response = TestClient(app).get("/api/workspace/ops-workspace-goals")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json() == projection


def test_workspace_goal_sync_receipt_binds_authority_and_semantics(
    monkeypatch,
    workspace_goal_projection,
):
    projection = workspace_goal_projection
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda workspace, kind, payload, **kwargs: (
            {"payload": payload, "updated_at": payload["generated_at"]},
            True,
        ),
    )

    response = TestClient(app).post(
        "/api/brain/ops-workspace-goals/sync",
        json={
            "schema_version": "ops_workspace_goal_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 200
    receipt = response.json()
    assert receipt["disposition"] == "stored"
    assert receipt["authority_sha256"] == projection["authority_sha256"]
    assert receipt["projected_contracts_sha256"] == projection[
        "projected_contracts_sha256"
    ]
    assert receipt["semantic_payload_sha256"] == (
        ops_workspace_goal_projection_semantic_sha256(projection)
    )


def test_workspace_goal_sync_is_idempotent_for_the_same_canonical_authority(
    monkeypatch,
    workspace_goal_projection,
):
    projection = workspace_goal_projection
    stored_projection = json.loads(json.dumps(projection))
    stored_projection["generated_at"] = projection["generated_at"]
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda workspace, kind, payload, **kwargs: (
            {
                "payload": stored_projection,
                "updated_at": stored_projection["generated_at"],
            },
            False,
        ),
    )

    response = TestClient(app).post(
        "/api/brain/ops-workspace-goals/sync",
        json={
            "schema_version": "ops_workspace_goal_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 200
    assert response.json()["stored"] is False
    assert response.json()["disposition"] == "idempotent_same_authority"


def test_workspace_goal_sync_retains_a_newer_canonical_observation(
    monkeypatch,
    workspace_goal_projection,
):
    projection = workspace_goal_projection
    stored_projection = json.loads(json.dumps(projection))
    stored_projection["generated_at"] = projection["generated_at"]
    stored_projection["observed_at"] = projection["generated_at"]
    stored_projection["clock"]["observed_at"] = stored_projection["observed_at"]
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda workspace, kind, payload, **kwargs: (
            {
                "payload": stored_projection,
                "updated_at": stored_projection["generated_at"],
            },
            False,
        ),
    )

    response = TestClient(app).post(
        "/api/brain/ops-workspace-goals/sync",
        json={
            "schema_version": "ops_workspace_goal_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 200
    assert response.json()["stored"] is False
    assert response.json()["disposition"] == "retained_newer"
    assert response.json()["observed_at"] == stored_projection["observed_at"]


def test_sync_route_acknowledges_exact_hash(monkeypatch, tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    projection = build_ops_standup_projection(store=store)
    snapshots = {}
    monkeypatch.setattr("app.routes.brain.upsert_snapshot_monotonic", lambda workspace, kind, payload, **kwargs: ({"payload": payload, "updated_at": payload["generated_at"]}, True))
    response = TestClient(app).post("/api/brain/ops-standup/sync", json={"schema_version": "ops_standup_projection_sync/v1", "generated_at": projection["generated_at"], "projection": projection})
    assert response.status_code == 200
    assert response.json()["disposition"] == "stored"
    assert len(response.json()["payload_sha256"]) == 64


@pytest.mark.parametrize(
    "mutate",
    [
        lambda projection: projection["clock"].update(
            authority="browser_local"
        ),
        lambda projection: projection["clock"].update(
            observed_at="2026-08-20T06:15:01Z"
        ),
        lambda projection: projection.update(cycle_date="2026-08-19"),
        lambda projection: projection.update(
            portfolio_cycle_id="daily-2026-08-20@20260820T061501000000Z"
        ),
    ],
)
def test_ops_projection_rejects_clock_cycle_and_observation_mismatch(mutate):
    projection = _semantic_projection()
    mutate(projection)

    with pytest.raises(OpsStandupProjectionError, match="semantic observation"):
        validate_ops_standup_projection(projection)


@pytest.mark.parametrize(
    "noncanonical_observed_at",
    [
        "20260820T061500Z",
        "2026-08-20T06:15Z",
        "2026-08-20 06:15:00Z",
        "2026-08-20T06:15:00+00:00",
    ],
)
def test_v3_projection_requires_exact_canonical_ai_clone_utc_syntax(
    noncanonical_observed_at: str,
):
    projection = _semantic_projection()
    projection["observed_at"] = noncanonical_observed_at
    projection["clock"]["observed_at"] = noncanonical_observed_at

    with pytest.raises(OpsStandupProjectionError, match="semantic observation"):
        validate_ops_standup_projection(projection)


@pytest.mark.parametrize(
    "identity_field",
    ["ops_conclusion_id", "portfolio_cycle_id"],
)
def test_v3_projection_rejects_non_exact_semantic_identity_before_storage(
    identity_field: str,
):
    projection = _semantic_projection()
    projection[identity_field] = f" {projection[identity_field]}"
    if identity_field == "ops_conclusion_id":
        projection["ops_conclusion_attempt_id"] = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "ai-clone:ops-attempt:"
                f"{projection['ops_conclusion_id']}:"
                f"{projection['ops_conclusion_attempt_number']}",
            )
        )

    with pytest.raises(OpsStandupProjectionError, match="Ops identity"):
        validate_ops_standup_projection(projection)


def test_sync_route_rejects_non_exact_identity_before_storage(monkeypatch):
    projection = _semantic_projection()
    projection["portfolio_cycle_id"] = f" {projection['portfolio_cycle_id']}"
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: pytest.fail("invalid identity reached storage"),
    )

    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 422


def test_sync_route_rejects_malformed_semantic_clock(monkeypatch):
    projection = _semantic_projection()
    projection["clock"]["observed_at"] = "2026-08-20T06:15:01Z"
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: pytest.fail("invalid projection reached storage"),
    )

    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 422


def test_ops_sync_orders_by_semantic_observation_not_projection_receipt(monkeypatch):
    incoming = _semantic_projection(
        observed_at="2026-08-20T06:15:00Z",
        generated_at="2026-08-21T12:00:00Z",
    )
    current = _semantic_projection(
        observed_at="2026-08-20T07:15:00Z",
        generated_at="2026-08-20T08:00:00Z",
    )

    def retain_newer(_workspace, _kind, _payload, **kwargs):
        assert kwargs["semantic_order_required"] is True
        assert kwargs["semantic_revision"] == 1
        assert kwargs["semantic_revision_field"] == "ops_conclusion_attempt_number"
        assert kwargs["semantic_revision_required"] is True
        assert kwargs["semantic_revision_strict_increment"] is True
        assert kwargs["semantic_identity_fields"] == (
            "ops_conclusion_id",
            "portfolio_cycle_id",
        )
        assert kwargs["semantic_observed_at"] == datetime(
            2026, 8, 20, 6, 15, tzinfo=timezone.utc
        )
        assert kwargs["generated_at"] == datetime(
            2026, 8, 21, 12, 0, tzinfo=timezone.utc
        )
        return {"payload": current, "updated_at": current["generated_at"]}, False

    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        retain_newer,
    )
    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": incoming["generated_at"],
            "projection": incoming,
        },
    )

    assert response.status_code == 200
    assert response.json()["stored"] is False
    assert response.json()["disposition"] == "retained_newer_semantic_observation"


def test_ops_sync_same_observation_is_idempotent_or_conflict(monkeypatch):
    projection = _semantic_projection()
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: (
            {"payload": projection, "updated_at": projection["generated_at"]},
            False,
        ),
    )
    exact = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )
    assert exact.status_code == 200
    assert exact.json()["disposition"] == "idempotent_same_hash"

    conflicting = copy.deepcopy(projection)
    conflicting.update(
        state="degraded",
        status="degraded",
        reason_codes=["ops_cycle_degraded"],
    )
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: (
            {"payload": projection, "updated_at": projection["generated_at"]},
            False,
        ),
    )
    conflict = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": conflicting["generated_at"],
            "projection": conflicting,
        },
    )
    assert conflict.status_code == 409


@pytest.mark.parametrize(
    "mutate",
    [
        lambda projection: projection.update(status="degraded"),
        lambda projection: projection.update(reason_codes=["ops_cycle_degraded"]),
        lambda projection: projection.update(workspace_recursion=[]),
        lambda projection: projection.update(state="empty", status="empty"),
    ],
)
def test_ops_projection_rejects_incoherent_readiness_claims(mutate):
    projection = _semantic_projection()
    mutate(projection)

    with pytest.raises(OpsStandupProjectionError, match="incoherent"):
        validate_ops_standup_projection(projection)


def test_ops_sync_rejects_incoherent_readiness_before_storage(monkeypatch):
    projection = _semantic_projection()
    projection["status"] = "degraded"
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: pytest.fail("incoherent projection reached storage"),
    )

    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 422


def test_unchanged_canonical_attempt_rebuild_has_stable_semantic_hash(tmp_path):
    store = IntegratedSystemStore(tmp_path / "stable-attempt.sqlite3")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="stable-attempt-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os"],
        readiness_id=_ready(store, cycle_id="stable-attempt-cycle"),
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="stable-attempt-cycle",
        workspace_key="feezie-os",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload={
            "summary": "No eligible change.",
            "goal": {
                "schema_version": "workspace_goal_contract/v1",
                "goal": "Advance truthful private content evidence without publishing.",
                "progress_signals": ["A bounded internal result has a verified receipt."],
                "phase_gate": "Owner review remains required before publication.",
                "no_action_trigger": "Reevaluate when eligible evidence arrives.",
                "safe_internal_boundary": ["Prepare bounded private drafts."],
                "owner_required_boundary": ["Publication requires the owner."],
                "authority_refs": ["SOURCE_OF_TRUTH.md"],
            },
            "no_action": [
                {
                    "selected": True,
                    "reason": "No new eligible evidence was observed.",
                    "future_trigger": "Eligible evidence arrives.",
                }
            ],
        },
        idempotency_key="stable-attempt-workspace",
    )
    service.conclude_ops(
        portfolio_cycle_id="stable-attempt-cycle",
        system_health={"api": "healthy"},
    )

    with patch(
        "app.services.ops_standup_projection_service._now_iso",
        side_effect=["2026-08-20T06:16:00Z", "2026-08-20T06:17:00Z"],
    ):
        first = build_ops_standup_projection(store=store)
        rebuilt = build_ops_standup_projection(store=store)

    assert first["generated_at"] != rebuilt["generated_at"]
    assert first["decision_readiness"]["checked_at"] != rebuilt["decision_readiness"]["checked_at"]
    assert first["ops_conclusion_attempt_number"] == 1
    assert rebuilt["ops_conclusion_attempt_number"] == 1
    assert ops_projection_semantic_sha256(first) == ops_projection_semantic_sha256(
        rebuilt
    )


def test_ops_sync_advances_same_observation_only_by_next_canonical_attempt(
    monkeypatch,
):
    remote: dict[str, dict | None] = {"payload": None}

    def monotonic_attempt_store(_workspace, _kind, incoming, **kwargs):
        assert kwargs["semantic_revision"] == incoming[
            "ops_conclusion_attempt_number"
        ]
        current = remote["payload"]
        should_store = current is None or (
            incoming["observed_at"] > current["observed_at"]
            or (
                incoming["observed_at"] == current["observed_at"]
                and incoming["ops_conclusion_id"] == current["ops_conclusion_id"]
                and incoming["portfolio_cycle_id"] == current["portfolio_cycle_id"]
                and incoming["ops_conclusion_attempt_number"]
                == current["ops_conclusion_attempt_number"] + 1
            )
        )
        if should_store:
            remote["payload"] = copy.deepcopy(incoming)
            return {
                "payload": remote["payload"],
                "updated_at": incoming["generated_at"],
            }, True
        return {
            "payload": copy.deepcopy(current),
            "updated_at": current["generated_at"],
        }, False

    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        monotonic_attempt_store,
    )
    client = TestClient(app)
    attempt_one = _semantic_projection(
        generated_at="2026-08-20T06:16:00Z",
        attempt_number=1,
    )
    attempt_one.update(
        state="degraded",
        status="degraded",
        reason_codes=["ops_cycle_degraded"],
    )
    attempt_two = _semantic_projection(
        generated_at="2026-08-20T06:17:00Z",
        attempt_number=2,
    )

    first = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": attempt_one["generated_at"],
            "projection": attempt_one,
        },
    )
    repaired = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": attempt_two["generated_at"],
            "projection": attempt_two,
        },
    )
    assert first.status_code == 200
    assert repaired.status_code == 200
    assert repaired.json()["stored"] is True
    assert remote["payload"]["ops_conclusion_attempt_number"] == 2
    assert remote["payload"]["status"] == "complete"

    rebuilt_attempt_two = copy.deepcopy(attempt_two)
    rebuilt_attempt_two["generated_at"] = "2026-08-20T06:18:00Z"
    rebuilt_attempt_two["decision_readiness"]["checked_at"] = (
        "2026-08-20T06:18:00Z"
    )
    retry = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": rebuilt_attempt_two["generated_at"],
            "projection": rebuilt_attempt_two,
        },
    )
    assert retry.status_code == 200
    assert retry.json()["stored"] is False
    assert retry.json()["disposition"] == "idempotent_same_canonical_attempt"

    changed_same_attempt = copy.deepcopy(rebuilt_attempt_two)
    changed_same_attempt["generated_at"] = "2026-08-20T06:19:00Z"
    changed_same_attempt["decision_readiness"]["checked_at"] = (
        "2026-08-20T06:19:00Z"
    )
    changed_same_attempt["recommended_next_actions"] = [
        {"summary": "Changed semantic recommendation.", "route": "ops"}
    ]
    conflict = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": changed_same_attempt["generated_at"],
            "projection": changed_same_attempt,
        },
    )
    assert conflict.status_code == 409

    stale = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": attempt_one["generated_at"],
            "projection": attempt_one,
        },
    )
    assert stale.status_code == 409

    remote["payload"] = copy.deepcopy(attempt_one)
    skipped_attempt = _semantic_projection(
        generated_at="2026-08-20T06:20:00Z",
        attempt_number=3,
    )
    skipped = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": skipped_attempt["generated_at"],
            "projection": skipped_attempt,
        },
    )
    assert skipped.status_code == 409

    remote["payload"] = copy.deepcopy(attempt_one)
    swapped_conclusion = _semantic_projection(
        generated_at="2026-08-20T06:21:00Z",
        attempt_number=2,
        ops_conclusion_id="ops-clock-test-swapped",
    )
    swapped = client.post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": swapped_conclusion["generated_at"],
            "projection": swapped_conclusion,
        },
    )
    assert swapped.status_code == 409
    assert remote["payload"]["ops_conclusion_id"] == "ops-clock-test"


def test_ops_sync_rejects_forged_canonical_attempt_identity(monkeypatch):
    projection = _semantic_projection()
    projection["ops_conclusion_attempt_id"] = str(uuid.uuid4())
    monkeypatch.setattr(
        "app.routes.brain.upsert_snapshot_monotonic",
        lambda *_args, **_kwargs: pytest.fail("forged attempt reached storage"),
    )

    response = TestClient(app).post(
        "/api/brain/ops-standup/sync",
        json={
            "schema_version": "ops_standup_projection_sync/v1",
            "generated_at": projection["generated_at"],
            "projection": projection,
        },
    )

    assert response.status_code == 422
