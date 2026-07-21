from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from automation_run_mirror import append_local_runs, mirror_runs  # noqa: E402


class AutomationRunMirrorLocalTests(unittest.TestCase):
    def test_append_local_runs_preserves_network_independent_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runs.jsonl"
            append_local_runs(
                [
                    {
                        "id": "run-1",
                        "automation_id": "memory_index",
                        "automation_name": "Memory Index",
                        "status": "ok",
                    }
                ],
                path,
            )
            payload = json.loads(path.read_text().strip())

        self.assertEqual(payload["id"], "run-1")
        self.assertIn("locally_recorded_at", payload["metadata"])

    def test_mirror_requires_truthful_success_count(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"success":true,"count":0}'
        response.__exit__.return_value = False
        run = {
            "id": "run-1",
            "automation_id": "memory_index",
            "automation_name": "Memory Index",
            "source": "local_launchd_registry",
            "runtime": "launchd",
            "status": "ok",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "automation_run_mirror.AUTOMATION_RUNS_ROOT", Path(temp_dir)
        ), patch("automation_run_mirror.urllib.request.urlopen", return_value=response):
            self.assertFalse(mirror_runs("https://example.invalid", [run]))


if __name__ == "__main__":
    unittest.main()
