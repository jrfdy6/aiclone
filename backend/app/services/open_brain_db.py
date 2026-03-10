from __future__ import annotations

import os
from typing import Optional

from psycopg_pool import ConnectionPool

_DB_KEYS = [
    "OPEN_BRAIN_DATABASE_URL",
    "BRAIN_VECTOR_DATABASE_URL",
    "DATABASE_URL",
]

_pool: Optional[ConnectionPool] = None


def _get_conninfo() -> Optional[str]:
    for key in _DB_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


def initialize_schema(pool: ConnectionPool) -> None:
    schema_sql = """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS knowledge_capture (
        id UUID PRIMARY KEY,
        content TEXT NOT NULL,
        source TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS memory_vectors (
        id UUID PRIMARY KEY,
        capture_id UUID REFERENCES knowledge_capture(id) ON DELETE CASCADE,
        embedding vector(1536),
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS memory_vectors_capture_idx
    ON memory_vectors(capture_id);
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        conninfo = _get_conninfo()
        if not conninfo:
            raise RuntimeError("Open brain database url is not configured")

        min_size = int(os.getenv("OPEN_BRAIN_POOL_MIN", "1"))
        max_size = int(os.getenv("OPEN_BRAIN_POOL_MAX", "5"))

        _pool = ConnectionPool(conninfo=conninfo, min_size=min_size, max_size=max_size)

        initialize_schema(_pool)

    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
