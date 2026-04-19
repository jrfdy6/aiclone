from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "local_codex_bridge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("local_codex_bridge", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalCodexBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bridge = _load_module()

    def test_resolve_codex_cli_model_falls_back_from_unsupported_labels(self) -> None:
        self.assertEqual(self.bridge._resolve_codex_cli_model("gpt-5.1-codex"), "gpt-5.4-mini")
        self.assertEqual(self.bridge._resolve_codex_cli_model("openai/gpt-5.3-codex"), "gpt-5.4-mini")
        self.assertEqual(self.bridge._resolve_codex_cli_model("openai/gpt-5.4-mini"), "gpt-5.4-mini")

    def test_run_codex_job_uses_resolved_model_in_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            def fake_run(command, **kwargs):
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(json.dumps({"options": ["one", "two", "three"]}), encoding="utf-8")
                return self.bridge.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with mock.patch.object(self.bridge.subprocess, "run", side_effect=fake_run) as mocked_run:
                options, _raw_output, _stdout, _stderr = self.bridge._run_codex_job(
                    workspace_root=workspace_root,
                    model="gpt-5.1-codex",
                    reasoning_effort="medium",
                    prompt="Return three options.",
                    expected_option_count=3,
                    timeout_seconds=30,
                )

        command = mocked_run.call_args.args[0]
        self.assertEqual(options, ["one", "two", "three"])
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.4-mini")


if __name__ == "__main__":
    unittest.main()
