from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import open_brain_metrics
from app.services.automation_service import list_automations
from app.services.brain_docs_service import count_brain_docs
from app.services.brain_response_privacy_service import sanitize_brain_payload
from app.services.brain_signal_service import list_signals_with_count
from app.services.workspace_registry_service import REPO_ROOT
from app.services.workspace_snapshot_store import get_snapshot_payload, list_snapshot_payloads
from app.services.workspace_snapshot_service import (
    project_linkedin_os_snapshot_for_browser,
    workspace_snapshot_service,
)


ROOT = REPO_ROOT
SOURCE_INTELLIGENCE_INDEX_FILENAMES = ("index.json", "index.json.txt")
SOCIAL_FEED_PREVIEW_LIMIT = 6
WEEKLY_RECOMMENDATION_PREVIEW_LIMIT = 6
REACTION_QUEUE_PREVIEW_LIMIT = 6
BRAIN_WORKSPACE_PREVIEW_TYPES = {
    "source_assets": "brain_source_assets_preview",
    "content_reservoir": "brain_content_reservoir_summary",
    "long_form_routes": "brain_long_form_routes_summary",
}

_PLAN_CANDIDATE_KEYS = (
    "title",
    "summary",
    "hook",
    "rationale",
    "source_path",
    "source_url",
    "priority_lane",
    "publish_posture",
    "score",
    "canonical_pillar",
    "career_signal",
    "employer_proximity",
    "employer_safety",
    "proof_posture",
    "audience",
    "audience_consequence",
    "distinct_thesis",
    "why_now",
    "development_status",
)

_REACTION_ITEM_KEYS = (
    "title",
    "author",
    "source_platform",
    "source_url",
    "source_path",
    "priority_lane",
    "hook",
    "summary",
    "why_it_matters",
    "suggested_comment",
    "post_angle",
    "score",
)

_SOCIAL_FEED_ITEM_KEYS = (
    "id",
    "platform",
    "title",
    "author",
    "source_url",
    "why_it_matters",
    "summary",
)


def _pick_dict(payload: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {key: payload[key] for key in keys if key in payload and payload[key] is not None}


def _compact_items(items: Any, keys: tuple[str, ...], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    compacted: list[dict[str, Any]] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            compacted.append(_pick_dict(item, keys))
    return compacted


def _compact_weekly_plan(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(
        payload,
        (
            "workspace",
            "generated_at",
            "base_generated_at",
            "source_counts",
            "strategy_contract",
            "strategy_contract_freshness",
            "pillar_coverage",
            "development_card_count",
        ),
    )
    for key in ("positioning_model", "priority_lanes"):
        value = payload.get(key)
        if isinstance(value, list):
            compacted[key] = value[:8]
    compacted["recommendations"] = _compact_items(
        payload.get("recommendations"),
        _PLAN_CANDIDATE_KEYS,
        limit=WEEKLY_RECOMMENDATION_PREVIEW_LIMIT,
    )
    compacted["hold_items"] = _compact_items(payload.get("hold_items"), _PLAN_CANDIDATE_KEYS, limit=3)
    return compacted


def _compact_reaction_queue(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(payload, ("workspace", "generated_at", "counts"))
    compacted["comment_opportunities"] = _compact_items(
        payload.get("comment_opportunities"),
        _REACTION_ITEM_KEYS,
        limit=REACTION_QUEUE_PREVIEW_LIMIT,
    )
    compacted["post_seeds"] = _compact_items(payload.get("post_seeds"), _REACTION_ITEM_KEYS, limit=REACTION_QUEUE_PREVIEW_LIMIT)
    return compacted


def _compact_social_feed_item(item: dict[str, Any]) -> dict[str, Any]:
    compacted = _pick_dict(item, _SOCIAL_FEED_ITEM_KEYS)
    standout_lines = item.get("standout_lines")
    if isinstance(standout_lines, list):
        compacted["standout_lines"] = [line for line in standout_lines[:3] if isinstance(line, str)]
    evaluation = item.get("evaluation")
    if isinstance(evaluation, dict):
        compacted["evaluation"] = _pick_dict(evaluation, ("overall", "genericity_penalty"))
    ranking = item.get("ranking")
    if isinstance(ranking, dict):
        compacted["ranking"] = _pick_dict(ranking, ("total",))
    return compacted


def _compact_social_feed(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(payload, ("workspace", "generated_at", "strategy_mode"))
    items = payload.get("items")
    if isinstance(items, list):
        compacted["items"] = [_compact_social_feed_item(item) for item in items[:SOCIAL_FEED_PREVIEW_LIMIT] if isinstance(item, dict)]
    else:
        compacted["items"] = []
    return compacted


def _compact_workspace_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    browser_snapshot = project_linkedin_os_snapshot_for_browser(snapshot)
    compacted: dict[str, Any] = {
        "workspace_files": [],
        "doc_entries": [],
        "weekly_plan": _compact_weekly_plan(browser_snapshot.get("weekly_plan")),
        "reaction_queue": _compact_reaction_queue(browser_snapshot.get("reaction_queue")),
        "social_feed": _compact_social_feed(browser_snapshot.get("social_feed")),
        "feedback_summary": browser_snapshot.get("feedback_summary"),
        "source_assets": browser_snapshot.get("source_assets"),
        "content_reservoir": browser_snapshot.get("content_reservoir"),
        "operator_story_signals": browser_snapshot.get("operator_story_signals"),
        "content_safe_operator_lessons": browser_snapshot.get("content_safe_operator_lessons"),
        "persona_review_summary": browser_snapshot.get("persona_review_summary"),
        "long_form_routes": browser_snapshot.get("long_form_routes"),
        "refresh_status": browser_snapshot.get("refresh_status"),
        "private_runtime_context_status": browser_snapshot.get("private_runtime_context_status"),
    }
    return {key: value for key, value in compacted.items() if value is not None}


def _overlay_local_runner_previews(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Prefer dedicated local-runner previews without mutating full pipeline snapshots."""
    try:
        persisted = list_snapshot_payloads("linkedin-content-os")
    except Exception:
        return snapshot
    overlaid = dict(snapshot)
    for response_key, snapshot_type in BRAIN_WORKSPACE_PREVIEW_TYPES.items():
        preview = persisted.get(snapshot_type)
        compacted = (
            project_linkedin_os_snapshot_for_browser({response_key: preview}).get(response_key)
            if isinstance(preview, dict)
            else None
        )
        if compacted is not None:
            overlaid[response_key] = compacted
    return overlaid


def _source_intelligence_index_candidates() -> list[Path]:
    state_root = Path(
        os.getenv("AI_CLONE_STATE_ROOT") or (Path.home() / ".codex" / "ai-clone" / "state")
    ).expanduser()
    roots = [
        ROOT,
        ROOT / "app",
        ROOT / "backend",
        ROOT / "backend" / "app",
        Path.cwd(),
        Path.cwd().parent,
        Path("/app"),
        Path("/app/app"),
        Path("/app/backend"),
        Path("/app/backend/app"),
        Path("/"),
    ]
    for parent in Path(__file__).resolve().parents:
        roots.extend(
            [
                parent,
                parent / "app",
                parent / "backend",
                parent / "backend" / "app",
            ]
        )
    paths = [state_root / "memory" / "source-intelligence" / "index.json"]
    paths.extend(
        root / "knowledge" / "source-intelligence" / filename
        for root in roots
        for filename in SOURCE_INTELLIGENCE_INDEX_FILENAMES
    )
    return list(dict.fromkeys(paths))


def _browser_timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _load_source_intelligence_index() -> dict[str, Any] | None:
    index_path = next((path for path in _source_intelligence_index_candidates() if path.exists()), None)
    if index_path is None:
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    sources = payload.get("sources")
    recent_source_count = min(len(sources), 8) if isinstance(sources, list) else 0
    raw_counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    safe_counts = {
        key: int(raw_counts.get(key) or 0)
        for key in ("total", "digested", "reviewed", "routed", "promoted", "ignored")
        if isinstance(raw_counts.get(key), int)
        and not isinstance(raw_counts.get(key), bool)
        and 0 <= raw_counts.get(key) <= 1_000_000
    }
    return {
        "schema_version": "source_intelligence_browser_status/v1",
        "generated_at": _browser_timestamp(payload.get("generated_at")),
        "source_mode": "deployed_snapshot",
        "counts": safe_counts,
        "recent_source_count": recent_source_count,
        "data_policy": {
            "projection": "aggregate_status_only",
            "source_names_included": False,
            "source_identifiers_included": False,
            "source_paths_included": False,
            "source_excerpts_included": False,
        },
    }


def build_brain_control_plane() -> dict[str, Any]:
    automations = list_automations()
    telemetry = open_brain_metrics.fetch_metrics()
    workspace_snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
        persisted_only=True,
        include_workspace_files=False,
        include_doc_entries=False,
    )
    workspace_snapshot = _compact_workspace_snapshot(workspace_snapshot)
    workspace_snapshot = _overlay_local_runner_previews(workspace_snapshot)
    brain_memory_sync = get_snapshot_payload("shared_ops", "brain_memory_sync")
    signal_preview, brain_signal_count = list_signals_with_count(limit=8)
    recent_brain_signals = [signal.model_dump(mode="json") for signal in signal_preview]
    source_intelligence_index = _load_source_intelligence_index()
    persona_counts = ((workspace_snapshot.get("persona_review_summary") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}
    persona_counts_available = any(
        key in persona_counts
        for key in (
            "brain_pending_review",
            "workspace_saved",
            "approved_unpromoted",
            "pending_promotion",
            "committed",
        )
    )
    source_asset_counts = ((workspace_snapshot.get("source_assets") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}
    source_intelligence_counts = (source_intelligence_index or {}).get("counts") or {}
    doc_count = count_brain_docs()

    response_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automations": automations,
        "telemetry": telemetry,
        "brain_memory_sync": brain_memory_sync,
        "workspace_snapshot": workspace_snapshot,
        "brain_signals": recent_brain_signals,
        "source_intelligence_index": source_intelligence_index,
        "summary": {
            "automation_count": len(automations),
            "active_automation_count": len([job for job in automations if str(getattr(job, "status", "")).lower() == "active"]),
            "capture_count": int(((telemetry.get("captures") or {}).get("total")) or 0),
            "doc_count": doc_count,
            "workspace_file_count": len((workspace_snapshot.get("workspace_files") or [])) if isinstance(workspace_snapshot, dict) else 0,
            "persona_review_available": persona_counts_available,
            "pending_review_count": int(persona_counts.get("brain_pending_review") or 0) if persona_counts_available else None,
            "workspace_saved_count": int(persona_counts.get("workspace_saved") or 0) if persona_counts_available else None,
            "source_asset_count": int(source_asset_counts.get("total") or 0),
            "brain_memory_sync_queue_count": int(((brain_memory_sync or {}).get("queued_route_count")) or 0),
            "brain_signal_count": brain_signal_count,
            "source_intelligence_total": int(source_intelligence_counts.get("total") or 0),
            "source_intelligence_routed": int(source_intelligence_counts.get("routed") or 0),
        },
    }
    return sanitize_brain_payload(response_payload)
