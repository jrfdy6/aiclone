from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    dict_row = None  # type: ignore
    Jsonb = None  # type: ignore

try:
    from app.services.open_brain_db import get_pool
except Exception:  # pragma: no cover
    get_pool = None  # type: ignore


def _maybe_pool():
    if get_pool is None or dict_row is None or Jsonb is None:
        return None
    try:
        return get_pool()
    except Exception:
        return None


def _row_to_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "workspace_key": row["workspace_key"],
        "snapshot_type": row["snapshot_type"],
        "payload": row.get("payload") or {},
        "metadata": row.get("metadata") or {},
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_snapshot(workspace_key: str, snapshot_type: str) -> Optional[dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                FROM workspace_snapshots
                WHERE workspace_key = %s AND snapshot_type = %s
                """,
                (workspace_key, snapshot_type),
            )
            row = cur.fetchone()
    return _row_to_snapshot(row) if row else None


def get_snapshot_payload(workspace_key: str, snapshot_type: str) -> Optional[dict[str, Any]]:
    snapshot = get_snapshot(workspace_key, snapshot_type)
    if not snapshot:
        return None
    payload = snapshot.get("payload")
    return payload if isinstance(payload, dict) else None


def list_snapshot_payloads(workspace_key: str) -> dict[str, dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return {}
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                FROM workspace_snapshots
                WHERE workspace_key = %s
                """,
                (workspace_key,),
            )
            rows = cur.fetchall() or []
    payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        snapshot = _row_to_snapshot(row)
        payload = snapshot.get("payload")
        if isinstance(payload, dict):
            payloads[snapshot["snapshot_type"]] = payload
    return payloads


def upsert_snapshot(
    workspace_key: str,
    snapshot_type: str,
    payload: dict[str, Any],
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return None
    snapshot_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO workspace_snapshots (id, workspace_key, snapshot_type, payload, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_key, snapshot_type) DO UPDATE
                SET payload = EXCLUDED.payload,
                    metadata = COALESCE(workspace_snapshots.metadata, '{}'::jsonb) || EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                """,
                (
                    snapshot_id,
                    workspace_key,
                    snapshot_type,
                    Jsonb(payload),
                    Jsonb(metadata or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_snapshot(row) if row else None
