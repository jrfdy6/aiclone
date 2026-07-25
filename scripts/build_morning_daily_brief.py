#!/usr/bin/env python3
"""Build a deterministic Morning Daily Brief from live operational evidence."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_bootstrap import maybe_reexec_with_workspace_venv  # noqa: E402
from runtime_paths import (  # noqa: E402
    PROJECT_ROOT,
    STATE_ROOT,
    memory_state_path,
    seed_memory_state_file,
)


WORKSPACE_ROOT = PROJECT_ROOT
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
DAILY_BRIEFS_LOGICAL_REF = "memory/daily-briefs.md"
DAILY_BRIEFS_PATH = memory_state_path("daily-briefs.md", state_root=STATE_ROOT)
BRIEF_TZ = ZoneInfo("America/New_York")
HEADING_RE = re.compile(r"(?m)^# Morning Daily Brief\s*[—-]\s*(\d{4}-\d{2}-\d{2})\s*$")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chronicle_memory_contract import build_memory_tail_context, filter_recent_chronicle_entries
from chronicle_signal_quality import clean_signal_text, entry_has_material_signal, entry_primary_signal, looks_like_blocker, normalize_text
from cron_digest_quality import ensure_digest
from cron_digest_support import (
    artifact_refs,
    chronicle_source_ref,
    entry_owner,
    load_runtime_context,
    match_pm_card,
    recent_focus_cards,
)
from brain_automation_context import (
    brain_signal_lines,
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
)
from heartbeat_report import build_report as build_heartbeat_report, render_summary as render_heartbeat_summary


MEMORY_PATHS: tuple[str, ...] = (
    "memory/persistent_state.md",
    "memory/cron-prune.md",
    "memory/doc-updates.md",
    "memory/LEARNINGS.md",
    "memory/daily-briefs.md",
    "memory/{today}.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", action="store_true", help="Upsert the current-date brief into memory/daily-briefs.md.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of markdown.")
    return parser.parse_args()


def _local_date() -> str:
    return datetime.now(BRIEF_TZ).date().isoformat()


def _trim(value: str, limit: int = 180) -> str:
    normalized = normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _brief_bullet(value: str, *, limit: int = 112) -> str:
    """Keep every brief lane readable while preserving the 1,800-char contract."""

    return f"- {_trim(value, limit=limit)}"


def _material_entries() -> list[dict[str, Any]]:
    entries = filter_recent_chronicle_entries("shared_ops", max_items=10)
    return [entry for entry in entries if entry_has_material_signal(entry)]


def _latest_doc_update_line(tail: str) -> str:
    for raw_line in reversed(tail.splitlines()):
        line = raw_line.strip()
        if line.startswith("Rolling Docs Refresh"):
            return line
    return ""


def _what_changed_lines(entries: list[dict[str, Any]], memory_context: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for entry in entries[-2:]:
        workspace = str(entry.get("workspace_key") or "shared_ops")
        signal = clean_signal_text(entry_primary_signal(entry) or entry.get("summary") or "")
        if signal:
            lines.append(f"`{workspace}`: {_trim(signal)}")
    doc_update = _latest_doc_update_line(memory_context.get("doc_updates_tail") or "")
    if doc_update:
        lines.append(f"`shared_ops`: {_trim(doc_update)}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in lines:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped[:2]


def _why_it_matters_lines(
    diagnostics: dict[str, Any],
    focus_cards: list[dict[str, Any]],
    automation_context: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    if diagnostics.get("runtime_out_of_sync"):
        lines.append("`persistent_state.md` is split between live and runtime paths, so Chronicle and PM stay primary until the runtime lane is repaired.")
    elif diagnostics.get("snapshot_heading_stale") or diagnostics.get("boilerplate_flags"):
        lines.append("`persistent_state.md` is stale, so Chronicle and PM are the reliable operator lanes for today.")
    if focus_cards:
        titles = ", ".join(f"`{card.get('title')}`" for card in focus_cards if card.get("title"))
        if titles:
            lines.append(f"Executive attention is concentrated in active PM lanes: {titles}.")
    mismatch_count = int(automation_context.get("mismatch_count") or 0)
    if mismatch_count:
        lines.append(f"The automation layer still has {mismatch_count} live mismatch(es), so summary trust is reduced until they close.")
    return lines[:2]


def _heartbeat_alerts(report: dict[str, Any]) -> list[str]:
    alerts: list[str] = []
    runtime = report.get("runtime") or {}
    latest_activity = runtime.get("latest_activity") or {}
    runtime_age = latest_activity.get("age_minutes")
    if isinstance(runtime_age, (int, float)) and runtime_age > 240:
        alerts.append(
            f"Local automation evidence is stale (last run age {runtime_age:.0f}m). Check launchd and the run ledger before the next brief."
        )
    status_counts = runtime.get("status_counts") or {}
    error_count = int(status_counts.get("error", 0) or 0)
    action_required_count = int(runtime.get("action_required_count", 0) or 0)
    if error_count or action_required_count:
        alerts.append(
            f"The local run ledger has {error_count} error run(s) and {action_required_count} action-required run(s) in the last {runtime.get('window_hours', 36)}h."
        )
    launchd_counts = (report.get("launchd") or {}).get("counts") or {}
    launchd_errors = int(launchd_counts.get("errors", 0) or 0)
    if launchd_errors and len(alerts) < 2:
        alerts.append(f"The latest launchd audit reports {launchd_errors} error(s).")
    return alerts[:2]


def _action_lines(primary: dict[str, Any] | None, focus_cards: list[dict[str, Any]], matched_card: dict[str, Any] | None) -> list[str]:
    owner = entry_owner(primary or {}, matched_card or (focus_cards[0] if focus_cards else None))
    if focus_cards:
        titles = ", ".join(f"`{card.get('title')}`" for card in focus_cards if card.get("title"))
        next_step = f"close or advance {titles} with execution write-back before the next executive standup."
    elif primary and primary.get("follow_ups"):
        next_step = _trim(clean_signal_text((primary.get("follow_ups") or [""])[0]), limit=160)
    else:
        next_step = "review the latest Chronicle motion and promote the next concrete action into PM."
    return [f"Owner: {owner}", f"Next: {next_step}"]


def _routing_lines(primary: dict[str, Any] | None, focus_cards: list[dict[str, Any]]) -> list[str]:
    workspaces = sorted(
        {
            str(card.get("workspace_key") or "").strip()
            for card in focus_cards
            if str(card.get("workspace_key") or "").strip()
        }
    )
    if not workspaces and primary:
        workspaces = [str(primary.get("workspace_key") or "shared_ops")]

    if focus_cards:
        card_refs = ", ".join(f"`{card.get('id')}`" for card in focus_cards if card.get("id"))
        route = f"PM cards {card_refs} -> executive standup `actions`."
    elif primary:
        route = f"`{primary.get('workspace_key') or 'shared_ops'}` Chronicle update -> PM triage -> executive standup `actions`."
    else:
        route = "`shared_ops` PM board -> executive standup `actions`."
    return [
        f"Workspace: {', '.join(workspaces) if workspaces else 'shared_ops'}",
        f"Route: {route}",
    ]


def _source_lines(
    entries: list[dict[str, Any]],
    focus_cards: list[dict[str, Any]],
    heartbeat_summary: str,
    memory_context: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    if entries:
        chronicle_ref = _trim(chronicle_source_ref(entries[-1]).replace("`", ""), limit=92)
        lines.append(f"Chronicle: `{chronicle_ref}`")
        for ref in artifact_refs(entries[-1]):
            lines.append(f"Artifact: `{_trim(ref, limit=96)}`")
            break
    if focus_cards:
        titles = ", ".join(f"`{card.get('id')}` {card.get('title')}" for card in focus_cards if card.get("id"))
        if titles:
            lines.append(f"PM cards: {titles}")
    doc_update = _latest_doc_update_line(memory_context.get("doc_updates_tail") or "")
    if doc_update:
        lines.append(f"Artifact: `memory/doc-updates.md` -> {_trim(doc_update, limit=80)}")
    if not lines:
        lines.append(f"Artifact: `scripts/heartbeat_report.py --summary` -> {_trim(heartbeat_summary, limit=70)}")
    return lines[:3]


def _alert_lines(
    entries: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    heartbeat_report: dict[str, Any],
    pm_context: dict[str, Any],
    automation_context: dict[str, Any],
) -> list[str]:
    alerts: list[str] = []
    if diagnostics.get("runtime_out_of_sync"):
        live_delta = diagnostics.get("live_newer_by_hours")
        delta_text = f" ({live_delta}h newer live mirror)" if isinstance(live_delta, (int, float)) else ""
        alerts.append(
            f"`persistent_state.md` runtime lane is out of sync with the live mirror{delta_text}; treat Chronicle and PM as the primary briefing lanes until Dream Cycle rewrites runtime memory."
        )
    elif diagnostics.get("snapshot_heading_stale") or diagnostics.get("boilerplate_flags"):
        stale_date = diagnostics.get("snapshot_heading_date") or "unknown"
        alerts.append(
            f"`persistent_state.md` is stale (snapshot heading `{stale_date}`) and still contains boilerplate; do not use it as the primary briefing source."
        )
    alerts.extend(_heartbeat_alerts(heartbeat_report))
    if pm_context.get("fallback_active"):
        alerts.append(
            f"PM context is on fallback source `{pm_context.get('source')}`; verify routing against the live board."
        )
    mismatch_count = int(automation_context.get("mismatch_count") or 0)
    if mismatch_count:
        alerts.append(f"Automation mismatch report is not clean ({mismatch_count} mismatch(es)).")
    if not alerts:
        blockers = []
        for entry in entries:
            for item in entry.get("blockers") or []:
                text = clean_signal_text(item)
                if text and looks_like_blocker(text):
                    blockers.append(_trim(text))
        if blockers:
            alerts.append(blockers[0])
        else:
            alerts.append("No new automation blocker is active, but the next PM state change still needs executive review.")
    return alerts[:2]


def build_brief_payload() -> dict[str, Any]:
    material_entries = _material_entries()
    primary = material_entries[-1] if material_entries else None
    memory_payload = build_memory_tail_context(MEMORY_PATHS, max_chars=1800)
    memory_context = memory_payload["memory_context"]
    diagnostics = memory_payload["memory_diagnostics"].get("memory/persistent_state.md") or {}
    runtime_context = load_runtime_context()
    pm_context = runtime_context.get("pm_context") or {}
    automation_context = runtime_context.get("automation_context") or {}
    focus_cards = recent_focus_cards(pm_context.get("cards") or [], limit=2)
    matched_card = match_pm_card(primary or {}, pm_context.get("cards") or []) if primary else None
    heartbeat_report = build_heartbeat_report(36.0)
    heartbeat_summary = render_heartbeat_summary(heartbeat_report)
    brain_context = build_brain_automation_context(signal_limit=4)

    lines = [
        f"Morning Daily Brief — {_local_date()}",
        "What Changed:",
    ]
    changed_lines = _what_changed_lines(material_entries, memory_context)
    if changed_lines:
        lines.extend(_brief_bullet(item) for item in changed_lines)
    else:
        lines.append("- No new material Chronicle movement was found; use PM and heartbeat state as the operating surface.")
    lines.append("Why It Matters:")
    why_lines = _why_it_matters_lines(diagnostics, focus_cards, automation_context)
    if why_lines:
        lines.extend(_brief_bullet(item) for item in why_lines)
    else:
        lines.append("- The system is operational, but it still needs a concrete PM-backed next move.")
    lines.append("Action Now:")
    lines.extend(_brief_bullet(item) for item in _action_lines(primary, focus_cards, matched_card))
    lines.append("Routing:")
    lines.extend(_brief_bullet(item) for item in _routing_lines(primary, focus_cards))
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *brain_signal_lines(brain_context, limit=2),
    ]
    lines.append("Brain Context:")
    if brain_context_lines:
        lines.extend(_brief_bullet(item) for item in brain_context_lines[:2])
    else:
        lines.append("- No active Brain Signal or portfolio blocker is demanding executive routing today.")
    lines.append("Source:")
    source_lines = _source_lines(material_entries, focus_cards, heartbeat_summary, memory_context)
    intelligence_lines = source_intelligence_lines(brain_context, limit=1)
    selected_sources = source_lines[:1]
    if intelligence_lines:
        selected_sources.extend(intelligence_lines)
    elif len(source_lines) > 1:
        selected_sources.append(source_lines[1])
    lines.extend(_brief_bullet(item) for item in selected_sources)
    lines.append("Alerts:")
    lines.extend(
        _brief_bullet(item)
        for item in _alert_lines(material_entries, diagnostics, heartbeat_report, pm_context, automation_context)
    )

    markdown = "\n".join(lines)
    ensure_digest("morning_daily_brief", markdown)
    source_paths = [
        *(memory_payload.get("source_paths") or []),
        *(pm_context.get("source_ref") and [pm_context["source_ref"]] or []),
        *(automation_context.get("source_ref") and [automation_context["source_ref"]] or []),
        *(brain_context.get("source_paths") or []),
    ]
    return {
        "date": _local_date(),
        "markdown": markdown,
        "source_paths": list(dict.fromkeys(source_paths)),
        "heartbeat_summary": heartbeat_summary,
        "brain_context": brain_context,
    }


def _upsert_brief(path: Path, block: str, brief_date: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    matches = list(HEADING_RE.finditer(existing))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(existing)
        sections.append((match.group(1), existing[start:end].strip()))

    replacement = block.strip()
    replaced = False
    rebuilt: list[str] = []
    for section_date, section_body in sections:
        if section_date == brief_date:
            rebuilt.append(replacement)
            replaced = True
        else:
            rebuilt.append(section_body)
    if not replaced:
        rebuilt.append(replacement)

    if not sections and existing.strip():
        rebuilt.insert(0, existing.strip())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(item for item in rebuilt if item).rstrip() + "\n", encoding="utf-8")


def _daily_briefs_write_path() -> Path:
    """Seed legacy history once, then keep generated briefs in private state."""

    return seed_memory_state_file(
        "daily-briefs.md",
        project_root=WORKSPACE_ROOT,
        state_root=STATE_ROOT,
    )


def main() -> int:
    maybe_reexec_with_workspace_venv()
    args = parse_args()
    payload = build_brief_payload()
    if args.append:
        _upsert_brief(_daily_briefs_write_path(), payload["markdown"], payload["date"])
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
