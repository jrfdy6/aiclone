from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import open_brain_metrics  # noqa: E402


class _FakeCursor:
    def __init__(self, connection: "_FakeConnection") -> None:
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()) -> None:
        self.connection.executed_queries.append((str(query), params))
        if self.connection.index >= len(self.connection.results):
            raise AssertionError(f"Unexpected query executed in test: {query}")
        result = self.connection.results[self.connection.index]
        self.connection.index += 1
        if isinstance(result, Exception):
            raise result
        self.connection.current_result = result

    def fetchone(self):
        result = self.connection.current_result
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def fetchall(self):
        result = self.connection.current_result
        if isinstance(result, list):
            return result
        if result is None:
            return []
        return [result]


class _FakeConnection:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.index = 0
        self.current_result = None
        self.executed_queries: list[tuple[str, tuple[object, ...] | object]] = []
        self.rollback_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, row_factory=None):
        return _FakeCursor(self)

    def rollback(self) -> None:
        self.rollback_calls += 1


class _FakePool:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def connection(self):
        return self._connection


class OpenBrainMetricsTests(unittest.TestCase):
    def test_fetch_metrics_uses_schema_aware_related_id_join(self) -> None:
        conn = _FakeConnection(
            [
                {"total": 43, "last_24h": 2, "last_7d": 8},
                [
                    {
                        "id": "capture-1",
                        "source": "brain",
                        "topic": ["ai"],
                        "importance": 3,
                        "markdown_path": "memory/test.md",
                        "created_at": datetime(2026, 4, 16, 20, 0, tzinfo=timezone.utc),
                        "chunk_count": 7,
                    }
                ],
                {"total": 298, "with_expiry": 10, "overdue": 3, "last_refresh_at": datetime(2026, 4, 16, 23, 0, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(open_brain_metrics, "get_pool", return_value=_FakePool(conn)), patch.object(
            open_brain_metrics,
            "detect_memory_vector_storage",
            return_value={"join_column": "related_id"},
        ):
            payload = open_brain_metrics.fetch_metrics(limit_recent=1)

        self.assertTrue(payload["database_connected"])
        self.assertEqual(payload["captures"]["total"], 43)
        self.assertEqual(payload["vectors"]["total"], 298)
        self.assertEqual(payload["recent_captures"][0]["chunk_count"], 7)
        recent_query = conn.executed_queries[1][0]
        self.assertIn("mv.related_id = kc.id", recent_query)

    def test_fetch_metrics_preserves_other_sections_when_recent_capture_query_fails(self) -> None:
        conn = _FakeConnection(
            [
                {"total": 43, "last_24h": 0, "last_7d": 5},
                RuntimeError("recent capture query failed"),
                {"total": 298, "with_expiry": 10, "overdue": 3, "last_refresh_at": datetime(2026, 4, 16, 23, 0, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(open_brain_metrics, "get_pool", return_value=_FakePool(conn)), patch.object(
            open_brain_metrics,
            "detect_memory_vector_storage",
            return_value={"join_column": "capture_id"},
        ):
            payload = open_brain_metrics.fetch_metrics(limit_recent=1)

        self.assertTrue(payload["database_connected"])
        self.assertEqual(payload["captures"]["total"], 43)
        self.assertEqual(payload["vectors"]["total"], 298)
        self.assertEqual(payload["recent_captures"], [])
        self.assertEqual(conn.rollback_calls, 1)


if __name__ == "__main__":
    unittest.main()
