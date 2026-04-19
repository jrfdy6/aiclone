from __future__ import annotations

import importlib
import sys
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


if __name__ == "__main__":
    unittest.main()
