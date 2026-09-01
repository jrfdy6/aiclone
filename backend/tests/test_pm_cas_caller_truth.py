from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models import PMCard, PMCardCreate
from app.services import linkedin_owner_review_service, pm_card_service


NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


def _card(
    card_id: str,
    *,
    title: str = "Bounded PM work",
    status: str = "todo",
    source: str = "pm_review_resolution",
    link_type: str | None = "standup",
    payload: dict | None = None,
    updated_at: datetime = NOW,
) -> PMCard:
    return PMCard(
        id=card_id,
        title=title,
        owner="Neo",
        status=status,
        source=source,
        link_type=link_type,
        link_id=None,
        payload=dict(payload or {}),
        created_at=NOW - timedelta(hours=1),
        updated_at=updated_at,
    )


def test_trigger_replay_rebuilds_once_from_fresh_row_after_cas_miss() -> None:
    original = _card(
        "trigger-card",
        source="codex_native:remote_queue",
        payload={
            "workspace_key": "fusion-os",
            "trigger_key": "codex:test-trigger",
            "trigger_replays": 0,
        },
    )
    concurrent = original.model_copy(
        update={
            "payload": {
                **original.payload,
                "trigger_replays": 1,
                "concurrent_note": "preserve me",
            },
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    attempts: list[tuple[datetime | None, dict]] = []

    def update_card(_card_id, mutation, *, _expected_updated_at=None, **_kwargs):
        attempts.append((_expected_updated_at, dict(mutation.payload or {})))
        if len(attempts) == 1:
            return None
        return concurrent.model_copy(
            update={
                "payload": dict(mutation.payload or {}),
                "updated_at": NOW + timedelta(seconds=2),
            }
        )

    request = PMCardCreate(
        title=original.title,
        owner="Neo",
        source=original.source,
        payload={
            "workspace_key": "fusion-os",
            "trigger_key": "codex:test-trigger",
            "trigger_origin": "codex_native_remote_queue",
        },
    )
    with (
        patch.object(pm_card_service, "find_active_card_by_trigger_key", return_value=original),
        patch.object(pm_card_service, "update_card", side_effect=update_card),
        patch.object(pm_card_service, "get_card", return_value=concurrent),
    ):
        result = pm_card_service.create_card(request)

    assert result.payload["trigger_replays"] == 2
    assert result.payload["concurrent_note"] == "preserve me"
    assert [attempt[0] for attempt in attempts] == [original.updated_at, concurrent.updated_at]


def test_trigger_replay_double_cas_miss_raises_instead_of_returning_stale_card() -> None:
    original = _card(
        "trigger-conflict",
        source="codex_native:remote_queue",
        payload={
            "workspace_key": "fusion-os",
            "trigger_key": "codex:conflict-trigger",
        },
    )
    current = original.model_copy(update={"updated_at": NOW + timedelta(seconds=1)})
    request = PMCardCreate(
        title=original.title,
        owner="Neo",
        source=original.source,
        payload={
            "workspace_key": "fusion-os",
            "trigger_key": "codex:conflict-trigger",
            "trigger_origin": "codex_native_remote_queue",
        },
    )
    with (
        patch.object(pm_card_service, "find_active_card_by_trigger_key", return_value=original),
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=current),
    ):
        with pytest.raises(pm_card_service.PMCardMutationConflict, match="not persisted"):
            pm_card_service.create_card(request)

    assert update.call_count == 2


def test_execution_contract_repair_accepts_only_fresh_durable_idempotent_state() -> None:
    original = _card(
        "repair-card",
        payload={"workspace_key": "fusion-os", "reason": "Repair this bounded lane."},
    )
    concurrently_repaired = original.model_copy(
        update={
            "payload": {
                **original.payload,
                "completion_contract": {
                    "source": "pm_review_resolution",
                    "autostart": True,
                },
                "execution": {"state": "queued"},
            },
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    with (
        patch.object(pm_card_service, "list_cards", return_value=[original]),
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=concurrently_repaired),
    ):
        result = pm_card_service.repair_execution_contracts(limit=10)

    assert result["repaired_count"] == 1
    assert result["repaired"][0]["card_id"] == original.id
    assert update.call_count == 1


def test_stale_owner_review_autoclose_double_cas_miss_never_reports_closed() -> None:
    duplicate = _card(
        "stale-owner-review",
        title="Schedule approved FEEZIE draft - FEEZIE-004",
        source="openclaw:workspace-owner-review",
        link_type="owner_review",
        payload={
            "workspace_key": "linkedin-os",
            "owner_review": {"queue_id": "FEEZIE-004", "decision": "approve"},
        },
    )
    completed = _card(
        "completed-owner-review",
        title="Host action required - Schedule approved FEEZIE draft - FEEZIE-004",
        status="done",
        source="pm_host_action_required",
        link_type="owner_review",
        payload={
            "workspace_key": "linkedin-os",
            "host_action_required": {
                "summary": "Schedule approved FEEZIE draft - FEEZIE-004",
                "source_card_title": duplicate.title,
            },
        },
    )
    current = duplicate.model_copy(update={"updated_at": NOW + timedelta(seconds=1)})
    with (
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=current),
    ):
        with pytest.raises(pm_card_service.PMCardMutationConflict, match="not persisted"):
            pm_card_service._auto_close_stale_owner_review_duplicates([duplicate, completed])

    assert update.call_count == 2


def test_superseded_owner_review_close_accepts_fresh_committed_row_after_cas_miss() -> None:
    pending_payload = {
        "workspace_key": "linkedin-os",
        "owner_review": {
            "identity_key": "latent-transform:idea:one",
            "sync_state": "pending_owner_review",
        },
    }
    duplicate = _card(
        "owner-review-duplicate",
        status="review",
        source=linkedin_owner_review_service.OWNER_REVIEW_CARD_SOURCE,
        link_type="owner_review",
        payload=pending_payload,
    )
    replacement = _card(
        "owner-review-current",
        status="review",
        source=linkedin_owner_review_service.OWNER_REVIEW_CARD_SOURCE,
        link_type="owner_review",
        payload=pending_payload,
    )
    committed_payload = {
        **pending_payload,
        "owner_review": {
            **pending_payload["owner_review"],
            "sync_state": "superseded",
        },
        "duplicate_resolution": {
            "rule": "owner_review_pending_identity_autoclose",
            "replacement_card_id": replacement.id,
        },
    }
    committed = duplicate.model_copy(
        update={
            "status": "done",
            "payload": committed_payload,
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    with (
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=committed),
    ):
        result = linkedin_owner_review_service._close_superseded_owner_review_card(
            duplicate,
            replacement=replacement,
            rule="owner_review_pending_identity_autoclose",
            reason="Bounded duplicate closure.",
        )

    assert result == duplicate.id
    assert update.call_count == 1


def test_owner_review_sync_cas_miss_does_not_overwrite_concurrent_owner_decision() -> None:
    item = {
        "queue_id": "FEEZIE-TEST-001",
        "title": "Exact owner-review draft",
        "approval_status": "owner_review_required",
        "publish_posture": "owner_review_required",
        "entry_kind": "queue",
        "source_kind": "feezie_queue",
    }
    pending_payload = linkedin_owner_review_service._build_pending_owner_review_card_payload(item)
    existing = _card(
        "owner-review-sync",
        title="Stale title",
        status="review",
        source=linkedin_owner_review_service.OWNER_REVIEW_CARD_SOURCE,
        link_type="owner_review",
        payload=pending_payload,
    )
    concurrent_payload = {
        **pending_payload,
        "owner_review": {
            **pending_payload["owner_review"],
            "decision": "approve",
            "sync_state": "owner_decision_recorded",
        },
    }
    concurrent = existing.model_copy(
        update={
            "payload": concurrent_payload,
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    with (
        patch.object(linkedin_owner_review_service, "_list_active_owner_review_cards", return_value=[existing]),
        patch.object(
            linkedin_owner_review_service,
            "list_owner_review_items",
            return_value={"items": [item]},
        ),
        patch.object(pm_card_service, "find_active_card_by_trigger_key", return_value=existing),
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=concurrent),
    ):
        with pytest.raises(
            linkedin_owner_review_service.LinkedinOwnerReviewConflictError,
            match="not persisted",
        ):
            linkedin_owner_review_service.sync_owner_review_pm_cards(
                legacy_compatibility=True,
            )

    assert update.call_count == 1


def test_owner_review_park_double_cas_miss_never_claims_cancellation() -> None:
    item = {
        "queue_id": "FEEZIE-TEST-002",
        "title": "Park this bounded draft",
        "entry_kind": "queue",
        "source_kind": "feezie_queue",
    }
    existing = _card(
        "owner-review-park",
        title="Owner-review follow-up",
        status="todo",
        source=linkedin_owner_review_service.OWNER_REVIEW_CARD_SOURCE,
        link_type="owner_review",
        payload={
            "workspace_key": "linkedin-os",
            "trigger_key": "owner-review:FEEZIE-TEST-002",
            "owner_review": {"queue_id": item["queue_id"]},
        },
    )
    current = existing.model_copy(update={"updated_at": NOW + timedelta(seconds=1)})
    with (
        patch.object(pm_card_service, "find_active_card_by_trigger_key", return_value=existing),
        patch.object(pm_card_service, "update_card", return_value=None) as update,
        patch.object(pm_card_service, "get_card", return_value=current),
    ):
        with pytest.raises(
            linkedin_owner_review_service.LinkedinOwnerReviewConflictError,
            match="not persisted",
        ):
            linkedin_owner_review_service._queue_owner_review_followup(
                item,
                decision="park",
                notes="",
                draft_rel_path="drafts/feezie-test-002.md",
                packet_rel_path=None,
                reviewed_at=NOW.isoformat(),
            )

    assert update.call_count == 2


def test_requeued_host_action_automation_double_cas_miss_never_returns_stale_success() -> None:
    card = _card(
        "queued-host-automation",
        title="Host action required - Run fallback watchdog write-back",
        status="in_progress",
        source="pm_host_action_required",
        link_type=None,
        payload={
            "workspace_key": "shared_ops",
            "host_action_required": {
                "summary": "Run fallback_watchdog_latest.json result write-back for PM card source-card-1.",
                "steps": ["Run the authorized write-back."],
                "source_card_id": "source-card-1",
            },
            "host_action_automation": {
                "automation_id": "fallback_watchdog_writeback",
                "state": "queued",
                "requires_host_confirmation": False,
                "source_card_id": "source-card-1",
            },
        },
    )
    current = card.model_copy(update={"updated_at": NOW + timedelta(seconds=1)})
    with (
        patch.object(pm_card_service, "get_card", side_effect=[card, current, current]),
        patch.object(pm_card_service, "update_card", return_value=None) as update,
    ):
        with pytest.raises(pm_card_service.PMCardMutationConflict, match="not persisted"):
            pm_card_service.queue_host_action_automation(card.id, requested_by="Neo")

    assert update.call_count == 2


def test_spawned_successor_link_double_cas_miss_is_an_explicit_conflict() -> None:
    card = _card(
        "review-parent",
        title="Finish bounded review then continue",
        status="review",
        source="standup:test",
        payload={"workspace_key": "fusion-os"},
    )
    successor = _card(
        "review-successor",
        title="Continue bounded internal work",
        status="todo",
        source="pm_review_resolution",
        payload={"workspace_key": "fusion-os"},
        updated_at=NOW + timedelta(seconds=1),
    )
    current: dict[str, PMCard] = {"card": card}
    calls = {"count": 0}

    def update_card(_card_id, mutation, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            current["card"] = card.model_copy(
                update={
                    "status": mutation.status or card.status,
                    "payload": dict(mutation.payload or {}),
                    "updated_at": NOW + timedelta(seconds=1),
                }
            )
            return current["card"]
        return None

    with (
        patch.object(pm_card_service, "update_card", side_effect=update_card),
        patch.object(pm_card_service, "get_card", side_effect=lambda _card_id: current["card"]),
        patch.object(pm_card_service, "_create_resolution_successor_card", return_value=successor),
    ):
        with pytest.raises(pm_card_service.PMCardMutationConflict, match="link receipt.*not persisted"):
            pm_card_service._apply_card_action(
                card,
                action="approve",
                requested_by="Neo",
                resolution_mode="close_and_spawn_next",
                next_title=successor.title,
                next_reason="Continue only the bounded internal lane.",
            )

    assert calls["count"] == 3
