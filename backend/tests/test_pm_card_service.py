from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.pm_board import PMCard, PMCardActionRequest, PMCardCreate, PMCardDispatchRequest, PMCardUpdate
from app.services import pm_card_service
from app.services import pm_review_hygiene_audit_service
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

    def test_auto_resolve_review_cards_closes_stale_shared_ops_review_residue(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-resolve-card",
            title="Recurring stale review lane",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-auto-1",
            payload={
                "workspace_key": "shared_ops",
                "reason": "Accountability sweep rerouted this stale `review` lane in `shared_ops` back to Jean-Claude for a required closure decision.",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_resolve_review_cards()

        self.assertEqual(result.get("resolved_count"), 1)
        resolved = (result.get("resolved") or [None])[0]
        self.assertEqual((resolved or {}).get("card_id"), "auto-resolve-card")
        self.assertEqual((resolved or {}).get("rule"), "accountability_stale_review_autoclose")

    def test_auto_resolve_review_cards_closes_stale_feezie_alias_review_residue(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-resolve-feezie-alias-card",
            title="Turn first FEEZIE queue items into owner-review drafts",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-auto-feezie-alias-1",
            payload={
                "workspace_key": "feezie-os",
                "reason": "Accountability sweep rerouted this stale `review` lane in `feezie-os` back to Jean-Claude for a required closure decision.",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_resolve_review_cards()

        self.assertEqual(result.get("resolved_count"), 1)
        resolved = (result.get("resolved") or [None])[0]
        self.assertEqual((resolved or {}).get("card_id"), "auto-resolve-feezie-alias-card")
        self.assertEqual((resolved or {}).get("rule"), "accountability_stale_review_autoclose")

    def test_auto_resolve_review_cards_skips_owner_review_gate(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-resolve-owner-gate",
            title="Owner review gate",
            owner="Neo",
            status="review",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id="FEEZIE-777",
            payload={
                "workspace_key": "linkedin-os",
                "owner_review": {"queue_id": "FEEZIE-777"},
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card") as update_card_mock,
        ):
            result = pm_card_service.auto_resolve_review_cards()

        self.assertEqual(result.get("resolved_count"), 0)
        update_card_mock.assert_not_called()

    def test_auto_progress_review_cards_closes_shared_ops_routine_review(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-shared-ops",
            title="Routine shared ops review",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-auto-progress-1",
            payload={
                "workspace_key": "shared_ops",
                "reason": "Routine execution result ready for review.",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 1)
        self.assertEqual(result.get("closed_count"), 1)
        self.assertEqual(result.get("continued_count"), 0)
        processed = (result.get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("card_id"), "auto-progress-shared-ops")
        self.assertEqual((processed or {}).get("rule"), "workspace_policy_accept_and_close")

    def test_auto_progress_review_cards_continues_feezie_review_and_spawns_successor(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-feezie",
            title="Seed FEEZIE backlog from canonical persona and lived work",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-auto-progress-2",
            payload={
                "workspace_key": "linkedin-os",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )
        successor = PMCard(
            id="auto-progress-feezie-next",
            title="Turn seeded FEEZIE backlog into first draft batch",
            owner="Jean-Claude",
            status="todo",
            source="pm_review_resolution",
            link_type="standup",
            link_id="standup-auto-progress-2",
            payload={"workspace_key": "linkedin-os"},
            created_at=now,
            updated_at=now,
        )

        def fake_create_card(payload: PMCardCreate) -> PMCard:
            self.assertEqual(payload.title, successor.title)
            self.assertEqual(payload.payload.get("workspace_key"), "linkedin-os")
            self.assertEqual(payload.payload.get("reason"), "The accepted backlog seed should now become concrete first-pass draft production.")
            return successor

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
            patch.object(pm_card_service, "create_card", side_effect=fake_create_card),
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 1)
        self.assertEqual(result.get("closed_count"), 0)
        self.assertEqual(result.get("continued_count"), 1)
        processed = (result.get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("card_id"), "auto-progress-feezie")
        self.assertEqual((processed or {}).get("rule"), "workspace_policy_accept_and_continue")
        self.assertEqual((processed or {}).get("successor_card_id"), "auto-progress-feezie-next")
        self.assertEqual((processed or {}).get("successor_card_title"), successor.title)

    def test_auto_progress_review_cards_skips_owner_review_gate(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-owner-gate",
            title="Owner review gate",
            owner="Neo",
            status="review",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id="FEEZIE-888",
            payload={
                "workspace_key": "linkedin-os",
                "owner_review": {"queue_id": "FEEZIE-888"},
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card") as update_card_mock,
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 0)
        update_card_mock.assert_not_called()

    def test_auto_progress_review_cards_returns_unmet_completion_contract_to_execution(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-contract-return",
            title="Routine review with unmet contract",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-contract-return-1",
            payload={
                "workspace_key": "shared_ops",
                "completion_contract": {
                    "source": "standup_promotion",
                    "auto_return_limit": 2,
                    "result_requirements": {
                        "summary_min_length": 20,
                        "require_outcome_or_artifact": True,
                        "require_writeback": True,
                        "allow_blockers": False,
                    },
                    "done_when": ["Return a bounded result with at least one concrete outcome."],
                },
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Started work.",
                    "outcomes": [],
                    "artifacts": [],
                    "blockers": [],
                },
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 1)
        self.assertEqual(result.get("returned_count"), 1)
        processed = (result.get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("action"), "return")
        self.assertEqual((processed or {}).get("rule"), "completion_contract_return_for_rework")
        self.assertIn("completion contract", (processed or {}).get("reason", "").lower())

    def test_auto_progress_review_cards_escalates_after_completion_contract_retry_limit(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-contract-blocked",
            title="Routine review with repeated unmet contract",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-contract-blocked-1",
            payload={
                "workspace_key": "shared_ops",
                "completion_contract": {
                    "source": "standup_promotion",
                    "auto_return_limit": 1,
                    "result_requirements": {
                        "summary_min_length": 20,
                        "require_outcome_or_artifact": True,
                        "require_writeback": True,
                        "allow_blockers": False,
                    },
                    "done_when": ["Return a bounded result with at least one concrete outcome."],
                },
                "latest_manual_review": {
                    "action": "return",
                    "contract_auto_return_count": 1,
                },
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Started work.",
                    "outcomes": [],
                    "artifacts": [],
                    "blockers": [],
                },
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 1)
        self.assertEqual(result.get("escalated_count"), 1)
        processed = (result.get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("action"), "blocked")
        self.assertEqual((processed or {}).get("rule"), "completion_contract_escalation_after_retries")

    def test_auto_progress_review_cards_accepts_met_completion_contract(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-contract-met",
            title="Routine review with met contract",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-contract-met-1",
            payload={
                "workspace_key": "shared_ops",
                "completion_contract": {
                    "source": "standup_promotion",
                    "auto_return_limit": 2,
                    "result_requirements": {
                        "summary_min_length": 20,
                        "require_outcome_or_artifact": True,
                        "require_writeback": True,
                        "allow_blockers": False,
                    },
                    "done_when": ["Return a bounded result with at least one concrete outcome."],
                },
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Updated the workflow and wrote the result back with a concrete artifact.",
                    "outcomes": ["The workflow now advances automatically."],
                    "artifacts": ["/tmp/result.json"],
                    "blockers": [],
                },
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_card_service, "list_cards", return_value=[card]),
            patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
        ):
            result = pm_card_service.auto_progress_review_cards()

        self.assertEqual(result.get("processed_count"), 1)
        self.assertEqual(result.get("closed_count"), 1)
        processed = (result.get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("action"), "approve")
        self.assertEqual((processed or {}).get("rule"), "workspace_policy_accept_and_close")

    def test_auto_progress_review_cards_records_audit_entry(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="auto-progress-audit",
            title="Routine review for audit trail",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-audit-1",
            payload={
                "workspace_key": "shared_ops",
                "latest_execution_result": {
                    "status": "review",
                    "summary": "Updated the workflow and wrote the result back with a concrete artifact.",
                    "outcomes": ["The workflow now advances automatically."],
                    "artifacts": ["/tmp/result.json"],
                    "blockers": [],
                },
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "pm_review_hygiene_audit.jsonl"
            with (
                patch.object(pm_card_service, "list_cards", return_value=[card]),
                patch.object(pm_card_service, "update_card", side_effect=lambda _card_id, patch: self._apply_update(card, patch)),
                patch.object(pm_review_hygiene_audit_service, "AUDIT_PATH", audit_path),
            ):
                result = pm_card_service.auto_progress_review_cards()
                report = pm_card_service.review_hygiene_audit(limit=5, hours=24)

        self.assertEqual(result.get("processed_count"), 1)
        self.assertIn("audit_entry", result)
        self.assertEqual((report.get("summary") or {}).get("processed_count"), 1)
        self.assertEqual((report.get("summary") or {}).get("advanced_count"), 1)
        entry = (report.get("entries") or [None])[0]
        self.assertEqual((entry or {}).get("processed_count"), 1)
        processed = ((entry or {}).get("processed") or [None])[0]
        self.assertEqual((processed or {}).get("card_id"), "auto-progress-audit")

    def test_decorate_card_for_client_marks_feezie_review_as_autonomous_and_prefills_followup(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="feezie-review-card",
            title="Seed FEEZIE backlog from canonical persona and lived work",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-feezie-1",
            payload={
                "workspace_key": "linkedin-os",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        decorated = pm_card_service.decorate_card_for_client(card)

        self.assertIsNotNone(decorated)
        policy = (decorated.payload.get("pm_review_policy") or {}) if decorated else {}
        self.assertEqual(policy.get("attention_class"), "autonomous")
        self.assertEqual(policy.get("recommended_resolution_mode"), "close_and_spawn_next")
        self.assertEqual(policy.get("suggested_next_title"), "Turn seeded FEEZIE backlog into first draft batch")

    def test_decorate_card_for_client_marks_feezie_alias_review_as_autonomous(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="feezie-alias-review-card",
            title="Turn first FEEZIE queue items into owner-review drafts",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-feezie-alias-1",
            payload={
                "workspace_key": "feezie-os",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        decorated = pm_card_service.decorate_card_for_client(card)

        self.assertIsNotNone(decorated)
        policy = (decorated.payload.get("pm_review_policy") or {}) if decorated else {}
        self.assertEqual(policy.get("attention_class"), "autonomous")
        self.assertEqual(policy.get("recommended_resolution_mode"), "close_and_spawn_next")
        self.assertEqual(policy.get("suggested_next_title"), "Package accepted FEEZIE draft into scheduling lane")

    def test_decorate_card_for_client_marks_fusion_review_as_needs_owner(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="fusion-review-card",
            title="Review Fusion delegated result",
            owner="Jean-Claude",
            status="review",
            source="standup:test",
            link_type="standup",
            link_id="standup-fusion-1",
            payload={
                "workspace_key": "fusion-os",
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Fusion Systems Operator",
                    "workspace_agent": "Fusion Systems Operator",
                    "execution_mode": "delegated",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        decorated = pm_card_service.decorate_card_for_client(card)

        self.assertIsNotNone(decorated)
        policy = (decorated.payload.get("pm_review_policy") or {}) if decorated else {}
        self.assertEqual(policy.get("attention_class"), "needs_owner")
        self.assertIsNone(policy.get("recommended_resolution_mode"))

    def test_decorate_card_for_client_treats_owner_review_followup_as_fyi_once_decided(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="owner-review-followup-card",
            title="Schedule approved FEEZIE draft - FEEZIE-002",
            owner="Neo",
            status="todo",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id=None,
            payload={
                "workspace_key": "linkedin-os",
                "owner_review": {
                    "queue_id": "FEEZIE-002",
                    "title": "Quiet inefficiency is still failure",
                    "decision": "approve",
                    "draft_path": "drafts/feezie-002_quiet-inefficiency-is-still-failure.md",
                    "entry_kind": "queue",
                    "source_kind": "feezie_queue",
                },
                "execution": {
                    "lane": "codex",
                    "state": "queued",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        decorated = pm_card_service.decorate_card_for_client(card)

        self.assertIsNotNone(decorated)
        policy = (decorated.payload.get("pm_review_policy") or {}) if decorated else {}
        self.assertEqual(policy.get("attention_class"), "fyi")
        self.assertFalse(bool(policy.get("owner_decision_gate")))

    def test_decorate_card_for_client_treats_owner_review_followup_review_as_autonomous(self) -> None:
        now = datetime.now(timezone.utc)
        card = PMCard(
            id="owner-review-followup-review-card",
            title="Promote approved latent draft - The Shape of the Thing",
            owner="Neo",
            status="review",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id=None,
            payload={
                "workspace_key": "linkedin-os",
                "owner_review": {
                    "queue_id": "LATENT-THE-SHAPE-OF-THE-THING-B030F5",
                    "title": "The Shape of the Thing",
                    "decision": "approve",
                    "draft_path": "drafts/2026-04-10_the-shape-of-the-thing-latent-transform.md",
                    "entry_kind": "supplemental",
                    "source_kind": "latent_transform",
                },
                "execution": {
                    "lane": "codex",
                    "state": "review",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "last_transition_at": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )

        decorated = pm_card_service.decorate_card_for_client(card)

        self.assertIsNotNone(decorated)
        policy = (decorated.payload.get("pm_review_policy") or {}) if decorated else {}
        self.assertEqual(policy.get("attention_class"), "autonomous")
        self.assertFalse(bool(policy.get("owner_decision_gate")))
        self.assertEqual(policy.get("recommended_resolution_mode"), "close_and_spawn_next")

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
