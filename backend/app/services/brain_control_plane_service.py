from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import open_brain_metrics, open_brain_service
from app.services.automation_service import list_automations
from app.services.brain_signal_service import count_signals, list_signals
from app.services.donor_repo_boundary_service import build_donor_repo_boundary_report
from app.services.email_draft_canary_service import build_email_draft_canary_report
from app.services.fallback_policy_service import build_fallback_policy_report
from app.services.portfolio_workspace_snapshot_service import build_portfolio_workspace_snapshot
from app.services.repo_surface_registry_service import build_repo_surface_registry
from app.services.truth_lane_cleanup_service import build_truth_lane_cleanup_report
from app.services.work_lifecycle_service import build_work_lifecycle_report
from app.services.workspace_registry_service import REPO_ROOT
from app.services.workspace_snapshot_store import get_snapshot_payload
from app.services.workspace_snapshot_service import workspace_snapshot_service


ROOT = REPO_ROOT
SOURCE_INTELLIGENCE_INDEX_PATH = ROOT / "knowledge" / "source-intelligence" / "index.json"
SOURCE_INTELLIGENCE_INDEX_FILENAMES = ("index.json", "index.json.txt")
SOURCE_ASSET_PREVIEW_LIMIT = 12
SOCIAL_FEED_PREVIEW_LIMIT = 6
WEEKLY_RECOMMENDATION_PREVIEW_LIMIT = 6
REACTION_QUEUE_PREVIEW_LIMIT = 6
BRAIN_DOC_ROOTS = (
    "knowledge/aiclone",
    "knowledge/source-intelligence",
    "docs",
    "SOPs",
    "knowledge/persona/feeze",
    "workspaces/shared-ops/docs",
    "workspaces/linkedin-content-os/docs",
    "workspaces/fusion-os/docs",
    "workspaces/easyoutfitapp/docs",
    "workspaces/ai-swag-store/docs",
    "workspaces/agc/docs",
)
BRAIN_DOC_EXPLICIT_FILES = (
    "memory/persistent_state.md",
    "memory/LEARNINGS.md",
    "memory/daily-briefs.md",
    "memory/cron-prune.md",
    "memory/dream_cycle_log.md",
    "memory/codex_session_handoff.jsonl",
    "memory/reports/brain_canonical_memory_sync_latest.md",
)

_WORKSPACE_SNAPSHOT_SIGNALS = (
    "weekly_plan",
    "reaction_queue",
    "social_feed",
    "feedback_summary",
    "source_assets",
    "content_reservoir",
    "operator_story_signals",
    "content_safe_operator_lessons",
    "persona_review_summary",
    "long_form_routes",
)

_SOURCE_ASSET_ITEM_KEYS = (
    "asset_id",
    "title",
    "source_channel",
    "source_type",
    "source_path",
    "source_url",
    "captured_at",
)

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


def _compact_source_assets(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(payload, ("workspace", "generated_at", "counts"))
    compacted["items"] = _compact_items(payload.get("items"), _SOURCE_ASSET_ITEM_KEYS, limit=SOURCE_ASSET_PREVIEW_LIMIT)
    return compacted


def _compact_content_reservoir(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(payload, ("workspace", "generated_at", "counts"))
    if "counts" not in compacted:
        items = payload.get("items")
        compacted["counts"] = {"total": len(items) if isinstance(items, list) else 0}
    return compacted


def _compact_long_form_routes(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return _pick_dict(
        payload,
        (
            "generated_at",
            "assets_considered",
            "segments_total",
            "route_counts",
            "primary_route_counts",
            "handoff_lane_counts",
        ),
    )


def _compact_weekly_plan(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    compacted = _pick_dict(payload, ("workspace", "generated_at", "base_generated_at", "source_counts"))
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
    compacted: dict[str, Any] = {
        "workspace_files": snapshot.get("workspace_files") if isinstance(snapshot.get("workspace_files"), list) else [],
        "doc_entries": snapshot.get("doc_entries") if isinstance(snapshot.get("doc_entries"), list) else [],
        "weekly_plan": _compact_weekly_plan(snapshot.get("weekly_plan")),
        "reaction_queue": _compact_reaction_queue(snapshot.get("reaction_queue")),
        "social_feed": _compact_social_feed(snapshot.get("social_feed")),
        "feedback_summary": snapshot.get("feedback_summary"),
        "source_assets": _compact_source_assets(snapshot.get("source_assets")),
        "content_reservoir": _compact_content_reservoir(snapshot.get("content_reservoir")),
        "operator_story_signals": snapshot.get("operator_story_signals"),
        "content_safe_operator_lessons": snapshot.get("content_safe_operator_lessons"),
        "persona_review_summary": snapshot.get("persona_review_summary"),
        "long_form_routes": _compact_long_form_routes(snapshot.get("long_form_routes")),
        "refresh_status": snapshot.get("refresh_status"),
    }
    return {key: value for key, value in compacted.items() if value is not None}


def _source_intelligence_index_candidates() -> list[Path]:
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
    paths = [root / "knowledge" / "source-intelligence" / filename for root in roots for filename in SOURCE_INTELLIGENCE_INDEX_FILENAMES]
    return list(dict.fromkeys(paths))


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
    recent_sources: list[dict[str, Any]] = []
    if isinstance(sources, list):
        for source in sources[:8]:
            if not isinstance(source, dict):
                continue
            recent_sources.append(
                _pick_dict(
                    source,
                    (
                        "source_id",
                        "source_kind",
                        "source_class",
                        "source_channel",
                        "source_type",
                        "title",
                        "status",
                        "raw_path",
                        "normalized_path",
                        "digest_path",
                    ),
                )
            )
    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "source_ref": str(index_path),
        "counts": payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
        "recent_sources": recent_sources,
    }


def _count_brain_docs() -> int:
    paths: set[str] = set()
    for relative_dir in BRAIN_DOC_ROOTS:
        directory = ROOT / relative_dir
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            if path.is_file():
                paths.add(path.resolve().as_posix())

    for relative_path in BRAIN_DOC_EXPLICIT_FILES:
        path = ROOT / relative_path
        if path.exists() and path.is_file():
            paths.add(path.resolve().as_posix())

    memory_dir = ROOT / "memory"
    if memory_dir.exists() and memory_dir.is_dir():
        latest_daily_log = sorted(path for path in memory_dir.glob("????-??-??.md") if path.is_file())
        if latest_daily_log:
            paths.add(latest_daily_log[-1].resolve().as_posix())

    return len(paths)


def build_brain_control_plane() -> dict[str, Any]:
    automations = list_automations()
    telemetry = open_brain_metrics.fetch_metrics()
    telemetry_health = open_brain_service.fetch_health().model_dump()
    workspace_snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
        persisted_only=True,
        include_workspace_files=False,
        include_doc_entries=False,
    )
    if not any(
        workspace_snapshot.get(key)
        for key in (
            *_WORKSPACE_SNAPSHOT_SIGNALS,
        )
    ):
        workspace_snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
            include_workspace_files=False,
            include_doc_entries=False,
        )
    workspace_snapshot = _compact_workspace_snapshot(workspace_snapshot)
    brain_memory_sync = get_snapshot_payload("shared_ops", "brain_memory_sync")
    portfolio_snapshot = build_portfolio_workspace_snapshot()
    repo_surface_registry = build_repo_surface_registry(include_entries=False)
    fallback_policy = build_fallback_policy_report(include_entries=False)
    truth_lane_cleanup = build_truth_lane_cleanup_report(include_findings=False)
    work_lifecycle = build_work_lifecycle_report(include_samples=False)
    donor_repo_boundary = build_donor_repo_boundary_report(include_targets=False)
    email_draft_canary = build_email_draft_canary_report(include_samples=False)
    recent_brain_signals = [signal.model_dump(mode="json") for signal in list_signals(limit=8)]
    brain_signal_count = count_signals()
    source_intelligence_index = _load_source_intelligence_index()
    persona_counts = ((workspace_snapshot.get("persona_review_summary") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}
    source_asset_counts = ((workspace_snapshot.get("source_assets") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}
    source_intelligence_counts = (source_intelligence_index or {}).get("counts") or {}
    repo_surface_summary = (repo_surface_registry or {}).get("summary") or {}
    repo_surface_status_counts = repo_surface_summary.get("status_counts") if isinstance(repo_surface_summary, dict) else {}
    fallback_policy_summary = (fallback_policy or {}).get("summary") or {}
    fallback_policy_counts = fallback_policy_summary.get("policy_class_counts") if isinstance(fallback_policy_summary, dict) else {}
    truth_lane_summary = (truth_lane_cleanup or {}).get("summary") or {}
    cleanup_decision = (truth_lane_cleanup or {}).get("cleanup_decision") or {}
    work_lifecycle_summary = (work_lifecycle or {}).get("summary") or {}
    donor_repo_summary = (donor_repo_boundary or {}).get("summary") or {}
    email_draft_canary_summary = (email_draft_canary or {}).get("summary") or {}
    email_draft_queue_summary = (email_draft_canary or {}).get("queue") or {}
    doc_count = _count_brain_docs()
    if not doc_count and isinstance(workspace_snapshot, dict):
        doc_count = len(workspace_snapshot.get("doc_entries") or [])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automations": automations,
        "telemetry": telemetry,
        "telemetry_health": telemetry_health,
        "brain_memory_sync": brain_memory_sync,
        "workspace_snapshot": workspace_snapshot,
        "portfolio_snapshot": portfolio_snapshot,
        "repo_surface_registry": repo_surface_registry,
        "fallback_policy": fallback_policy,
        "truth_lane_cleanup": truth_lane_cleanup,
        "work_lifecycle": work_lifecycle,
        "donor_repo_boundary": donor_repo_boundary,
        "email_draft_canary": email_draft_canary,
        "brain_signals": recent_brain_signals,
        "source_intelligence_index": source_intelligence_index,
        "summary": {
            "automation_count": len(automations),
            "active_automation_count": len([job for job in automations if str(getattr(job, "status", "")).lower() == "active"]),
            "capture_count": int(((telemetry.get("captures") or {}).get("total")) or 0),
            "doc_count": doc_count,
            "workspace_file_count": len((workspace_snapshot.get("workspace_files") or [])) if isinstance(workspace_snapshot, dict) else 0,
            "pending_review_count": int(persona_counts.get("brain_pending_review") or 0),
            "workspace_saved_count": int(persona_counts.get("workspace_saved") or 0),
            "source_asset_count": int(source_asset_counts.get("total") or 0),
            "brain_memory_sync_queue_count": int(((brain_memory_sync or {}).get("queued_route_count")) or 0),
            "portfolio_workspace_count": int(((portfolio_snapshot or {}).get("counts") or {}).get("workspaces") or 0),
            "portfolio_attention_count": int(((portfolio_snapshot or {}).get("counts") or {}).get("needs_brain_attention") or 0),
            "brain_signal_count": brain_signal_count,
            "source_intelligence_total": int(source_intelligence_counts.get("total") or 0),
            "source_intelligence_routed": int(source_intelligence_counts.get("routed") or 0),
            "repo_surface_count": int(repo_surface_summary.get("total_surfaces") or 0),
            "repo_surface_mismatch_count": int(repo_surface_summary.get("mismatch_count") or 0),
            "repo_surface_live_count": int(repo_surface_status_counts.get("live_and_production_relevant") or 0),
            "repo_surface_legacy_count": int(repo_surface_status_counts.get("present_but_dormant_legacy") or 0),
            "fallback_policy_count": int(fallback_policy_summary.get("total_policies") or 0),
            "fallback_allowed_count": int(fallback_policy_counts.get("allowed_in_production") or 0),
            "fallback_temporary_scaffold_count": int(fallback_policy_counts.get("temporary_scaffold") or 0),
            "fallback_failure_count": int(fallback_policy_counts.get("treat_as_failure") or 0),
            "truth_lane_cleanup_mode": str(cleanup_decision.get("mode") or ""),
            "truth_lane_suspect_count": int(truth_lane_summary.get("suspect_line_count") or 0),
            "lifecycle_open_count": int(work_lifecycle_summary.get("open_count") or 0),
            "lifecycle_written_back_count": int(work_lifecycle_summary.get("written_back_count") or 0),
            "lifecycle_closed_count": int(work_lifecycle_summary.get("closed_count") or 0),
            "donor_repo_count": int(donor_repo_summary.get("donor_repo_count") or 0),
            "donor_porting_target_count": int(donor_repo_summary.get("worth_porting_count") or 0),
            "donor_pending_extraction_count": int(donor_repo_summary.get("pending_extraction_count") or 0),
            "email_draft_canary_status": str(email_draft_canary_summary.get("status") or ""),
            "email_draft_queue_active_count": int(email_draft_queue_summary.get("active_count") or 0),
            "email_draft_queue_stale_count": int(email_draft_queue_summary.get("stale_job_count") or 0),
        },
    }
