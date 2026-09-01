from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import app.services.portfolio_cycle_service as portfolio_cycle

from app.services.integrated_memory_readiness_service import IntegratedMemoryReadinessService
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.portfolio_cycle_service import (
    PortfolioCycleConflict,
    PortfolioCycleService,
    active_portfolio_workspaces,
    classify_ops_subsystem_health,
)


def _goal(workspace_key: str) -> dict[str, object]:
    return {
        "schema_version": "workspace_goal_contract/v1",
        "goal": f"Advance {workspace_key} only from verified bounded evidence.",
        "progress_signals": ["One verified goal-aligned change is durably recorded."],
        "phase_gate": "The current bounded goal phase has verified completion evidence.",
        "no_action_trigger": "New eligible evidence or a governed lifecycle change arrives.",
        "safe_internal_boundary": ["Analyze approved evidence and maintain bounded internal work."],
        "owner_required_boundary": ["External, irreversible, or strategic action requires the owner."],
        "authority_refs": ["SOURCE_OF_TRUTH.md"],
    }


def _healthy_no_change_payload(summary: str, workspace_key: str) -> dict[str, object]:
    return {
        "summary": summary,
        "goal": _goal(workspace_key),
        "no_action": [
            {
                "selected": True,
                "reason": "No new eligible goal-aligned action or verified outcome was observed.",
                "future_trigger": "New eligible evidence or a governed lifecycle change arrives.",
            }
        ],
    }


def _ready_store(
    tmp_path: Path,
    *,
    cycle_id: str,
    degraded: bool = False,
) -> tuple[IntegratedSystemStore, str]:
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    readiness = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id=cycle_id,
        retrieval_refresh=lambda: {"schema_version": "codex_memory_index/v1", "status": "ok", "files": 10, "last_sync_at": "2026-08-20T08:00:00+00:00"},
        recall_search=(lambda _query: []) if degraded else (lambda _query: [{"path": "memory"}]),
        now=datetime(2026, 8, 20, 8, tzinfo=timezone.utc),
    )
    return store, readiness["readiness_id"]


def test_active_workspaces_use_registry_status_and_visibility() -> None:
    entries = [
        {"key": "feezie-os", "status": "live", "portfolio_visible": True},
        {"key": "agc", "status": "standing_up", "portfolio_visible": True},
        {"key": "shared_ops", "status": "live", "portfolio_visible": False},
        {"key": "retired", "status": "retired", "portfolio_visible": True},
    ]
    assert active_portfolio_workspaces(entries) == ["agc", "feezie-os"]


def test_cycle_start_replay_requires_same_readiness_date_and_morning_brief(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="strict-cycle")
    second_readiness = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id="memory-second",
        retrieval_refresh=lambda: {
            "schema_version": "codex_memory_index/v1",
            "status": "ok",
            "files": 10,
            "last_sync_at": "2026-08-20T09:00:00+00:00",
        },
        recall_search=lambda _query: [{"path": "memory"}],
        now=datetime(2026, 8, 20, 9, tzinfo=timezone.utc),
    )
    service = PortfolioCycleService(store)
    first = service.start_cycle(
        portfolio_cycle_id="strict-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
        morning_brief_ref="brief:one",
    )
    replay = service.start_cycle(
        portfolio_cycle_id="strict-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
        morning_brief_ref="brief:one",
    )
    assert replay["portfolio_cycle_id"] == first["portfolio_cycle_id"]

    with pytest.raises(ValueError, match="not bound to this exact cycle"):
        service.start_cycle(
            portfolio_cycle_id="strict-cycle",
            cycle_date=date(2026, 8, 20),
            expected_workspaces=["agc"],
            readiness_id=second_readiness["readiness_id"],
            morning_brief_ref="brief:one",
        )
    with pytest.raises(ValueError, match="observation does not match"):
        service.start_cycle(
            portfolio_cycle_id="strict-cycle",
            cycle_date=date(2026, 8, 21),
            expected_workspaces=["agc"],
            readiness_id=readiness_id,
            morning_brief_ref="brief:one",
        )
    with pytest.raises(PortfolioCycleConflict, match="idempotency conflict"):
        service.start_cycle(
            portfolio_cycle_id="strict-cycle",
            cycle_date=date(2026, 8, 20),
            expected_workspaces=["agc"],
            readiness_id=readiness_id,
            morning_brief_ref="brief:two",
        )


def test_cycle_replay_can_fill_missing_morning_brief_without_changing_core_lineage(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="brief-repair-cycle")
    service = PortfolioCycleService(store)
    first = service.start_cycle(
        portfolio_cycle_id="brief-repair-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
        morning_brief_ref=None,
    )
    repaired = service.start_cycle(
        portfolio_cycle_id="brief-repair-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
        morning_brief_ref="brief:recovered",
    )

    assert repaired["portfolio_cycle_id"] == first["portfolio_cycle_id"]
    assert json.loads(repaired["metadata_json"])["morning_brief_ref"] == "brief:recovered"


def test_cycle_and_ops_reject_naive_semantic_observations(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="clock-strict-cycle")
    service = PortfolioCycleService(store)

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        service.start_cycle(
            portfolio_cycle_id="clock-strict-cycle",
            cycle_date=date(2026, 8, 20),
            expected_workspaces=["agc"],
            readiness_id=readiness_id,
            observed_at=datetime(2026, 8, 20, 8),
        )

    service.start_cycle(
        portfolio_cycle_id="clock-strict-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="clock-strict-cycle",
        workspace_key="agc",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("No eligible change.", "agc"),
        idempotency_key="clock-strict-workspace",
    )

    with pytest.raises(PortfolioCycleConflict, match="timezone-aware UTC"):
        service.conclude_ops(
            portfolio_cycle_id="clock-strict-cycle",
            system_health={"api": "healthy"},
            observed_at=datetime(2026, 8, 20, 8),
        )

def test_all_workspace_receipts_produce_complete_ops_artifact(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="portfolio-1")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="portfolio-1",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os", "work-life-tools"],
        readiness_id=readiness_id,
        morning_brief_ref="daily-brief:2026-08-20",
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="portfolio-1",
        workspace_key="feezie-os",
        conclusion_kind="conclusion",
        provenance_kind="independent_agent",
        payload={
            "summary": "One content opportunity advanced.",
            "goal": _goal("feezie-os"),
            "decisions": [{"summary": "Select it", "route": "uncertain"}],
            "blockers": [{"summary": "Exact owner publication approval is still required."}],
            "evidence_links": [{"ref": "opportunity:1"}],
            "recommended_next_actions": [
                {"summary": "Prepare the bounded internal review packet."}
            ],
            "reference_only": [
                {"summary": "Prior content plan, retained for comparison only."}
            ],
        },
        idempotency_key="feezie",
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="portfolio-1",
        workspace_key="work-life-tools",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("Healthy; no material change.", "work-life-tools"),
        idempotency_key="work-life",
    )
    ops = service.conclude_ops(
        portfolio_cycle_id="portfolio-1",
        system_health={"backend": "healthy", "memory": "ready"},
        recommended_next_actions=["Review the selected content opportunity."],
    )
    assert ops["schema_version"] == "ops_standup_summary_conclusion/v1"
    assert ops["status"] == "complete"
    assert len(ops["workspace_updates"]) == 2
    assert ops["workspace_decisions"][0]["route"] == "ops"
    assert ops["workspace_recursion"][0]["blocked"] == [
        {
            "summary": "Exact owner publication approval is still required.",
            "route": "ops",
        }
    ]
    assert ops["workspace_recursion"][0]["recommendations"] == [
        {
            "summary": "Prepare the bounded internal review packet.",
            "route": "ops",
        }
    ]
    assert ops["workspace_recursion"][0]["reference_only"] == [
        {
            "summary": "Prior content plan, retained for comparison only.",
        }
    ]
    assert ops["shared_ops_reconciliation"]["goal"]["schema_version"] == (
        "workspace_goal_contract/v1"
    )
    assert ops["shared_ops_reconciliation"]["actions_taken"][0]["kind"] == (
        "portfolio_reconciliation"
    )
    assert "without executing project work" in (
        ops["shared_ops_reconciliation"]["actions_taken"][0]["summary"]
    )
    assert ops["shared_ops_reconciliation"]["recommendations"] == [
        {"summary": "Review the selected content opportunity.", "route": "ops"}
    ]
    assert ops["shared_ops_reconciliation"]["reference_only"] == [
        {
            "classification": "reference_only",
            "workspace_key": "feezie-os",
            "ref": "opportunity:1",
        }
    ]
    assert ops["degraded_system_warnings"] == []
    assert service.conclude_ops(
        portfolio_cycle_id="portfolio-1",
        system_health={"backend": "healthy", "memory": "ready"},
        recommended_next_actions=["Review the selected content opportunity."],
    )["ops_conclusion_id"] == ops["ops_conclusion_id"]
    with pytest.raises(PortfolioCycleConflict, match="replay inputs changed"):
        service.conclude_ops(
            portfolio_cycle_id="portfolio-1",
            system_health={"backend": "degraded", "memory": "ready"},
            recommended_next_actions=["Review the selected content opportunity."],
        )
    with store.connection() as connection:
        event = connection.execute(
            "SELECT payload_json FROM system_events WHERE event_type='workspace.concluded' AND aggregate_id=?",
            (
                connection.execute(
                    "SELECT conclusion_id FROM workspace_conclusions WHERE workspace_key='feezie-os'"
                ).fetchone()[0],
            ),
        ).fetchone()
    payload = json.loads(event["payload_json"])
    assert payload["cycle_id"] == "portfolio-1"
    assert payload["decisions"][0]["summary"] == "Select it"


def test_missing_workspace_and_failed_memory_are_visibly_degraded(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(
        tmp_path,
        cycle_id="portfolio-degraded",
        degraded=True,
    )
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="portfolio-degraded",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os", "agc"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="portfolio-degraded",
        workspace_key="feezie-os",
        conclusion_kind="healthy_no_change",
        provenance_kind="synthesized_lens",
        payload=_healthy_no_change_payload("No material content change.", "feezie-os"),
        idempotency_key="feezie-degraded",
    )
    ops = service.conclude_ops(portfolio_cycle_id="portfolio-degraded", system_health={"memory": "degraded"})
    assert ops["status"] == "degraded"
    assert any("Missing workspace conclusions: agc" in item for item in ops["degraded_system_warnings"])
    assert any("Memory readiness is degraded" in item for item in ops["degraded_system_warnings"])
    assert {item["workspace_key"]: item["state"] for item in ops["workspace_updates"]}["agc"] == "missing"


def test_missing_shared_ops_goal_is_visible_and_degrades_only_reconciliation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store, readiness_id = _ready_store(
        tmp_path,
        cycle_id="shared-ops-goal-missing",
    )
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="shared-ops-goal-missing",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="shared-ops-goal-missing",
        workspace_key="agc",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("AGC has no eligible change.", "agc"),
        idempotency_key="shared-ops-goal-missing-agc",
    )
    monkeypatch.setattr(
        portfolio_cycle,
        "_shared_ops_goal_contract",
        lambda: ({}, "canonical Shared Ops workspace-goal authority is unavailable"),
    )

    ops = service.conclude_ops(
        portfolio_cycle_id="shared-ops-goal-missing",
        system_health={"api": "healthy"},
    )

    assert ops["status"] == "degraded"
    assert ops["workspace_recursion"][0]["workspace_key"] == "agc"
    assert ops["shared_ops_reconciliation"]["goal"] == {}
    assert any(
        item.get("reason_code") == "shared_ops_goal_authority_blocked"
        for item in ops["shared_ops_reconciliation"]["blocked"]
    )
    assert ops["degraded_system_warnings"][-1] == (
        "Shared Ops goal authority is unavailable or invalid."
    )


def test_unexpected_workspace_is_rejected(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="portfolio-2")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="portfolio-2",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os"],
        readiness_id=readiness_id,
    )
    with pytest.raises(ValueError, match="not active"):
        service.record_workspace_conclusion(
            portfolio_cycle_id="portfolio-2",
            workspace_key="unknown",
            conclusion_kind="conclusion",
            provenance_kind="independent_agent",
            payload={"summary": "No."},
            idempotency_key="unknown",
        )


def test_workspace_conclusion_replay_rejects_changed_payload_under_same_key(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="workspace-idempotency")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="workspace-idempotency",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="workspace-idempotency",
        workspace_key="agc",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("Stable evaluated state.", "agc"),
        idempotency_key="agc-stable",
    )

    with pytest.raises(PortfolioCycleConflict, match="idempotency conflict"):
        service.record_workspace_conclusion(
            portfolio_cycle_id="workspace-idempotency",
            workspace_key="agc",
            conclusion_kind="healthy_no_change",
            provenance_kind="deterministic_policy",
            payload=_healthy_no_change_payload("Silently changed state.", "agc"),
            idempotency_key="agc-stable",
        )


def test_workspace_conclusion_is_bound_to_exact_cycle_observation(tmp_path: Path) -> None:
    cycle_id = "workspace-clock-binding"
    observed_at = datetime(
        2026, 8, 20, 8, 0, 0, 482752, tzinfo=timezone.utc
    )
    store, readiness_id = _ready_store(tmp_path, cycle_id=cycle_id)
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc", "fusion-os"],
        readiness_id=readiness_id,
        observed_at=observed_at,
    )

    for idempotency_key, payload, expected_error in (
        (
            "wrong-cycle",
            {"summary": "Wrong cycle.", "cycle_id": "another-cycle"},
            "cycle identity does not match",
        ),
        (
            "wrong-observation",
            {
                "summary": "Wrong observation.",
                "cycle_id": cycle_id,
                "observed_at": "2026-08-20T08:01:00Z",
            },
            "observation does not match",
        ),
        (
            "naive-observation",
            {
                "summary": "Naive observation.",
                "cycle_id": cycle_id,
                "observed_at": "2026-08-20T08:00:00",
            },
            "observation does not match",
        ),
    ):
        with pytest.raises(PortfolioCycleConflict, match=expected_error):
            service.record_workspace_conclusion(
                portfolio_cycle_id=cycle_id,
                workspace_key="agc",
                conclusion_kind="conclusion",
                provenance_kind="deterministic_policy",
                payload=payload,
                idempotency_key=idempotency_key,
            )

    inferred = service.record_workspace_conclusion(
        portfolio_cycle_id=cycle_id,
        workspace_key="agc",
        conclusion_kind="conclusion",
        provenance_kind="deterministic_policy",
        payload={"summary": "The canonical writer binds omitted clock fields."},
        idempotency_key="canonical-clock-inferred",
    )
    explicit = service.record_workspace_conclusion(
        portfolio_cycle_id=cycle_id,
        workspace_key="fusion-os",
        conclusion_kind="conclusion",
        provenance_kind="deterministic_policy",
        payload={
            "summary": "The caller supplied the exact explicit observation.",
            "cycle_id": cycle_id,
            "observed_at": "2026-08-20T08:00:00Z",
        },
        idempotency_key="canonical-clock-explicit",
    )

    assert json.loads(inferred["payload_json"])["cycle_id"] == cycle_id
    assert json.loads(inferred["payload_json"])["observed_at"] == observed_at.isoformat()
    assert json.loads(explicit["payload_json"])["observed_at"] == observed_at.isoformat()
    with store.connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM workspace_conclusions WHERE portfolio_cycle_id=?",
            (cycle_id,),
        ).fetchone()[0] == 2
        events = connection.execute(
            "SELECT payload_json FROM system_events WHERE event_type='workspace.concluded' ORDER BY event_id",
        ).fetchall()
    assert all(json.loads(row["payload_json"])["cycle_id"] == cycle_id for row in events)
    assert all(
        json.loads(row["payload_json"])["observed_at"] == observed_at.isoformat()
        for row in events
    )


def test_goal_authority_blocks_healthy_no_change_and_degrades_ops_with_visible_trigger(
    tmp_path: Path,
) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="goal-authority-cycle")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="goal-authority-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["agc", "fusion-os"],
        readiness_id=readiness_id,
    )

    for workspace_key, goal in (
        ("agc", {}),
        (
            "fusion-os",
            {
                "schema_version": "workspace_goal_contract/v1",
                "goal": "An incomplete non-canonical goal must not pass.",
            },
        ),
    ):
        with pytest.raises(ValueError, match="complete canonical workspace goal"):
            service.record_workspace_conclusion(
                portfolio_cycle_id="goal-authority-cycle",
                workspace_key=workspace_key,
                conclusion_kind="healthy_no_change",
                provenance_kind="deterministic_policy",
                payload={
                    "summary": "No change was claimed without goal authority.",
                    "goal": goal,
                    "no_action": [
                        {
                            "selected": True,
                            "reason": "Nothing changed.",
                            "future_trigger": "New evidence arrives.",
                        }
                    ],
                },
                idempotency_key=f"invalid-healthy:{workspace_key}",
            )
        service.record_workspace_conclusion(
            portfolio_cycle_id="goal-authority-cycle",
            workspace_key=workspace_key,
            conclusion_kind="conclusion",
            provenance_kind="deterministic_policy",
            payload={
                "summary": "Goal-directed evaluation was blocked.",
                "goal": goal,
            },
            idempotency_key=f"blocked-goal:{workspace_key}",
        )

    ops = service.conclude_ops(
        portfolio_cycle_id="goal-authority-cycle",
        system_health={"api": "healthy"},
    )

    assert ops["status"] == "degraded"
    assert ops["degraded_system_warnings"] == [
        "Workspace goal authority is unavailable or invalid: agc, fusion-os."
    ]
    assert all(item["blocked"] for item in ops["workspace_recursion"])
    assert all(
        item["blocked"][0]["reason_code"] == "workspace_goal_authority_blocked"
        and item["blocked"][0]["reason"]
        and item["blocked"][0]["future_trigger"]
        for item in ops["workspace_recursion"]
    )


def test_unhealthy_subsystem_makes_ops_visibly_degraded(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="health-cycle")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="health-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="health-cycle",
        workspace_key="feezie-os",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("Healthy no change.", "feezie-os"),
        idempotency_key="health-cycle-feezie",
    )
    result = service.conclude_ops(
        portfolio_cycle_id="health-cycle",
        system_health={"memory_readiness": "ready", "backup_recovery": "not_verified"},
    )
    assert result["status"] == "degraded"
    assert result["degraded_system_warnings"] == ["Unhealthy or unverified subsystems: backup_recovery."]
    unavailable = service.conclude_ops(
        portfolio_cycle_id="health-cycle",
        system_health={"memory_readiness": "ready", "primary_api": "unavailable"},
    )
    assert unavailable["status"] == "degraded"
    assert unavailable["endpoint_and_subsystem_health"]["primary_api"] == "unavailable"
    assert unavailable["degraded_system_warnings"] == [
        "Unhealthy or unverified subsystems: primary_api."
    ]


def test_ops_health_taxonomy_is_closed_and_unknown_states_fail_closed() -> None:
    verdict = classify_ops_subsystem_health(
        {
            "ready_lane": "ready",
            "completed_lane": "completed",
            "available_lane": "available",
            "blocking_unavailable": "unavailable",
            "blocking_unknown": "unknown",
            "drifted_state": "looks_good",
            "backup_recovery": "unknown",
            "firestore_readiness": "unavailable",
        }
    )

    assert verdict["normalized_health"]["drifted_state"] == "unknown"
    assert verdict["warning_only_keys"] == [
        "backup_recovery",
        "firestore_readiness",
    ]
    assert verdict["blocking_keys"] == [
        "blocking_unavailable",
        "blocking_unknown",
        "drifted_state",
    ]


def test_degraded_ops_conclusion_can_repair_same_cycle_and_preserves_attempts(tmp_path: Path) -> None:
    store, readiness_id = _ready_store(tmp_path, cycle_id="repair-cycle")
    service = PortfolioCycleService(store)
    service.start_cycle(
        portfolio_cycle_id="repair-cycle",
        cycle_date=date(2026, 8, 20),
        expected_workspaces=["feezie-os", "agc"],
        readiness_id=readiness_id,
    )
    service.record_workspace_conclusion(
        portfolio_cycle_id="repair-cycle",
        workspace_key="feezie-os",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("Healthy.", "feezie-os"),
        idempotency_key="repair-feezie",
    )
    first = service.conclude_ops(portfolio_cycle_id="repair-cycle", system_health={"api": "healthy"})
    assert first["status"] == "degraded"
    service.record_workspace_conclusion(
        portfolio_cycle_id="repair-cycle",
        workspace_key="agc",
        conclusion_kind="healthy_no_change",
        provenance_kind="deterministic_policy",
        payload=_healthy_no_change_payload("Healthy.", "agc"),
        idempotency_key="repair-agc",
    )
    repaired = service.conclude_ops(portfolio_cycle_id="repair-cycle", system_health={"api": "healthy"})
    assert repaired["status"] == "complete"
    assert repaired["ops_conclusion_id"] == first["ops_conclusion_id"]
    with store.connection() as connection:
        attempts = connection.execute(
            "SELECT attempt_number,status FROM ops_conclusion_attempts ORDER BY attempt_number"
        ).fetchall()
        assert [(row["attempt_number"], row["status"]) for row in attempts] == [(1, "degraded"), (2, "complete")]
