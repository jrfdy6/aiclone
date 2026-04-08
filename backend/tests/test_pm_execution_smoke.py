from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PMExecutionSmokeScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.script = _load_module("run_pm_execution_smoke", SCRIPTS_ROOT / "run_pm_execution_smoke.py")

    def test_build_smoke_card_payload_forces_direct_jean_claude_lane(self) -> None:
        args = types.SimpleNamespace(
            title="Smoke card",
            workspace_key="fusion-os",
            reason="Verify the smoke lane.",
            instruction=["Keep it bounded."],
            acceptance_criterion=["The card reaches review."],
            artifact=["smoke result"],
        )

        payload = self.script.build_smoke_card_payload(args)

        self.assertEqual(payload["owner"], "Neo")
        self.assertEqual(payload["payload"]["execution"]["manager_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["execution"]["target_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["execution"]["execution_mode"], "direct")
        self.assertTrue(str(payload["payload"]["trigger_key"]).startswith("openclaw:"))

    def test_run_live_smoke_orchestrates_create_dispatch_execute_and_verify(self) -> None:
        args = types.SimpleNamespace(
            api_url="https://example.test",
            workspace_key="shared_ops",
            title="Smoke card",
            reason="Verify the smoke lane.",
            instruction=["Keep it bounded."],
            acceptance_criterion=["The card reaches review."],
            artifact=["smoke result"],
            card_id="",
            worker_id="smoke-codex",
        )

        responses = [
            {"id": "card-1", "status": "todo"},
            [
                {
                    "id": "card-1",
                    "status": "review",
                    "payload": {
                        "execution": {"state": "review", "executor_status": "completed"},
                        "latest_execution_result": {"status": "review", "summary": "Smoke completed."},
                    },
                }
            ],
        ]

        def fake_request_json(_api_url: str, _path: str, *, method: str = "GET", payload: dict | None = None):
            self.assertIn(method, {"GET", "POST"})
            if method == "POST":
                self.assertEqual(_path, "/api/pm/cards")
                self.assertIsNotNone(payload)
            return responses.pop(0)

        completed = subprocess.CompletedProcess(args=["python3"], returncode=0, stdout="ok\n", stderr="")
        with patch.object(self.script, "request_json", side_effect=fake_request_json), patch.object(
            self.script.subprocess,
            "run",
            side_effect=[completed, completed],
        ) as run_mock:
            result = self.script.run_live_smoke(args)

        self.assertTrue(result["success"])
        self.assertEqual(result["card_id"], "card-1")
        self.assertEqual(result["execution_state"], "review")
        self.assertEqual(result["executor_status"], "completed")
        self.assertEqual(result["latest_result_summary"], "Smoke completed.")
        self.assertEqual(run_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
