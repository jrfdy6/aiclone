from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from typing import Any, List

try:
    from psycopg.errors import UndefinedTable
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - local fallback when DB deps are absent
    UndefinedTable = Exception  # type: ignore[assignment]
    dict_row = None

from app.models import DailyBrief
from app.services.daily_brief_parser import ParsedBrief, parse_briefs_markdown

_WORKSPACE_CANDIDATES = (
    Path(os.getenv("OPENCLAW_WORKSPACE", "")),
    Path("/Users/neo/.openclaw/workspace"),
    Path(__file__).resolve().parents[3],
)


def list_daily_briefs(limit: int = 50) -> List[DailyBrief]:
    rows = _load_from_db(limit)
    if rows:
        return _attach_source_intelligence_overlay(rows)
    return _attach_source_intelligence_overlay(_load_from_local_files(limit))


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


def _load_from_local_files(limit: int) -> List[DailyBrief]:
    entries: List[DailyBrief] = []
    for workspace in _WORKSPACE_CANDIDATES:
        if not workspace:
            continue
        current_file = workspace / "memory" / "daily-briefs.md"
        if current_file.exists():
            parsed = parse_briefs_markdown(current_file.read_text(), source_ref=str(current_file))
            entries.extend(_parsed_to_models(parsed, source="workspace_markdown"))
            break
    entries.sort(key=lambda item: (item.brief_date, item.updated_at), reverse=True)
    return entries[:limit]


def _parsed_to_models(parsed_entries: List[ParsedBrief], *, source: str) -> List[DailyBrief]:
    models: List[DailyBrief] = []
    for entry in parsed_entries:
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
                created_at=datetime.combine(entry.brief_date, time.min),
                updated_at=datetime.combine(entry.brief_date, time.min),
            )
        )
    return models


def _normalize_candidate_items(items: Any, *, limit: int = 3) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title") or ""),
                "priority_lane": str(item.get("priority_lane") or ""),
                "source_kind": str(item.get("source_kind") or ""),
                "route_reason": str(item.get("route_reason") or ""),
                "target_file": str(item.get("target_file") or ""),
            }
        )
    return normalized


def _snapshot_payloads() -> dict[str, dict[str, Any]]:
    try:
        from app.services.workspace_snapshot_service import workspace_snapshot_service
    except Exception:
        return {}

    try:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
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
    belief_evidence_candidates = weekly_plan.get("belief_evidence_candidates") if isinstance(weekly_plan, dict) else []
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
        "belief_evidence_candidate_count": len(belief_evidence_candidates) if isinstance(belief_evidence_candidates, list) else 0,
        "top_media_post_seeds": _normalize_candidate_items(media_post_seeds),
        "top_belief_evidence": _normalize_candidate_items(belief_evidence_candidates),
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
            overlay["belief_evidence_candidate_count"],
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
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
