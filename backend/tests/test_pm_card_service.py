from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.pm_board import PMCard
from app.services.pm_card_service import build_execution_queue_entry


class PMCardServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
