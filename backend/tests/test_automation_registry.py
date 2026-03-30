from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.automation_service import list_automations


class AutomationRegistryTests(unittest.TestCase):
    def test_includes_local_youtube_watchlist_auto_ingest(self) -> None:
        automations = list_automations()
        youtube_automation = next((item for item in automations if item.id == "youtube_watchlist_auto_ingest"), None)
        self.assertIsNotNone(youtube_automation)
        assert youtube_automation is not None
        self.assertEqual(youtube_automation.schedule, "Every 2 hours")
        self.assertEqual(youtube_automation.cron, "0 */2 * * *")
        self.assertEqual(youtube_automation.channel, "brain/youtube-watchlist")
        self.assertIn("openclaw", youtube_automation.metrics.get("framework", ""))
        self.assertIn("ollama -> gemini flash -> openai", youtube_automation.metrics.get("cheap_task_defaults", ""))


if __name__ == "__main__":
    unittest.main()
