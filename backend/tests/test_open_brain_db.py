from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib
import os
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _fake_db_modules() -> dict[str, types.ModuleType]:
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.Connection = object
    fake_psycopg_rows = types.ModuleType("psycopg.rows")
    fake_psycopg_rows.dict_row = object()
    fake_psycopg_pool = types.ModuleType("psycopg_pool")
    fake_psycopg_pool.ConnectionPool = object
    fake_embedders = types.ModuleType("app.services.embedders")
    return {
        "psycopg": fake_psycopg,
        "psycopg.rows": fake_psycopg_rows,
        "psycopg_pool": fake_psycopg_pool,
        "app.services.embedders": fake_embedders,
    }


class _FakeCursor:
    def __init__(self, connection: "_FakeConnection") -> None:
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()) -> None:
        self.connection.executed.append(str(query))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, row_factory=None):
        return _FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class OpenBrainDbTests(unittest.TestCase):
    def test_database_configured_reflects_durable_database_environment(self) -> None:
        from app.services import open_brain_db

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(open_brain_db.database_configured())
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example.invalid/brain"}, clear=True):
            self.assertTrue(open_brain_db.database_configured())

    def test_get_pool_initializes_one_candidate_across_concurrent_callers(self) -> None:
        from app.services import open_brain_db

        worker_count = 8
        start_barrier = threading.Barrier(worker_count)
        initialize_started = threading.Event()
        release_initialize = threading.Event()
        candidates: list[object] = []
        initialized: list[object] = []

        class FakePool:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs
                self.close_calls = 0
                candidates.append(self)

            def close(self) -> None:
                self.close_calls += 1

        def initialize(candidate) -> None:
            initialized.append(candidate)
            initialize_started.set()
            if not release_initialize.wait(timeout=2):
                raise AssertionError("timed out waiting to release schema initialization")

        def acquire_pool():
            start_barrier.wait(timeout=2)
            return open_brain_db.get_pool()

        with (
            patch.dict(
                os.environ,
                {
                    "OPEN_BRAIN_DATABASE_URL": "postgresql://example.invalid/brain",
                    "OPEN_BRAIN_POOL_MIN": "1",
                    "OPEN_BRAIN_POOL_MAX": "2",
                },
            ),
            patch.object(open_brain_db, "_pool", None),
            patch.object(open_brain_db, "ConnectionPool", FakePool),
            patch.object(open_brain_db, "initialize_schema", side_effect=initialize),
            ThreadPoolExecutor(max_workers=worker_count) as executor,
        ):
            futures = [executor.submit(acquire_pool) for _ in range(worker_count)]
            self.assertTrue(initialize_started.wait(timeout=2))
            release_initialize.set()
            pools = [future.result(timeout=2) for future in futures]

        self.assertEqual(len(candidates), 1)
        self.assertEqual(initialized, candidates)
        self.assertTrue(all(pool is candidates[0] for pool in pools))

    def test_get_pool_closes_failed_candidate_and_retries_cleanly(self) -> None:
        from app.services import open_brain_db

        candidates: list[object] = []

        class FakePool:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs
                self.close_calls = 0
                candidates.append(self)

            def close(self) -> None:
                self.close_calls += 1

        with (
            patch.dict(os.environ, {"OPEN_BRAIN_DATABASE_URL": "postgresql://example.invalid/brain"}),
            patch.object(open_brain_db, "_pool", None),
            patch.object(open_brain_db, "ConnectionPool", FakePool),
            patch.object(
                open_brain_db,
                "initialize_schema",
                side_effect=[RuntimeError("schema initialization failed"), None],
            ) as initialize,
        ):
            with self.assertRaisesRegex(RuntimeError, "schema initialization failed"):
                open_brain_db.get_pool()

            self.assertIsNone(open_brain_db._pool)
            self.assertEqual(candidates[0].close_calls, 1)

            recovered = open_brain_db.get_pool()
            self.assertIs(recovered, candidates[1])
            self.assertIs(open_brain_db._pool, candidates[1])

        self.assertEqual(len(candidates), 2)
        self.assertEqual(initialize.call_count, 2)
        self.assertEqual(candidates[1].close_calls, 0)

    def test_open_brain_db_does_not_import_embedder_stack_on_module_import(self) -> None:
        previous_module = sys.modules.pop("app.services.open_brain_db", None)
        try:
            with patch.dict(sys.modules, _fake_db_modules()):
                module = importlib.import_module("app.services.open_brain_db")

            self.assertEqual(module.DEFAULT_VECTOR_DIM, 1024)
        finally:
            sys.modules.pop("app.services.open_brain_db", None)
            if previous_module is not None:
                sys.modules["app.services.open_brain_db"] = previous_module

    def test_initialize_schema_uses_default_vector_dimension(self) -> None:
        from app.services import open_brain_db

        conn = _FakeConnection()
        with (
            patch.object(open_brain_db, "_maybe_enable_vector_extension", return_value=True),
            patch.object(open_brain_db, "_backfill_legacy_columns", return_value=None),
        ):
            open_brain_db.initialize_schema_on_connection(conn)

        self.assertTrue(any("embedding vector(1024)" in query for query in conn.executed))

    def test_initialize_schema_adds_neo_progress_columns_idempotently(self) -> None:
        from app.services import open_brain_db

        conn = _FakeConnection()
        with (
            patch.object(open_brain_db, "_maybe_enable_vector_extension", return_value=True),
            patch.object(open_brain_db, "_backfill_legacy_columns", return_value=None),
        ):
            open_brain_db.initialize_schema_on_connection(conn)

        for column in (
            "partial_response TEXT",
            "model_started_at TIMESTAMPTZ",
            "first_token_at TIMESTAMPTZ",
            "progress_at TIMESTAMPTZ",
        ):
            self.assertTrue(
                any(
                    f"ALTER TABLE neo_guest_jobs ADD COLUMN IF NOT EXISTS {column}" in query
                    for query in conn.executed
                ),
                column,
            )


if __name__ == "__main__":
    unittest.main()
