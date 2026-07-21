from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codex_memory_index import index_status, search_index, sync_index  # noqa: E402


class CodexMemoryIndexTests(unittest.TestCase):
    def test_sync_search_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            memory = project / "memory"
            memory.mkdir(parents=True)
            note = memory / "decision.md"
            note.write_text("# Durable Decision\nUse Railway PM cards for execution truth.\n", encoding="utf-8")
            index = Path(temp_dir) / "state" / "memory.sqlite3"

            report = sync_index(project_root=project, index_path=index)
            self.assertEqual(report["files"], 1)
            results = search_index("Railway execution", project_root=project, index_path=index)
            self.assertEqual(results[0]["path"], "memory/decision.md")
            self.assertEqual(results[0]["source"], "codex_memory_index")

            note.unlink()
            report = sync_index(project_root=project, index_path=index)
            self.assertEqual(report["removed"], 1)
            self.assertEqual(index_status(index)["files"], 0)

    def test_status_and_search_use_immutable_read_only_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "read-only-task"
            memory = project / "memory"
            memory.mkdir(parents=True)
            (memory / "decision.md").write_text(
                "# Immutable Recall\nCodex runners use the Railway control plane.\n",
                encoding="utf-8",
            )
            index_dir = root / "state"
            index = index_dir / "memory.sqlite3"
            sync_index(project_root=project, index_path=index)

            index.chmod(0o444)
            index_dir.chmod(0o555)
            memory.chmod(0o555)
            project.chmod(0o555)
            before_entries = sorted(path.name for path in index_dir.iterdir())
            before_mtime_ns = index.stat().st_mtime_ns
            previous_cwd = Path.cwd()
            real_connect = sqlite3.connect
            try:
                os.chdir(project)
                with (
                    mock.patch(
                        "codex_memory_index.ensure_runtime_dirs",
                        side_effect=AssertionError("read path initialized runtime directories"),
                    ),
                    mock.patch(
                        "codex_memory_index.sqlite3.connect",
                        wraps=real_connect,
                    ) as connect,
                ):
                    status = index_status(index)
                    results = search_index(
                        "Railway control",
                        project_root=project,
                        index_path=index,
                        sync_if_missing=False,
                    )
            finally:
                os.chdir(previous_cwd)
                project.chmod(0o755)
                memory.chmod(0o755)
                index_dir.chmod(0o755)
                index.chmod(0o644)

            self.assertEqual(status["status"], "ok")
            self.assertEqual(results[0]["path"], "memory/decision.md")
            self.assertEqual(before_entries, sorted(path.name for path in index_dir.iterdir()))
            self.assertEqual(before_mtime_ns, index.stat().st_mtime_ns)
            self.assertEqual(connect.call_count, 2)
            for call in connect.call_args_list:
                self.assertIn("?mode=ro&immutable=1", call.args[0])
                self.assertTrue(call.kwargs["uri"])

    def test_missing_status_does_not_create_index_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index = Path(temp_dir) / "missing" / "memory.sqlite3"
            with mock.patch(
                "codex_memory_index.ensure_runtime_dirs",
                side_effect=AssertionError("status initialized runtime directories"),
            ):
                status = index_status(index)

            self.assertEqual(status["status"], "missing")
            self.assertFalse(index.parent.exists())


if __name__ == "__main__":
    unittest.main()
