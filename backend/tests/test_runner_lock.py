from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

SCRIPT_PATH = WORKSPACE_ROOT / "scripts/runners/runner_lock.py"
SPEC = importlib.util.spec_from_file_location("runner_lock", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["runner_lock"] = MODULE
SPEC.loader.exec_module(MODULE)


class RunnerLockTests(unittest.TestCase):
    def test_runner_lock_rejects_second_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(MODULE, "LOCK_DIR", Path(tmpdir)):
                with MODULE.RunnerLock("codex_workspace_execution"):
                    with self.assertRaises(MODULE.RunnerLockUnavailable):
                        with MODULE.RunnerLock("codex_workspace_execution"):
                            pass

    def test_execute_with_runner_lock_mirrors_noop_locked(self) -> None:
        mirrored: list[dict] = []

        def fake_mirror(api_url: str, runs: list[dict]) -> bool:
            mirrored.extend(runs)
            return True

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(MODULE, "LOCK_DIR", Path(tmpdir)), patch.object(MODULE, "mirror_runs", fake_mirror):
                with MODULE.RunnerLock("pm_review_resolution"):
                    exit_code = MODULE.execute_with_runner_lock(
                        lock_name="pm_review_resolution",
                        automation_id="pm_review_resolution",
                        automation_name="PM Review Resolution",
                        default_api_url="https://example.test",
                        main_func=lambda: 99,
                    )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(mirrored), 1)
        self.assertEqual(mirrored[0]["metadata"]["result"], "noop_locked")
        self.assertFalse(mirrored[0]["action_required"])


if __name__ == "__main__":
    unittest.main()
