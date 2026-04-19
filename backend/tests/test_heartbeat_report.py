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
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        if str(BACKEND_ROOT) not in sys.path:
            sys.path.insert(0, str(BACKEND_ROOT))
        cls.report = _load_module("heartbeat_report", SCRIPTS_ROOT / "heartbeat_report.py")

    def test_analyze_gateway_tracks_latest_activity_even_if_bootstrap_is_old(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "gateway.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-04-15T14:37:51.739-04:00 [heartbeat] started",
                        "2026-04-17T23:48:02.779-04:00 [discord] client initialized as 123 (NEO)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            now = datetime(2026, 4, 18, 0, 0, tzinfo=ZoneInfo("America/New_York"))
            with mock.patch.object(self.report, "GATEWAY_LOG", log_path):
                gateway = self.report.analyze_gateway(now, 36.0)

        self.assertIsNotNone(gateway["last_activity"])
        self.assertIn("2026-04-17T23:48:02", gateway["last_activity"]["timestamp_local"])
        self.assertIsNotNone(gateway["last_entry"])
        self.assertIn("2026-04-15T14:37:51", gateway["last_entry"]["timestamp_local"])

    def test_render_summary_prefers_gateway_activity_label(self) -> None:
        summary = self.report.render_summary(
            {
                "state": {
                    "status": "ok",
                    "note": "HEARTBEAT_OK",
                    "checks": [{"name": "automation_health", "timestamp": "2026-04-18T03:39:00+00:00", "age_minutes": 10}],
                },
                "gateway": {
                    "last_activity": {"timestamp_local": "2026-04-17T23:48:02-04:00", "age_minutes": 12},
                    "last_entry": {"timestamp_local": "2026-04-15T18:37:51+00:00", "age_minutes": 3400},
                },
                "discord": {"counts": {"closed": 1, "reconnect": 8}, "window_hours": 36, "latest": None},
                "artifacts": [],
            }
        )

        self.assertIn("gateway activity", summary)
        self.assertNotIn("gateway run", summary)


if __name__ == "__main__":
    unittest.main()
