from __future__ import annotations

import importlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402

brain_route_module = importlib.import_module("app.routes.brain")
workspace_route_module = importlib.import_module("app.routes.workspace")


class SnapshotRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_workspace_snapshot_route_uses_live_snapshot_service(self) -> None:
        refresh_status = {
            "running": False,
            "last_run": datetime(2026, 4, 16, 23, 30, tzinfo=timezone.utc),
            "started_at": None,
            "error": None,
        }
        snapshot = {
            "source_assets": {"counts": {"total": 1}},
            "social_feed": {"items": [{"title": "live item"}]},
            "persona_review_summary": {"counts": {"brain_pending_review": 2}},
            "refresh_status": refresh_status,
        }

        with patch.object(workspace_route_module.workspace_snapshot_service, "get_linkedin_os_snapshot", return_value=snapshot) as snapshot_mock:
            response = self.client.get("/api/workspace/linkedin-os-snapshot")

        self.assertEqual(response.status_code, 200)
        snapshot_mock.assert_called_once_with()
        payload = response.json()
        self.assertEqual(((payload.get("refresh_status") or {}).get("last_run")), "2026-04-16T23:30:00+00:00")

    def test_brain_ingest_long_form_route_reads_live_snapshot_after_register(self) -> None:
        snapshot = {
            "source_assets": {"counts": {"total": 3}},
            "content_reservoir": {"counts": {"total": 2}},
            "long_form_routes": {"route_counts": {"post_seed": 1}},
            "persona_review_summary": {"counts": {"brain_pending_review": 1}},
        }
        result = {
            "asset_id": "asset-123",
            "source_channel": "youtube",
            "source_type": "youtube_transcript",
        }

        with patch.object(brain_route_module.brain_long_form_ingest_service, "register_source", return_value=result), patch.object(
            brain_route_module.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            return_value=snapshot,
        ) as snapshot_mock:
            response = self.client.post(
                "/api/brain/ingest-long-form",
                json={
                    "url": "https://www.youtube.com/watch?v=brain123",
                    "title": "Live ingest route test",
                },
            )

        self.assertEqual(response.status_code, 200)
        snapshot_mock.assert_called_once_with(include_workspace_files=False, include_doc_entries=False)
        payload = response.json()
        self.assertEqual(((payload.get("source_assets") or {}).get("counts") or {}).get("total"), 3)

    def test_refresh_persona_review_route_reads_live_snapshot_after_refresh(self) -> None:
        snapshot = {
            "persona_review_summary": {"counts": {"brain_pending_review": 4}},
            "source_assets": {"counts": {"total": 8}},
        }

        with patch.object(
            brain_route_module.workspace_snapshot_service,
            "refresh_persisted_linkedin_os_state",
            return_value={"persona_review_summary": {"counts": {"brain_pending_review": 4}}},
        ), patch.object(
            brain_route_module.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            return_value=snapshot,
        ) as snapshot_mock:
            response = self.client.post("/api/brain/refresh-persona-review")

        self.assertEqual(response.status_code, 200)
        snapshot_mock.assert_called_once_with(include_workspace_files=False, include_doc_entries=False)
        payload = response.json()
        self.assertEqual((((payload.get("persona_review_summary") or {}).get("counts") or {}).get("brain_pending_review")), 4)


if __name__ == "__main__":
    unittest.main()
