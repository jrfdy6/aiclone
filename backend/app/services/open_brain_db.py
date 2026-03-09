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


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        conninfo = _get_conninfo()
        if not conninfo:
            raise RuntimeError("Open brain database url is not configured")
        min_size = int(os.getenv("OPEN_BRAIN_POOL_MIN", "1"))
        max_size = int(os.getenv("OPEN_BRAIN_POOL_MAX", "5"))
        _pool = ConnectionPool(conninfo=conninfo, min_size=min_size, max_size=max_size)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
