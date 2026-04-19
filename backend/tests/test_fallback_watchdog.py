from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
BACKEND_ROOT = ROOT / "backend"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FallbackWatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        if str(BACKEND_ROOT) not in sys.path:
            sys.path.insert(0, str(BACKEND_ROOT))
        cls.watchdog = _load_module("fallback_watchdog", SCRIPTS_ROOT / "fallback_watchdog.py")

    def test_build_report_creates_followup_for_active_alerts(self) -> None:
        calls: list[tuple[str, str]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload=None):
            calls.append((method, url))
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return []
            if method == "POST" and url.endswith("/api/pm/cards"):
                return {"id": "pm-fallback-1", "status": "todo"}
            raise AssertionError(f"Unexpected request: {method} {url}")

        with mock.patch.object(self.watchdog, "_load_workspace_keys", return_value=["shared_ops", "fusion-os"]), mock.patch.object(
            self.watchdog,
            "_memory_alerts",
            return_value=(
                [
                    {
                        "id": "core_memory::memory/persistent_state.md",
                        "kind": "core_memory_resolution",
                        "severity": "critical",
                        "workspace_key": "shared_ops",
                        "summary": "persistent_state fell back to snapshot",
                    }
                ],
                ["/tmp/runtime/persistent_state.md"],
            ),
        ), mock.patch.object(
            self.watchdog,
            "_durable_checks",
            return_value=(
                [
                    {
                        "workspace_key": "fusion-os",
                        "retrieval_mode": "filesystem_fallback",
                        "fallback_active": True,
                        "filesystem_result_count": 1,
                        "qmd_result_count": 0,
                        "warnings": ["qmd unavailable"],
                        "source_paths": ["/tmp/workspaces/fusion-os/research.md"],
                    }
                ],
                [
                    {
                        "id": "durable_memory::fusion-os",
                        "kind": "durable_memory_retrieval",
                        "severity": "critical",
                        "workspace_key": "fusion-os",
                        "summary": "fusion-os durable retrieval is in filesystem fallback mode.",
                    }
                ],
                ["/tmp/workspaces/fusion-os/research.md"],
            ),
        ), mock.patch.object(
            self.watchdog,
            "_progress_pulse_alerts",
            return_value=(
                [
                    {
                        "id": "progress_pulse::delivery",
                        "kind": "progress_pulse_delivery",
                        "severity": "warning",
                        "workspace_key": "shared_ops",
                        "summary": "Progress Pulse would deliver from persistent_state drift.",
                    }
                ],
                {"delivery_fallback_active": True},
            ),
        ), mock.patch.object(
            self.watchdog,
            "_runtime_context_alerts",
            return_value=(
                [
                    {
                        "id": "runtime_context::pm",
                        "kind": "pm_context_loader",
                        "severity": "warning",
                        "workspace_key": "shared_ops",
                        "summary": "PM context loader is using `pm_api` because `pm_backend_service_unavailable`.",
                    }
                ],
                {
                    "pm_context": {"source": "pm_api", "fallback_active": True},
                    "automation_context": {"source": "automation_mismatch_service", "fallback_active": False},
                },
                ["https://example.invalid/api/pm/cards?limit=100"],
            ),
        ):
            report = self.watchdog.build_report(
                "https://example.invalid",
                sync_live=True,
                fetch_json=fake_fetch_json,
            )

        self.assertEqual(report["status"], "action_required")
        self.assertEqual(report["active_count"], 4)
        self.assertEqual(report["memory_alert_count"], 1)
        self.assertEqual(report["durable_retrieval_alert_count"], 1)
        self.assertEqual(report["delivery_alert_count"], 1)
        self.assertEqual(report["runtime_alert_count"], 1)
        self.assertEqual(report["followup_card"]["action"], "created")
        self.assertEqual(report["followup_card"]["card_id"], "pm-fallback-1")
        self.assertIn("/tmp/runtime/persistent_state.md", report["source_paths"])
        self.assertIn("/tmp/workspaces/fusion-os/research.md", report["source_paths"])
        self.assertIn("https://example.invalid/api/pm/cards?limit=100", report["source_paths"])
        self.assertEqual(report["runtime_checks"]["pm_context"]["source"], "pm_api")
        self.assertTrue(any(method == "POST" for method, _ in calls))

    def test_build_report_closes_existing_followup_when_alerts_clear(self) -> None:
        existing_card = {
            "id": "pm-fallback-1",
            "title": self.watchdog.FOLLOWUP_TITLE,
            "source": self.watchdog.FOLLOWUP_SOURCE,
            "status": "todo",
            "payload": {
                "execution": {
                    "state": "queued",
                    "history": [],
                }
            },
        }
        calls: list[tuple[str, str]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload=None):
            calls.append((method, url))
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return [existing_card]
            if method == "PATCH" and url.endswith("/api/pm/cards/pm-fallback-1"):
                return {"id": "pm-fallback-1", "status": "done"}
            raise AssertionError(f"Unexpected request: {method} {url}")

        with mock.patch.object(self.watchdog, "_load_workspace_keys", return_value=["shared_ops"]), mock.patch.object(
            self.watchdog, "_memory_alerts", return_value=([], [])
        ), mock.patch.object(
            self.watchdog, "_durable_checks", return_value=([], [], [])
        ), mock.patch.object(
            self.watchdog, "_progress_pulse_alerts", return_value=([], {"delivery_fallback_active": False})
        ), mock.patch.object(
            self.watchdog,
            "_runtime_context_alerts",
            return_value=(
                [],
                {
                    "pm_context": {"source": "pm_backend_service", "fallback_active": False},
                    "automation_context": {"source": "automation_mismatch_service", "fallback_active": False},
                },
                [],
            ),
        ):
            report = self.watchdog.build_report(
                "https://example.invalid",
                sync_live=True,
                fetch_json=fake_fetch_json,
            )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["active_count"], 0)
        self.assertEqual(report["runtime_alert_count"], 0)
        self.assertEqual(report["followup_card"]["action"], "closed")
        self.assertEqual(report["followup_card"]["status"], "done")
        self.assertTrue(any(method == "PATCH" for method, _ in calls))

    def test_memory_alerts_flag_runtime_sync_drift(self) -> None:
        resolution = {
            "resolved_path": "/tmp/runtime/persistent_state.md",
            "fallback_active": False,
            "runtime_out_of_sync": True,
            "live_newer_by_hours": 8.25,
            "live_path": "/tmp/live/persistent_state.md",
            "runtime_path": "/tmp/runtime/persistent_state.md",
            "expected_mode": "runtime",
            "resolved_mode": "runtime",
        }

        with mock.patch.object(self.watchdog, "MONITORED_MEMORY_PATHS", ("memory/persistent_state.md",)), mock.patch.object(
            self.watchdog, "resolve_memory_read_target", return_value=resolution
        ):
            alerts, source_paths = self.watchdog._memory_alerts()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["kind"], "core_memory_sync_drift")
        self.assertIn("out of sync", alerts[0]["summary"])
        self.assertIn("/tmp/runtime/persistent_state.md", source_paths)


if __name__ == "__main__":
    unittest.main()
