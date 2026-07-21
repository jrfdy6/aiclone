from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

workspace_snapshot_module = importlib.import_module("app.services.workspace_snapshot_service")


class WorkspaceSnapshotPersistenceTests(unittest.TestCase):
    def test_load_snapshot_returns_persisted_doc_entries_when_runtime_missing(self) -> None:
        persisted = {
            "generated_at": "2026-04-16T23:30:00+00:00",
            "workspace": "linkedin-content-os",
            "items": [
                {
                    "name": "persistent_memory_blueprint.md",
                    "path": "docs/persistent_memory_blueprint.md",
                    "group": "System Docs",
                    "updatedAt": "2026-04-16T23:29:00+00:00",
                }
            ],
            "counts": {"total": 1},
        }

        with patch.object(
            workspace_snapshot_module,
            "get_snapshot_payload",
            return_value=persisted,
        ), patch.object(
            workspace_snapshot_module,
            "_runtime_snapshot_payload",
            return_value=None,
        ):
            payload = workspace_snapshot_module._load_snapshot(workspace_snapshot_module.SNAPSHOT_DOC_ENTRIES)

        self.assertEqual(payload, persisted)

    def test_snapshot_service_extracts_wrapped_doc_and_workspace_items(self) -> None:
        refresh_status = {"running": False, "last_run": None, "started_at": None, "error": None}
        wrapped_workspace_files = {
            "generated_at": "2026-04-16T23:30:00+00:00",
            "workspace": "linkedin-content-os",
            "items": [
                {
                    "name": "claims.md",
                    "path": "knowledge/persona/feeze/identity/claims.md",
                    "group": "persona-bundle/identity",
                    "updatedAt": "2026-04-16T23:29:00+00:00",
                }
            ],
            "counts": {"total": 1},
        }
        wrapped_doc_entries = {
            "generated_at": "2026-04-16T23:31:00+00:00",
            "workspace": "linkedin-content-os",
            "items": [
                {
                    "name": "AGENTS.md",
                    "path": "AGENTS.md",
                    "group": "Operating Docs",
                    "updatedAt": "2026-04-16T23:28:00+00:00",
                }
            ],
            "counts": {"total": 1},
        }

        def fake_load_snapshot(snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_WORKSPACE_FILES:
                return wrapped_workspace_files
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_DOC_ENTRIES:
                return wrapped_doc_entries
            return None

        with patch.object(workspace_snapshot_module, "_load_snapshot", side_effect=fake_load_snapshot), patch.object(
            workspace_snapshot_module.social_feed_refresh_service,
            "get_status",
            return_value=refresh_status,
        ):
            snapshot = workspace_snapshot_module.workspace_snapshot_service.get_linkedin_os_snapshot()

        self.assertEqual(snapshot.get("workspace_files"), wrapped_workspace_files["items"])
        self.assertEqual(snapshot.get("doc_entries"), wrapped_doc_entries["items"])


if __name__ == "__main__":
    unittest.main()
