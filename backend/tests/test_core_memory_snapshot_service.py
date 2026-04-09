from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import (  # noqa: E402
    build_core_memory_snapshot,
    latest_snapshot_id,
    resolve_snapshot_fallback_path,
    restore_core_memory_snapshot,
)


class CoreMemorySnapshotServiceTest(unittest.TestCase):
    def test_build_resolve_and_restore_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            memory_root = workspace_root / "memory"
            docs_root = workspace_root / "docs"
            memory_root.mkdir(parents=True, exist_ok=True)
            docs_root.mkdir(parents=True, exist_ok=True)

            live_daily_briefs = memory_root / "daily-briefs.md"
            live_daily_briefs.write_text("# Daily Briefs\n\nCurrent brief.\n", encoding="utf-8")
            live_persistent = memory_root / "persistent_state.md"
            live_persistent.write_text("# Persistent State\n\nCurrent state.\n", encoding="utf-8")

            build_core_memory_snapshot(
                workspace_root,
                snapshot_id="2026-04-09",
                relative_paths=("memory/daily-briefs.md", "memory/persistent_state.md"),
            )

            self.assertEqual(latest_snapshot_id(workspace_root), "2026-04-09")

            live_daily_briefs.unlink()
            fallback = resolve_snapshot_fallback_path(workspace_root, "memory/daily-briefs.md")
            self.assertTrue(fallback.exists())
            self.assertIn("docs/runtime_snapshots/core_memory/2026-04-09", fallback.as_posix())
            self.assertIn("Current brief.", fallback.read_text(encoding="utf-8"))

            restore_result = restore_core_memory_snapshot(workspace_root, snapshot_id="2026-04-09")
            self.assertEqual(restore_result["count"], 2)
            self.assertTrue(live_daily_briefs.exists())
            self.assertIn("Current brief.", live_daily_briefs.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
