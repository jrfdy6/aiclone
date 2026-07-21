from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import codex_memory_freshness_check as freshness  # noqa: E402


class CodexMemoryFreshnessCheckTests(unittest.TestCase):
    def test_report_is_ready_when_index_and_probe_are_healthy(self) -> None:
        with mock.patch.object(
            freshness,
            "index_status",
            return_value={
                "status": "ok",
                "files": 42,
                "index_path": "/tmp/memory.sqlite3",
                "last_sync_at": "2099-01-01T00:00:00Z",
            },
        ), mock.patch.object(freshness, "search_index", return_value=[{"path": "memory/a.md"}]):
            report = freshness.build_report()

        self.assertEqual(report["backend"], "sqlite_fts5")
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["ready"])
        self.assertEqual(report["probe_result_count"], 1)


if __name__ == "__main__":
    unittest.main()
