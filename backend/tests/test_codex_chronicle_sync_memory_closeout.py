from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_PATH = SCRIPTS_ROOT / "sync_codex_chronicle.py"


def load_script_module():
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    spec = importlib.util.spec_from_file_location("sync_codex_chronicle_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CodexChronicleSyncMemoryCloseoutTests(unittest.TestCase):
    def test_material_codex_history_appends_learnings_and_persistent_state(self) -> None:
        module = load_script_module()
        signal = (
            "The key learning is that autonomous loops need one connected source-intelligence, "
            "BrainSignal, Chronicle, LEARNINGS, and persistent-state closeout so posts bank without manual rescue."
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.jsonl"
            chronicle_path = root / "codex_session_handoff.jsonl"
            learnings_path = root / "LEARNINGS.md"
            persistent_state_path = root / "persistent_state.md"
            state_path = root / "codex_chronicle_state.json"
            history_path.write_text(
                json.dumps({"session_id": "session-1", "ts": 100, "text": signal}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                sys,
                "argv",
                [
                    "sync_codex_chronicle.py",
                    "--history-path",
                    str(history_path),
                    "--chronicle-path",
                    str(chronicle_path),
                    "--learnings-path",
                    str(learnings_path),
                    "--persistent-state-path",
                    str(persistent_state_path),
                    "--state-path",
                    str(state_path),
                    "--skip-session-transcripts",
                    "--initial-tail",
                    "5",
                ],
            ):
                self.assertEqual(module.main(), 0)

            chronicle_entry = json.loads(chronicle_path.read_text(encoding="utf-8").strip())
            self.assertEqual(chronicle_entry["memory_closeout"]["learning_count"], 1)
            self.assertEqual(chronicle_entry["memory_closeout"]["persistent_count"], 1)
            self.assertEqual(chronicle_entry["memory_closeout"]["learnings_path"], str(learnings_path))
            self.assertIn(signal, learnings_path.read_text(encoding="utf-8"))
            self.assertIn(signal, persistent_state_path.read_text(encoding="utf-8"))

    def test_assistant_session_transcript_can_close_out_build_learning(self) -> None:
        module = load_script_module()
        signal = (
            "The key learning is that direct Codex session transcripts must feed Chronicle closeout, "
            "because user-only history misses build-side learnings from autonomous system repair."
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.jsonl"
            session_root = root / "sessions"
            session_path = session_root / "2026" / "04" / "22" / (
                "rollout-2026-04-22T12-00-00-019db705-be83-7103-bf71-36d62427b9f2.jsonl"
            )
            chronicle_path = root / "codex_session_handoff.jsonl"
            learnings_path = root / "LEARNINGS.md"
            persistent_state_path = root / "persistent_state.md"
            state_path = root / "codex_chronicle_state.json"
            history_path.write_text("", encoding="utf-8")
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-22T12:00:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": signal}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                sys,
                "argv",
                [
                    "sync_codex_chronicle.py",
                    "--history-path",
                    str(history_path),
                    "--session-root",
                    str(session_root),
                    "--chronicle-path",
                    str(chronicle_path),
                    "--learnings-path",
                    str(learnings_path),
                    "--persistent-state-path",
                    str(persistent_state_path),
                    "--state-path",
                    str(state_path),
                    "--initial-tail",
                    "5",
                ],
            ):
                self.assertEqual(module.main(), 0)

            chronicle_entry = json.loads(chronicle_path.read_text(encoding="utf-8").strip())
            self.assertEqual(chronicle_entry["memory_closeout"]["learning_count"], 1)
            self.assertEqual(chronicle_entry["record_counts"]["session_transcript"], 1)
            self.assertIn(signal, learnings_path.read_text(encoding="utf-8"))
            self.assertIn("codex-session-transcript", chronicle_entry["source_refs"][0]["source"])


if __name__ == "__main__":
    unittest.main()
