from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.standups import StandupCreate, StandupEntry, StandupUpdate
from app.routes import standups as standup_routes
from app.services import standup_service


NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
CYCLE_ID = "daily-2026-08-26@20260826T180000000000Z"


def _cycle_recursion(*, authority: str = "ai_clone_utc") -> dict:
    return {
        "cycle_id": CYCLE_ID,
        "observed_at": "2026-08-26T18:00:00Z",
        "clock": {
            "schema_version": "ai_clone_clock/v1",
            "authority": authority,
            "timezone": "UTC",
            "observed_at": "2026-08-26T18:00:00Z",
        },
    }


def _meeting_claim() -> dict:
    return {
        "workspace_key": "shared_ops",
        "standup_kind": "executive_ops",
        "cycle_id": CYCLE_ID,
        "meeting_id": "meeting-shared-ops-20260826T180000Z",
        "record_kind": "standup",
        "meeting_held": True,
        "evaluation_only": False,
        "participants": ["Jean-Claude", "Neo", "Yoda"],
        "discussion": [],
        "meeting_evidence": {
            "schema_version": "standup_meeting_evidence/v1",
            "meeting_id": "meeting-shared-ops-20260826T180000Z",
            "participant_report_run_ids": ["caller-supplied-run"],
            "transcript_sha256": "a" * 64,
        },
    }


def _row(payload: dict) -> dict:
    return {
        "id": "standup-real-1",
        "owner": "Jean-Claude",
        "workspace_key": "shared_ops",
        "status": "completed",
        "blockers": [],
        "commitments": [],
        "needs": [],
        "source": "standup_prep",
        "conversation_path": None,
        "payload": payload,
        "created_at": NOW,
    }


def _pool_with_current_row(row: dict):
    pool = MagicMock()
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = row
    return pool, connection, cursor


def test_generic_create_cannot_inject_completed_real_meeting() -> None:
    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError, match="governed standup promotion"):
            standup_service.create_standup(
                StandupCreate(
                    owner="Jean-Claude",
                    workspace_key="shared_ops",
                    status="completed",
                    payload=_meeting_claim(),
                )
            )

    get_pool.assert_not_called()


def test_generic_patch_cannot_inject_authority_shaped_meeting() -> None:
    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError, match="governed standup promotion"):
            standup_service.update_standup(
                "standup-plan-1",
                StandupUpdate(payload=_meeting_claim()),
            )

    get_pool.assert_not_called()


@pytest.mark.parametrize(
    "update",
    [
        StandupUpdate(status="prepared"),
        StandupUpdate(payload={"record_kind": "workspace_cycle_plan", "meeting_held": False}),
        StandupUpdate(blockers=["Caller attempted to alter the completed meeting."]),
    ],
)
def test_generic_patch_cannot_alter_or_remove_completed_meeting_truth(update: StandupUpdate) -> None:
    pool, _connection, cursor = _pool_with_current_row(_row(_meeting_claim()))

    with patch.object(standup_service, "get_pool", return_value=pool):
        with pytest.raises(ValueError, match="governed standup promotion"):
            standup_service.update_standup("standup-real-1", update)

    assert cursor.execute.call_count in {0, 1}
    if cursor.execute.call_count:
        assert "SELECT" in cursor.execute.call_args.args[0]


def test_generic_create_cannot_forge_nonmeeting_workspace_cycle_plan() -> None:
    plan_payload = {
        "workspace_key": "fusion-os",
        "standup_kind": "workspace_sync",
        "cycle_id": CYCLE_ID,
        "recursion": _cycle_recursion(),
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "participants": [],
        "planned_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "meeting_evidence": {},
    }
    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError, match="governed standup promotion"):
            standup_service.create_standup(
                StandupCreate(
                    owner="Jean-Claude",
                    workspace_key="fusion-os",
                    status="completed",
                    payload=plan_payload,
                )
            )

    get_pool.assert_not_called()


def test_generic_create_cannot_front_run_completed_cycle_identity() -> None:
    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError, match="governed standup promotion"):
            standup_service.create_standup(
                StandupCreate(
                    owner="Jean-Claude",
                    workspace_key="fusion-os",
                    status="completed",
                    payload={
                        "standup_kind": "workspace_sync",
                        "cycle_id": "daily-2026-08-26@20260826T180000000000Z",
                        "summary": "An ungoverned caller cannot reserve this identity.",
                    },
                )
            )

    get_pool.assert_not_called()


def test_governed_promotion_writer_preserves_nonmeeting_workspace_cycle_plan() -> None:
    plan_payload = {
        "workspace_key": "fusion-os",
        "standup_kind": "workspace_sync",
        "cycle_id": CYCLE_ID,
        "recursion": _cycle_recursion(),
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "meeting_evidence_state": "synthetic_planning_only",
        "meeting_evidence_reason": "independent_agent_evidence_missing",
        "participants": [],
        "planned_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "meeting_evidence": {},
        "promotion_claims": {},
    }
    pool, connection, cursor = _pool_with_current_row(_row(plan_payload))

    with patch.object(standup_service, "get_pool", return_value=pool):
        created = standup_service.create_standup(
            StandupCreate(
                owner="Jean-Claude",
                workspace_key="fusion-os",
                status="completed",
                payload=plan_payload,
            ),
            _governed_plan_write=True,
        )

    assert created.payload["record_kind"] == "workspace_cycle_plan"
    assert created.payload["meeting_held"] is False
    connection.commit.assert_called_once()
    assert "INSERT INTO standups" in cursor.execute.call_args.args[0]


@pytest.mark.parametrize(
    "recursion",
    [
        {},
        _cycle_recursion(authority="browser_time"),
        {
            **_cycle_recursion(),
            "observed_at": "2026-08-26T18:00:01Z",
        },
    ],
)
def test_governed_cycle_plan_rejects_invalid_clock_before_any_write(
    recursion: dict,
) -> None:
    plan_payload = {
        "workspace_key": "fusion-os",
        "standup_kind": "workspace_sync",
        "cycle_id": CYCLE_ID,
        "recursion": recursion,
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "meeting_evidence_state": "synthetic_planning_only",
        "meeting_evidence_reason": "independent_agent_evidence_missing",
        "participants": [],
        "planned_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "meeting_evidence": {},
        "promotion_claims": {},
    }
    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError):
            standup_service.create_standup(
                StandupCreate(
                    owner="Jean-Claude",
                    workspace_key="fusion-os",
                    status="completed",
                    payload=plan_payload,
                ),
                _governed_plan_write=True,
            )

    get_pool.assert_not_called()


def test_generic_patch_cannot_mutate_plan_or_inject_recommendation_resolutions() -> None:
    plan_payload = {
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "meeting_evidence_state": "synthetic_planning_only",
        "meeting_evidence_reason": "independent_agent_evidence_missing",
        "meeting_evidence": {},
        "participants": [],
        "planned_participants": ["Jean-Claude", "Fusion Systems Operator"],
    }
    pool, _connection, cursor = _pool_with_current_row(_row(plan_payload))
    with patch.object(standup_service, "get_pool", return_value=pool):
        with pytest.raises(ValueError, match="immutable outside governed standup promotion"):
            standup_service.update_standup(
                "standup-plan-1",
                StandupUpdate(blockers=["Caller mutation"]),
            )
    assert cursor.execute.call_count == 1

    with patch.object(standup_service, "get_pool") as get_pool:
        with pytest.raises(ValueError, match="Coordination authority receipts"):
            standup_service.update_standup(
                "legacy-standup-1",
                StandupUpdate(
                    payload={
                        "summary": "Legacy record",
                        "recommendation_resolutions": [
                            {"card_id": "forged", "state": "executed_automatically"}
                        ],
                    }
                ),
            )
    get_pool.assert_not_called()


def test_generic_routes_return_bounded_400_for_meeting_authority_violation() -> None:
    create_payload = StandupCreate(
        owner="Jean-Claude",
        workspace_key="shared_ops",
        status="completed",
        payload=_meeting_claim(),
    )
    with patch.object(
        standup_routes.standup_service,
        "create_standup",
        side_effect=ValueError("governed meeting write required"),
    ):
        with pytest.raises(HTTPException) as create_error:
            asyncio.run(standup_routes.create_entry(create_payload))
    assert create_error.value.status_code == 400

    with patch.object(
        standup_routes.standup_service,
        "update_standup",
        side_effect=ValueError("completed meeting is immutable"),
    ):
        with pytest.raises(HTTPException) as patch_error:
            asyncio.run(
                standup_routes.update_entry(
                    "standup-real-1",
                    StandupUpdate(status="prepared"),
                )
            )
    assert patch_error.value.status_code == 400


def test_public_route_never_passes_private_governed_write_flag() -> None:
    entry = StandupEntry(
        id="workspace-cycle-plan-1",
        owner="Jean-Claude",
        workspace_key="shared_ops",
        status="completed",
        payload={
            "record_kind": "workspace_cycle_plan",
            "meeting_held": False,
            "evaluation_only": True,
        },
        created_at=NOW,
    )
    with (
        patch.object(standup_routes.standup_service, "create_standup", return_value=entry) as create,
        patch.object(standup_routes.standup_service, "public_standup_entry", return_value=entry),
    ):
        asyncio.run(
            standup_routes.create_entry(
                StandupCreate(
                    owner="Jean-Claude",
                    status="completed",
                    payload=entry.payload,
                )
            )
        )

    assert create.call_args.kwargs == {}


def _canonical_plan_resolution_row() -> tuple[dict, dict, dict]:
    recommendation_request = {
        "workspace_key": "fusion-os",
        "scope": "workspace",
        "owner_agent": "Jean-Claude",
        "title": "Advance the bounded Fusion packet",
        "status": "todo",
        "reason": "The exact plan recommendation needs one PM lane.",
        "payload": {},
    }
    plan_payload = {
        "workspace_key": "fusion-os",
        "standup_kind": "workspace_sync",
        "cycle_id": CYCLE_ID,
        "recursion": _cycle_recursion(),
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "meeting_evidence_state": "synthetic_planning_only",
        "meeting_evidence_reason": "independent_agent_evidence_missing",
        "participants": [],
        "planned_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "meeting_evidence": {},
        "promotion_claims": {},
        "recommendation_requests": [recommendation_request],
    }
    entry = StandupEntry(
        id="standup-plan-1",
        owner="Jean-Claude",
        workspace_key="fusion-os",
        status="completed",
        source="standup_prep",
        payload=plan_payload,
        created_at=NOW,
    )
    plan_payload["semantic_payload_sha256"] = (
        standup_service._standup_semantic_payload_sha256(entry)
    )
    row = _row(plan_payload)
    row.update(
        {
            "id": "standup-plan-1",
            "workspace_key": "fusion-os",
            "payload": plan_payload,
        }
    )
    resolution = {
        "card_id": "pm-card-1",
        "state": "placed_in_execution_queue",
        "title": recommendation_request["title"],
        "workspace_key": "fusion-os",
        "request_sha256": standup_service._recommendation_request_sha256(
            recommendation_request
        ),
    }
    return row, recommendation_request, resolution


def _resolution_merge_pool(*, standup_row: dict, card_rows: list[dict]):
    pool = MagicMock()
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [standup_row, standup_row]
    cursor.fetchall.return_value = card_rows
    return pool, connection, cursor


def test_resolution_merge_requires_governed_coordination_record() -> None:
    row, request, resolution = _canonical_plan_resolution_row()
    row["payload"] = {
        "standup_kind": "workspace_sync",
        "cycle_id": "daily-2026-08-26@20260826T180000000000Z",
        "recommendation_requests": [request],
    }
    current = StandupEntry(
        id=row["id"],
        owner=row["owner"],
        workspace_key=row["workspace_key"],
        status=row["status"],
        source=row["source"],
        payload=row["payload"],
        created_at=NOW,
    )
    row["payload"]["semantic_payload_sha256"] = (
        standup_service._standup_semantic_payload_sha256(current)
    )
    pool, connection, cursor = _resolution_merge_pool(
        standup_row=row,
        card_rows=[],
    )

    with patch.object(standup_service, "get_pool", return_value=pool):
        with pytest.raises(ValueError, match="governed coordination record"):
            standup_service._merge_promotion_recommendation_resolutions(
                row["id"],
                recommendation_requests=[request],
                proposed_resolutions=[resolution],
            )

    connection.rollback.assert_called_once()
    assert cursor.fetchall.call_count == 0


def test_resolution_merge_verifies_exact_pm_card_reference() -> None:
    row, request, resolution = _canonical_plan_resolution_row()
    card_row = {
        "id": "pm-card-1",
        "title": request["title"],
        "link_type": "workspace_cycle_plan",
        "link_id": row["id"],
        "payload": {"workspace_key": "fusion-os"},
        "recommendation_coordination_record_id": row["id"],
        "recommendation_request_sha256": (
            standup_service._recommendation_request_sha256(request)
        ),
    }
    pool, connection, cursor = _resolution_merge_pool(
        standup_row=row,
        card_rows=[card_row],
    )

    with patch.object(standup_service, "get_pool", return_value=pool):
        merged = standup_service._merge_promotion_recommendation_resolutions(
            row["id"],
            recommendation_requests=[request],
            proposed_resolutions=[resolution],
        )

    assert merged.id == row["id"]
    connection.commit.assert_called_once()
    assert any("FROM pm_cards" in call.args[0] for call in cursor.execute.call_args_list)


@pytest.mark.parametrize(
    ("card_rows", "state", "error"),
    [
        ([], "placed_in_execution_queue", "missing canonical PM card"),
        (
            [
                {
                    "id": "pm-card-1",
                    "title": "A different lane",
                    "link_type": None,
                    "link_id": None,
                    "payload": {"workspace_key": "agc"},
                    "recommendation_coordination_record_id": None,
                    "recommendation_request_sha256": None,
                }
            ],
            "placed_in_execution_queue",
            "not bound to its exact request",
        ),
        (
            [
                {
                    "id": "pm-card-1",
                    "title": "Advance the bounded Fusion packet",
                    "link_type": "workspace_cycle_plan",
                    "link_id": "standup-plan-1",
                    "payload": {"workspace_key": "fusion-os"},
                    "recommendation_coordination_record_id": "standup-plan-1",
                    "recommendation_request_sha256": None,
                }
            ],
            "made_up_terminal_state",
            "no permitted terminal resolution state",
        ),
    ],
)
def test_resolution_merge_rejects_unproved_pm_reference(
    card_rows: list[dict],
    state: str,
    error: str,
) -> None:
    row, request, resolution = _canonical_plan_resolution_row()
    resolution["state"] = state
    pool, connection, _cursor = _resolution_merge_pool(
        standup_row=row,
        card_rows=card_rows,
    )

    with patch.object(standup_service, "get_pool", return_value=pool):
        with pytest.raises(Exception, match=error):
            standup_service._merge_promotion_recommendation_resolutions(
                row["id"],
                recommendation_requests=[request],
                proposed_resolutions=[resolution],
            )

    connection.rollback.assert_called_once()
