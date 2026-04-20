from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, List
from uuid import uuid4

try:
    from psycopg.errors import UndefinedTable
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - local fallback when DB deps are absent
    UndefinedTable = Exception  # type: ignore[assignment]
    dict_row = None
    Jsonb = None  # type: ignore[assignment]

from app.models import DailyBrief
from app.services import brief_reaction_service
from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path
from app.services.daily_brief_parser import ParsedBrief, parse_briefs_markdown
from app.services.workspace_snapshot_store import list_snapshot_payloads

_WORKSPACE_CANDIDATES = (
    Path(os.getenv("OPENCLAW_WORKSPACE", "")),
    Path("/Users/neo/.openclaw/workspace"),
    Path(__file__).resolve().parents[3],
)


def list_daily_briefs(limit: int = 50) -> List[DailyBrief]:
    rows = _load_from_db(limit)
    local_rows = _load_from_local_files(limit)
    merged = _merge_briefs(rows, local_rows, limit=limit)
    return _attach_brief_stream(_attach_source_intelligence_overlay(merged))


def _load_from_db(limit: int) -> List[DailyBrief]:
    try:
        from app.services.open_brain_db import get_pool

        pool = get_pool()
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, brief_date, title, summary, content_markdown, source, source_ref, metadata, created_at, updated_at
                    FROM daily_briefs
                    ORDER BY brief_date DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall() or []
        return [_row_to_brief(row) for row in rows]
    except UndefinedTable:
        return []
    except Exception:
        return []


def sync_daily_briefs_from_markdown(
    raw_markdown: str,
    *,
    source: str = "workspace_markdown",
    source_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    expected_latest_brief_date: date | None = None,
) -> List[DailyBrief]:
    if not raw_markdown.strip():
        raise ValueError("Daily brief markdown is empty.")

    parsed = parse_briefs_markdown(raw_markdown, source_ref=source_ref)
    if not parsed:
        raise ValueError("No daily brief entries were found in the provided markdown.")

    latest_brief_date = max(entry.brief_date for entry in parsed)
    if expected_latest_brief_date and latest_brief_date != expected_latest_brief_date:
        raise ValueError(
            "Latest brief date "
            f"{latest_brief_date.isoformat()} does not match expected {expected_latest_brief_date.isoformat()}."
        )

    try:
        from app.services.open_brain_db import get_pool

        pool = get_pool()
    except Exception:
        return []

    synced: List[DailyBrief] = []
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            for entry in parsed:
                row_id = str(uuid4())
                row_metadata = dict(entry.metadata or {})
                row_metadata.update(metadata or {})
                row_metadata["synced_from_markdown"] = True
                if source_ref:
                    row_metadata["source_ref"] = source_ref
                cur.execute(
                    """
                    INSERT INTO daily_briefs (id, brief_date, title, summary, content_markdown, source, source_ref, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (brief_date) DO UPDATE
                    SET title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content_markdown = EXCLUDED.content_markdown,
                        source = EXCLUDED.source,
                        source_ref = EXCLUDED.source_ref,
                        metadata = COALESCE(daily_briefs.metadata, '{}'::jsonb) || EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id, brief_date, title, summary, content_markdown, source, source_ref, metadata, created_at, updated_at
                    """,
                    (
                        row_id,
                        entry.brief_date,
                        entry.title,
                        entry.summary,
                        entry.content_markdown,
                        source,
                        source_ref,
                        Jsonb(row_metadata) if Jsonb is not None else row_metadata,
                    ),
                )
                row = cur.fetchone()
                if row:
                    synced.append(_row_to_brief(row))
        conn.commit()

    synced.sort(key=lambda item: (item.brief_date, item.updated_at), reverse=True)
    return synced


def _load_from_local_files(limit: int) -> List[DailyBrief]:
    entries: List[DailyBrief] = []
    for workspace in _WORKSPACE_CANDIDATES:
        if not workspace:
            continue
        current_file = resolve_snapshot_fallback_path(workspace, "memory/daily-briefs.md")
        if current_file.exists():
            stat = current_file.stat()
            parsed = parse_briefs_markdown(current_file.read_text(), source_ref=str(current_file))
            entries.extend(
                _parsed_to_models(
                    parsed,
                    source="workspace_markdown",
                    file_updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
            break
    entries.sort(key=lambda item: (item.brief_date, item.updated_at), reverse=True)
    return entries[:limit]


def _parsed_to_models(parsed_entries: List[ParsedBrief], *, source: str, file_updated_at: datetime | None = None) -> List[DailyBrief]:
    models: List[DailyBrief] = []
    for entry in parsed_entries:
        timestamp = _aware_utc(file_updated_at or datetime.combine(entry.brief_date, time.min))
        models.append(
            DailyBrief(
                id=f"local-{entry.brief_date.isoformat()}",
                brief_date=entry.brief_date,
                title=entry.title,
                summary=entry.summary,
                content_markdown=entry.content_markdown,
                source=source,
                source_ref=entry.metadata.get("source_ref"),
                metadata=entry.metadata,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return models


def _merge_briefs(primary: List[DailyBrief], secondary: List[DailyBrief], *, limit: int) -> List[DailyBrief]:
    by_date: dict[str, DailyBrief] = {}
    for entry in [*primary, *secondary]:
        key = entry.brief_date.isoformat()
        current = by_date.get(key)
        if current is None:
            by_date[key] = _normalize_brief_datetimes(entry)
            continue
        normalized_entry = _normalize_brief_datetimes(entry)
        current_sort = (_aware_utc(current.updated_at), current.source == "workspace_markdown")
        entry_sort = (_aware_utc(normalized_entry.updated_at), normalized_entry.source == "workspace_markdown")
        if entry_sort > current_sort:
            by_date[key] = normalized_entry
    merged = list(by_date.values())
    merged.sort(key=lambda item: (item.brief_date, _aware_utc(item.updated_at)), reverse=True)
    return merged[:limit]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_brief_datetimes(entry: DailyBrief) -> DailyBrief:
    created_at = _aware_utc(entry.created_at)
    updated_at = _aware_utc(entry.updated_at)
    if created_at == entry.created_at and updated_at == entry.updated_at:
        return entry
    return entry.model_copy(update={"created_at": created_at, "updated_at": updated_at})


def _normalize_candidate_items(items: Any, *, limit: int = 3) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        candidate = {
            "title": str(item.get("title") or ""),
            "priority_lane": str(item.get("priority_lane") or ""),
            "source_kind": str(item.get("source_kind") or ""),
            "route_reason": str(item.get("route_reason") or ""),
            "handoff_lane": str(item.get("handoff_lane") or ""),
            "handoff_reason": str(item.get("handoff_reason") or ""),
            "target_file": str(item.get("target_file") or ""),
            "source_url": str(item.get("source_url") or ""),
            "source_path": str(item.get("source_path") or ""),
            "summary": str(item.get("rationale") or item.get("summary") or ""),
            "hook": str(item.get("hook") or ""),
            "response_modes": [
                str(value).strip()
                for value in (item.get("response_modes") or [])
                if str(value).strip()
            ],
            "secondary_consumers": [
                str(value).strip()
                for value in (item.get("secondary_consumers") or [])
                if str(value).strip()
            ],
        }
        candidate["item_key"] = brief_reaction_service.build_brief_item_key(candidate)
        normalized.append(
            candidate
        )
    return normalized


def _snapshot_payloads() -> dict[str, dict[str, Any]]:
    try:
        snapshot = list_snapshot_payloads("linkedin-content-os")
    except Exception:
        return {}

    payloads: dict[str, dict[str, Any]] = {}
    for key in ("weekly_plan", "long_form_routes", "source_assets", "persona_review_summary"):
        payload = snapshot.get(key)
        if isinstance(payload, dict):
            payloads[key] = payload
    return payloads


def _build_source_intelligence_overlay() -> dict[str, Any] | None:
    payloads = _snapshot_payloads()
    if not payloads:
        return None

    weekly_plan = payloads.get("weekly_plan") or {}
    long_form_routes = payloads.get("long_form_routes") or {}
    source_assets = payloads.get("source_assets") or {}
    persona_review_summary = payloads.get("persona_review_summary") or {}

    media_summary = weekly_plan.get("media_summary") if isinstance(weekly_plan, dict) else {}
    if not isinstance(media_summary, dict):
        media_summary = {}

    media_post_seeds = weekly_plan.get("media_post_seeds") if isinstance(weekly_plan, dict) else []
    brief_awareness_candidates = weekly_plan.get("brief_awareness_candidates") if isinstance(weekly_plan, dict) else []
    belief_evidence_candidates = weekly_plan.get("belief_evidence_candidates") if isinstance(weekly_plan, dict) else []
    operational_route_candidates = weekly_plan.get("operational_route_candidates") if isinstance(weekly_plan, dict) else []
    source_counts = weekly_plan.get("source_counts") if isinstance(weekly_plan, dict) else {}
    source_asset_counts = source_assets.get("counts") if isinstance(source_assets, dict) else {}
    belief_relation_counts = persona_review_summary.get("belief_relation_counts") if isinstance(persona_review_summary, dict) else {}
    recent_reviews = persona_review_summary.get("recent") if isinstance(persona_review_summary, dict) else []

    if not isinstance(source_counts, dict):
        source_counts = {}
    if not isinstance(source_asset_counts, dict):
        source_asset_counts = {}
    if not isinstance(belief_relation_counts, dict):
        belief_relation_counts = {}
    if not isinstance(recent_reviews, list):
        recent_reviews = []

    route_counts = media_summary.get("route_counts") or (long_form_routes.get("route_counts") if isinstance(long_form_routes, dict) else {}) or {}
    primary_route_counts = media_summary.get("primary_route_counts") or (
        long_form_routes.get("primary_route_counts") if isinstance(long_form_routes, dict) else {}
    ) or {}

    overlay = {
        "generated_at": media_summary.get("generated_at")
        or (weekly_plan.get("generated_at") if isinstance(weekly_plan, dict) else None)
        or (long_form_routes.get("generated_at") if isinstance(long_form_routes, dict) else None)
        or (persona_review_summary.get("generated_at") if isinstance(persona_review_summary, dict) else None),
        "base_generated_at": weekly_plan.get("base_generated_at") if isinstance(weekly_plan, dict) else None,
        "source_counts": source_counts,
        "source_asset_counts": source_asset_counts,
        "route_counts": route_counts if isinstance(route_counts, dict) else {},
        "primary_route_counts": primary_route_counts if isinstance(primary_route_counts, dict) else {},
        "belief_relation_counts": belief_relation_counts,
        "media_post_seed_count": len(media_post_seeds) if isinstance(media_post_seeds, list) else 0,
        "brief_awareness_count": len(brief_awareness_candidates) if isinstance(brief_awareness_candidates, list) else 0,
        "belief_evidence_candidate_count": len(belief_evidence_candidates) if isinstance(belief_evidence_candidates, list) else 0,
        "pm_route_candidate_count": len(operational_route_candidates) if isinstance(operational_route_candidates, list) else 0,
        "top_brief_awareness": _normalize_candidate_items(brief_awareness_candidates),
        "top_media_post_seeds": _normalize_candidate_items(media_post_seeds),
        "top_belief_evidence": _normalize_candidate_items(belief_evidence_candidates),
        "top_pm_route_candidates": _normalize_candidate_items(operational_route_candidates),
        "top_review_items": [
            {
                "trait": str(item.get("trait") or ""),
                "belief_relation": str(item.get("belief_relation") or ""),
                "review_source": str(item.get("review_source") or ""),
                "target_file": str(item.get("target_file") or ""),
            }
            for item in recent_reviews[:3]
            if isinstance(item, dict)
        ],
    }

    has_signal = any(
        [
            overlay["media_post_seed_count"],
            overlay["brief_awareness_count"],
            overlay["belief_evidence_candidate_count"],
            overlay["pm_route_candidate_count"],
            bool(overlay["route_counts"]),
            bool(overlay["belief_relation_counts"]),
        ]
    )
    return overlay if has_signal else None


def _attach_source_intelligence_overlay(entries: List[DailyBrief]) -> List[DailyBrief]:
    if not entries:
        return entries

    overlay = _build_source_intelligence_overlay()
    if not overlay:
        return entries

    latest_date = max(entry.brief_date for entry in entries)
    enriched: List[DailyBrief] = []
    for entry in entries:
        metadata = dict(entry.metadata or {})
        if entry.brief_date == latest_date:
            metadata["source_intelligence"] = overlay
            metadata["source_intelligence_live"] = True
        enriched.append(entry.model_copy(update={"metadata": metadata}))
    return enriched


def _attach_brief_stream(entries: List[DailyBrief]) -> List[DailyBrief]:
    if not entries:
        return entries

    enriched: List[DailyBrief] = []
    for entry in entries:
        metadata = dict(entry.metadata or {})
        overlay = metadata.get("source_intelligence")
        if not isinstance(overlay, dict):
            enriched.append(entry)
            continue

        brief_stream = _build_brief_stream(entry, overlay)
        if brief_stream:
            overlay = dict(overlay)
            overlay["brief_stream"] = brief_stream
            metadata["source_intelligence"] = overlay
        enriched.append(entry.model_copy(update={"metadata": metadata}))
    return enriched


def _build_brief_stream(entry: DailyBrief, overlay: dict[str, Any]) -> list[dict[str, Any]]:
    stream_items: list[dict[str, Any]] = []
    for section, candidates in (
        ("post_seed", overlay.get("top_media_post_seeds")),
        ("belief_evidence", overlay.get("top_belief_evidence")),
    ):
        if not isinstance(candidates, list):
            continue
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item["section"] = section
            item["item_key"] = str(item.get("item_key") or brief_reaction_service.build_brief_item_key(item, brief_id=entry.id))
            stream_items.append(item)

    if not stream_items:
        return []

    try:
        reactions_by_key = brief_reaction_service.list_reactions_by_item_key(
            brief_id=entry.id,
            item_keys=[str(item.get("item_key") or "") for item in stream_items],
            limit=120,
        )
    except Exception:
        reactions_by_key = {}
    try:
        related_context = brief_reaction_service.related_persona_context_for_items(stream_items)
    except Exception:
        related_context = {}

    enriched: list[dict[str, Any]] = []
    for item in stream_items:
        item_key = str(item.get("item_key") or "")
        enriched.append(
            {
                **item,
                "existing_reactions": [reaction.model_dump(mode="json") for reaction in reactions_by_key.get(item_key, [])[:3]],
                "related_persona_context": [context.model_dump(mode="json") for context in related_context.get(item_key, [])[:2]],
            }
        )
    return enriched


def _row_to_brief(row: dict) -> DailyBrief:
    return DailyBrief(
        id=str(row["id"]),
        brief_date=row["brief_date"],
        title=row["title"],
        summary=row.get("summary"),
        content_markdown=row.get("content_markdown") or "",
        source=row.get("source") or "unknown",
        source_ref=row.get("source_ref"),
        metadata=row.get("metadata") or {},
        created_at=_aware_utc(row["created_at"]),
        updated_at=_aware_utc(row["updated_at"]),
    )
