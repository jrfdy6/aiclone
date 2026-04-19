#!/usr/bin/env python3
"""Build a deterministic Progress Pulse digest from material Chronicle changes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
RUN_LOG = Path("/Users/neo/.openclaw/cron/runs/717f5346-f58f-4eac-ac30-014d8774a6c7.jsonl")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path
from brain_automation_context import (
    brain_signal_lines,
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
)
from chronicle_signal_quality import (
    clean_signal_text,
    entry_has_material_signal,
    entry_primary_signal,
    is_boilerplate_maintenance_text,
    looks_like_blocker,
    normalize_text,
)
from cron_digest_quality import ensure_digest
from cron_digest_support import (
    artifact_refs,
    chronicle_source_ref,
    entry_owner,
    load_runtime_context,
    match_pm_card,
    next_state_text,
    route_text,
)
from progress_pulse_gate import build_report


HANDOFF_LOG = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            rows.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return rows


def _parse_iso_ts(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _latest_delivered_run_ms() -> int | None:
    latest: int | None = None
    for row in _parse_jsonl(RUN_LOG):
        if row.get("action") != "finished" or not row.get("delivered"):
            continue
        run_at = row.get("runAtMs")
        if isinstance(run_at, int):
            latest = run_at
    return latest


def _recent_material_handoffs() -> list[dict[str, Any]]:
    since_ms = _latest_delivered_run_ms()
    rows: list[dict[str, Any]] = []
    for row in _parse_jsonl(HANDOFF_LOG):
        created_at_ms = _parse_iso_ts(row.get("created_at"))
        if since_ms is not None and (created_at_ms is None or created_at_ms <= since_ms):
            continue
        if entry_has_material_signal(row):
            rows.append(row)
    return rows


def _entry_workspace(entry: dict[str, Any]) -> str:
    return str(entry.get("workspace_key") or "shared_ops")


def _entry_owner(entry: dict[str, Any]) -> str:
    for field in ("pm_candidates", "follow_ups"):
        for item in entry.get(field) or []:
            text = normalize_text(item)
            if text.lower().startswith("host:"):
                return "Host"
    workspace_key = _entry_workspace(entry)
    if workspace_key != "shared_ops":
        return workspace_key
    author_agent = normalize_text(entry.get("author_agent"))
    return author_agent or "shared_ops"


def _trim(value: str, limit: int = 180) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _status(entries: list[dict[str, Any]], *, persistent_state_newer: bool) -> str:
    if any(entry.get("blockers") for entry in entries):
        return "red"
    if entries or persistent_state_newer:
        return "yellow"
    return "green"


def _highlight(entry: dict[str, Any]) -> str:
    workspace = _entry_workspace(entry)
    primary = clean_signal_text(entry_primary_signal(entry) or normalize_text(entry.get("summary")) or "Material Chronicle update recorded.")
    return f"`{workspace}`: {primary}"


def _blocker_lines(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for entry in entries:
        workspace = _entry_workspace(entry)
        for blocker in entry.get("blockers") or []:
            text = clean_signal_text(blocker)
            if not text or not looks_like_blocker(text) or is_boilerplate_maintenance_text(text):
                continue
            blockers.append(f"`{workspace}`: {_trim(text)}")
            if len(blockers) >= 3:
                return blockers
    return blockers


def _follow_up(entries: list[dict[str, Any]], *, persistent_state_newer: bool) -> str:
    for entry in entries:
        owner = _entry_owner(entry)
        for field in ("pm_candidates", "follow_ups", "project_updates"):
            for item in entry.get(field) or []:
                text = clean_signal_text(item)
                if not text or is_boilerplate_maintenance_text(text):
                    continue
                return f"yes — {owner}: {_trim(text)}"
        for blocker in entry.get("blockers") or []:
            text = clean_signal_text(blocker)
            if text and not is_boilerplate_maintenance_text(text):
                return f"yes — {owner}: resolve {_trim(text)}"
    if persistent_state_newer:
        return "yes — shared_ops: review the latest persistent-state changes and promote any missing PM or standup action."
    return "yes — shared_ops: review the latest Chronicle change and decide whether it belongs in PM, standup, or durable memory."


def _what_changed_lines(entries: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for entry in entries[-2:]:
        workspace = _entry_workspace(entry)
        signal = clean_signal_text(
            entry_primary_signal(entry) or normalize_text(entry.get("summary")) or "Material Chronicle update recorded."
        )
        if signal.lower().startswith("synced "):
            continue
        lines.append(f"`{workspace}`: {_trim(signal)}")
    return lines[:2]


def _why_it_matters_lines(entries: list[dict[str, Any]], pm_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    focus_cards = [item for item in (pm_context.get("cards") or []) if str(item.get("status") or "").lower() != "done"][:2]
    if focus_cards:
        titles = ", ".join(f"`{card.get('title')}`" for card in focus_cards if card.get("title"))
        if titles:
            lines.append(f"These signals are already sitting in active PM lanes: {titles}.")
    for entry in reversed(entries):
        follow_up = next((clean_signal_text(item) for item in (entry.get("follow_ups") or []) if clean_signal_text(item)), "")
        if follow_up and not is_boilerplate_maintenance_text(follow_up):
            lines.append(_trim(follow_up))
            break
    return lines[:2]


def _alert_lines(entries: list[dict[str, Any]], report: dict[str, Any]) -> list[str]:
    alerts = _blocker_lines(entries)
    diagnostics = report.get("persistent_state_diagnostics") or {}
    if diagnostics.get("snapshot_heading_stale") or diagnostics.get("boilerplate_flags"):
        alerts.append(
            "Persistent state is stale/boilerplate, so this digest is grounded in Chronicle and PM instead of `persistent_state.md`."
        )
    if not alerts:
        alerts.append("No new blocker was extracted from the latest material handoffs.")
    return alerts[:2]


def build_digest() -> str:
    report = build_report()
    if not report["should_deliver"]:
        return "NO_REPLY"

    entries = _recent_material_handoffs()
    primary = entries[-1] if entries else None
    runtime_context = load_runtime_context()
    pm_context = runtime_context.get("pm_context") or {}
    matched_card = match_pm_card(primary or {}, pm_context.get("cards") or []) if primary else None
    brain_context = build_brain_automation_context(signal_limit=3)
    owner = entry_owner(primary or {}, matched_card)
    workspace_value = _entry_workspace(primary or {}) if primary else "shared_ops"
    source_lines = []
    if primary:
        source_lines.append(f"- Chronicle: {chronicle_source_ref(primary)}")
    if matched_card:
        source_lines.append(
            f"- PM card: `{matched_card.get('id')}` `{matched_card.get('title')}`"
        )
    for ref in artifact_refs(primary or {}):
        source_lines.append(f"- Artifact: `{ref}`")
    source_lines.extend(f"- {item}" for item in source_intelligence_lines(brain_context, limit=1))
    if not source_lines:
        source_lines.append("- Chronicle: latest material handoff without attached artifact references.")
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *brain_signal_lines(brain_context, limit=1),
    ]

    lines = [
        f"Progress Pulse — {report['checked_at_utc']}",
        f"Status: {_status(entries, persistent_state_newer=bool(report['persistent_state_material']))}",
        "What Changed:",
    ]
    changed_lines = _what_changed_lines(entries)
    if changed_lines:
        lines.extend(f"- {item}" for item in changed_lines)
    else:
        lines.append("- A material persistent-state update landed without a newer Chronicle handoff.")
    lines.append("Why It Matters:")
    why_lines = _why_it_matters_lines(entries, pm_context)
    if why_lines:
        lines.extend(f"- {item}" for item in why_lines)
    else:
        lines.append("- The latest signal needs promotion into PM or standup before it can close with evidence.")
    lines.append("Action Now:")
    lines.append(f"- Owner: {owner}")
    lines.append(f"- Next: {_trim(next_state_text(primary or {}, matched_card), limit=160)}")
    lines.append("Routing:")
    lines.append(f"- Workspace: {workspace_value}")
    lines.append(f"- Route: {_trim(route_text(primary or {}, matched_card), limit=170)}")
    lines.append("Brain Context:")
    if brain_context_lines:
        lines.extend(f"- {item}" for item in brain_context_lines[:3])
    else:
        lines.append("- No active Brain Signal or portfolio blocker changes this pulse route.")
    lines.append("Source:")
    lines.extend(source_lines[:3])
    lines.append("Alerts:")
    lines.extend(f"- {item}" for item in _alert_lines(entries, report))
    digest = "\n".join(lines)
    return ensure_digest("progress_pulse", digest)


def main() -> int:
    print(build_digest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
