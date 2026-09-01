from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone

import pytest
import app.services.daily_portfolio_coordinator_service as coordinator
import app.services.portfolio_cycle_service as portfolio_cycle
from app.services.daily_portfolio_coordinator_service import (
    adapt_daily_workspace_evaluations,
    adapt_daily_workspace_cycle_plans,
    adapt_daily_workspace_standups,
    run_portfolio_coordination,
)
from app.services.integrated_memory_readiness_service import IntegratedMemoryReadinessService
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.portfolio_cycle_service import PortfolioCycleService
from app.services.standup_relevance_service import build_standup_relevance_plan


def _feezie_goal() -> dict:
    return {
        "schema_version": "workspace_goal_contract/v1",
        "goal": "Advance FEEZIE from verified evidence without fabricating external progress.",
        "progress_signals": ["One verified internal content decision advances."],
        "phase_gate": "Verified evidence before internal content work",
        "no_action_trigger": "New eligible FEEZIE evidence changes the relevance result.",
        "safe_internal_boundary": ["Analyze already-approved canonical evidence."],
        "owner_required_boundary": ["Require owner approval for publication or social mutation."],
        "authority_refs": ["SOURCE_OF_TRUTH.md"],
    }


@pytest.fixture(autouse=True)
def _isolated_shared_ops_goal_authority(monkeypatch):
    """Keep public-source tests independent of the private goal authority file."""

    monkeypatch.setattr(
        portfolio_cycle,
        "_shared_ops_goal_contract",
        lambda: (
            {
                **_feezie_goal(),
                "goal": "Reconcile bounded portfolio evidence without becoming a project writer.",
            },
            None,
        ),
    )


def test_coordinator_rejects_naive_cycle_observation_at_every_public_boundary():
    naive = datetime(2026, 8, 26, 12, 30)
    common = {
        "cycle_id": "daily-2026-08-26@20260826T123000000000Z",
        "cycle_date": date(2026, 8, 26),
        "observed_at": naive,
        "expected_workspaces": ["fusion-os"],
    }

    with pytest.raises(ValueError, match="timezone offset.*ai_clone_utc"):
        adapt_daily_workspace_standups(rows=[], **common)
    with pytest.raises(ValueError, match="timezone offset.*ai_clone_utc"):
        adapt_daily_workspace_cycle_plans(rows=[], **common)
    with pytest.raises(ValueError, match="timezone offset.*ai_clone_utc"):
        adapt_daily_workspace_evaluations(evaluations=[], **common)
    with pytest.raises(ValueError, match="timezone offset.*ai_clone_utc"):
        run_portfolio_coordination(
            service=object(),
            portfolio_cycle_id=common["cycle_id"],
            cycle_date=common["cycle_date"],
            observed_at=naive,
            expected_workspaces=common["expected_workspaces"],
            readiness_id="readiness-naive-clock",
            standup_rows=[],
            system_health={},
        )


def test_coordinator_normalizes_offset_without_collapsing_observation_precision():
    observed_at = datetime(
        2026,
        8,
        26,
        8,
        30,
        15,
        123456,
        tzinfo=timezone(-timedelta(hours=4)),
    )

    assert coordinator._ai_clone_utc_observation(observed_at) == datetime(
        2026,
        8,
        26,
        12,
        30,
        15,
        123456,
        tzinfo=timezone.utc,
    )


def _bounded_goal(goal: dict) -> dict:
    return {
        key: copy.deepcopy(goal[key])
        for key in (
            "schema_version",
            "goal",
            "progress_signals",
            "phase_gate",
            "no_action_trigger",
        )
    }


def _feezie_evaluation(
    *,
    cycle_id: str,
    observed_at: str,
    status: str,
    goal: dict | None = None,
) -> dict:
    evaluation = {
        "workspace_key": "feezie-os",
        "standup_kind": "workspace_sync",
        "status": status,
        "promotion_suppressed": True,
        "cycle_id": cycle_id,
        "cycle_evaluation_only": True,
        "owner_decision_count": 0,
        "evaluation_schema_version": "workspace_cycle_evaluation/v1",
        "observed_at": observed_at,
        "meeting_held": False,
    }
    if goal is not None:
        evaluation["goal"] = _bounded_goal(goal)
    if status == "decision_record":
        evaluation.update(
            {
                "decision_record_schema_version": "standup_decision_record/v1",
                "decision_record_id": "standup-decision-0123456789abcdef01234567",
                "decision_record_owner_role": "jean_claude",
            }
        )
    return evaluation


def _ready_portfolio_service(tmp_path, *, cycle_id: str, observed_at: datetime):
    store = IntegratedSystemStore(tmp_path / f"{cycle_id.replace(':', '_')}.sqlite3")
    readiness = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id=cycle_id,
        retrieval_refresh=lambda: {
            "schema_version": "codex_memory_index/v1",
            "status": "ok",
            "files": 1,
            "last_sync_at": observed_at.isoformat(),
        },
        recall_search=lambda _query: [{"path": "memory"}],
        now=observed_at,
    )
    return store, PortfolioCycleService(store), readiness["readiness_id"]


def _blocked_goal_row(
    *,
    workspace_key: str,
    cycle_id: str,
    observed_at: str,
    goal: dict,
) -> dict:
    return {
        "id": f"standup:{workspace_key}",
        "workspace_key": workspace_key,
        "status": "completed",
        "created_at": observed_at,
        "payload": {
            "cycle_id": cycle_id,
            "observed_at": observed_at,
            "summary": "Goal-directed evaluation was blocked.",
            "strategy_context": {"goal_contract": goal},
            "recursion": {
                # This deliberately models the historical fail-open producer;
                # the daily adapter must still refuse healthy_no_change.
                "evaluated": True,
                "observed_at": observed_at,
                "no_action": {
                    "selected": True,
                    "reason": "No new action was selected.",
                    "future_trigger": "New evidence arrives.",
                },
            },
        },
    }


def _workspace_cycle_plan_row(
    *,
    cycle_id: str,
    observed_at: str,
    workspace_key: str = "fusion-os",
    recommendation_count: int = 1,
) -> dict:
    requests = [
        {
            "workspace_key": workspace_key,
            "scope": "workspace",
            "owner_agent": "jean-claude",
            "title": "Advance one bounded internal lane",
            "status": "todo",
            "reason": "The workspace cycle selected one safe internal handoff.",
            "payload": {},
        }
        for _ in range(recommendation_count)
    ]
    resolutions = [
        {
            "request_sha256": f"request-{index}",
            "card_id": f"pm-card-{index}",
            "state": "placed_in_execution_queue",
            "summary": "The existing PM authority accepted the bounded lane.",
        }
        for index in range(recommendation_count)
    ]
    return {
        "id": f"plan-{workspace_key}",
        "workspace_key": workspace_key,
        "status": "completed",
        "source": "standup_prep",
        "created_at": observed_at,
        "payload": {
            "record_kind": "workspace_cycle_plan",
            "meeting_held": False,
            "evaluation_only": True,
            "meeting_evidence_state": "synthetic_planning_only",
            "meeting_evidence_reason": "independent_agent_evidence_missing",
            "meeting_evidence": {},
            "participants": [],
            "planned_participants": ["Jean-Claude", "Fusion Operator"],
            "discussion": [
                {
                    "round": 1,
                    "speaker": "Jean-Claude",
                    "note": "A deterministic planning lens, not attendance.",
                    "provenance": "synthesized_role_lens",
                }
            ],
            "standup_kind": "workspace_sync",
            "cycle_id": cycle_id,
            "summary": "Fusion evaluated its goal and prior work.",
            "recommendations_authorized": True,
            "recommendation_authority_state": "existing_system_evaluation_authority",
            "pm_recommendation_count": recommendation_count,
            "recommendation_requests": requests,
            "recommendation_resolutions": resolutions,
            "recursion": {
                "evaluated": True,
                "observed_at": observed_at,
                "goal": _feezie_goal(),
                "changes_since_prior": [
                    {"summary": "One bounded internal lane became eligible."}
                ],
                "system_decisions": [
                    {"summary": "Route that lane through the existing PM authority."}
                ],
                "actions_since_prior": [
                    {"summary": "Queued the bounded internal lane."}
                ],
                "next_cycle_inputs": [
                    {"summary": "Consume the PM result or failure next cycle."}
                ],
            },
        },
    }


def test_adapter_rejects_generic_completed_rows_without_verified_meeting_evidence():
    cycle_id = "daily-2026-08-20@20260820T123000000000Z"
    rows = [
        {"id": "old", "workspace_key": "feezie-os", "status": "completed", "created_at": "2026-08-20T12:29:00Z", "payload": {"cycle_id": "daily-2026-08-19", "summary": "Yesterday", "recursion": {"observed_at": "2026-08-19T23:00:00Z"}}},
        {"id": "new", "workspace_key": "feezie-os", "status": "completed", "created_at": "2026-08-20T12:31:00Z", "payload": {"cycle_id": cycle_id, "summary": "Today", "standup_sections": {"blockers": ["One blocker"]}, "recursion": {"observed_at": "2026-08-20T12:30:00Z"}}},
        {"id": "prepared", "workspace_key": "agc", "status": "prepared", "created_at": "2026-08-20T12:00:00Z", "payload": {"summary": "Not complete"}},
    ]
    result = adapt_daily_workspace_standups(
        rows,
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 20),
        observed_at=datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc),
        expected_workspaces=["feezie-os", "agc"],
    )
    assert result == {}


def test_adapter_rejects_explicit_meeting_with_invalid_evidence():
    cycle_id = "daily-2026-08-26@20260826T123000000000Z"
    row = {
        "id": "invalid-meeting",
        "workspace_key": "fusion-os",
        "status": "completed",
        "source": "standup_prep",
        "payload": {
            "record_kind": "standup",
            "meeting_held": True,
            "evaluation_only": False,
            "standup_kind": "workspace_sync",
            "cycle_id": cycle_id,
            "observed_at": "2026-08-26T12:30:00Z",
            "participants": ["Jean-Claude", "Fusion Operator"],
            "meeting_evidence": {
                "schema_version": "standup_meeting_evidence/v1",
                "meeting_id": "forged-meeting",
                "participant_report_run_ids": [],
            },
        },
    }

    assert adapt_daily_workspace_standups(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    ) == {}


def test_feezie_adapter_validates_effective_roster_without_turning_closer_into_lens(
    monkeypatch,
):
    observed_at = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)
    observed_text = "2026-08-26T12:30:00Z"
    cycle_id = "daily-2026-08-26@20260826T123000000000Z"
    relevance = build_standup_relevance_plan(
        [
            {
                "workspace_key": "feezie-os",
                "title": "Resolve the owner boundary and long-term positioning tradeoff.",
                "source_ids": ["bounded-agenda-1"],
                "observed_at": observed_text,
                "tags": [
                    "owner_intent_or_approval",
                    "strategy_or_positioning",
                ],
            }
        ],
        now=observed_at,
    )
    assert relevance["selected_roles"] == ["neo", "yoda"]
    assert [
        item["display_name"] for item in relevance["participant_plan"]
    ] == ["Neo", "Yoda"]

    captured: dict[str, object] = {}

    def verified(_payload, **kwargs):
        captured["expected_participants"] = kwargs["expected_participants"]
        return True

    monkeypatch.setattr(coordinator, "is_verified_meeting_record", verified)
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(_feezie_goal())},
    )
    row = {
        "id": "feezie-neo-yoda-with-jean-claude-close",
        "workspace_key": "feezie-os",
        "status": "completed",
        "source": "independent_agent_meeting_worker",
        "payload": {
            "record_kind": "standup",
            "meeting_held": True,
            "evaluation_only": False,
            "standup_kind": "workspace_sync",
            "cycle_id": cycle_id,
            "observed_at": observed_text,
            "clock": {
                "schema_version": "ai_clone_clock/v1",
                "authority": "ai_clone_utc",
                "timezone": "UTC",
                "observed_at": observed_text,
            },
            "participants": ["Jean-Claude", "Neo", "Yoda"],
            "standup_relevance": relevance,
            "summary": "Neo and Yoda reported; Jean-Claude closed the exact proposal.",
            "recommendations_authorized": True,
            "recommendation_authority_state": "ratified_by_canonical_closer",
            "recursion": {"evaluated": True, "observed_at": observed_text},
        },
    }

    adapted = adapt_daily_workspace_standups(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
    )

    assert list(adapted) == ["feezie-os"]
    assert captured["expected_participants"] == ["Jean-Claude", "Neo", "Yoda"]
    assert relevance["selected_roles"] == ["neo", "yoda"]


def test_real_standup_adapter_rejects_wrong_authority_and_conflicting_observations(
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T123000000000Z"
    observed_at = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(
        coordinator,
        "is_verified_meeting_record",
        lambda *_args, **_kwargs: True,
    )
    base = {
        "id": "clock-invalid-meeting",
        "workspace_key": "fusion-os",
        "status": "completed",
        "source": "independent_agent_meeting_worker",
        "payload": {
            "record_kind": "standup",
            "meeting_held": True,
            "evaluation_only": False,
            "standup_kind": "workspace_sync",
            "cycle_id": cycle_id,
            "summary": "A meeting whose semantic clock must fail closed.",
            "recommendations_authorized": True,
            "recommendation_authority_state": "ratified_by_canonical_closer",
            "recursion": {
                "evaluated": True,
                "observed_at": "2026-08-26T12:30:00Z",
            },
        },
    }
    wrong_authority = copy.deepcopy(base)
    wrong_authority["payload"]["recursion"]["clock"] = {
        "authority": "host_local_time",
        "observed_at": "2026-08-26T12:30:00Z",
    }
    conflicting = copy.deepcopy(base)
    conflicting["payload"]["observed_at"] = "2026-08-26T12:29:59Z"

    for row in (wrong_authority, conflicting):
        assert adapt_daily_workspace_standups(
            [row],
            cycle_id=cycle_id,
            cycle_date=date(2026, 8, 26),
            observed_at=observed_at,
            expected_workspaces=["fusion-os"],
        ) == {}


def test_adapter_does_not_stamp_a_fresh_prior_receipt_as_current_cycle_work():
    rows = [
        {"id": "prior", "workspace_key": "agc", "status": "completed", "created_at": "2026-08-19T12:00:00Z", "payload": {"summary": "Stable workspace state."}},
        {"id": "stale", "workspace_key": "feezie-os", "status": "completed", "created_at": "2026-08-15T12:00:00Z", "payload": {"summary": "Too old."}},
    ]
    result = adapt_daily_workspace_standups(
        rows,
        cycle_id="daily-2026-08-20@20260820T123000000000Z",
        cycle_date=date(2026, 8, 20),
        observed_at=datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc),
        expected_workspaces=["agc", "feezie-os"],
    )
    assert result == {}


def test_coordinator_degrades_when_any_expected_daily_conclusion_is_missing(tmp_path):
    store = IntegratedSystemStore(tmp_path / "system.sqlite3")
    cycle_id = "daily-2026-08-20"
    readiness = IntegratedMemoryReadinessService(store).run_readiness(cycle_id=cycle_id, retrieval_refresh=lambda: {"schema_version": "codex_memory_index/v1", "status": "ok", "files": 1, "last_sync_at": "2026-08-20T12:30:00+00:00"}, recall_search=lambda _query: [{"path": "memory"}], now=datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc))
    ops = run_portfolio_coordination(
        service=PortfolioCycleService(store), portfolio_cycle_id=cycle_id, cycle_date=date(2026, 8, 20),
        observed_at=datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc),
        expected_workspaces=["feezie-os", "agc"], readiness_id=readiness["readiness_id"],
        standup_rows=[{"id": "s", "workspace_key": "feezie-os", "status": "completed", "created_at": "2026-08-20T12:31:00Z", "payload": {"cycle_id": cycle_id, "summary": "Done", "recursion": {"observed_at": "2026-08-20T12:30:00Z"}}}],
        system_health={"api": "healthy"},
    )
    assert ops["status"] == "degraded"
    assert "agc" in ops["degraded_system_warnings"][0]
    assert ops["workspace_updates"][0]["state"] == "missing"


def test_adapter_rejects_prior_receipts_even_when_database_age_would_be_fresh():
    rows = [
        {
            "id": "within-72-hours",
            "workspace_key": "agc",
            "status": "completed",
            "created_at": "2026-08-21T22:51:46Z",
            "payload": {"summary": "Still inside the exact freshness window."},
        },
        {
            "id": "outside-72-hours",
            "workspace_key": "feezie-os",
            "status": "completed",
            "created_at": "2026-08-21T09:00:00Z",
            "payload": {"summary": "Actually stale at cycle execution."},
        },
    ]

    result = adapt_daily_workspace_standups(
        rows,
        cycle_id="daily-2026-08-24@20260824T101500000000Z",
        cycle_date=date(2026, 8, 24),
        observed_at=datetime(2026, 8, 24, 10, 15, tzinfo=timezone.utc),
        expected_workspaces=["agc", "feezie-os"],
    )

    assert result == {}


def test_adapter_preserves_verified_meeting_recursion_and_uses_local_goal_authority(
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T181000000000Z"
    canonical_goal = {
        **_feezie_goal(),
        "goal": "Advance the canonical local Fusion goal.",
        "no_action_trigger": "A new canonical Fusion signal arrives.",
    }
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(canonical_goal)},
    )
    monkeypatch.setattr(
        coordinator,
        "is_verified_meeting_record",
        lambda *_args, **_kwargs: True,
    )
    rows = [
        {
            "id": "recursive-standup",
            "workspace_key": "fusion-os",
            "status": "completed",
            "created_at": "2026-08-26T18:05:00Z",
            "payload": {
                "record_kind": "standup",
                "meeting_held": True,
                "evaluation_only": False,
                "standup_kind": "workspace_sync",
                "cycle_id": cycle_id,
                "summary": "Fusion evaluated its goal and prior commitment.",
                "recommendations_authorized": True,
                "recommendation_authority_state": "ratified_by_canonical_closer",
                "recommendation_resolutions": [
                    {
                        "request_sha256": "a" * 64,
                        "card_id": "ratified-owner-card",
                        "state": "bounded_owner_decision",
                    }
                ],
                "strategy_context": {
                    "goal_contract": {
                        "schema_version": "workspace_goal_contract/v1",
                        "goal": "Advance Signal -> Narrative -> Trust from verified evidence.",
                        "progress_signals": ["One verified institutional narrative advances."],
                        "phase_gate": "Signal -> Narrative -> Trust",
                        "no_action_trigger": "A new verified Fusion signal arrives.",
                    }
                },
                "standup_sections": {"next_focus": ["This remains a proposal, not performed work."]},
                "recursion": {
                    "evaluated": True,
                    "observed_at": "2026-08-26T18:10:00Z",
                    "actions_since_prior": [{"summary": "Dispatched the bounded internal review.", "effective_state": "in_progress"}],
                    "current_cycle_completed_work": [{"summary": "Verified one review receipt.", "result_id": "result-1"}],
                    "failed": [{"summary": "A prior packet failed.", "retryable": True}],
                    "carried": [{"summary": "The review remains queued.", "effective_state": "queued"}],
                    "owner_required": [{"summary": "Choose the external narrative fork.", "state": "open"}],
                    "system_decisions": [{"summary": "Carry the existing internal review."}],
                    "changes_since_prior": [{"summary": "One prior commitment completed."}],
                    "reference_only": [
                        {"summary": "Prior roadmap, retained as static context only."}
                    ],
                    "no_action": {
                        "selected": False,
                        "reason": "Material work was recorded.",
                        "future_trigger": "The queued review completes.",
                    },
                    "next_cycle_inputs": [{"summary": "Consume result-1."}],
                },
            },
        }
    ]

    result = adapt_daily_workspace_standups(
        rows,
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 18, 10, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    )["fusion-os"]

    assert result["actions_taken"][0]["summary"].startswith("Dispatched")
    assert result["completed_work"][0]["result_id"] == "result-1"
    assert result["failed_work"][0]["retryable"] is True
    assert result["carried_forward"][0]["effective_state"] == "queued"
    assert result["work_underway"][0]["effective_state"] == "queued"
    assert result["owner_decisions"][0]["state"] == "open"
    assert result["recommendation_resolutions"] == [
        {
            "request_sha256": "a" * 64,
            "card_id": "ratified-owner-card",
            "state": "bounded_owner_decision",
        }
    ]
    assert result["no_action"] == []
    assert result["_conclusion_kind"] == "conclusion"
    assert result["goal"] == canonical_goal
    assert result["goal"]["goal"] != rows[0]["payload"]["strategy_context"]["goal_contract"]["goal"]
    assert "This remains a proposal" not in str(result["work_underway"])
    assert result["recommended_next_actions"] == [
        "This remains a proposal, not performed work."
    ]
    assert result["reference_only"] == [
        {"summary": "Prior roadmap, retained as static context only."}
    ]
    assert "This remains a proposal" not in str(result["actions_taken"])


def test_closer_withhold_suppresses_proposed_decisions_in_ops_projection(
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T182000000000Z"
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(_feezie_goal())},
    )
    monkeypatch.setattr(
        coordinator,
        "is_verified_meeting_record",
        lambda *_args, **_kwargs: True,
    )
    row = {
        "id": "withheld-real-standup",
        "workspace_key": "fusion-os",
        "status": "completed",
        "source": "standup_prep",
        "payload": {
            "record_kind": "standup",
            "meeting_held": True,
            "evaluation_only": False,
            "standup_kind": "workspace_sync",
            "cycle_id": cycle_id,
            "summary": "The closer withheld the pending proposal.",
            "recommendations_authorized": False,
            "recommendation_authority_state": "withheld_by_canonical_closer",
            "recommendation_resolutions": [
                {
                    "card_id": "unratified-owner-card",
                    "state": "bounded_owner_decision",
                }
            ],
            "meeting_ratification": {
                "ratification_reason": "The signed evidence does not support dispatching this exact proposal.",
                "next_step_or_trigger": "A revised proposal receives an exact canonical ratification.",
            },
            "standup_sections": {
                "next_focus": ["Dispatch the unratified packet."],
                "recommended_next_actions": ["Treat the proposal as decided."],
            },
            "continuity": {"changes": [{"summary": "One source fact changed."}]},
            "recursion": {
                "evaluated": True,
                "observed_at": "2026-08-26T18:20:00Z",
                "system_decisions": [{"summary": "Dispatch the unratified packet."}],
                "decisions": [{"summary": "Treat the proposal as decided."}],
                "owner_required": [
                    {
                        "card_id": "unratified-owner-card",
                        "summary": "Choose the unratified owner fork.",
                        "state": "open",
                    }
                ],
                "recommendation_resolutions": [
                    {
                        "card_id": "unratified-recursion-card",
                        "state": "bounded_owner_decision",
                    }
                ],
                "actions_since_prior": [{"summary": "Verified an earlier action receipt."}],
                "completed_work": [{"summary": "The earlier internal review completed."}],
                "next_cycle_inputs": [{"summary": "Consume a result that was never dispatched."}],
            },
        },
    }

    adapted = adapt_daily_workspace_standups(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 18, 20, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    )["fusion-os"]

    assert adapted["recommendations_authorized"] is False
    assert adapted["system_decisions"] == []
    assert adapted["decisions"] == []
    assert adapted["owner_decisions"] == []
    assert adapted["recommendation_resolutions"] == []
    assert adapted["recommended_next_actions"] == []
    assert adapted["actions_taken"] == [
        {"summary": "Verified an earlier action receipt."}
    ]
    assert adapted["completed_work"] == [
        {"summary": "The earlier internal review completed."}
    ]
    assert adapted["changes_since_prior"] == [
        {"summary": "One source fact changed."}
    ]
    assert adapted["blockers"][-1] == {
        "kind": "recommendation_authority_withheld",
        "reason_code": "withheld_by_canonical_closer",
        "summary": "The signed evidence does not support dispatching this exact proposal.",
        "future_trigger": "A revised proposal receives an exact canonical ratification.",
    }
    assert adapted["next_cycle_inputs"] == [
        {
            "summary": "The signed evidence does not support dispatching this exact proposal.",
            "trigger": "A revised proposal receives an exact canonical ratification.",
            "reason_code": "withheld_by_canonical_closer",
        }
    ]


def test_failed_due_meeting_plan_cannot_project_pre_meeting_decisions():
    cycle_id = "daily-2026-08-26@20260826T182500000000Z"
    row = _workspace_cycle_plan_row(
        cycle_id=cycle_id,
        observed_at="2026-08-26T18:25:00Z",
        recommendation_count=0,
    )
    payload = row["payload"]
    payload["recommendations_authorized"] = False
    payload["recommendation_authority_state"] = (
        "withheld_pending_verified_due_meeting"
    )
    payload["standup_sections"] = {
        "next_focus": ["Dispatch the pre-meeting packet."],
    }
    payload["recursion"].update(
        {
            "system_decisions": [{"summary": "Dispatch the pre-meeting packet."}],
            "decisions": [{"summary": "Record the packet as decided."}],
            "meeting_attempt": {
                "attempted": True,
                "status": "failed",
                "reason": "participant_receipt_unavailable",
                "future_trigger": "A complete independently receipted due meeting.",
                # A contradictory nested caller value is evidence only and
                # cannot override the server-owned top-level authority.
                "recommendations_authorized": True,
            },
        }
    )

    adapted = adapt_daily_workspace_cycle_plans(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 18, 25, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    )["fusion-os"]

    assert adapted["recommendations_authorized"] is False
    assert adapted["system_decisions"] == []
    assert adapted["decisions"] == []
    assert adapted["recommended_next_actions"] == []
    assert adapted["recommendation_resolutions"] == []
    assert adapted["blockers"][-1]["reason_code"] == (
        "withheld_pending_verified_due_meeting"
    )
    assert adapted["blockers"][-1]["summary"] == "participant_receipt_unavailable"
    assert adapted["next_cycle_inputs"][0]["trigger"] == (
        "A complete independently receipted due meeting."
    )


def test_adapter_keeps_two_verified_same_day_meetings_isolated_from_write_order(
    monkeypatch,
):
    first_cycle = "daily-2026-08-26@20260826T120000000000Z"
    second_cycle = "daily-2026-08-26@20260826T130000000000Z"
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(_feezie_goal())},
    )
    monkeypatch.setattr(
        coordinator,
        "is_verified_meeting_record",
        lambda *_args, **_kwargs: True,
    )
    rows = [
        {
            "id": "cycle-two-written-first",
            "workspace_key": "fusion-os",
            "status": "completed",
            "created_at": "2026-08-26T11:00:00Z",
                "payload": {"record_kind": "standup", "meeting_held": True, "evaluation_only": False, "standup_kind": "workspace_sync", "cycle_id": second_cycle, "summary": "Second cycle", "recursion": {"observed_at": "2026-08-26T13:00:00Z"}},
        },
        {
            "id": "cycle-one-written-later",
            "workspace_key": "fusion-os",
            "status": "completed",
            "created_at": "2026-08-26T14:00:00Z",
                "payload": {"record_kind": "standup", "meeting_held": True, "evaluation_only": False, "standup_kind": "workspace_sync", "cycle_id": first_cycle, "summary": "First cycle", "recursion": {"observed_at": "2026-08-26T12:00:00Z"}},
        },
    ]

    first = adapt_daily_workspace_standups(
        rows,
        cycle_id=first_cycle,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    )
    second = adapt_daily_workspace_standups(
        rows,
        cycle_id=second_cycle,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 13, 0, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    )

    assert first["fusion-os"]["summary"] == "First cycle"
    assert first["fusion-os"]["observed_at"] == "2026-08-26T12:00:00+00:00"
    assert second["fusion-os"]["summary"] == "Second cycle"
    assert second["fusion-os"]["observed_at"] == "2026-08-26T13:00:00+00:00"


def test_adapter_never_admits_a_source_observation_after_requested_observation():
    cycle_id = "daily-2026-08-26@20260826T120000000000Z"
    rows = [
        {
            "id": "future-source-row",
            "workspace_key": "agc",
            "status": "completed",
            "created_at": "2026-08-26T11:00:00Z",
            "payload": {"cycle_id": cycle_id, "summary": "Future", "recursion": {"observed_at": "2026-08-26T12:45:00Z"}},
        }
    ]

    assert adapt_daily_workspace_standups(
        rows,
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc),
        expected_workspaces=["agc"],
    ) == {}


def test_missing_or_invalid_local_goal_never_becomes_healthy_no_change_and_degrades_ops(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T190000000000Z"
    observed_at = datetime(2026, 8, 26, 19, 0, tzinfo=timezone.utc)
    observed_text = "2026-08-26T19:00:00Z"
    rows = [
        _blocked_goal_row(
            workspace_key="agc",
            cycle_id=cycle_id,
            observed_at=observed_text,
            goal={},
        ),
        _blocked_goal_row(
            workspace_key="fusion-os",
            cycle_id=cycle_id,
            observed_at=observed_text,
            goal={
                "schema_version": "workspace_goal_contract/v1",
                "goal": "This incomplete contract is invalid.",
            },
        ),
    ]
    invalid_goals = {
        "agc": {},
        "fusion-os": {
            "schema_version": "workspace_goal_contract/v1",
            "goal": "This incomplete local contract is invalid.",
        },
    }
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda workspace_key: {
            "goal_contract": copy.deepcopy(invalid_goals[workspace_key])
        },
    )
    monkeypatch.setattr(
        coordinator,
        "is_verified_meeting_record",
        lambda *_args, **_kwargs: True,
    )

    adapted = adapt_daily_workspace_standups(
        rows,
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["agc", "fusion-os"],
    )

    assert {item["_conclusion_kind"] for item in adapted.values()} == {"conclusion"}
    assert all(
        item["blockers"][-1]["reason_code"] == "workspace_goal_authority_blocked"
        and item["blockers"][-1]["reason"]
        and item["blockers"][-1]["future_trigger"]
        for item in adapted.values()
    )

    store = IntegratedSystemStore(tmp_path / "goal-authority.sqlite3")
    readiness = IntegratedMemoryReadinessService(store).run_readiness(
        cycle_id=cycle_id,
        retrieval_refresh=lambda: {
            "schema_version": "codex_memory_index/v1",
            "status": "ok",
            "files": 1,
            "last_sync_at": observed_at.isoformat(),
        },
        recall_search=lambda _query: [{"path": "memory"}],
        now=observed_at,
    )
    ops = run_portfolio_coordination(
        service=PortfolioCycleService(store),
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["agc", "fusion-os"],
        readiness_id=readiness["readiness_id"],
        standup_rows=rows,
        system_health={"api": "healthy"},
    )
    assert ops["status"] == "degraded"
    assert ops["degraded_system_warnings"] == [
        "Workspace goal authority is unavailable or invalid: agc, fusion-os."
    ]


def test_feezie_compatibility_decision_record_cannot_become_a_conclusion(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T200000482752Z"
    observed_at = datetime(
        2026, 8, 26, 20, 0, 0, 482752, tzinfo=timezone.utc
    )
    goal = _feezie_goal()
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(goal)},
    )
    store, service, readiness_id = _ready_portfolio_service(
        tmp_path,
        cycle_id=cycle_id,
        observed_at=observed_at,
    )
    evaluation = _feezie_evaluation(
        cycle_id=cycle_id,
        observed_at="2026-08-26T20:00:00Z",
        status="decision_record",
    )

    assert adapt_daily_workspace_evaluations(
        [evaluation],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
    ) == {}

    result = run_portfolio_coordination(
        service=service,
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
        readiness_id=readiness_id,
        standup_rows=[],
        system_health={"api": "healthy"},
        workspace_cycle_evaluations=[evaluation],
    )

    assert result["status"] == "degraded"
    assert result["workspace_updates"] == [
        {
            "workspace_key": "feezie-os",
            "state": "missing",
            "summary": "No conclusion receipt received.",
        }
    ]
    with store.connection() as connection:
        conclusion_count = connection.execute(
            "SELECT COUNT(*) FROM workspace_conclusions WHERE portfolio_cycle_id=?",
            (cycle_id,),
        ).fetchone()[0]
    assert conclusion_count == 0


def test_signed_async_role_plan_is_consumed_with_action_decision_and_terminal_outcome(
    monkeypatch,
):
    cycle_id = "daily-2026-08-27@20260827T200000482752Z"
    observed_at = datetime(
        2026, 8, 27, 20, 0, 0, 482752, tzinfo=timezone.utc
    )
    goal = _feezie_goal()
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(goal)},
    )
    relevance = build_standup_relevance_plan(
        [
            {
                "id": "neo-only-boundary",
                "workspace_key": "feezie-os",
                "title": "Resolve one bounded owner boundary",
                "source_ids": ["bounded-source-1"],
                "observed_at": observed_at,
                "tags": ["owner_intent_or_approval"],
            }
        ],
        now=observed_at,
    )
    contribution_id = "2c54697e-ddbe-5ea8-a38c-acde2c1f6b02"
    run_id = "9d42eea7-c9b2-5a48-a2bb-6886775a9c5a"
    card_id = "0be8b860-f50d-5cb4-93e9-04d0b3c253fe"
    rows = [
        {
            "id": "e532fa73-8fd0-5ad1-9a0d-d0013597014a",
            "workspace_key": "feezie-os",
            "status": "completed",
            "source": "standup_prep",
            "payload": {
                "record_kind": "workspace_cycle_plan",
                "standup_kind": "workspace_sync",
                "cycle_id": cycle_id,
                "observed_at": "2026-08-27T20:00:00.482752Z",
                "clock": {
                    "schema_version": "ai_clone_clock/v1",
                    "authority": "ai_clone_utc",
                    "timezone": "UTC",
                    "observed_at": "2026-08-27T20:00:00.482752Z",
                },
                "summary": "One signed Neo input entered the existing PM authority.",
                "meeting_held": False,
                "evaluation_only": True,
                "meeting_evidence_state": "verified_signed_async_role_contribution",
                "meeting_evidence_reason": "signed_async_role_contribution_verified",
                "meeting_evidence": {},
                "participants": [],
                "planned_participants": ["Neo"],
                "discussion": [],
                "standup_relevance": relevance,
                "recommendations_authorized": True,
                "recommendation_authority_state": (
                    "existing_system_evaluation_authority_after_signed_async_role_input"
                ),
                "pm_recommendation_count": 1,
                "recommendation_requests": [{"title": "Prepare checklist"}],
                "recommendation_resolutions": [
                    {
                        "request_sha256": "a" * 64,
                        "card_id": card_id,
                        "state": "placed_in_execution_queue",
                    }
                ],
                "recursion": {
                    "cycle_id": cycle_id,
                    "observed_at": "2026-08-27T20:00:00.482752Z",
                    "clock": {
                        "schema_version": "ai_clone_clock/v1",
                        "authority": "ai_clone_utc",
                        "timezone": "UTC",
                        "observed_at": "2026-08-27T20:00:00.482752Z",
                    },
                    "evaluated": True,
                    "async_role_contribution": {
                        "schema_version": "standup_async_role_evidence/v1",
                        "contribution_id": contribution_id,
                        "participant_report_run_id": run_id,
                        "display_name": "Neo",
                        "meeting_held": False,
                        "canonical_pm_execution_authority": "Jean-Claude",
                        "pm_execution_authority_transferred": False,
                    },
                    "actions_taken": [
                        {
                            "kind": "verified_async_role_contribution",
                            "contribution_id": contribution_id,
                        }
                    ],
                    "system_decisions": [
                        {
                            "kind": "admit_signed_async_role_input",
                            "contribution_id": contribution_id,
                        }
                    ],
                    "next_cycle_inputs": [
                        {
                            "kind": "async_role_recommendation_outcomes",
                            "summary": "Consume the terminal PM outcome next cycle.",
                        }
                    ],
                    "recommendation_resolutions": [
                        {
                            "request_sha256": "a" * 64,
                            "card_id": card_id,
                            "state": "placed_in_execution_queue",
                        }
                    ],
                },
            },
        }
    ]

    adapted = adapt_daily_workspace_cycle_plans(
        rows,
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 27),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
    )

    assert list(adapted) == ["feezie-os"]
    conclusion = adapted["feezie-os"]
    assert conclusion["summary"].startswith(
        "Workspace async role contribution (no meeting held):"
    )
    assert conclusion["actions_taken"] == [
        {
            "kind": "verified_async_role_contribution",
            "contribution_id": contribution_id,
        }
    ]
    assert conclusion["system_decisions"] == [
        {
            "kind": "admit_signed_async_role_input",
            "contribution_id": contribution_id,
        }
    ]
    assert conclusion["recommendation_resolutions"][0]["state"] == (
        "placed_in_execution_queue"
    )
    assert conclusion["next_cycle_inputs"] == [
        {
            "kind": "async_role_recommendation_outcomes",
            "summary": "Consume the terminal PM outcome next cycle.",
        }
    ]
    assert conclusion["evidence_links"] == [
        {
            "ref": "coordination-record:e532fa73-8fd0-5ad1-9a0d-d0013597014a",
            "source_observed_at": "2026-08-27T20:00:00.482752+00:00",
        },
        {
            "ref": f"automation-run:{run_id}",
            "source_observed_at": "2026-08-27T20:00:00.482752+00:00",
        },
    ]


def test_feezie_collapse_becomes_healthy_no_change_with_exact_goal_trigger(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T203000000000Z"
    observed_at = datetime(2026, 8, 26, 20, 30, tzinfo=timezone.utc)
    goal = _feezie_goal()
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(goal)},
    )
    store, service, readiness_id = _ready_portfolio_service(
        tmp_path,
        cycle_id=cycle_id,
        observed_at=observed_at,
    )

    ops = run_portfolio_coordination(
        service=service,
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
        readiness_id=readiness_id,
        standup_rows=[],
        system_health={"api": "healthy"},
        workspace_cycle_evaluations=[
            _feezie_evaluation(
                cycle_id=cycle_id,
                observed_at="2026-08-26T20:30:00Z",
                status="collapse_freshness",
            )
        ],
    )

    assert ops["status"] == "complete"
    assert ops["workspace_updates"][0]["state"] == "healthy_no_change"
    with store.connection() as connection:
        row = connection.execute(
            "SELECT * FROM workspace_conclusions WHERE portfolio_cycle_id=? AND workspace_key='feezie-os'",
            (cycle_id,),
        ).fetchone()
    payload = json.loads(row["payload_json"])
    assert payload["goal"] == goal
    assert payload["actions_taken"] == []
    assert payload["decisions"] == []
    assert payload["no_action"] == [
        {
            "route": "ops",
            "selected": True,
            "summary": "No changed eligible FEEZIE input required a meeting or internal work.",
            "trigger": goal["no_action_trigger"],
        }
    ]


def test_feezie_cycle_evaluation_missing_or_malformed_fails_closed(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T210000000000Z"
    observed_at = datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc)
    goal = _feezie_goal()
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(goal)},
    )
    valid = _feezie_evaluation(
        cycle_id=cycle_id,
        observed_at="2026-08-26T21:00:00Z",
        status="decision_record",
    )
    malformed: list[list[dict]] = []
    for key, value in (
        ("cycle_id", "wrong-cycle"),
        ("observed_at", "2026-08-26T21:00:00"),
        ("meeting_held", True),
        ("decision_record_id", "forged-record"),
    ):
        item = copy.deepcopy(valid)
        item[key] = value
        malformed.append([item])
    leaked_goal = copy.deepcopy(valid)
    leaked_goal["goal"] = _bounded_goal(goal)
    malformed.append([leaked_goal])
    malformed.append([copy.deepcopy(valid), copy.deepcopy(valid)])

    for evaluations in [[], *malformed]:
        assert adapt_daily_workspace_evaluations(
            evaluations,
            cycle_id=cycle_id,
            cycle_date=date(2026, 8, 26),
            observed_at=observed_at,
            expected_workspaces=["feezie-os"],
        ) == {}

    store, service, readiness_id = _ready_portfolio_service(
        tmp_path,
        cycle_id=cycle_id,
        observed_at=observed_at,
    )
    ops = run_portfolio_coordination(
        service=service,
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["feezie-os"],
        readiness_id=readiness_id,
        standup_rows=[],
        system_health={"api": "healthy"},
        workspace_cycle_evaluations=[],
    )
    assert ops["status"] == "degraded"
    assert ops["workspace_updates"] == [
        {
            "workspace_key": "feezie-os",
            "state": "missing",
            "summary": "No conclusion receipt received.",
        }
    ]


def test_non_meeting_evaluation_row_never_enters_standup_adapter():
    cycle_id = "daily-2026-08-26@20260826T213000000000Z"
    assert adapt_daily_workspace_standups(
        [
            {
                "id": "not-a-meeting",
                "workspace_key": "feezie-os",
                "status": "completed",
                "payload": {
                    "cycle_id": cycle_id,
                    "observed_at": "2026-08-26T21:30:00Z",
                    "evaluation_only": True,
                    "meeting_held": False,
                    "summary": "This is an evaluation, not a standup.",
                },
            }
        ],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 21, 30, tzinfo=timezone.utc),
        expected_workspaces=["feezie-os"],
    ) == {}


def test_workspace_cycle_plan_advances_ops_without_becoming_a_standup(
    tmp_path,
    monkeypatch,
):
    cycle_id = "daily-2026-08-26@20260826T220000000000Z"
    observed_at = datetime(2026, 8, 26, 22, 0, tzinfo=timezone.utc)
    synthetic_goal = {
        **_feezie_goal(),
        "goal": "Advance the bounded synthetic Fusion fixture from verified evidence.",
        "no_action_trigger": "A new verified synthetic Fusion signal arrives.",
    }
    monkeypatch.setattr(
        coordinator,
        "workspace_registry_entry",
        lambda _workspace_key: {"goal_contract": copy.deepcopy(synthetic_goal)},
    )
    row = _workspace_cycle_plan_row(
        cycle_id=cycle_id,
        observed_at="2026-08-26T22:00:00Z",
    )

    assert adapt_daily_workspace_standups(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["fusion-os"],
    ) == {}

    adapted = adapt_daily_workspace_cycle_plans(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["fusion-os"],
    )["fusion-os"]
    assert adapted["summary"].startswith("Workspace cycle plan (no meeting held):")
    assert adapted["actions_taken"] == [
        {"summary": "Queued the bounded internal lane."}
    ]
    assert adapted["recommendation_resolutions"][0]["card_id"] == "pm-card-0"
    assert adapted["evidence_links"] == [
        {
            "ref": "coordination-record:plan-fusion-os",
            "source_observed_at": "2026-08-26T22:00:00+00:00",
        }
    ]
    assert "participants" not in adapted
    assert "discussion" not in adapted

    store, service, readiness_id = _ready_portfolio_service(
        tmp_path,
        cycle_id=cycle_id,
        observed_at=observed_at,
    )
    first = run_portfolio_coordination(
        service=service,
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["fusion-os"],
        readiness_id=readiness_id,
        standup_rows=[row],
        system_health={"api": "healthy"},
    )
    replay = run_portfolio_coordination(
        service=service,
        portfolio_cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=observed_at,
        expected_workspaces=["fusion-os"],
        readiness_id=readiness_id,
        standup_rows=[row],
        system_health={"api": "healthy"},
    )

    assert first["status"] == "complete"
    assert replay["ops_conclusion_id"] == first["ops_conclusion_id"]
    assert first["workspace_updates"] == [
        {
            "workspace_key": "fusion-os",
            "state": "conclusion",
            "summary": (
                "Workspace cycle plan (no meeting held): Fusion evaluated its goal "
                "and prior work."
            ),
            "provenance_kind": "deterministic_policy",
        }
    ]
    with store.connection() as connection:
        conclusion = connection.execute(
            "SELECT payload_json FROM workspace_conclusions WHERE portfolio_cycle_id=?",
            (cycle_id,),
        ).fetchone()
        event_count = connection.execute(
            "SELECT COUNT(*) FROM system_events WHERE event_type='workspace.concluded'",
        ).fetchone()[0]
    stored = json.loads(conclusion["payload_json"])
    assert stored["evidence_links"][0]["ref"] == "coordination-record:plan-fusion-os"
    assert not stored["evidence_links"][0]["ref"].startswith("standup:")
    assert event_count == 1


def test_workspace_cycle_plan_fails_closed_on_meeting_claim_or_incomplete_handoff():
    cycle_id = "daily-2026-08-26@20260826T223000000000Z"
    observed_at = datetime(2026, 8, 26, 22, 30, tzinfo=timezone.utc)
    valid = _workspace_cycle_plan_row(
        cycle_id=cycle_id,
        observed_at="2026-08-26T22:30:00Z",
    )
    malformed = []
    for field, value in (
        ("record_kind", "standup"),
        ("meeting_held", True),
        ("evaluation_only", False),
        ("meeting_evidence_state", "verified_independent_agent_meeting"),
        ("participants", ["Jean-Claude"]),
        ("meeting_evidence", {"schema_version": "forged"}),
        ("recommendation_resolutions", []),
    ):
        row = copy.deepcopy(valid)
        row["payload"][field] = value
        malformed.append(row)
    non_synthetic_round = copy.deepcopy(valid)
    non_synthetic_round["payload"]["discussion"][0]["provenance"] = "independent_agent"
    malformed.append(non_synthetic_round)
    naive_clock = copy.deepcopy(valid)
    naive_clock["payload"]["recursion"]["observed_at"] = "2026-08-26T22:30:00"
    malformed.append(naive_clock)
    wrong_authority = copy.deepcopy(valid)
    wrong_authority["payload"]["recursion"]["clock"] = {
        "authority": "host_local_time",
        "observed_at": "2026-08-26T22:30:00Z",
    }
    malformed.append(wrong_authority)
    conflicting_clock = copy.deepcopy(valid)
    conflicting_clock["payload"]["observed_at"] = "2026-08-26T22:29:59Z"
    malformed.append(conflicting_clock)

    for row in malformed:
        assert adapt_daily_workspace_cycle_plans(
            [row],
            cycle_id=cycle_id,
            cycle_date=date(2026, 8, 26),
            observed_at=observed_at,
            expected_workspaces=["fusion-os"],
        ) == {}


def test_historical_synthesized_prep_record_cannot_reenter_real_standup_adapter():
    cycle_id = "daily-2026-08-26@20260826T230000000000Z"
    row = {
        "id": "historical-synthetic",
        "workspace_key": "fusion-os",
        "status": "completed",
        "source": "standup_prep",
        "payload": {
            "cycle_id": cycle_id,
            "summary": "Historical meeting-shaped planning record.",
            "discussion": [
                {
                    "speaker": "Jean-Claude",
                    "note": "Generated lens.",
                    "provenance": "synthesized_role_lens",
                }
            ],
            "recursion": {"observed_at": "2026-08-26T23:00:00Z"},
        },
    }

    assert adapt_daily_workspace_standups(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 23, 0, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    ) == {}
    assert adapt_daily_workspace_cycle_plans(
        [row],
        cycle_id=cycle_id,
        cycle_date=date(2026, 8, 26),
        observed_at=datetime(2026, 8, 26, 23, 0, tzinfo=timezone.utc),
        expected_workspaces=["fusion-os"],
    ) == {}
