from __future__ import annotations

import importlib.util
import plistlib
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FusionFeedbackRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.runner = _load_module(
            "run_fusion_feedback_refresh_test",
            SCRIPTS_ROOT / "run_fusion_feedback_refresh.py",
        )

    def test_child_environment_removes_model_tokens_but_keeps_control_auth(self) -> None:
        env = self.runner._child_environment(
            {
                "PATH": "/usr/bin:/bin",
                "OPENAI_API_KEY": "model-token",
                "ANTHROPIC_API_KEY": "model-token",
                "CONTROL_PLANE_SERVICE_TOKEN": "control-token",
            }
        )

        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual(env["CONTROL_PLANE_SERVICE_TOKEN"], "control-token")

    def test_run_refreshes_feedback_then_builds_standup_and_records_locally(self) -> None:
        refresh_result = {
            "ok": True,
            "returncode": 0,
            "stdout": '{"workspace_key":"fusion-os","followers":42,"sample_size":12}',
            "error": None,
        }
        standup_result = {
            "ok": True,
            "returncode": 0,
            "stdout": "Prep ready\nJSON: /tmp/prep.json\nMarkdown: /tmp/prep.md\n",
            "error": None,
        }
        with mock.patch.object(self.runner, "_run_stage", side_effect=[refresh_result, standup_result]) as run_stage, mock.patch.object(
            self.runner, "append_local_runs"
        ) as append_local, mock.patch.object(self.runner, "mirror_runs") as mirror:
            report, ok = self.runner.run(remote_mirror=False)

        self.assertTrue(ok)
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["remote_mirror"], "disabled")
        self.assertEqual(run_stage.call_count, 2)
        refresh_command = run_stage.call_args_list[0].args[0]
        standup_command = run_stage.call_args_list[1].args[0]
        self.assertTrue(refresh_command[1].endswith("refresh_fusion_instagram_feedback.py"))
        self.assertEqual(refresh_command[refresh_command.index("--workspace-key") + 1], "fusion-os")
        self.assertTrue(standup_command[1].endswith("build_standup_prep.py"))
        self.assertEqual(standup_command[standup_command.index("--owner-agent") + 1], "jean-claude")
        append_local.assert_called_once()
        mirror.assert_not_called()
        payload = append_local.call_args.args[0][0]
        self.assertEqual(payload["automation_id"], "fusion_feedback_refresh")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["scope"], "workspace")
        self.assertEqual(payload["workspace_key"], "fusion-os")
        self.assertFalse(payload["metadata"]["model_api_tokens_used"])
        self.assertEqual(payload["metadata"]["standup_prep"]["json_path"], "/tmp/prep.json")

    def test_failed_refresh_still_builds_standup_and_requests_action(self) -> None:
        refresh_result = {"ok": False, "returncode": 1, "stdout": "", "error": "stage exited with code 1"}
        standup_result = {
            "ok": True,
            "returncode": 0,
            "stdout": "JSON: /tmp/prep.json\nMarkdown: /tmp/prep.md\n",
            "error": None,
        }
        with mock.patch.object(self.runner, "_run_stage", side_effect=[refresh_result, standup_result]) as run_stage, mock.patch.object(
            self.runner, "append_local_runs"
        ) as append_local:
            report, ok = self.runner.run(remote_mirror=False)

        self.assertFalse(ok)
        self.assertEqual(run_stage.call_count, 2)
        payload = append_local.call_args.args[0][0]
        self.assertEqual(payload["status"], "error")
        self.assertTrue(payload["action_required"])
        self.assertIn("feedback_refresh", report["error"])

    def test_launchd_schedule_and_paths_are_codex_native(self) -> None:
        plist_path = ROOT / "automations" / "launchd" / "com.neo.fusion_feedback_refresh.plist"
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)

        self.assertEqual(payload["Label"], "com.neo.fusion_feedback_refresh")
        self.assertEqual(payload["StartCalendarInterval"], {"Hour": 12, "Minute": 15})
        self.assertEqual(payload["ProgramArguments"][0], "/Users/neo/.codex/ai-clone/venv/bin/python")
        self.assertIn("/Users/neo/Documents/Codex/AI-Clone", " ".join(payload["ProgramArguments"]))
        self.assertNotIn(".openclaw", str(payload).lower())


if __name__ == "__main__":
    unittest.main()
