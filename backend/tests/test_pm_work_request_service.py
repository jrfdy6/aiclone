from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from app.models import (
    ExecutionQueueEntry,
    PMCard,
    PMCardDispatchResult,
    PMWorkRequestCreate,
)
from app.services import pm_work_request_service as service
from app.services.workspace_registry_service import workspace_registry_entries
from app.services.workspace_runtime_contract_service import execution_defaults_for_workspace


def _card(*, card_id: str = "card-1", workspace_key: str = "shared_ops", state: str = "ready") -> PMCard:
    now = datetime.now(timezone.utc)
    return PMCard(
        id=card_id,
        title="Deliver the requested outcome",
        owner="Neo",
        status="todo",
        source=service.REQUEST_SOURCE,
        payload={
            "workspace_key": workspace_key,
            "execution": {
                "state": state,
                "manager_agent": "Jean-Claude",
                "target_agent": "Jean-Claude",
                "execution_mode": "direct",
            },
        },
        created_at=now,
        updated_at=now,
    )


def _queue_entry(card: PMCard, *, workspace_key: str, state: str, target_agent: str) -> ExecutionQueueEntry:
    return ExecutionQueueEntry(
        card_id=card.id,
        title=card.title,
        workspace_key=workspace_key,
        pm_status=card.status,
        execution_state=state,
        manager_agent="Jean-Claude",
        target_agent=target_agent,
        execution_mode="direct" if target_agent == "Jean-Claude" else "delegated",
        lane="codex",
    )


class PMWorkRequestServiceTests(unittest.TestCase):
    def _request(self, **updates: object) -> PMWorkRequestCreate:
        values: dict[str, object] = {
            "request_id": uuid4(),
            "workspace_key": "shared_ops",
            "outcome": "Turn the executive request into a bounded, verified result.",
            "context": "Keep the existing runner and return proof to PM.",
            "approved_for_queue": True,
        }
        values.update(updates)
        return PMWorkRequestCreate(**values)

    def test_enqueues_one_signed_front_door_request(self) -> None:
        created_payloads = []
        ready_card = _card()
        queued_entry = _queue_entry(ready_card, workspace_key="shared_ops", state="queued", target_agent="Jean-Claude")

        def fake_create(payload):
            created_payloads.append(payload)
            return ready_card.model_copy(update={"title": payload.title, "payload": payload.payload})

        def fake_dispatch(card_id, payload):
            self.assertEqual(card_id, ready_card.id)
            self.assertEqual(payload.execution_state, "queued")
            self.assertEqual(payload.requested_by, "Neo")
            queued_card = ready_card.model_copy(update={"payload": created_payloads[0].payload})
            return PMCardDispatchResult(card=queued_card, queue_entry=queued_entry)

        with (
            patch.object(service, "execution_signing_configured", return_value=True),
            patch.object(service.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(service.pm_card_service, "create_card", side_effect=fake_create),
            patch.object(service.pm_card_service, "build_execution_queue_entry", return_value=_queue_entry(ready_card, workspace_key="shared_ops", state="ready", target_agent="Jean-Claude")),
            patch.object(service.pm_card_service, "dispatch_card", side_effect=fake_dispatch),
            patch.object(service.pm_card_service, "decorate_card_for_client", side_effect=lambda card: card),
        ):
            result = service.enqueue_work_request(self._request())

        self.assertEqual(result.disposition, "queued")
        self.assertEqual(result.queue_entry.execution_state, "queued")
        self.assertEqual(len(created_payloads), 1)
        created = created_payloads[0]
        self.assertEqual(created.owner, "Neo")
        self.assertEqual(created.source, "codex_native:remote_queue")
        self.assertEqual(created.payload["front_door_agent"], "Neo")
        self.assertTrue(created.payload["queue_approval"]["approved"])
        self.assertEqual(created.payload["execution"]["state"], "ready")
        self.assertEqual(created.payload["trigger_origin"], "codex_native_remote_queue")
        self.assertTrue(str(created.payload["trigger_key"]).startswith("codex:request-work:"))
        self.assertTrue(created.payload["completion_contract"]["writeback_required"])

    def test_work_life_tools_uses_registry_agent_routing(self) -> None:
        request = self._request(workspace_key="work-life-tools")
        ready_card = _card(workspace_key="work-life-tools")
        ready_entry = _queue_entry(
            ready_card,
            workspace_key="work-life-tools",
            state="ready",
            target_agent="Work Life Tools Operator Agent",
        )
        queued_entry = ready_entry.model_copy(update={"execution_state": "queued"})
        captured = []

        with (
            patch.object(service, "execution_signing_configured", return_value=True),
            patch.object(service.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(service.pm_card_service, "create_card", side_effect=lambda payload: captured.append(payload) or ready_card),
            patch.object(service.pm_card_service, "build_execution_queue_entry", return_value=ready_entry),
            patch.object(
                service.pm_card_service,
                "dispatch_card",
                return_value=PMCardDispatchResult(card=ready_card, queue_entry=queued_entry),
            ),
            patch.object(service.pm_card_service, "decorate_card_for_client", side_effect=lambda card: card),
        ):
            result = service.enqueue_work_request(request)

        self.assertEqual(result.routing.workspace_key, "work-life-tools")
        self.assertEqual(result.routing.target_agent, "Work Life Tools Operator Agent")
        self.assertEqual(result.routing.execution_mode, "delegated")
        self.assertEqual(captured[0].payload["execution"]["target_agent"], "Work Life Tools Operator Agent")

    def test_retry_returns_existing_active_request_without_requeueing(self) -> None:
        request = self._request()
        existing = _card(state="running")
        running_entry = _queue_entry(existing, workspace_key="shared_ops", state="running", target_agent="Jean-Claude")

        with (
            patch.object(service, "execution_signing_configured", return_value=True),
            patch.object(service.pm_card_service, "find_active_card_by_trigger_key", return_value=existing),
            patch.object(service.pm_card_service, "build_execution_queue_entry", return_value=running_entry),
            patch.object(service.pm_card_service, "create_card") as create_card,
            patch.object(service.pm_card_service, "dispatch_card") as dispatch_card,
            patch.object(service.pm_card_service, "decorate_card_for_client", side_effect=lambda card: card),
        ):
            result = service.enqueue_work_request(request)

        self.assertEqual(result.disposition, "already_active")
        self.assertEqual(result.queue_entry.execution_state, "running")
        create_card.assert_not_called()
        dispatch_card.assert_not_called()

    def test_rejects_unknown_workspace_before_creating_card(self) -> None:
        with (
            patch.object(service, "execution_signing_configured", return_value=True),
            patch.object(service.pm_card_service, "create_card") as create_card,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown project workspace"):
                service.enqueue_work_request(self._request(workspace_key="made-up-project"))
        create_card.assert_not_called()

    def test_fails_closed_when_job_signing_is_unavailable(self) -> None:
        with (
            patch.object(service, "execution_signing_configured", return_value=False),
            patch.object(service.pm_card_service, "create_card") as create_card,
        ):
            with self.assertRaisesRegex(RuntimeError, "signed Codex work queue"):
                service.enqueue_work_request(self._request())
        create_card.assert_not_called()

    def test_runtime_defaults_match_registry_for_every_workspace(self) -> None:
        for entry in workspace_registry_entries():
            defaults = execution_defaults_for_workspace(str(entry["key"]))
            self.assertEqual(defaults["manager_agent"], entry["manager_agent"], entry["key"])
            self.assertEqual(defaults["target_agent"], entry["target_agent"], entry["key"])
            self.assertEqual(defaults["workspace_agent"], entry["workspace_agent"], entry["key"])
            self.assertEqual(defaults["execution_mode"], entry["execution_mode"], entry["key"])


if __name__ == "__main__":
    unittest.main()
