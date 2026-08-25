from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json, Jsonb

from app.models import PersonaDelta, PersonaDeltaCreate, PersonaDeltaResolve, PersonaDeltaUpdate
from app.services.open_brain_db import get_pool
from app.services.persona_review_queue_service import has_selectable_promotion_metadata


_PERSPECTIVE_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "and",
    "because",
    "being",
    "but",
    "from",
    "have",
    "into",
    "just",
    "more",
    "only",
    "over",
    "same",
    "some",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}
_OWNER_PERSPECTIVE_LINEAGE_SCHEMA = "owner_perspective_lineage/v1"
_OWNER_RESPONSE_HISTORY_SCHEMA = "owner_response_history/v1"


def perspective_terms(*values: Any, limit: int = 18) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
            if len(token) <= 2 or token in _PERSPECTIVE_STOPWORDS or token in seen:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= limit:
                return terms
    return terms


def _perspective_source_title(delta: PersonaDelta) -> str:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    return str(
        metadata.get("evidence_source")
        or metadata.get("brief_item_title")
        or metadata.get("source_asset_id")
        or delta.trait
        or "Owner perspective"
    ).strip()


def find_related_owner_perspectives(
    *,
    texts: Iterable[Any],
    metadata: dict[str, Any] | None = None,
    exclude_delta_id: str | None = None,
    limit: int = 4,
    deltas: Iterable[PersonaDelta] | None = None,
) -> list[dict[str, Any]]:
    """Return bounded owner-authored positions related to a source question.

    This is retrieval context, not a semantic judgment.  It never labels an
    opinion as changed, reinforced, or canonical; only the owner may do that.
    """

    current_metadata = metadata if isinstance(metadata, dict) else {}
    current_terms = set(
        perspective_terms(
            *texts,
            current_metadata.get("priority_lane"),
            current_metadata.get("lane_hint"),
            current_metadata.get("target_file"),
        )
    )
    current_url = str(current_metadata.get("source_url") or "").strip()
    current_item_key = str(current_metadata.get("brief_item_key") or "").strip()
    current_lane = str(current_metadata.get("priority_lane") or current_metadata.get("lane_hint") or "").strip().lower()
    candidates = list(deltas) if deltas is not None else list_deltas(limit=400)
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for delta in candidates:
        if exclude_delta_id and delta.id == exclude_delta_id:
            continue
        prior_metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        excerpt = str(prior_metadata.get("owner_response_excerpt") or "").strip()
        if not excerpt:
            continue
        prior_terms = set(
            str(value).strip().lower()
            for value in prior_metadata.get("perspective_topic_terms") or []
            if str(value).strip()
        )
        if not prior_terms:
            prior_terms = set(
                perspective_terms(
                    delta.trait,
                    delta.notes,
                    prior_metadata.get("evidence_source"),
                    prior_metadata.get("brief_item_title"),
                    prior_metadata.get("brief_item_summary"),
                    prior_metadata.get("priority_lane"),
                    prior_metadata.get("lane_hint"),
                    prior_metadata.get("target_file"),
                )
            )
        overlap = len(current_terms.intersection(prior_terms))
        denominator = max(1, min(len(current_terms), len(prior_terms)))
        overlap_ratio = overlap / denominator
        prior_url = str(prior_metadata.get("source_url") or "").strip()
        exact_source = bool(current_url and prior_url and current_url == prior_url)
        prior_item_key = str(prior_metadata.get("brief_item_key") or "").strip()
        exact_item = bool(current_item_key and prior_item_key and current_item_key == prior_item_key)
        prior_lane = str(prior_metadata.get("priority_lane") or prior_metadata.get("lane_hint") or "").strip().lower()
        same_lane = bool(current_lane and prior_lane and current_lane == prior_lane)
        if not exact_source and not exact_item and (overlap < 2 or overlap_ratio < 0.24):
            continue
        score = (
            (12.0 if exact_item else 0.0)
            + (10.0 if exact_source else 0.0)
            + (overlap * 1.5)
            + (overlap_ratio * 4.0)
            + (1.0 if same_lane else 0.0)
        )
        created_timestamp = delta.created_at.timestamp() if delta.created_at else 0.0
        ranked.append(
            (
                score,
                created_timestamp,
                {
                    "delta_id": delta.id,
                    "trait": delta.trait,
                    "response_kind": str(prior_metadata.get("owner_response_kind") or "nuance"),
                    "excerpt": excerpt[:500],
                    "source_title": _perspective_source_title(delta)[:240],
                    "target_file": str(prior_metadata.get("target_file") or "") or None,
                    "review_source": str(prior_metadata.get("review_source") or "") or None,
                    "created_at": delta.created_at.isoformat() if delta.created_at else None,
                    "position_sequence": int(prior_metadata.get("perspective_position_sequence") or 1),
                    "relationship_status": "owner_not_explicitly_classified",
                },
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in ranked[: max(0, min(limit, 12))]]


def build_owner_perspective_lineage(
    *,
    texts: Iterable[Any],
    metadata: dict[str, Any] | None = None,
    exclude_delta_id: str | None = None,
    deltas: Iterable[PersonaDelta] | None = None,
) -> dict[str, Any]:
    current_metadata = metadata if isinstance(metadata, dict) else {}
    terms = perspective_terms(
        *texts,
        current_metadata.get("priority_lane"),
        current_metadata.get("lane_hint"),
        current_metadata.get("target_file"),
    )
    related = find_related_owner_perspectives(
        texts=texts,
        metadata=current_metadata,
        exclude_delta_id=exclude_delta_id,
        deltas=deltas,
    )
    previous_sequences = [int(item.get("position_sequence") or 1) for item in related]
    existing_response_revision = int(current_metadata.get("owner_response_revision") or 0)
    if existing_response_revision <= 0 and current_metadata.get("owner_response_excerpt"):
        existing_response_revision = 1
    existing_position_sequence = int(
        current_metadata.get("perspective_position_sequence") or existing_response_revision or 0
    )
    if existing_position_sequence > 0:
        previous_sequences.append(existing_position_sequence)
    topic_key = hashlib.sha256("|".join(sorted(terms)).encode("utf-8")).hexdigest()[:24]
    return {
        "perspective_lineage_schema": _OWNER_PERSPECTIVE_LINEAGE_SCHEMA,
        "perspective_topic_key": f"perspective-{topic_key}",
        "perspective_topic_terms": terms,
        "perspective_position_sequence": (max(previous_sequences) if previous_sequences else 0) + 1,
        "perspective_prior_position_count": len(related) + existing_response_revision,
        "perspective_prior_delta_ids": [str(item["delta_id"]) for item in related],
        "related_owner_positions": related,
        "perspective_relationship_status": (
            "owner_not_explicitly_classified"
            if related or existing_response_revision
            else "initial_position"
        ),
    }


def build_owner_response_history_metadata(
    existing_metadata: dict[str, Any] | None,
    *,
    response_kind: str,
    excerpt: str,
    recorded_at: str,
    capture_id: str | None,
) -> dict[str, Any]:
    metadata = existing_metadata if isinstance(existing_metadata, dict) else {}
    history = [dict(item) for item in metadata.get("owner_response_history") or [] if isinstance(item, dict)]
    prior_revision = int(metadata.get("owner_response_revision") or 0)
    if prior_revision <= 0 and history:
        prior_revision = max(int(item.get("revision") or 0) for item in history)
    if not history and metadata.get("owner_response_excerpt"):
        prior_revision = max(1, prior_revision)
        history.append(
            {
                "revision": prior_revision,
                "response_kind": str(metadata.get("owner_response_kind") or "nuance"),
                "excerpt": str(metadata.get("owner_response_excerpt") or "")[:500],
                "recorded_at": metadata.get("owner_response_updated_at"),
                "capture_id": metadata.get("resolution_capture_id"),
            }
        )
    revision = prior_revision + 1 if prior_revision else 1
    history.append(
        {
            "revision": revision,
            "response_kind": response_kind,
            "excerpt": excerpt[:500],
            "recorded_at": recorded_at,
            "capture_id": capture_id,
        }
    )
    return {
        "owner_response_history_schema": _OWNER_RESPONSE_HISTORY_SCHEMA,
        "owner_response_revision": revision,
        "owner_response_history": history[-20:],
        "owner_response_history_truncated": len(history) > 20,
    }


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


def sync_projected_review_candidates(
    items: list[dict[str, Any]],
    *,
    active_source_limit: int = 8,
) -> dict[str, Any]:
    """Idempotently add bounded canonical-source excerpts to Persona.

    One server-side advisory lock owns capacity and review-key arbitration.
    The canonical source body never reaches this function; each item is the
    already bounded, explicitly attributed projection validated by the route.
    """

    from app.services.social_persona_review_service import (
        projected_candidate_to_delta_payload,
    )

    bounded_limit = max(1, min(int(active_source_limit), 20))
    grouped: dict[str, list[tuple[dict[str, Any], PersonaDeltaCreate]]] = {}
    for raw_item in items:
        item = dict(raw_item)
        source_id = str(item.get("canonical_source_id") or "").strip()
        if not source_id:
            raise ValueError("canonical Persona projection is missing source identity")
        grouped.setdefault(source_id, []).append(
            (item, projected_candidate_to_delta_payload(item))
        )

    receipts: list[dict[str, Any]] = []
    created_count = 0
    existing_count = 0
    deferred_count = 0
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("canonical-persona-review-candidate-sync/v1",),
            )
            cur.execute(
                """SELECT DISTINCT metadata->>'canonical_source_id' AS source_id
                   FROM persona_deltas
                   WHERE status IN ('draft','pending','in_review')
                     AND metadata->>'review_origin'='canonical_sql'
                     AND COALESCE(metadata->>'canonical_source_id','') <> ''"""
            )
            active_sources = {
                str(row.get("source_id") or "").strip()
                for row in (cur.fetchall() or [])
                if str(row.get("source_id") or "").strip()
            }

            for source_id, source_items in grouped.items():
                review_keys = [str(item[0]["review_key"]) for item in source_items]
                cur.execute(
                    """SELECT id::text AS id,status,metadata
                       FROM persona_deltas
                       WHERE metadata->>'review_key' = ANY(%s)""",
                    (review_keys,),
                )
                existing_rows = cur.fetchall() or []
                existing_by_key: dict[str, dict[str, Any]] = {}
                for row in existing_rows:
                    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                    review_key = str(metadata.get("review_key") or "").strip()
                    if (
                        str(metadata.get("canonical_source_id") or "").strip() != source_id
                        or str(metadata.get("canonical_artifact_id") or "").strip()
                        != str(source_items[0][0]["canonical_artifact_id"])
                    ):
                        raise ValueError("canonical Persona review key belongs to different lineage")
                    existing_by_key[review_key] = dict(row)

                missing_candidate_count = len(source_items) - len(existing_by_key)
                would_open_active_source = (
                    missing_candidate_count > 0 and source_id not in active_sources
                )
                if would_open_active_source and len(active_sources) >= bounded_limit:
                    deferred_count += len(source_items)
                    receipts.append(
                        {
                            "canonical_source_id": source_id,
                            "canonical_artifact_id": str(source_items[0][0]["canonical_artifact_id"]),
                            "disposition": "deferred_capacity",
                            "candidate_count": len(source_items),
                            "created_count": 0,
                            "existing_count": 0,
                            "review_keys": review_keys,
                        }
                    )
                    continue

                source_created = 0
                source_existing = 0
                delta_ids: list[str] = []
                for item, payload in source_items:
                    review_key = str(item["review_key"])
                    existing = existing_by_key.get(review_key)
                    if existing is not None:
                        source_existing += 1
                        delta_ids.append(str(existing["id"]))
                        continue
                    cur.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (review_key,),
                    )
                    cur.execute(
                        """SELECT id::text AS id,status,metadata
                           FROM persona_deltas
                           WHERE metadata->>'review_key'=%s
                           ORDER BY created_at DESC
                           LIMIT 1""",
                        (review_key,),
                    )
                    raced = cur.fetchone()
                    if raced is not None:
                        raced_metadata = raced.get("metadata") if isinstance(raced.get("metadata"), dict) else {}
                        if (
                            str(raced_metadata.get("canonical_source_id") or "").strip() != source_id
                            or str(raced_metadata.get("canonical_artifact_id") or "").strip()
                            != str(item["canonical_artifact_id"])
                        ):
                            raise ValueError("canonical Persona review key belongs to different lineage")
                        source_existing += 1
                        delta_ids.append(str(raced["id"]))
                        continue
                    delta_id = str(uuid4())
                    cur.execute(
                        """INSERT INTO persona_deltas(
                               id,capture_id,persona_target,trait,notes,status,metadata
                           ) VALUES (%s,%s,%s,%s,%s,'draft',%s)
                           RETURNING id::text AS id""",
                        (
                            delta_id,
                            payload.capture_id,
                            payload.persona_target,
                            payload.trait,
                            payload.notes,
                            Jsonb(payload.metadata or {}),
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted is None:
                        raise RuntimeError("canonical Persona review candidate was not stored")
                    source_created += 1
                    delta_ids.append(str(inserted["id"]))

                if source_created:
                    active_sources.add(source_id)
                created_count += source_created
                existing_count += source_existing
                receipts.append(
                    {
                        "canonical_source_id": source_id,
                        "canonical_artifact_id": str(source_items[0][0]["canonical_artifact_id"]),
                        "disposition": "created" if source_created else "idempotent_existing",
                        "candidate_count": len(source_items),
                        "created_count": source_created,
                        "existing_count": source_existing,
                        "review_keys": review_keys,
                        "delta_ids": delta_ids,
                    }
                )
        conn.commit()
    return {
        "created_count": created_count,
        "existing_count": existing_count,
        "deferred_count": deferred_count,
        "active_source_count": len(active_sources),
        "active_source_limit": bounded_limit,
        "source_receipts": receipts,
    }


def skip_brain_review(delta_id: str, *, scope: str) -> dict[str, Any] | None:
    """Resolve a claim or source without recording an owner opinion."""

    normalized_scope = str(scope or "source").strip().lower()
    if normalized_scope not in {"claim", "source"}:
        raise ValueError("Unsupported Persona review skip scope.")
    pool = get_pool()
    skipped_at = datetime.now(timezone.utc).isoformat()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT id::text AS id,status,metadata
                   FROM persona_deltas
                   WHERE id=%s
                   FOR UPDATE""",
                (delta_id,),
            )
            selected = cur.fetchone()
            if selected is None:
                return None
            metadata = selected.get("metadata") if isinstance(selected.get("metadata"), dict) else {}
            if str(metadata.get("review_source") or "").strip() != "long_form_media.segment":
                raise ValueError("Only source-review claims can be skipped through this action.")
            source_asset_id = str(metadata.get("source_asset_id") or "").strip()
            if normalized_scope == "source" and not source_asset_id:
                raise ValueError("This review item does not have a stable source identity.")

            if normalized_scope == "claim":
                cur.execute(
                    """SELECT id::text AS id
                       FROM persona_deltas
                       WHERE id=%s AND status IN ('draft','pending','in_review')""",
                    (delta_id,),
                )
            else:
                cur.execute(
                    """SELECT id::text AS id
                       FROM persona_deltas
                       WHERE metadata->>'source_asset_id'=%s
                         AND metadata->>'review_source'='long_form_media.segment'
                         AND status IN ('draft','pending','in_review')
                       ORDER BY created_at,id""",
                    (source_asset_id,),
                )
            target_ids = [str(row["id"]) for row in (cur.fetchall() or [])]
            if target_ids:
                skip_metadata = {
                    "review_disposition": "skipped",
                    "review_skip_scope": normalized_scope,
                    "review_skipped_at": skipped_at,
                    "review_completed": True,
                    "owner_comment_status": "declined",
                    "owner_evidence_created": False,
                    "source_retention": "attributed_external_knowledge",
                    "retrieval_policy": "unchanged",
                }
                cur.execute(
                    """UPDATE persona_deltas
                       SET status='resolved',
                           metadata=COALESCE(metadata,'{}'::jsonb) || %s
                       WHERE id = ANY(%s)""",
                    (Jsonb(skip_metadata), target_ids),
                )
        conn.commit()
    return {
        "scope": normalized_scope,
        "source_asset_id": source_asset_id or None,
        "skipped_count": len(target_ids),
        "skipped_delta_ids": target_ids,
        "owner_evidence_created": False,
        "source_retention": "attributed_external_knowledge",
    }


def apply_brain_review(
    delta_id: str,
    *,
    mode: str,
    response_kind: str,
    reflection_excerpt: str,
    resolution_capture_id: str | None = None,
    selected_promotion_items: list[dict] | None = None,
    complete_review: bool = False,
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
    keep_selectable_source_open = (
        normalized_mode == "reviewed"
        and not complete_review
        and has_selectable_promotion_metadata(existing_metadata)
    )
    review_status = "approved" if normalized_mode == "approved" else ("in_review" if keep_selectable_source_open else "reviewed")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    perspective_texts = (
        existing.trait,
        existing.notes,
        existing_metadata.get("evidence_source"),
        existing_metadata.get("brief_item_title"),
        existing_metadata.get("brief_item_summary"),
        existing_metadata.get("segment_excerpt"),
        existing_metadata.get("source_context_excerpt"),
    )
    try:
        perspective_lineage = build_owner_perspective_lineage(
            texts=perspective_texts,
            metadata=existing_metadata,
            exclude_delta_id=existing.id,
        )
    except Exception:
        perspective_lineage = {
            "perspective_lineage_schema": _OWNER_PERSPECTIVE_LINEAGE_SCHEMA,
            "perspective_topic_terms": perspective_terms(*perspective_texts),
            "perspective_prior_position_count": 0,
            "perspective_prior_delta_ids": [],
            "related_owner_positions": [],
            "perspective_relationship_status": "lineage_retrieval_unavailable",
        }
    response_history = build_owner_response_history_metadata(
        existing_metadata,
        response_kind=response_kind,
        excerpt=trimmed_excerpt,
        recorded_at=reviewed_at,
        capture_id=resolution_capture_id,
    )

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
        "review_completed": complete_review,
        "last_reviewed_at": reviewed_at,
        **perspective_lineage,
        **response_history,
    }
    if normalized_mode != "approved":
        update_metadata["pending_promotion"] = False

    update = PersonaDeltaUpdate(status=review_status, metadata=update_metadata)
    return update_delta(delta_id, update)
