from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json, Jsonb

from app.models.build_reviews import BuildReview, BuildReviewUpdate, BuildReviewUpsert
from app.services.open_brain_db import get_pool

TERMINAL_BUILD_STATUSES = {"resolved", "pm_card_created", "reference_only", "rejected", "deferred"}


def list_reviews(limit: int = 100, status: Optional[str] = None) -> List[BuildReview]:
    pool = get_pool()
    params = []
    where = ""
    if status:
        where = "WHERE status = %s"
        params.append(status)
    params.append(limit)
    query = f"""
        SELECT id, title, status, source_type, source_url, ingestion_path, summary, why_showing,
               decision, response_notes, resolution_capture_id, payload, created_at, updated_at, resolved_at
        FROM build_reviews
        {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_review(row) for row in rows]


def get_review(review_id: str) -> Optional[BuildReview]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, status, source_type, source_url, ingestion_path, summary, why_showing,
                       decision, response_notes, resolution_capture_id, payload, created_at, updated_at, resolved_at
                FROM build_reviews
                WHERE id = %s
                """,
                (review_id,),
            )
            row = cur.fetchone()
    return _row_to_review(row) if row else None


def upsert_review(payload: BuildReviewUpsert) -> BuildReview:
    pool = get_pool()
    review_id = payload.id or str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO build_reviews (
                    id, title, status, source_type, source_url, ingestion_path, summary, why_showing,
                    decision, response_notes, resolution_capture_id, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    source_type = EXCLUDED.source_type,
                    source_url = EXCLUDED.source_url,
                    ingestion_path = EXCLUDED.ingestion_path,
                    summary = EXCLUDED.summary,
                    why_showing = EXCLUDED.why_showing,
                    status = CASE
                        WHEN build_reviews.status = ANY(%s) THEN build_reviews.status
                        ELSE EXCLUDED.status
                    END,
                    decision = COALESCE(build_reviews.decision, EXCLUDED.decision),
                    response_notes = COALESCE(build_reviews.response_notes, EXCLUDED.response_notes),
                    resolution_capture_id = COALESCE(build_reviews.resolution_capture_id, EXCLUDED.resolution_capture_id),
                    payload = COALESCE(build_reviews.payload, '{}'::jsonb) || EXCLUDED.payload,
                    updated_at = NOW()
                RETURNING id, title, status, source_type, source_url, ingestion_path, summary, why_showing,
                          decision, response_notes, resolution_capture_id, payload, created_at, updated_at, resolved_at
                """,
                (
                    review_id,
                    payload.title,
                    payload.status or "pending",
                    payload.source_type,
                    payload.source_url,
                    payload.ingestion_path,
                    payload.summary,
                    payload.why_showing,
                    payload.decision,
                    payload.response_notes,
                    payload.resolution_capture_id,
                    Json(payload.payload or {}),
                    list(TERMINAL_BUILD_STATUSES),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_review(row)


def update_review(review_id: str, payload: BuildReviewUpdate) -> Optional[BuildReview]:
    pool = get_pool()
    fields = []
    values = []
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
        if payload.status in TERMINAL_BUILD_STATUSES:
            fields.append("resolved_at = NOW()")
    if payload.decision is not None:
        fields.append("decision = %s")
        values.append(payload.decision)
    if payload.response_notes is not None:
        fields.append("response_notes = %s")
        values.append(payload.response_notes)
    if payload.resolution_capture_id is not None:
        fields.append("resolution_capture_id = %s")
        values.append(payload.resolution_capture_id)
    if payload.payload is not None:
        fields.append("payload = COALESCE(payload, '{}'::jsonb) || %s")
        values.append(Jsonb(payload.payload))
    if not fields:
        return get_review(review_id)

    fields.append("updated_at = NOW()")
    values.append(review_id)
    query = f"""
        UPDATE build_reviews
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, title, status, source_type, source_url, ingestion_path, summary, why_showing,
                  decision, response_notes, resolution_capture_id, payload, created_at, updated_at, resolved_at
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_review(row) if row else None


def _row_to_review(row: dict) -> BuildReview:
    if not row:
        raise ValueError("Build review row is empty")
    return BuildReview(
        id=str(row["id"]),
        title=row.get("title") or "Untitled",
        status=row.get("status") or "pending",
        source_type=row.get("source_type"),
        source_url=row.get("source_url"),
        ingestion_path=row.get("ingestion_path"),
        summary=row.get("summary"),
        why_showing=row.get("why_showing"),
        decision=row.get("decision"),
        response_notes=row.get("response_notes"),
        resolution_capture_id=row.get("resolution_capture_id"),
        payload=row.get("payload") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        resolved_at=row.get("resolved_at"),
    )
