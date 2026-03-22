from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row

from app.models import StandupCreate, StandupEntry, StandupUpdate
from app.services.open_brain_db import get_pool


def list_standups(limit: int = 50, owner: Optional[str] = None) -> List[StandupEntry]:
    pool = get_pool()
    clauses = []
    params = []
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    query = f"""
        SELECT id, owner, status, blockers, commitments, needs, source, conversation_path, created_at
        FROM standups
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_entry(row) for row in rows]


def create_standup(payload: StandupCreate) -> StandupEntry:
    pool = get_pool()
    entry_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO standups (id, owner, status, blockers, commitments, needs, source, conversation_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, owner, status, blockers, commitments, needs, source, conversation_path, created_at
                """,
                (
                    entry_id,
                    payload.owner,
                    payload.status,
                    payload.blockers,
                    payload.commitments,
                    payload.needs,
                    payload.source,
                    payload.conversation_path,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_entry(row)


def update_standup(entry_id: str, payload: StandupUpdate) -> Optional[StandupEntry]:
    pool = get_pool()
    fields = []
    values = []
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
    if payload.blockers is not None:
        fields.append("blockers = %s")
        values.append(payload.blockers)
    if payload.commitments is not None:
        fields.append("commitments = %s")
        values.append(payload.commitments)
    if payload.needs is not None:
        fields.append("needs = %s")
        values.append(payload.needs)
    if payload.source is not None:
        fields.append("source = %s")
        values.append(payload.source)
    if payload.conversation_path is not None:
        fields.append("conversation_path = %s")
        values.append(payload.conversation_path)

    if not fields:
        return get_standup(entry_id)

    values.append(entry_id)
    query = f"""
        UPDATE standups
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, owner, status, blockers, commitments, needs, source, conversation_path, created_at
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_entry(row) if row else None


def get_standup(entry_id: str) -> Optional[StandupEntry]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, owner, status, blockers, commitments, needs, source, conversation_path, created_at
                FROM standups
                WHERE id = %s
                """,
                (entry_id,),
            )
            row = cur.fetchone()
    return _row_to_entry(row) if row else None


def _row_to_entry(row: dict) -> StandupEntry:
    if not row:
        raise ValueError("Standup row is empty")
    return StandupEntry(
        id=str(row["id"]),
        owner=row.get("owner") or "unknown",
        status=row.get("status"),
        blockers=row.get("blockers") or [],
        commitments=row.get("commitments") or [],
        needs=row.get("needs") or [],
        source=row.get("source"),
        conversation_path=row.get("conversation_path"),
        created_at=row.get("created_at"),
    )
