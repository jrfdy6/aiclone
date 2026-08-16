from __future__ import annotations

from datetime import datetime, timezone
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


def delete_snapshot_types(
    workspace_key: str,
    snapshot_types: list[str],
) -> int:
    """Delete an explicit, bounded set of snapshot rows and return the row count."""
    cleaned = list(dict.fromkeys(str(value or "").strip() for value in snapshot_types if str(value or "").strip()))
    if not cleaned:
        return 0
    if len(cleaned) > 100:
        raise ValueError("Snapshot cleanup is limited to 100 explicit snapshot types.")
    pool = _maybe_pool()
    if pool is None:
        return 0
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                DELETE FROM workspace_snapshots
                WHERE workspace_key = %s AND snapshot_type = ANY(%s)
                """,
                (workspace_key, cleaned),
            )
            deleted = int(cur.rowcount or 0)
        conn.commit()
    return deleted


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


def upsert_snapshot_monotonic(
    workspace_key: str,
    snapshot_type: str,
    payload: dict[str, Any],
    *,
    generated_at: datetime,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[Optional[dict[str, Any]], bool]:
    """Store a snapshot only when its source timestamp is newer than the current payload."""
    pool = _maybe_pool()
    if pool is None:
        return None, False
    normalized_generated_at = generated_at
    if normalized_generated_at.tzinfo is None:
        normalized_generated_at = normalized_generated_at.replace(tzinfo=timezone.utc)
    normalized_generated_at = normalized_generated_at.astimezone(timezone.utc)
    snapshot_id = str(uuid4())
    effective_metadata = {
        **(metadata or {}),
        "payload_generated_at": normalized_generated_at.isoformat(),
    }
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
                WHERE CASE
                    WHEN COALESCE(workspace_snapshots.payload->>'generated_at', '') ~
                         '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
                    THEN (workspace_snapshots.payload->>'generated_at')::timestamptz
                    ELSE '-infinity'::timestamptz
                END < %s
                RETURNING id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                """,
                (
                    snapshot_id,
                    workspace_key,
                    snapshot_type,
                    Jsonb(payload),
                    Jsonb(effective_metadata),
                    normalized_generated_at,
                ),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                    FROM workspace_snapshots
                    WHERE workspace_key = %s AND snapshot_type = %s
                    """,
                    (workspace_key, snapshot_type),
                )
                current = cur.fetchone()
            else:
                current = None
        conn.commit()
    if row is not None:
        return _row_to_snapshot(row), True
    return (_row_to_snapshot(current) if current else None), False
