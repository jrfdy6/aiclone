from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import brain_control_plane_service  # noqa: E402


class BrainControlPlaneServiceTests(unittest.TestCase):
    def test_build_brain_control_plane_uses_live_workspace_snapshot(self) -> None:
        workspace_snapshot = {
            "doc_entries": [{"path": "docs/example.md"}],
            "workspace_files": [{"path": "knowledge/persona/feeze/identity/claims.md"}],
            "persona_review_summary": {"counts": {"brain_pending_review": 3, "workspace_saved": 2}},
            "source_assets": {"counts": {"total": 9}},
        }
        brain_memory_sync = {"queued_route_count": 4}
        health = SimpleNamespace(model_dump=lambda: {"database_connected": True, "search_ready": True})

        with patch.object(brain_control_plane_service, "list_automations", return_value=[SimpleNamespace(status="active")]) as list_mock, patch.object(
            brain_control_plane_service.open_brain_metrics,
            "fetch_metrics",
            return_value={"captures": {"total": 11}, "vectors": {}, "recent_captures": []},
        ), patch.object(
            brain_control_plane_service.open_brain_service,
            "fetch_health",
            return_value=health,
        ), patch.object(
            brain_control_plane_service.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            return_value=workspace_snapshot,
        ) as snapshot_mock, patch.object(
            brain_control_plane_service,
            "get_snapshot_payload",
            return_value=brain_memory_sync,
        ):
            payload = brain_control_plane_service.build_brain_control_plane()

        list_mock.assert_called_once_with()
        snapshot_mock.assert_called_once_with()
        self.assertEqual((payload.get("summary") or {}).get("pending_review_count"), 3)
        self.assertEqual((payload.get("summary") or {}).get("workspace_saved_count"), 2)
        self.assertEqual((payload.get("summary") or {}).get("doc_count"), 1)
        self.assertEqual((payload.get("summary") or {}).get("workspace_file_count"), 1)
        self.assertEqual((payload.get("summary") or {}).get("brain_memory_sync_queue_count"), 4)
        self.assertEqual((payload.get("workspace_snapshot") or {}).get("doc_entries"), workspace_snapshot["doc_entries"])


if __name__ == "__main__":
    unittest.main()
