from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "build_dream_cycle_snapshot.py"
SCRIPTS_ROOT = REPO_ROOT / "scripts"


def load_module():
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location("build_dream_cycle_snapshot", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuildDreamCycleSnapshotTests(unittest.TestCase):
    def test_write_payload_updates_runtime_lane_without_recreating_tracked_live_file(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            live_path = root / "memory" / "persistent_state.md"
            runtime_path = root / "memory" / "runtime" / "persistent_state.md"
            dream_cycle_log_path = root / "memory" / "dream_cycle_log.md"
            payload = {
                "snapshot_markdown": "# Snapshot for April 25, 2026\n",
                "log_markdown": f"# Dream Cycle Log - {module._long_date()}\n\n- Runtime-only update\n",
            }

            with mock.patch.object(module, "RUNTIME_PERSISTENT_STATE_PATH", runtime_path), mock.patch.object(
                module,
                "DREAM_CYCLE_LOG_PATH",
                dream_cycle_log_path,
            ):
                module.write_payload(payload)

            self.assertFalse(live_path.exists())
            self.assertEqual(runtime_path.read_text(encoding="utf-8"), payload["snapshot_markdown"])
            self.assertIn("Runtime-only update", dream_cycle_log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
