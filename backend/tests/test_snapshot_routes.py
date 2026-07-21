from __future__ import annotations

import asyncio
import importlib
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.models import PMCard  # noqa: E402

brain_route_module = importlib.import_module("app.routes.brain")
workspace_route_module = importlib.import_module("app.routes.workspace")


class SnapshotRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @staticmethod
    def _queued_card(card_id: str = "brain-local-card") -> PMCard:
        now = datetime.now(timezone.utc)
        return PMCard(
            id=card_id,
            title="Brain local action",
            owner="Jean-Claude",
            status="todo",
            source="brain_local_action:test",
            payload={},
            created_at=now,
            updated_at=now,
        )

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
        snapshot_mock.assert_called_once_with(persisted_only=True)
        payload = response.json()
        self.assertEqual(((payload.get("refresh_status") or {}).get("last_run")), "2026-04-16T23:30:00+00:00")

    def test_workspace_snapshot_route_keeps_event_loop_responsive_during_sync_build(self) -> None:
        refresh_status = {
            "running": False,
            "last_run": datetime(2026, 4, 16, 23, 30, tzinfo=timezone.utc),
            "started_at": None,
            "error": None,
        }
        snapshot = {
            "source_assets": {"counts": {"total": 1}},
            "refresh_status": refresh_status,
        }
        service_thread_id: int | None = None

        def slow_snapshot_build(*, persisted_only: bool = False) -> dict:
            nonlocal service_thread_id
            self.assertTrue(persisted_only)
            service_thread_id = threading.get_ident()
            time.sleep(0.12)
            return snapshot

        async def exercise_route() -> tuple[dict, int, int]:
            event_loop_thread_id = threading.get_ident()
            finished = asyncio.Event()
            ticks = 0

            async def invoke() -> dict:
                try:
                    return await workspace_route_module.get_linkedin_os_snapshot()
                finally:
                    finished.set()

            async def heartbeat() -> None:
                nonlocal ticks
                while not finished.is_set():
                    ticks += 1
                    await asyncio.sleep(0.005)

            result, _ = await asyncio.gather(invoke(), heartbeat())
            return result, ticks, event_loop_thread_id

        with patch.object(
            workspace_route_module.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            side_effect=slow_snapshot_build,
        ) as snapshot_mock:
            result, ticks, event_loop_thread_id = asyncio.run(exercise_route())

        snapshot_mock.assert_called_once_with(persisted_only=True)
        self.assertIsNotNone(service_thread_id)
        self.assertNotEqual(service_thread_id, event_loop_thread_id)
        self.assertGreaterEqual(ticks, 5)
        self.assertEqual(result["source_assets"], {"counts": {"total": 1}})
        self.assertEqual(result["refresh_status"]["last_run"], "2026-04-16T23:30:00+00:00")

    def test_brain_ingest_long_form_route_queues_local_execution(self) -> None:
        card = self._queued_card("long-form-card")
        with patch.object(brain_route_module, "enqueue_brain_local_action", return_value=(card, "queued")) as enqueue:
            response = self.client.post(
                "/api/brain/ingest-long-form",
                json={
                    "url": "https://www.youtube.com/watch?v=brain123",
                    "title": "Live ingest route test",
                },
            )

        self.assertEqual(response.status_code, 200)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.args[0], "long_form_ingest")
        payload = response.json()
        self.assertTrue(payload.get("queued"))
        self.assertEqual(payload.get("card_id"), "long-form-card")

    def test_refresh_persona_review_route_queues_local_execution(self) -> None:
        card = self._queued_card("persona-refresh-card")
        with patch.object(brain_route_module, "enqueue_brain_local_action", return_value=(card, "queued")) as enqueue:
            response = self.client.post("/api/brain/refresh-persona-review")

        self.assertEqual(response.status_code, 200)
        enqueue.assert_called_once_with("refresh_persona_review", {})
        payload = response.json()
        self.assertTrue(payload.get("queued"))
        self.assertEqual(payload.get("job_id"), "persona-refresh-card")

    def test_workspace_image_upload_saves_image_inside_workspaces_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_workspaces_root = Path(tmpdir) / "workspaces"
            with patch.object(workspace_route_module, "WORKSPACES_ROOT", patched_workspaces_root):
                response = self.client.post(
                    "/api/workspace/artifacts/upload-image",
                    data={"path": "workspaces/linkedin-content-os/analytics/2026-05-01_feezie-012/confirmation.png"},
                    files={"image": ("confirmation.png", b"fake-png-bytes", "image/png")},
                )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload.get("path"), "workspaces/linkedin-content-os/analytics/2026-05-01_feezie-012/confirmation.png")
            saved_path = patched_workspaces_root / "linkedin-content-os" / "analytics" / "2026-05-01_feezie-012" / "confirmation.png"
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), b"fake-png-bytes")

    def test_workspace_image_upload_rejects_paths_outside_workspaces_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            patched_workspaces_root = Path(tmpdir) / "workspaces"
            with patch.object(workspace_route_module, "WORKSPACES_ROOT", patched_workspaces_root):
                response = self.client.post(
                    "/api/workspace/artifacts/upload-image",
                    data={"path": "../confirmation.png"},
                    files={"image": ("confirmation.png", b"fake-png-bytes", "image/png")},
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn("workspaces tree", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
