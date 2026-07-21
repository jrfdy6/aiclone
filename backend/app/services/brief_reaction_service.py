from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable, List
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import (
    BriefReaction,
    BriefReactionCreate,
    BriefReactionCreateResponse,
    BriefReactionPersonaContext,
    CaptureRequest,
    PersonaDeltaCreate,
    PersonaDeltaUpdate,
)
from app.services import capture_service, persona_delta_service
from app.services.open_brain_db import get_pool
from app.services.persona_review_queue_service import annotate_for_brain_queue

_STOPWORDS = {
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


def build_brief_item_key(item: dict[str, Any] | BriefReactionCreate, *, brief_id: str | None = None) -> str:
    values = [
        brief_id or (str(item.get("brief_id") or "") if isinstance(item, dict) else item.brief_id),
        str(item.get("title") or item.get("item_title") or "") if isinstance(item, dict) else item.item_title,
        str(item.get("source_url") or "") if isinstance(item, dict) else (item.source_url or ""),
        str(item.get("source_path") or "") if isinstance(item, dict) else (item.source_path or ""),
        str(item.get("route_reason") or "") if isinstance(item, dict) else (item.route_reason or ""),
        str(item.get("target_file") or item.get("targetFile") or "") if isinstance(item, dict) else (item.target_file or ""),
    ]
    digest = hashlib.sha1("||".join(values).encode("utf-8")).hexdigest()
    return f"brief-item-{digest[:16]}"


def list_reactions(*, brief_id: str | None = None, item_keys: Iterable[str] | None = None, limit: int = 200) -> List[BriefReaction]:
    pool = get_pool()
    filters: list[str] = []
    params: list[Any] = []

    if brief_id:
        filters.append("brief_id = %s")
        params.append(brief_id)

    normalized_item_keys = [value.strip() for value in (item_keys or []) if str(value).strip()]
    if normalized_item_keys:
        filters.append("item_key = ANY(%s)")
        params.append(normalized_item_keys)

    params.append(limit)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT id, brief_id, item_key, item_title, reaction_kind, text, source_kind, source_url, source_path,
                       linked_delta_id, linked_capture_id, metadata, created_at, updated_at
                FROM brief_reactions
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall() or []
    return [_row_to_reaction(row) for row in rows]


def list_reactions_by_item_key(*, brief_id: str | None = None, item_keys: Iterable[str], limit: int = 200) -> dict[str, list[BriefReaction]]:
    grouped: dict[str, list[BriefReaction]] = defaultdict(list)
    for reaction in list_reactions(brief_id=brief_id, item_keys=item_keys, limit=limit):
        grouped[reaction.item_key].append(reaction)
    return grouped


def related_persona_context_for_items(items: list[dict[str, Any]], *, limit_per_item: int = 2, delta_limit: int = 250) -> dict[str, list[BriefReactionPersonaContext]]:
    if not items:
        return {}
    try:
        deltas = persona_delta_service.list_deltas(limit=delta_limit)
    except Exception:
        return {}

    results: dict[str, list[BriefReactionPersonaContext]] = {}
    for item in items:
        item_key = str(item.get("item_key") or "").strip()
        if not item_key:
            continue
        item_terms = _significant_terms(
            " ".join(
                part
                for part in (
                    str(item.get("title") or "").strip(),
                    str(item.get("summary") or "").strip(),
                    str(item.get("route_reason") or "").strip(),
                    str(item.get("target_file") or "").strip(),
                )
                if part
            )
        )
        if not item_terms:
            continue

        ranked: list[tuple[int, BriefReactionPersonaContext]] = []
        for delta in deltas:
            metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
            linked_item_key = str(metadata.get("brief_item_key") or "").strip()
            response_excerpt = str(metadata.get("owner_response_excerpt") or "").strip()
            trait = str(delta.trait or "").strip()
            comparison_terms = _significant_terms(" ".join(part for part in (trait, response_excerpt, delta.notes or "") if part))
            overlap = len(item_terms.intersection(comparison_terms))
            if linked_item_key == item_key:
                overlap += 5
            if overlap < 2:
                continue
            ranked.append(
                (
                    overlap,
                    BriefReactionPersonaContext(
                        delta_id=delta.id,
                        trait=trait,
                        response_kind=str(metadata.get("owner_response_kind") or "") or None,
                        excerpt=response_excerpt[:280] if response_excerpt else None,
                        target_file=str(metadata.get("target_file") or "") or None,
                        review_source=str(metadata.get("review_source") or "") or None,
                        created_at=delta.created_at,
                    ),
                )
            )
        ranked.sort(key=lambda entry: (entry[0], entry[1].created_at or 0), reverse=True)
        results[item_key] = [context for _, context in ranked[:limit_per_item]]
    return results


def create_reaction(payload: BriefReactionCreate) -> BriefReactionCreateResponse:
    trimmed_text = payload.text.strip()
    capture_result = capture_service.create_capture(
        CaptureRequest(
            text=_build_capture_text(payload),
            source="daily_brief_reaction",
            topics=_reaction_topics(payload),
            importance=2 if payload.reaction_kind == "story" else 3,
            metadata={
                "capture_kind": "daily_brief_reaction",
                "origin": "brain.daily_brief.stream",
                "brief_id": payload.brief_id,
                "brief_item_key": payload.item_key,
                "brief_item_title": payload.item_title,
                "reaction_kind": payload.reaction_kind,
                "source_kind": payload.source_kind,
                "source_url": payload.source_url,
                "source_path": payload.source_path,
                "target_file": payload.target_file or _default_target_file(payload.reaction_kind),
            },
        )
    )

    delta_metadata = {
        "review_source": "brain.daily_brief.stream",
        "review_state": "in_review",
        "owner_response_kind": payload.reaction_kind,
        "owner_response_excerpt": trimmed_text[:4000],
        "owner_response_updated_at": _utc_now_iso(),
        "resolution_capture_id": capture_result.capture_id,
        "brief_id": payload.brief_id,
        "brief_item_key": payload.item_key,
        "brief_item_title": payload.item_title,
        "brief_item_summary": payload.item_summary,
        "brief_item_hook": payload.item_hook,
        "source_kind": payload.source_kind,
        "source_url": payload.source_url,
        "source_path": payload.source_path,
        "priority_lane": payload.priority_lane,
        "route_reason": payload.route_reason,
        "target_file": payload.target_file or _default_target_file(payload.reaction_kind),
        "evidence_source": payload.item_title,
        "input_mode": "daily_brief_reaction",
        **_promotion_metadata_for_reaction(payload),
    }

    delta = persona_delta_service.create_delta(
        PersonaDeltaCreate(
            capture_id=capture_result.capture_id,
            persona_target="worldview",
            trait=payload.item_title.strip(),
            notes=(payload.item_summary or payload.route_reason or trimmed_text[:500]).strip() or None,
            metadata=delta_metadata,
        )
    )
    updated_delta = persona_delta_service.update_delta(delta.id, PersonaDeltaUpdate(status="in_review"))
    annotated_delta = annotate_for_brain_queue(updated_delta or delta)

    reaction_id = str(uuid4())
    reaction_metadata = dict(payload.metadata or {})
    reaction_metadata.update(
        {
            "item_summary": payload.item_summary,
            "item_hook": payload.item_hook,
            "priority_lane": payload.priority_lane,
            "route_reason": payload.route_reason,
            "target_file": payload.target_file or _default_target_file(payload.reaction_kind),
        }
    )

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO brief_reactions (
                    id, brief_id, item_key, item_title, reaction_kind, text, source_kind, source_url, source_path,
                    linked_delta_id, linked_capture_id, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, brief_id, item_key, item_title, reaction_kind, text, source_kind, source_url, source_path,
                          linked_delta_id, linked_capture_id, metadata, created_at, updated_at
                """,
                (
                    reaction_id,
                    payload.brief_id,
                    payload.item_key,
                    payload.item_title.strip(),
                    payload.reaction_kind,
                    trimmed_text,
                    payload.source_kind,
                    payload.source_url,
                    payload.source_path,
                    annotated_delta.id,
                    capture_result.capture_id,
                    Json(reaction_metadata),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return BriefReactionCreateResponse(
        reaction=_row_to_reaction(row),
        delta=annotated_delta,
        capture_id=capture_result.capture_id,
    )


def _row_to_reaction(row: dict[str, Any]) -> BriefReaction:
    return BriefReaction(
        id=str(row["id"]),
        brief_id=str(row["brief_id"]),
        item_key=str(row["item_key"]),
        item_title=str(row["item_title"]),
        reaction_kind=str(row["reaction_kind"]),
        text=str(row["text"]),
        source_kind=row.get("source_kind"),
        source_url=row.get("source_url"),
        source_path=row.get("source_path"),
        linked_delta_id=row.get("linked_delta_id"),
        linked_capture_id=row.get("linked_capture_id"),
        metadata=row.get("metadata") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _promotion_metadata_for_reaction(payload: BriefReactionCreate) -> dict[str, Any]:
    trimmed = payload.text.strip()
    if payload.reaction_kind == "story":
        return {
            "anecdotes": [
                {
                    "title": payload.item_title.strip(),
                    "summary": trimmed,
                    "evidence": payload.item_summary or payload.route_reason or trimmed,
                }
            ]
        }
    if payload.reaction_kind == "agree":
        return {"talking_points": [trimmed]}
    if payload.reaction_kind == "disagree":
        return {"talking_points": [f"Disagreement: {trimmed}"]}
    return {"talking_points": [trimmed]}


def _default_target_file(reaction_kind: str) -> str:
    normalized = (reaction_kind or "").strip().lower()
    if normalized == "story":
        return "history/story_bank.md"
    return "identity/claims.md"


def _build_capture_text(payload: BriefReactionCreate) -> str:
    lines = [
        f"Daily brief item: {payload.item_title.strip()}",
        f"Reaction kind: {payload.reaction_kind}",
    ]
    if (payload.item_summary or "").strip():
        lines.append(f"Summary: {payload.item_summary.strip()}")
    if (payload.route_reason or "").strip():
        lines.append(f"Why it matters: {payload.route_reason.strip()}")
    if (payload.item_hook or "").strip():
        lines.append(f"Hook: {payload.item_hook.strip()}")
    lines.extend(["", "My take:", payload.text.strip()])
    return "\n".join(lines).strip()


def _reaction_topics(payload: BriefReactionCreate) -> list[str]:
    topics = [
        payload.priority_lane or "",
        payload.source_kind or "",
        payload.item_title or "",
    ]
    normalized = []
    seen: set[str] = set()
    for topic in topics:
        compact = " ".join(str(topic or "").split()).strip()
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(compact[:120])
    return normalized[:5]


def _significant_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
