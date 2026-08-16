from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json, Jsonb

from app.models import PersonaDelta, PersonaDeltaCreate, PersonaDeltaResolve, PersonaDeltaUpdate
from app.services.open_brain_db import get_pool
from app.services.persona_review_queue_service import has_selectable_promotion_metadata


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


def get_delta_by_review_key(review_key: str) -> Optional[PersonaDelta]:
    if not review_key:
        return None
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, capture_id, persona_target, trait, notes, status, metadata, created_at, committed_at
                FROM persona_deltas
                WHERE metadata->>'review_key' = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (review_key,),
            )
            row = cur.fetchone()
    return _row_to_delta(row) if row else None


def apply_brain_review(
    delta_id: str,
    *,
    mode: str,
    response_kind: str,
    reflection_excerpt: str,
    resolution_capture_id: str | None = None,
    selected_promotion_items: list[dict] | None = None,
) -> Optional[PersonaDelta]:
    existing = get_delta(delta_id)
    if existing is None:
        return None

    normalized_mode = (mode or "reviewed").strip().lower()
    if normalized_mode not in {"reviewed", "approved"}:
        raise ValueError("Unsupported review mode.")

    trimmed_excerpt = (reflection_excerpt or "").strip()
    if not trimmed_excerpt:
        raise ValueError("Reflection excerpt cannot be empty.")

    promotion_items = [item for item in (selected_promotion_items or []) if isinstance(item, dict)]
    if normalized_mode == "approved" and not promotion_items:
        raise ValueError("At least one promotion item is required for approval.")

    existing_metadata = existing.metadata if isinstance(existing.metadata, dict) else {}
    keep_selectable_source_open = normalized_mode == "reviewed" and has_selectable_promotion_metadata(existing_metadata)
    review_status = "approved" if normalized_mode == "approved" else ("in_review" if keep_selectable_source_open else "reviewed")
    reviewed_at = datetime.now(timezone.utc).isoformat()

    update_metadata = {
        "review_state": review_status,
        "review_source": "brain.persona.ui",
        "owner_response_kind": response_kind,
        "owner_response_excerpt": trimmed_excerpt[:4000],
        "owner_response_updated_at": reviewed_at,
        "resolution_capture_id": resolution_capture_id,
        "pending_promotion": normalized_mode == "approved" and len(promotion_items) > 0,
        "selected_promotion_items": promotion_items,
        "selected_promotion_item_ids": [str(item.get("id") or "") for item in promotion_items if str(item.get("id") or "")],
        "selected_promotion_count": len(promotion_items),
        "last_reviewed_at": reviewed_at,
    }
    if normalized_mode != "approved":
        update_metadata["pending_promotion"] = False

    update = PersonaDeltaUpdate(status=review_status, metadata=update_metadata)
    return update_delta(delta_id, update)
