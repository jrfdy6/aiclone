from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.services.social_feed_builder_service import build_feed
from app.services.workspace_snapshot_service import workspace_snapshot_service


class WorkspaceSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_social_feed_builder_returns_rich_items(self) -> None:
        feed = build_feed()
        items = feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertTrue(feed.get("generated_at"))

    def test_workspace_snapshot_service_returns_live_sections(self) -> None:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
        social_feed = snapshot.get("social_feed") or {}
        items = social_feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertIn("feedback_summary", snapshot)
        self.assertIn("refresh_status", snapshot)

    def test_health_route(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "healthy")

    def test_workspace_snapshot_route(self) -> None:
        response = self.client.get("/api/workspace/linkedin-os-snapshot")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        social_feed = payload.get("social_feed") or {}
        items = social_feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))

    def test_ingest_signal_route(self) -> None:
        response = self.client.post(
            "/api/workspace/ingest-signal",
            json={
                "text": "AI agents fail from lack of context, not lack of smarts. Teams need cleaner workflow context.",
                "priority_lane": "ai",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        preview_item = payload.get("preview_item") or {}
        self.assertTrue(preview_item.get("lens_variants"))
        self.assertIn("title", preview_item)


if __name__ == "__main__":
    unittest.main()
