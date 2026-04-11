from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.pm_board import PMCard  # noqa: E402
from app.models.standups import StandupEntry, StandupPromotionRequest  # noqa: E402
from app.services import standup_service  # noqa: E402


class StandupServiceTests(unittest.TestCase):
    def test_promote_standup_creates_queued_card_with_execution_contract(self) -> None:
        now = datetime.now(timezone.utc)
        standup_entry = StandupEntry(
            id="standup-123",
            owner="Jean-Claude",
            workspace_key="shared_ops",
            status="completed",
            blockers=[],
            commitments=[],
            needs=[],
            source="standup_prep",
            conversation_path=None,
            payload={},
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
            patch.object(standup_service, "create_standup", return_value=standup_entry),
            patch.object(standup_service.pm_card_service, "find_card_by_signature", return_value=None),
            patch.object(standup_service.pm_card_service, "find_active_card_by_title", return_value=None),
            patch.object(standup_service.pm_card_service, "create_card", side_effect=_fake_create_card),
        ):
            result = standup_service.promote_standup(
                StandupPromotionRequest(
                    owner="Jean-Claude",
                    workspace_key="shared_ops",
                    standup_kind="executive_ops",
                    summary="Test standup.",
                    pm_updates=[
                        {
                            "workspace_key": "shared_ops",
                            "scope": "shared_ops",
                            "owner_agent": "Jean-Claude",
                            "title": "Advance the standup-created lane",
                            "status": "todo",
                            "reason": "Created from a completed standup commitment.",
                            "payload": {},
                        }
                    ],
                )
            )

        self.assertEqual(len(result.created_cards), 1)
        self.assertEqual(len(created_cards), 1)
        created_payload = created_cards[0]
        execution = dict(created_payload.payload.get("execution") or {})
        self.assertEqual(execution.get("state"), "queued")
        self.assertTrue(str(execution.get("queued_at") or "").strip())
        self.assertEqual(created_payload.payload.get("completion_contract", {}).get("source"), "standup_promotion")
        self.assertTrue(created_payload.payload.get("completion_contract", {}).get("autostart"))
        self.assertGreaterEqual(len(created_payload.payload.get("instructions") or []), 1)
        self.assertGreaterEqual(len(created_payload.payload.get("acceptance_criteria") or []), 1)


if __name__ == "__main__":
    unittest.main()
