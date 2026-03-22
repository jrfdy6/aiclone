from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json, Jsonb

from app.models import PersonaDelta, PersonaDeltaCreate, PersonaDeltaResolve, PersonaDeltaUpdate
from app.services.open_brain_db import get_pool


def list_deltas(limit: int = 50, status: Optional[str] = None) -> List[PersonaDelta]:
    pool = get_pool()
    query = """
        SELECT id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
        FROM persona_deltas
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """
    where = ""
    params = []
    if status:
        where = "WHERE status = %s"
        params.append(status)
    params.append(limit)

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query.format(where=where), params)
            rows = cur.fetchall() or []
    return [_row_to_delta(row) for row in rows]


def create_delta(payload: PersonaDeltaCreate) -> PersonaDelta:
    pool = get_pool()
    delta_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO persona_deltas (id, capture_id, persona_target, trait, notes, status, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
                """,
                (
                    delta_id,
                    payload.capture_id,
                    payload.persona_target,
                    payload.trait,
                    payload.notes,
                    "draft",
                    Json(payload.metadata or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_delta(row)


def update_delta(delta_id: str, payload: PersonaDeltaUpdate) -> Optional[PersonaDelta]:
    pool = get_pool()
    fields = []
    values = []
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
        if payload.status == "committed":
            fields.append("committed_at = NOW()")
    if payload.notes is not None:
        fields.append("notes = %s")
        values.append(payload.notes)
    if payload.metadata is not None:
        fields.append("metadata = COALESCE(metadata, '{}'::jsonb) || %s")
        values.append(Jsonb(payload.metadata))
    if not fields:
        return get_delta(delta_id)
    values.append(delta_id)

    query = f"""
        UPDATE persona_deltas
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_delta(row) if row else None


def resolve_delta(delta_id: str, payload: PersonaDeltaResolve) -> Optional[PersonaDelta]:
    metadata = dict(payload.metadata or {})
    if payload.resolution_capture_id:
        metadata["resolution_capture_id"] = payload.resolution_capture_id
    update = PersonaDeltaUpdate(status=payload.status, metadata=metadata or None)
    return update_delta(delta_id, update)


def get_delta(delta_id: str) -> Optional[PersonaDelta]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
                FROM persona_deltas
                WHERE id = %s
                """,
                (delta_id,),
            )
            row = cur.fetchone()
    return _row_to_delta(row) if row else None


def _row_to_delta(row: dict) -> PersonaDelta:
    if not row:
        raise ValueError("Persona delta row is empty")
    return PersonaDelta(
        id=str(row["id"]),
        capture_id=str(row["capture_id"]) if row.get("capture_id") else None,
        persona_target=row.get("persona_target") or "unknown",
        trait=row.get("trait") or "",
        notes=row.get("notes"),
        status=row.get("status") or "draft",
        metadata=row.get("metadata") or {},
        created_at=row.get("created_at"),
        committed_at=row.get("committed_at"),
    )


def get_delta_by_capture(capture_id: str) -> Optional[PersonaDelta]:
    if not capture_id:
        return None
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
                FROM persona_deltas
                WHERE capture_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (capture_id,),
            )
            row = cur.fetchone()
    return _row_to_delta(row) if row else None
