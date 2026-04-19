from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import (  # noqa: E402
    build_core_memory_snapshot,
    expected_memory_read_mode,
    latest_snapshot_id,
    resolve_memory_read_target,
    resolve_live_memory_write_path,
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
            runtime_persistent = resolve_live_memory_write_path(workspace_root, "memory/persistent_state.md")
            runtime_persistent.parent.mkdir(parents=True, exist_ok=True)
            runtime_persistent.write_text("# Persistent State\n\nCurrent state.\n", encoding="utf-8")

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

            runtime_fallback = resolve_snapshot_fallback_path(workspace_root, "memory/persistent_state.md")
            self.assertEqual(runtime_fallback, runtime_persistent)
            self.assertIn("Current state.", runtime_fallback.read_text(encoding="utf-8"))

            runtime_persistent.unlink()
            restore_result = restore_core_memory_snapshot(workspace_root, snapshot_id="2026-04-09")
            self.assertEqual(restore_result["count"], 2)
            self.assertTrue(live_daily_briefs.exists())
            self.assertTrue(runtime_persistent.exists())
            self.assertIn("Current brief.", live_daily_briefs.read_text(encoding="utf-8"))
            self.assertIn("Current state.", runtime_persistent.read_text(encoding="utf-8"))

    def test_resolve_memory_read_target_reports_expected_and_fallback_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "memory").mkdir(parents=True, exist_ok=True)
            (workspace_root / "docs").mkdir(parents=True, exist_ok=True)

            runtime_path = resolve_live_memory_write_path(workspace_root, "memory/persistent_state.md")
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("runtime\n", encoding="utf-8")
            live_daily_briefs = workspace_root / "memory" / "daily-briefs.md"
            live_daily_briefs.write_text("live\n", encoding="utf-8")

            runtime_target = resolve_memory_read_target(workspace_root, "memory/persistent_state.md")
            self.assertEqual(expected_memory_read_mode("memory/persistent_state.md"), "runtime")
            self.assertEqual(runtime_target["expected_mode"], "runtime")
            self.assertEqual(runtime_target["resolved_mode"], "runtime")
            self.assertFalse(runtime_target["fallback_active"])

            build_core_memory_snapshot(
                workspace_root,
                snapshot_id="2026-04-17",
                relative_paths=("memory/daily-briefs.md",),
            )
            live_daily_briefs.unlink()
            snapshot_target = resolve_memory_read_target(workspace_root, "memory/daily-briefs.md")
            self.assertEqual(expected_memory_read_mode("memory/daily-briefs.md"), "live")
            self.assertEqual(snapshot_target["expected_mode"], "live")
            self.assertEqual(snapshot_target["resolved_mode"], "snapshot")
            self.assertTrue(snapshot_target["fallback_active"])
            self.assertEqual(snapshot_target["snapshot_id"], "2026-04-17")

            runtime_path.unlink()
            missing_target = resolve_memory_read_target(workspace_root, "memory/persistent_state.md")
            self.assertEqual(missing_target["resolved_mode"], "missing")
            self.assertTrue(missing_target["fallback_active"])

    def test_resolve_memory_read_target_flags_runtime_sync_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            memory_root = workspace_root / "memory"
            memory_root.mkdir(parents=True, exist_ok=True)
            (workspace_root / "docs").mkdir(parents=True, exist_ok=True)

            runtime_path = resolve_live_memory_write_path(workspace_root, "memory/persistent_state.md")
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text("runtime\n", encoding="utf-8")
            live_path = memory_root / "persistent_state.md"
            live_path.write_text("live\n", encoding="utf-8")

            older = runtime_path.stat().st_mtime
            newer = older + 7200
            os.utime(live_path, (newer, newer))
            os.utime(runtime_path, (older, older))

            target = resolve_memory_read_target(workspace_root, "memory/persistent_state.md")

        self.assertEqual(target["resolved_mode"], "runtime")
        self.assertFalse(target["fallback_active"])
        self.assertTrue(target["runtime_out_of_sync"])
        self.assertGreater(target["live_newer_by_hours"], 0)


if __name__ == "__main__":
    unittest.main()
