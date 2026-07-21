from __future__ import annotations

import importlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import (  # noqa: E402
    BrainPersonaRerouteRequest,
    BrainPersonaReviewRequest,
    BrainSystemRouteRequest,
    PMCard,
    PersonaDelta,
    StandupEntry,
)
from app.models.brain import PromotionItemPayload  # noqa: E402
from app.services import brain_system_route_service  # noqa: E402


brain_routes = importlib.import_module("app.routes.brain")


class BrainSystemRouteServiceTests(unittest.TestCase):
    def test_route_id_is_order_stable_but_changes_for_materially_different_route(self) -> None:
        common = {
            "delta_id": "delta-route-id",
            "workspace_key": "shared_ops",
            "summary": "A durable route summary.",
            "route_to_standup": True,
            "standup_kind": "executive_ops",
            "route_to_pm": True,
            "pm_title": "Operationalize durable route summary",
        }
        first = brain_system_route_service.build_brain_route_id(
            **common,
            selected_items=[{"id": "b", "content": "Second"}, {"id": "a", "content": "First"}],
            canonical_memory_targets=["learnings", "chronicle"],
        )
        reordered = brain_system_route_service.build_brain_route_id(
            **common,
            selected_items=[{"id": "a", "content": "First"}, {"id": "b", "content": "Second"}],
            canonical_memory_targets=["chronicle", "learnings"],
        )
        changed = brain_system_route_service.build_brain_route_id(
            **{**common, "summary": "A materially different route summary."},
            selected_items=[{"id": "a", "content": "First"}, {"id": "b", "content": "Second"}],
            canonical_memory_targets=["chronicle", "learnings"],
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)
        self.assertLessEqual(len(first), 80)

    def test_route_retry_reuses_effects_and_dedupes_metadata_after_update_outage(self) -> None:
        now = datetime.now(timezone.utc)
        current_delta = PersonaDelta(
            id="delta-retry",
            capture_id="capture-retry",
            persona_target="feezie",
            trait="Retry-safe routes matter.",
            status="reviewed",
            metadata={},
            created_at=now,
        )
        standups: list[StandupEntry] = []
        cards: list[PMCard] = []
        fail_update = True

        def create_standup(payload):
            entry = StandupEntry(
                id=f"standup-{len(standups) + 1}",
                owner=payload.owner,
                workspace_key=payload.workspace_key,
                status=payload.status,
                needs=payload.needs,
                source=payload.source,
                payload=payload.payload,
                created_at=now,
            )
            standups.append(entry)
            return entry

        def create_card(payload):
            card = PMCard(
                id=f"pm-{len(cards) + 1}",
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
            cards.append(card)
            return card

        def update_delta(_delta_id, update):
            nonlocal current_delta, fail_update
            if fail_update:
                fail_update = False
                raise RuntimeError("metadata write unavailable")
            current_delta = current_delta.model_copy(
                update={"metadata": {**current_delta.metadata, **dict(update.metadata or {})}}
            )
            return current_delta

        route_kwargs = {
            "reflection_excerpt": "Route this safely and exactly once.",
            "selected_promotion_items": [{"id": "item-1", "content": "Durable fragment"}],
            "workspace_key": "shared_ops",
            "workspace_keys": ["shared_ops"],
            "canonical_memory_targets": ["learnings", "chronicle"],
            "route_to_standup": True,
            "standup_kind": "executive_ops",
            "route_to_pm": True,
            "pm_title": "Operationalize retry safe route",
        }
        with (
            patch.object(brain_system_route_service.persona_delta_service, "get_delta", side_effect=lambda _id: current_delta),
            patch.object(brain_system_route_service.persona_delta_service, "update_delta", side_effect=update_delta),
            patch.object(brain_system_route_service.standup_service, "list_standups", side_effect=lambda **_kwargs: list(standups)),
            patch.object(
                brain_system_route_service.standup_service,
                "get_standup",
                side_effect=lambda entry_id: next((item for item in standups if item.id == entry_id), None),
            ),
            patch.object(brain_system_route_service.standup_service, "create_standup", side_effect=create_standup),
            patch.object(
                brain_system_route_service.pm_card_service,
                "find_card_by_signature",
                side_effect=lambda title, source: next(
                    (item for item in cards if item.title == title and item.source == source),
                    None,
                ),
            ),
            patch.object(
                brain_system_route_service.pm_card_service,
                "get_card",
                side_effect=lambda card_id: next((item for item in cards if item.id == card_id), None),
            ),
            patch.object(brain_system_route_service.pm_card_service, "create_card", side_effect=create_card),
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata write unavailable"):
                brain_system_route_service.route_delta_signal("delta-retry", **route_kwargs)

            second = brain_system_route_service.route_delta_signal("delta-retry", **route_kwargs)
            current_delta = current_delta.model_copy(
                update={
                    "metadata": {
                        **current_delta.metadata,
                        "brain_route_history": [
                            *current_delta.metadata["brain_route_history"],
                            dict(current_delta.metadata["brain_route_history"][0]),
                        ],
                        "pending_canonical_memory_routes": [
                            *current_delta.metadata["pending_canonical_memory_routes"],
                            dict(current_delta.metadata["pending_canonical_memory_routes"][0]),
                        ],
                    }
                }
            )
            third = brain_system_route_service.route_delta_signal("delta-retry", **route_kwargs)
            changed = brain_system_route_service.route_delta_signal(
                "delta-retry",
                **{**route_kwargs, "reflection_excerpt": "Route this into a materially different outcome."},
            )

        self.assertEqual(len(standups), 2)
        self.assertEqual(len(cards), 2)
        self.assertTrue(second[4][0]["standup_reused"])
        self.assertTrue(second[4][0]["pm_card_reused"])
        self.assertTrue(third[4][0]["standup_reused"])
        self.assertTrue(third[4][0]["pm_card_reused"])
        self.assertFalse(changed[4][0]["standup_reused"])
        self.assertFalse(changed[4][0]["pm_card_reused"])
        self.assertEqual(len(current_delta.metadata["brain_route_history"]), 2)
        self.assertEqual(len(current_delta.metadata["pending_canonical_memory_routes"]), 2)
        self.assertEqual(
            current_delta.metadata["brain_route_history"][0]["route_id"],
            standups[0].payload["brain_route_id"],
        )
        self.assertEqual(cards[0].payload["brain_route_id"], standups[0].payload["brain_route_id"])

    def test_system_route_request_is_bounded_and_rejects_irrelevant_fields(self) -> None:
        with self.assertRaises(ValidationError):
            BrainSystemRouteRequest(
                reflection_excerpt="Route this.",
                canonical_memory_targets=["learnings"],
                unexpected="not-allowed",
            )
        with self.assertRaises(ValidationError):
            BrainSystemRouteRequest(
                reflection_excerpt="Route this.",
                canonical_memory_targets=["learnings"],
                workspace_keys=[f"workspace-{index}" for index in range(13)],
            )
        with self.assertRaises(ValidationError):
            BrainSystemRouteRequest(
                reflection_excerpt="Route this.",
                canonical_memory_targets=["learnings"],
                pm_title="Operationalize irrelevant title",
            )
        with self.assertRaises(ValidationError):
            PromotionItemPayload(
                id="item-1",
                kind="framework",
                label="Bounded item",
                content="Bounded content",
                leverageSignal="x" * 2_001,
            )
        with self.assertRaises(ValidationError):
            BrainPersonaReviewRequest(reflection_excerpt="x" * 20_001)
        with self.assertRaises(ValidationError):
            BrainPersonaRerouteRequest(target_file="x" * 501)

    def test_system_route_masks_unexpected_internal_error(self) -> None:
        payload = BrainSystemRouteRequest(
            reflection_excerpt="Route this.",
            canonical_memory_targets=["learnings"],
        )
        with (
            patch.object(brain_routes, "route_delta_signal", side_effect=RuntimeError("database password leaked")),
            patch.object(brain_routes.logger, "exception") as log,
        ):
            with self.assertRaises(HTTPException) as raised:
                brain_routes.route_brain_signal("delta-secret", payload)

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, "Brain system route could not be completed.")
        self.assertNotIn("password", raised.exception.detail)
        log.assert_called_once()

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
        self.assertTrue(str(created_payload.payload.get("brain_route_id") or "").startswith("brain-route-v1-"))
        self.assertEqual(created_payload.payload.get("source_signal", {}).get("brain_route_id"), created_payload.payload["brain_route_id"])

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

    def test_create_pm_route_reuses_same_deterministic_route_card(self) -> None:
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
        route_id = brain_system_route_service.build_brain_route_id(
            delta_id=delta.id,
            workspace_key="shared_ops",
            summary="Reviewed operator signal.",
            selected_items=[],
            canonical_memory_targets=[],
            route_to_standup=False,
            standup_kind=None,
            route_to_pm=True,
            pm_title="Operationalize existing signal",
        )
        existing = PMCard(
            id="pm-existing",
            title="Operationalize existing signal",
            owner="Jean-Claude",
            status="todo",
            source=f"brain-triage:{route_id}",
            link_type="persona_delta",
            link_id=delta.id,
            payload={"workspace_key": "shared_ops", "brain_route_id": route_id},
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(brain_system_route_service.pm_card_service, "find_card_by_signature", return_value=existing),
            patch.object(brain_system_route_service.pm_card_service, "create_card") as create_mock,
        ):
            result = brain_system_route_service._create_pm_route(
                delta=delta,
                workspace_key="shared_ops",
                summary="Reviewed operator signal.",
                selected_items=[],
                pm_title="Operationalize existing signal",
            )

        create_mock.assert_not_called()
        self.assertEqual(result.id, "pm-existing")

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
