#!/usr/bin/env python3
"""Shared Brain substrate context for scheduled automations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SOURCE_INDEX_PATH = WORKSPACE_ROOT / "knowledge" / "source-intelligence" / "index.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _trim(value: Any, *, limit: int = 180) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _compact_signal(signal: Any) -> dict[str, Any]:
    payload = signal.model_dump(mode="json") if hasattr(signal, "model_dump") else dict(signal or {})
    latest_route = dict((payload.get("route_decision") or {}).get("latest") or {})
    summary = payload.get("digest") or payload.get("raw_summary") or ""
    return {
        "id": payload.get("id"),
        "source_kind": payload.get("source_kind"),
        "source_ref": payload.get("source_ref"),
        "source_workspace_key": payload.get("source_workspace_key") or "shared_ops",
        "summary": _trim(summary, limit=220),
        "signal_types": list(payload.get("signal_types") or [])[:6],
        "review_status": payload.get("review_status") or "new",
        "workspace_candidates": list(payload.get("workspace_candidates") or [])[:6],
        "route": latest_route.get("route"),
        "route_workspace_key": latest_route.get("workspace_key"),
        "updated_at": payload.get("updated_at"),
    }


def _compact_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    counts = dict(workspace.get("counts") or {})
    latest_state = ""
    latest_briefing = workspace.get("latest_briefing") or {}
    execution_log = workspace.get("execution_log") or {}
    latest_analytics = workspace.get("latest_analytics") or {}
    for candidate in (
        latest_briefing.get("snippet"),
        execution_log.get("snippet"),
        latest_analytics.get("snippet"),
        workspace.get("description"),
    ):
        latest_state = _trim(candidate, limit=180)
        if latest_state:
            break
    blockers: list[str] = []
    for standup in workspace.get("latest_standups") or []:
        blockers.extend(_trim(item, limit=160) for item in (standup.get("blockers") or []) if _clean_text(item))
    active_cards = []
    for card in workspace.get("active_pm_cards") or []:
        active_cards.append(
            {
                "id": card.get("id"),
                "title": _trim(card.get("title"), limit=140),
                "status": card.get("status"),
                "owner": card.get("owner"),
            }
        )
    return {
        "workspace_key": workspace.get("workspace_key"),
        "display_name": workspace.get("display_name") or workspace.get("workspace_key"),
        "status": workspace.get("status"),
        "latest_state": latest_state,
        "needs_brain_attention": bool(workspace.get("needs_brain_attention")),
        "counts": {
            "active_pm_cards": int(counts.get("active_pm_cards") or 0),
            "attention_pm_cards": int(counts.get("attention_pm_cards") or 0),
            "standup_blockers": int(counts.get("standup_blockers") or 0),
        },
        "blockers": blockers[:3],
        "active_pm_cards": active_cards[:3],
        "source_paths": list(workspace.get("source_paths") or [])[:8],
    }


def _read_source_index() -> dict[str, Any]:
    if not SOURCE_INDEX_PATH.exists():
        return {"available": False, "source_ref": str(SOURCE_INDEX_PATH), "counts": {}, "recent_sources": []}
    try:
        payload = json.loads(SOURCE_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "source_ref": str(SOURCE_INDEX_PATH),
            "error": str(exc),
            "counts": {},
            "recent_sources": [],
        }
    sources = [item for item in payload.get("sources") or [] if isinstance(item, dict)]
    return {
        "available": True,
        "source_ref": str(SOURCE_INDEX_PATH),
        "generated_at": payload.get("generated_at"),
        "schema_version": payload.get("schema_version"),
        "counts": dict(payload.get("counts") or {}),
        "recent_sources": [
            {
                "source_id": item.get("source_id"),
                "title": _trim(item.get("title"), limit=140),
                "status": item.get("status"),
                "source_kind": item.get("source_kind"),
                "source_ref": item.get("source_url") or item.get("raw_path") or item.get("digest_path"),
            }
            for item in sources[-5:]
        ],
    }


def build_brain_automation_context(
    *,
    signal_limit: int = 5,
    portfolio_pm_limit: int = 4,
    portfolio_standup_limit: int = 3,
) -> dict[str, Any]:
    """Return a compact Brain context payload that cron jobs can cite safely."""
    source_paths: list[str] = []
    errors: list[str] = []

    try:
        from app.services.brain_signal_service import SIGNALS_PATH, list_signals

        raw_signals = list_signals(limit=signal_limit)
        brain_signals = [_compact_signal(signal) for signal in raw_signals]
        source_paths.append(str(SIGNALS_PATH))
    except Exception as exc:
        brain_signals = []
        errors.append(f"brain_signals: {exc}")

    try:
        from app.services.portfolio_workspace_snapshot_service import build_portfolio_workspace_snapshot

        raw_snapshot = build_portfolio_workspace_snapshot(pm_limit=portfolio_pm_limit, standup_limit=portfolio_standup_limit)
        workspaces = [_compact_workspace(workspace) for workspace in (raw_snapshot.get("workspaces") or []) if isinstance(workspace, dict)]
        portfolio_snapshot = {
            "available": True,
            "generated_at": raw_snapshot.get("generated_at"),
            "schema_version": raw_snapshot.get("schema_version"),
            "counts": dict(raw_snapshot.get("counts") or {}),
            "workspaces": workspaces,
        }
        for workspace in workspaces:
            source_paths.extend(str(item) for item in workspace.get("source_paths") or [])
    except Exception as exc:
        portfolio_snapshot = {"available": False, "counts": {}, "workspaces": []}
        errors.append(f"portfolio_snapshot: {exc}")

    source_intelligence = _read_source_index()
    source_paths.append(str(SOURCE_INDEX_PATH))

    return {
        "available": not errors,
        "schema_version": "brain_automation_context/v1",
        "brain_signals": brain_signals,
        "portfolio_snapshot": portfolio_snapshot,
        "source_intelligence": source_intelligence,
        "source_paths": list(dict.fromkeys(path for path in source_paths if _clean_text(path))),
        "errors": errors,
    }


def brain_signal_lines(context: dict[str, Any], *, limit: int = 3) -> list[str]:
    lines: list[str] = []
    for signal in context.get("brain_signals") or []:
        status = _clean_text(signal.get("review_status")) or "new"
        workspace = _clean_text(signal.get("route_workspace_key") or signal.get("source_workspace_key")) or "shared_ops"
        summary = _trim(signal.get("summary"), limit=170)
        if summary:
            lines.append(f"Brain Signal `{status}` for `{workspace}`: {summary}")
        if len(lines) >= limit:
            break
    return lines


def workspace_brain_signal_lines(context: dict[str, Any], workspace_key: str, *, limit: int = 3) -> list[str]:
    normalized_workspace = _clean_text(workspace_key) or "shared_ops"
    lines: list[str] = []
    for signal in context.get("brain_signals") or []:
        candidates = {
            _clean_text(signal.get("source_workspace_key")),
            _clean_text(signal.get("route_workspace_key")),
            *[_clean_text(item) for item in signal.get("workspace_candidates") or []],
        }
        if normalized_workspace != "shared_ops" and normalized_workspace not in candidates:
            continue
        status = _clean_text(signal.get("review_status")) or "new"
        route = _clean_text(signal.get("route")) or "unrouted"
        summary = _trim(signal.get("summary"), limit=170)
        if summary:
            lines.append(f"Brain Signal `{status}` / `{route}`: {summary}")
        if len(lines) >= limit:
            break
    return lines


def portfolio_attention_lines(context: dict[str, Any], *, limit: int = 3) -> list[str]:
    snapshot = context.get("portfolio_snapshot") or {}
    workspaces = [workspace for workspace in (snapshot.get("workspaces") or []) if workspace.get("needs_brain_attention")]
    if not workspaces:
        return []
    lines: list[str] = []
    for workspace in workspaces:
        counts = workspace.get("counts") or {}
        display_name = _clean_text(workspace.get("display_name") or workspace.get("workspace_key"))
        lines.append(
            f"{display_name}: {int(counts.get('attention_pm_cards') or 0)} attention PM card(s), "
            f"{int(counts.get('standup_blockers') or 0)} standup blocker(s)."
        )
        if len(lines) >= limit:
            break
    return lines


def source_intelligence_lines(context: dict[str, Any], *, limit: int = 2) -> list[str]:
    source_intelligence = context.get("source_intelligence") or {}
    if not source_intelligence.get("available"):
        return []
    counts = source_intelligence.get("counts") or {}
    total = int(counts.get("total") or 0)
    routed = int(counts.get("routed") or 0)
    reviewed = int(counts.get("reviewed") or 0)
    digested = int(counts.get("digested") or 0)
    lines = [f"Source intelligence registry: {total} total, {digested} digested, {reviewed} reviewed, {routed} routed."]
    for source in (source_intelligence.get("recent_sources") or [])[: max(0, limit - 1)]:
        title = _trim(source.get("title"), limit=130)
        status = _clean_text(source.get("status")) or "indexed"
        if title:
            lines.append(f"Recent source `{status}`: {title}")
    return lines[:limit]
