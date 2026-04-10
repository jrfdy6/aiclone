from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.pm_board import PMCard, PMCardActionRequest, PMCardCreate, PMCardDispatchRequest, PMCardUpdate
from app.services import pm_card_service
from app.services.pm_card_service import build_execution_queue_entry


class PMCardServiceTests(unittest.TestCase):
    def _apply_update(self, card: PMCard, patch: PMCardUpdate) -> PMCard:
        return card.model_copy(
            update={
                "status": patch.status if patch.status is not None else card.status,
                "payload": patch.payload if patch.payload is not None else card.payload,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    def test_closed_card_with_execution_payload_does_not_surface_in_queue(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="done-card",
            title="Already finished",
            owner="Jean-Claude",
            status="done",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-1",
            payload={
                "workspace_key": "shared_ops",
                "execution": {
                    "state": "queued",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                }
            },
            created_at=now,
            updated_at=now,
        )

        self.assertIsNone(build_execution_queue_entry(card))

    def test_open_standup_card_surfaces_with_defaults(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="todo-card",
            title="Needs follow-through",
            owner="Jean-Claude",
            status="todo",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-2",
            payload={"workspace_key": "shared_ops"},
            created_at=now,
            updated_at=now,
        )

        entry = build_execution_queue_entry(card)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.pm_status, "todo")
        self.assertEqual(entry.execution_state, "ready")
        self.assertEqual(entry.manager_agent, "Jean-Claude")

    def test_normalize_human_front_door_payload_sets_neo_and_trigger_key(self) -> None:
        payload = PMCardCreate(
            title="Wire the next fusion lane",
            owner=None,
            status="todo",
            source="openclaw:thin-trigger",
            payload={
                "workspace_key": "fusion-os",
                "reason": "Route a human request into Fusion.",
                "instructions": ["Use the PM card as the source of truth."],
                "execution": {
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                    "execution_mode": "delegated",
                    "lane": "codex",
                },
            },
        )

        normalized = pm_card_service._normalize_card_create_payload(payload)

        self.assertEqual(normalized.owner, "Neo")
        self.assertEqual(normalized.payload.get("front_door_agent"), "Neo")
        self.assertEqual(normalized.payload.get("source_agent"), "Neo")
        self.assertEqual(normalized.payload.get("requested_by"), "Neo")
        self.assertTrue(str(normalized.payload.get("trigger_key") or "").startswith("openclaw:"))
        self.assertEqual((normalized.payload.get("execution") or {}).get("requested_by"), "Neo")

    def test_build_execution_queue_entry_exposes_executor_and_result_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="metadata-card",
            title="Metadata lane",
            owner="Neo",
            status="in_progress",
            source="openclaw:thin-trigger",
            link_type=None,
            link_id=None,
            payload={
                "workspace_key": "fusion-os",
                "front_door_agent": "Neo",
                "trigger_key": "openclaw:test-trigger",
                "execution": {
                    "lane": "codex",
                    "state": "running",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                    "execution_mode": "delegated",
                    "requested_by": "Neo",
                    "assigned_runner": "fusion-systems-operator",
                    "manager_attention_required": True,
                    "executor_status": "running",
                    "executor_worker_id": "macbook-codex",
                    "execution_packet_path": "/tmp/fusion_work_order.json",
                    "sop_path": "/tmp/fusion_sop.json",
                    "briefing_path": "/tmp/fusion_briefing.md",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Fusion lane changes are ready for review.",
                    "artifacts": ["/tmp/fusion_result.json", "/tmp/fusion_result.md"],
                },
            },
            created_at=now,
            updated_at=now,
        )

        entry = build_execution_queue_entry(card)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.front_door_agent, "Neo")
        self.assertEqual(entry.trigger_key, "openclaw:test-trigger")
        self.assertTrue(entry.manager_attention_required)
        self.assertEqual(entry.executor_status, "running")
        self.assertEqual(entry.executor_worker_id, "macbook-codex")
        self.assertEqual(entry.execution_packet_path, "/tmp/fusion_work_order.json")
        self.assertEqual(entry.sop_path, "/tmp/fusion_sop.json")
        self.assertEqual(entry.briefing_path, "/tmp/fusion_briefing.md")
        self.assertEqual(entry.latest_result_status, "review")
        self.assertEqual(entry.latest_result_summary, "Fusion lane changes are ready for review.")
        self.assertEqual(entry.latest_result_artifacts, ["/tmp/fusion_result.json", "/tmp/fusion_result.md"])

    def test_dispatch_card_moves_ready_work_into_queued_execution(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="dispatch-card",
            title="Dispatch me",
            owner="Jean-Claude",
            status="todo",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-3",
            payload={"workspace_key": "shared_ops"},
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.dispatch_card(
                card.id,
                PMCardDispatchRequest(target_agent="Jean-Claude", lane="codex", requested_by="Jean-Claude", execution_state="queued"),
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.queue_entry.execution_state, "queued")
        self.assertEqual(result.queue_entry.target_agent, "Jean-Claude")
        self.assertEqual((result.card.payload.get("execution") or {}).get("state"), "queued")

    def test_act_on_card_approve_close_only_closes_review_lane(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="approve-card",
            title="Review result",
            owner="Jean-Claude",
            status="review",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-4",
            payload={
                "workspace_key": "shared_ops",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Looks ready to close.",
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.act_on_card(
                card.id,
                PMCardActionRequest(action="approve", requested_by="Neo", resolution_mode="close_only"),
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.card.status, "done")
        self.assertIsNone(result.queue_entry)
        self.assertEqual((result.card.payload.get("latest_manual_review") or {}).get("action"), "approve")
        self.assertEqual((result.card.payload.get("latest_manual_review") or {}).get("resolution_mode"), "close_only")
        self.assertEqual((result.card.payload.get("latest_execution_result") or {}).get("review_resolution"), "approve")

    def test_act_on_card_approve_requires_resolution_mode(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="approve-no-mode-card",
            title="Review result without mode",
            owner="Jean-Claude",
            status="review",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-4b",
            payload={
                "workspace_key": "shared_ops",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with patch.object(pm_card_service, "get_card", return_value=card):
            with self.assertRaisesRegex(ValueError, "explicit next-step mode"):
                pm_card_service.act_on_card(card.id, PMCardActionRequest(action="approve", requested_by="Neo"))

    def test_act_on_card_approve_can_spawn_successor_card(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="approve-spawn-card",
            title="Resolve then continue",
            owner="Jean-Claude",
            status="review",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-4c",
            payload={
                "workspace_key": "feezie-os",
                "created_from_standup_id": "standup-4c",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )
        successor = PMCard(
            id="spawned-card",
            title="Package backlog into the next release step",
            owner="Jean-Claude",
            status="todo",
            source="pm_review_resolution",
            link_type="standup",
            link_id="standup-4c",
            payload={"workspace_key": "feezie-os"},
            created_at=now,
            updated_at=now,
        )

        def fake_create_card(payload: PMCardCreate) -> PMCard:
            self.assertEqual(payload.title, successor.title)
            self.assertEqual(payload.status, "todo")
            self.assertEqual(payload.source, "pm_review_resolution")
            self.assertEqual(payload.link_type, "standup")
            self.assertEqual(payload.link_id, "standup-4c")
            self.assertEqual(payload.payload.get("workspace_key"), "feezie-os")
            self.assertEqual((payload.payload.get("resolution_predecessor") or {}).get("card_id"), card.id)
            self.assertEqual(payload.payload.get("reason"), "Turn the accepted backlog seed into a concrete next lane.")
            return successor

        with (
            patch.object(pm_card_service, "get_card", return_value=card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
            patch.object(pm_card_service, "create_card", side_effect=fake_create_card),
        ):
            result = pm_card_service.act_on_card(
                card.id,
                PMCardActionRequest(
                    action="approve",
                    requested_by="Neo",
                    resolution_mode="close_and_spawn_next",
                    next_title=successor.title,
                    next_reason="Turn the accepted backlog seed into a concrete next lane.",
                ),
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.card.status, "done")
        self.assertIsNone(result.queue_entry)
        self.assertIsNotNone(result.successor_card)
        assert result.successor_card is not None
        self.assertEqual(result.successor_card.id, "spawned-card")
        latest_manual_review = result.card.payload.get("latest_manual_review") or {}
        self.assertEqual(latest_manual_review.get("resolution_mode"), "close_and_spawn_next")
        self.assertEqual(latest_manual_review.get("successor_card_id"), "spawned-card")
        self.assertEqual((result.card.payload.get("resolution_successor") or {}).get("card_id"), "spawned-card")

    def test_act_on_card_return_reroutes_to_jean_claude(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="return-card",
            title="Needs another pass",
            owner="Jean-Claude",
            status="review",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-5",
            payload={
                "workspace_key": "fusion-os",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                    "execution_mode": "delegated",
                    "assigned_runner": "codex",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.act_on_card(card.id, PMCardActionRequest(action="return", requested_by="Neo"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.card.status, "todo")
        assert result.queue_entry is not None
        self.assertEqual(result.queue_entry.execution_state, "queued")
        self.assertEqual(result.queue_entry.target_agent, "Jean-Claude")
        self.assertEqual((result.card.payload.get("latest_manual_review") or {}).get("action"), "return")

    def test_act_on_card_blocked_sets_manager_attention_and_preserves_returned_agent(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="blocked-card",
            title="Blocked work",
            owner="Jean-Claude",
            status="running",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-6",
            payload={
                "workspace_key": "fusion-os",
                "execution": {
                    "lane": "codex",
                    "state": "running",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                    "execution_mode": "delegated",
                    "assigned_runner": "codex",
                    "queued_at": now.isoformat(),
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.act_on_card(card.id, PMCardActionRequest(action="blocked", requested_by="Neo"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.card.status, "blocked")
        assert result.queue_entry is not None
        self.assertEqual(result.queue_entry.execution_state, "queued")
        self.assertEqual(result.queue_entry.target_agent, "Jean-Claude")
        execution = result.card.payload.get("execution") or {}
        self.assertTrue(execution.get("manager_attention_required"))
        self.assertEqual(execution.get("returned_from_agent"), "Fusion Systems Operator")

    def test_lifecycle_harness_ready_dispatch_review_close(self) -> None:
        now = datetime.now(timezone.utc)
        ready_card = PMCard(
            id="lifecycle-card",
            title="Lifecycle test",
            owner="Jean-Claude",
            status="todo",
            source="standup-prep:test",
            link_type="standup",
            link_id="standup-7",
            payload={"workspace_key": "shared_ops"},
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=ready_card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(ready_card, patch)),
        ):
            dispatch_result = pm_card_service.dispatch_card(
                ready_card.id,
                PMCardDispatchRequest(target_agent="Jean-Claude", lane="codex", requested_by="Jean-Claude", execution_state="queued"),
            )

        self.assertIsNotNone(dispatch_result)
        assert dispatch_result is not None
        self.assertEqual(dispatch_result.queue_entry.execution_state, "queued")

        review_card = dispatch_result.card.model_copy(
            update={
                "status": "review",
                "payload": {
                    **(dispatch_result.card.payload or {}),
                    "latest_execution_result": {
                        "status": "review",
                        "summary": "Execution completed and is ready for manual closeout.",
                    },
                    "execution": {
                        **((dispatch_result.card.payload or {}).get("execution") or {}),
                        "state": "review",
                    },
                },
            }
        )

        with (
            patch.object(pm_card_service, "get_card", return_value=review_card),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(review_card, patch)),
        ):
            close_result = pm_card_service.act_on_card(
                review_card.id,
                PMCardActionRequest(action="approve", requested_by="Neo", resolution_mode="close_only"),
            )

        self.assertIsNotNone(close_result)
        assert close_result is not None
        self.assertEqual(close_result.card.status, "done")
        self.assertIsNone(close_result.queue_entry)


if __name__ == "__main__":
    unittest.main()
