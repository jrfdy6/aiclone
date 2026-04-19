from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PMCard, PersonaDelta  # noqa: E402
from app.services import brain_system_route_service  # noqa: E402


class BrainSystemRouteServiceTests(unittest.TestCase):
    def test_create_pm_route_autostarts_and_includes_execution_contract(self) -> None:
        now = datetime.now(timezone.utc)
        delta = PersonaDelta(
            id="delta-123",
            capture_id="capture-123",
            persona_target="feezie",
            trait="Operator clarity matters more than model price.",
            status="reviewed",
            metadata={},
            created_at=now,
        )

        created_cards: list[object] = []

        def _fake_create_card(payload):
            created_cards.append(payload)
            return PMCard(
                id="pm-card-1",
                title=payload.title,
                owner=payload.owner,
                status=payload.status,
                source=payload.source,
                link_type=payload.link_type,
                link_id=payload.link_id,
                payload=payload.payload,
                created_at=now,
                updated_at=now,
            )

        with (
            patch.object(brain_system_route_service.pm_card_service, "find_card_by_signature", return_value=None),
            patch.object(brain_system_route_service.pm_card_service, "find_active_card_by_title", return_value=None),
            patch.object(brain_system_route_service.pm_card_service, "create_card", side_effect=_fake_create_card),
        ):
            result = brain_system_route_service._create_pm_route(
                delta=delta,
                workspace_key="shared_ops",
                summary="Reviewed operator signal.",
                selected_items=[{"id": "item-1", "text": "Use concrete operator proof."}],
                pm_title="Operationalize reviewed signal",
            )

        self.assertEqual(result.id, "pm-card-1")
        self.assertEqual(len(created_cards), 1)
        created_payload = created_cards[0]
        execution = dict(created_payload.payload.get("execution") or {})
        self.assertEqual(execution.get("state"), "queued")
        self.assertTrue(str(execution.get("queued_at") or "").strip())
        self.assertEqual(created_payload.payload.get("completion_contract", {}).get("source"), "brain_triage")
        self.assertTrue(created_payload.payload.get("completion_contract", {}).get("autostart"))
        self.assertGreaterEqual(len(created_payload.payload.get("instructions") or []), 1)
        self.assertGreaterEqual(len(created_payload.payload.get("acceptance_criteria") or []), 1)
        self.assertTrue(created_payload.payload.get("route_guardrail", {}).get("ok"))
        self.assertTrue(str(created_payload.payload.get("why_pm_now") or "").strip())
        self.assertEqual(created_payload.payload.get("source_signal", {}).get("kind"), "persona_delta")
        self.assertTrue(created_payload.payload.get("writeback_requirements", {}).get("require_writeback"))
        self.assertEqual(created_payload.owner, "Jean-Claude")

    def test_create_pm_route_rejects_advisory_title(self) -> None:
        now = datetime.now(timezone.utc)
        delta = PersonaDelta(
            id="delta-456",
            capture_id="capture-456",
            persona_target="feezie",
            trait="A signal that should not become vague PM work.",
            status="reviewed",
            metadata={},
            created_at=now,
        )

        with self.assertRaises(ValueError) as context:
            brain_system_route_service._create_pm_route(
                delta=delta,
                workspace_key="shared_ops",
                summary="Reviewed operator signal.",
                selected_items=[],
                pm_title="Review this signal later",
            )

        self.assertIn("advisory", str(context.exception).lower())

    def test_create_pm_route_rejects_duplicate_active_card(self) -> None:
        now = datetime.now(timezone.utc)
        delta = PersonaDelta(
            id="delta-789",
            capture_id="capture-789",
            persona_target="feezie",
            trait="A signal that already has PM work.",
            status="reviewed",
            metadata={},
            created_at=now,
        )
        existing = PMCard(
            id="pm-existing",
            title="Operationalize existing signal",
            owner="Jean-Claude",
            status="todo",
            source="brain-triage:delta-789:shared_ops",
            link_type="persona_delta",
            link_id=delta.id,
            payload={"workspace_key": "shared_ops"},
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(brain_system_route_service.pm_card_service, "find_card_by_signature", return_value=existing),
            patch.object(brain_system_route_service.pm_card_service, "find_active_card_by_title", return_value=None),
            patch.object(brain_system_route_service.pm_card_service, "create_card") as create_mock,
        ):
            with self.assertRaises(ValueError) as context:
                brain_system_route_service._create_pm_route(
                    delta=delta,
                    workspace_key="shared_ops",
                    summary="Reviewed operator signal.",
                    selected_items=[],
                    pm_title="Operationalize existing signal",
                )

        create_mock.assert_not_called()
        self.assertIn("duplicate", str(context.exception).lower())

    def test_validate_brain_pm_route_requires_writeback_contract(self) -> None:
        result = brain_system_route_service.validate_brain_pm_route(
            title="Operationalize reviewed signal",
            workspace_key="shared_ops",
            summary="Reviewed operator signal.",
            owner="Jean-Claude",
            why_pm_now="Brain has enough review context to make this executable now.",
            acceptance_criteria=["The result creates a concrete workspace artifact with a bounded summary."],
            completion_contract={"writeback_required": False, "result_requirements": {}},
            source_signal={"kind": "persona_delta", "delta_id": "delta-1"},
        )

        self.assertFalse(result["ok"])
        self.assertIn("write-back", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
