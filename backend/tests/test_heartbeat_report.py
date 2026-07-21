from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
BACKEND_ROOT = ROOT / "backend"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HeartbeatReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for path in (SCRIPTS_ROOT, BACKEND_ROOT):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        cls.report = _load_module("heartbeat_report", SCRIPTS_ROOT / "heartbeat_report.py")

    def test_analyze_runtime_tracks_latest_run_and_window_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_log = Path(temp_dir) / "all.jsonl"
            run_log.write_text(
                "\n".join(
                    [
                        '{"automation_id":"memory_sync","status":"ok","finished_at":"2026-04-17T20:00:00-04:00"}',
                        '{"automation_id":"pm_runner","status":"error","action_required":true,"finished_at":"2026-04-17T23:48:02-04:00"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            now = datetime(2026, 4, 18, 0, 0, tzinfo=ZoneInfo("America/New_York"))
            with mock.patch.object(self.report, "RUN_LOG", run_log):
                runtime = self.report.analyze_runtime(now, 36.0)

        self.assertEqual(runtime["runs_within_hours"], 2)
        self.assertEqual(runtime["status_counts"], {"ok": 1, "error": 1})
        self.assertEqual(runtime["action_required_count"], 1)
        self.assertEqual(runtime["latest_activity"]["automation_id"], "pm_runner")

    def test_render_summary_reports_runtime_and_launchd_health(self) -> None:
        summary = self.report.render_summary(
            {
                "state": {
                    "status": "ok",
                    "note": "HEARTBEAT_OK",
                    "checks": [{"name": "automation_health", "timestamp": "2026-04-18T03:39:00+00:00", "age_minutes": 10}],
                },
                "runtime": {
                    "latest_activity": {"automation_id": "memory_sync", "status": "ok", "age_minutes": 12},
                    "runs_within_hours": 8,
                    "status_counts": {"ok": 8},
                    "action_required_count": 0,
                },
                "launchd": {"counts": {"loaded_labels": 2, "installed_labels": 3, "errors": 0}},
                "artifacts": [],
            }
        )

        self.assertIn("runtime `memory_sync` ok", summary)
        self.assertIn("launchd 2/3 loaded", summary)
        self.assertNotIn("Discord", summary)


if __name__ == "__main__":
    unittest.main()
