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
    def test_sync_upgrades_existing_index_without_dropping_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            note = project / "knowledge" / "canon.md"
            note.parent.mkdir(parents=True)
            note.write_text(
                "# Existing Canon\nThe topaz principle remains searchable.\n",
                encoding="utf-8",
            )
            index = root / "state" / "memory.sqlite3"
            index.parent.mkdir(parents=True)
            connection = sqlite3.connect(index)
            connection.executescript(
                """
                CREATE TABLE memory_documents (
                    path TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE memory_fts USING fts5(
                    path UNINDEXED,
                    title,
                    content,
                    tokenize='porter unicode61'
                );
                CREATE TABLE memory_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            connection.close()

            report = sync_index(
                project_root=project,
                state_root=root / "private-state",
                index_path=index,
            )
            results = search_index(
                "topaz",
                project_root=project,
                state_root=root / "private-state",
                index_path=index,
            )

            self.assertEqual(report["files"], 1)
            self.assertEqual(results[0]["path"], "knowledge/canon.md")
            self.assertEqual(results[0]["storage_scope"], "project")

    def test_private_state_is_indexed_first_with_future_workspaces_and_project_canon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            state = root / "private-state"
            index = root / "index" / "memory.sqlite3"

            legacy = project / "memory" / "decision.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                "# Legacy Decision\nThe old generated choice used the amber route.\n",
                encoding="utf-8",
            )
            runtime_legacy = project / "memory" / "runtime" / "decision.md"
            runtime_legacy.parent.mkdir(parents=True)
            runtime_legacy.write_text(
                "# Runtime Legacy Decision\nThe intermediate choice used the vermilion route.\n",
                encoding="utf-8",
            )
            reviewed_canon = project / "knowledge" / "reviewed-canon.md"
            reviewed_canon.parent.mkdir(parents=True)
            reviewed_canon.write_text(
                "# Reviewed Canon\nThe lighthouse principle remains authoritative.\n",
                encoding="utf-8",
            )
            private = state / "memory" / "decision.md"
            private.parent.mkdir(parents=True)
            private.write_text(
                "# Current Decision\nThe private generated choice now uses the saffron route.\n",
                encoding="utf-8",
            )
            future_workspace = (
                state
                / "workspaces"
                / "future-capability"
                / "memory"
                / "execution_log.md"
            )
            future_workspace.parent.mkdir(parents=True)
            future_workspace.write_text(
                "# Future Capability\nThe quasar workflow completed successfully.\n",
                encoding="utf-8",
            )

            report = sync_index(
                project_root=project,
                state_root=state,
                index_path=index,
            )
            current_results = search_index(
                "saffron",
                project_root=project,
                state_root=state,
                index_path=index,
            )
            stale_results = search_index(
                "amber",
                project_root=project,
                state_root=state,
                index_path=index,
            )
            runtime_stale_results = search_index(
                "vermilion",
                project_root=project,
                state_root=state,
                index_path=index,
            )
            canon_results = search_index(
                "lighthouse",
                project_root=project,
                state_root=state,
                index_path=index,
            )
            future_results = search_index(
                "quasar",
                project_root=project,
                state_root=state,
                index_path=index,
            )

            self.assertEqual(report["files"], 3)
            self.assertEqual(report["private_state_files"], 2)
            self.assertEqual(current_results[0]["path"], "memory/decision.md")
            self.assertEqual(current_results[0]["storage_scope"], "private_state_memory")
            self.assertTrue(current_results[0]["private_state"])
            self.assertFalse(stale_results)
            self.assertFalse(runtime_stale_results)
            self.assertEqual(canon_results[0]["path"], "knowledge/reviewed-canon.md")
            self.assertEqual(canon_results[0]["storage_scope"], "project")
            self.assertEqual(
                future_results[0]["path"],
                "workspaces/future-capability/memory/execution_log.md",
            )
            self.assertEqual(
                future_results[0]["storage_scope"],
                "private_state_workspace",
            )
            self.assertNotIn("absolute_path", future_results[0])

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
