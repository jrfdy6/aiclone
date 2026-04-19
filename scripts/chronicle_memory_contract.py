#!/usr/bin/env python3
"""Shared recent-chronicle plus durable-memory contract for cron and runner flows."""
from __future__ import annotations

import json
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPT_ROOT = WORKSPACE_ROOT / "scripts"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from app.services.core_memory_snapshot_service import expected_memory_read_mode, resolve_memory_read_target, resolve_snapshot_fallback_path
from durable_memory_context import build_durable_memory_context

CODEX_HANDOFF_PATH = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")

DEFAULT_MEMORY_PATHS: tuple[str, ...] = (
    "memory/persistent_state.md",
    "memory/cron-prune.md",
    "memory/daily-briefs.md",
    "memory/LEARNINGS.md",
    "memory/{today}.md",
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonicalize_chronicle_text(value: Any) -> str:
    normalized = _normalize_text(value)
    lowered = normalized.lower()
    if lowered.startswith("--- ## context") or "current fusion-os workspace is internally inconsistent" in lowered:
        return "Fusion OS needed a coherent content-and-signal operating model before weekly automation could be trusted."
    if "voice system" in lowered and "fusion academy dc" in lowered and "observation" in lowered and "guidance" in lowered:
        return (
            "Fusion content should use institutional voice, represent Fusion Academy DC, avoid first-person singular, "
            "and follow Observation -> Clarification -> Guidance."
        )
    if lowered.startswith("excellent please let me know what you need to implement"):
        return "Implement the approved Fusion operating model and audience-feedback loop."
    if "ai clone" in lowered and "workspace" in lowered and ("stand up" in lowered or "standup" in lowered):
        return "Jean-Claude should use whole-system AI Clone context to inform each workspace while only routing workspace-relevant signal into standups."
    if "jean claude" in lowered and ("multiple wrkspaces" in lowered or "multiple workspaces" in lowered):
        return "Jean-Claude needs a routing contract for using whole-system context across multiple workspaces."
    if lowered.startswith("i think a great place to start") and "jean claude" in lowered:
        return "Start with Jean-Claude's cross-workspace routing contract."
    if lowered.startswith("so he will need") and "workspace" in lowered:
        return "Jean-Claude should filter whole-system context down to the signals that matter for each workspace."
    if lowered in {"yes please do that.", "yes please do that", "please execute on both.", "please execute on both"}:
        return "Confirmed the next execution step."
    return normalized


def _trim_text(value: str, *, limit: int = 220) -> str:
    cleaned = _canonicalize_chronicle_text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def read_jsonl_tail(path: Path, *, max_items: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=max_items)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                lines.append(line)
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _compact_strings(values: Iterable[Any], *, limit: int, max_chars: int = 220) -> list[str]:
    compacted: list[str] = []
    for value in values:
        text = _trim_text(_normalize_text(value), limit=max_chars)
        if text:
            compacted.append(text)
        if len(compacted) >= limit:
            break
    return compacted


def _compact_chronicle_entry(entry: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "created_at": str(entry.get("created_at") or ""),
        "source": str(entry.get("source") or ""),
        "author_agent": str(entry.get("author_agent") or ""),
        "workspace_key": str(entry.get("workspace_key") or "shared_ops"),
        "summary": _trim_text(_normalize_text(entry.get("summary") or "")),
        "decisions": _compact_strings(entry.get("decisions") or [], limit=2),
        "blockers": _compact_strings(entry.get("blockers") or [], limit=2),
        "project_updates": _compact_strings(entry.get("project_updates") or [], limit=2),
        "follow_ups": _compact_strings(entry.get("follow_ups") or [], limit=2),
        "memory_promotions": _compact_strings(entry.get("memory_promotions") or [], limit=2),
        "pm_candidates": _compact_strings(entry.get("pm_candidates") or [], limit=2),
        "artifacts": _compact_strings(entry.get("artifacts") or [], limit=3, max_chars=180),
    }
    return {key: value for key, value in compact.items() if value}


def _workspace_entry_matches(workspace_key: str, entry_workspace: str, *, include_shared_ops: bool = False) -> bool:
    if workspace_key == "shared_ops":
        return True
    allowed = {workspace_key}
    if include_shared_ops:
        allowed.add("shared_ops")
    return entry_workspace in allowed


def filter_recent_chronicle_entries(
    workspace_key: str,
    *,
    max_items: int = 8,
    path: Path = CODEX_HANDOFF_PATH,
    include_shared_ops: bool = False,
) -> list[dict[str, Any]]:
    entries = read_jsonl_tail(path, max_items=max(max_items * 3, max_items))
    filtered: list[dict[str, Any]] = []
    for item in entries:
        entry_workspace = str(item.get("workspace_key") or "shared_ops")
        if not _workspace_entry_matches(workspace_key, entry_workspace, include_shared_ops=include_shared_ops):
            continue
        filtered.append(_compact_chronicle_entry(item))
    return filtered[-max_items:]


def durable_memory_hints(
    workspace_key: str,
    seed_texts: Iterable[Any],
    chronicle_entries: Iterable[dict[str, Any]],
) -> list[str]:
    hints: list[str] = [workspace_key]
    for item in seed_texts:
        text = _normalize_text(item)
        if text:
            hints.append(text)
    for entry in chronicle_entries:
        for field in (
            entry.get("summary"),
            *(entry.get("decisions") or [])[:2],
            *(entry.get("memory_promotions") or [])[:2],
            *(entry.get("learning_updates") or [])[:1],
            *(entry.get("follow_ups") or [])[:1],
            *(entry.get("pm_candidates") or [])[:1],
        ):
            text = _normalize_text(field)
            if text:
                hints.append(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        lowered = hint.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(hint)
    return deduped


def _resolve_relative_path(relative_path: str) -> str:
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    return relative_path.replace("{today}", today)


def _tail_text(path: Path, *, max_chars: int = 1800) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return text[-max_chars:]


def inspect_memory_path(
    path: Path | None = None,
    *,
    relative_path: str,
    now: datetime | None = None,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_resolution = resolution
    if active_resolution is None and path is None:
        active_resolution = resolve_memory_read_target(WORKSPACE_ROOT, relative_path)
        path = active_resolution["resolved_path"]
    if path is None:
        raise ValueError("inspect_memory_path requires either path or resolution.")

    expected_mode = expected_memory_read_mode(relative_path)
    resolved_mode = expected_mode if path.exists() else "missing"
    fallback_active = resolved_mode != expected_mode
    expected_path = path
    snapshot_id = None
    runtime_path = None
    live_path = path
    snapshot_path = None
    missing = not path.exists()
    if active_resolution is not None:
        expected_mode = str(active_resolution.get("expected_mode") or expected_mode)
        resolved_mode = str(active_resolution.get("resolved_mode") or resolved_mode)
        fallback_active = bool(active_resolution.get("fallback_active"))
        expected_path = Path(active_resolution.get("expected_path") or path)
        snapshot_id = active_resolution.get("snapshot_id")
        runtime_path = active_resolution.get("runtime_path")
        live_path = active_resolution.get("live_path") or live_path
        snapshot_path = active_resolution.get("snapshot_path")
        missing = bool(active_resolution.get("missing"))

    diagnostics: dict[str, Any] = {
        "relative_path": relative_path,
        "path": str(path),
        "exists": path.exists(),
        "expected_mode": expected_mode,
        "resolution_mode": resolved_mode,
        "fallback_active": fallback_active,
        "expected_path": str(expected_path),
        "runtime_path": str(runtime_path) if runtime_path else None,
        "live_path": str(live_path),
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
        "snapshot_id": snapshot_id,
        "missing": missing,
        "runtime_out_of_sync": bool(active_resolution.get("runtime_out_of_sync")) if active_resolution else False,
        "live_newer_by_hours": active_resolution.get("live_newer_by_hours") if active_resolution else None,
    }
    if not path.exists():
        return diagnostics

    current = now or datetime.now(timezone.utc)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    diagnostics["modified_at_utc"] = mtime.isoformat().replace("+00:00", "Z")
    diagnostics["age_hours"] = round((current - mtime).total_seconds() / 3600, 2)

    if relative_path != "memory/persistent_state.md":
        return diagnostics

    text = path.read_text(encoding="utf-8", errors="ignore")
    boilerplate_flags: list[str] = []
    for line in (
        "Daily log input processing completed without errors.",
        "Latest heartbeats are syncing, ensuring ongoing stability.",
        "No significant new blockers identified; systems remain optimal.",
    ):
        if line in text:
            boilerplate_flags.append(line)
    diagnostics["boilerplate_flags"] = boilerplate_flags

    match = re.search(r"^# Snapshot for ([A-Za-z]+ \d{1,2}, \d{4})$", text, re.MULTILINE)
    if match:
        snapshot_date = datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
        diagnostics["snapshot_heading_date"] = snapshot_date
        diagnostics["snapshot_heading_stale"] = snapshot_date != current.date().isoformat()
    else:
        diagnostics["snapshot_heading_stale"] = False
    return diagnostics


def _memory_context_key(relative_path: str) -> str:
    resolved = _resolve_relative_path(relative_path)
    if resolved == "memory/persistent_state.md":
        return "persistent_state_tail"
    if resolved == "memory/cron-prune.md":
        return "cron_prune_tail"
    if resolved == "memory/daily-briefs.md":
        return "daily_briefs_tail"
    if resolved == "memory/LEARNINGS.md":
        return "learnings_tail"
    if re.fullmatch(r"memory/\d{4}-\d{2}-\d{2}\.md", resolved):
        return "today_log_tail"
    stem = Path(resolved).stem.replace("-", "_")
    return f"{stem}_tail"


def build_memory_tail_context(
    relative_paths: Iterable[str] | None = None,
    *,
    max_chars: int = 1800,
) -> dict[str, Any]:
    resolved_paths = list(relative_paths or DEFAULT_MEMORY_PATHS)
    memory_context: dict[str, str] = {}
    source_paths: list[str] = []
    diagnostics: dict[str, Any] = {}
    for relative_path in resolved_paths:
        resolved_relative = _resolve_relative_path(relative_path)
        resolution = resolve_memory_read_target(WORKSPACE_ROOT, resolved_relative)
        path = Path(resolution["resolved_path"])
        memory_context[_memory_context_key(relative_path)] = _tail_text(path, max_chars=max_chars)
        source_paths.append(str(path))
        diagnostics[resolved_relative] = inspect_memory_path(
            path,
            relative_path=resolved_relative,
            resolution=resolution,
        )
    deduped_paths = list(dict.fromkeys(source_paths))
    return {
        "memory_context": memory_context,
        "source_paths": deduped_paths,
        "memory_diagnostics": diagnostics,
    }


def build_workspace_memory_contract(
    workspace_key: str,
    *,
    seed_texts: Iterable[Any] = (),
    chronicle_limit: int = 8,
    memory_paths: Iterable[str] | None = None,
    max_tail_chars: int = 1800,
    include_shared_ops: bool = False,
) -> dict[str, Any]:
    chronicle_entries = filter_recent_chronicle_entries(
        workspace_key,
        max_items=chronicle_limit,
        include_shared_ops=include_shared_ops,
    )
    hints = durable_memory_hints(workspace_key, seed_texts, chronicle_entries)
    durable_memory_context = build_durable_memory_context(workspace_key, hints)
    memory_payload = build_memory_tail_context(memory_paths, max_chars=max_tail_chars)
    source_paths = list(
        dict.fromkeys(
            [
                str(CODEX_HANDOFF_PATH),
                *memory_payload["source_paths"],
                *(durable_memory_context.get("source_paths") or []),
            ]
        )
    )
    return {
        "workspace_key": workspace_key,
        "chronicle_entry_count": len(chronicle_entries),
        "chronicle_entries": chronicle_entries,
        "durable_memory_context": durable_memory_context,
        "memory_context": memory_payload["memory_context"],
        "memory_diagnostics": memory_payload["memory_diagnostics"],
        "source_paths": source_paths,
        "queries": durable_memory_context.get("queries") or [],
    }
