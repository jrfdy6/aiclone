#!/usr/bin/env python3
"""Build and write a deterministic Dream Cycle snapshot from live operational evidence."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from runtime_bootstrap import maybe_reexec_with_workspace_venv


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
TZ = ZoneInfo("America/New_York")
DREAM_CYCLE_LOG_PATH = WORKSPACE_ROOT / "memory" / "dream_cycle_log.md"
LOG_HEADING_RE = re.compile(r"(?m)^# Dream Cycle Log - ([A-Za-z]+ \d{1,2}, \d{4})$")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from app.services.core_memory_snapshot_service import resolve_live_memory_write_path
from brain_automation_context import (
    brain_signal_lines,
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
)
from chronicle_memory_contract import build_memory_tail_context, filter_recent_chronicle_entries
from chronicle_signal_quality import clean_signal_text, entry_has_material_signal, entry_primary_signal, normalize_text
from cron_digest_support import entry_owner, load_runtime_context, match_pm_card, next_state_text, recent_focus_cards
from heartbeat_report import build_report as build_heartbeat_report, render_summary as render_heartbeat_summary


RUNTIME_PERSISTENT_STATE_PATH = resolve_live_memory_write_path(WORKSPACE_ROOT, "memory/persistent_state.md")
MEMORY_PATHS: tuple[str, ...] = (
    "memory/cron-prune.md",
    "memory/doc-updates.md",
    "memory/LEARNINGS.md",
    "memory/daily-briefs.md",
    "memory/{today}.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the Dream Cycle snapshot and log to disk.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a markdown summary.")
    return parser.parse_args()


def _local_now() -> datetime:
    return datetime.now(TZ)


def _local_date(now: datetime | None = None) -> str:
    return (now or _local_now()).date().isoformat()


def _long_date(now: datetime | None = None) -> str:
    current = now or _local_now()
    return f"{current.strftime('%B')} {current.day}, {current.year}"


def _trim(value: str, *, limit: int = 180) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _material_entries() -> list[dict[str, Any]]:
    entries = filter_recent_chronicle_entries("shared_ops", max_items=10)
    return [entry for entry in entries if entry_has_material_signal(entry)]


def _latest_doc_update_line(tail: str) -> str:
    for raw_line in reversed(tail.splitlines()):
        line = raw_line.strip()
        if line.startswith("Rolling Docs Refresh"):
            return line
    return ""


def _snapshot_lines(
    entries: list[dict[str, Any]],
    focus_cards: list[dict[str, Any]],
    memory_context: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for entry in entries[-2:]:
        workspace = str(entry.get("workspace_key") or "shared_ops")
        signal = clean_signal_text(entry_primary_signal(entry) or entry.get("summary") or "")
        if signal:
            item = f"`{workspace}`: {_trim(signal)}"
            key = item.lower()
            if key not in seen:
                seen.add(key)
                lines.append(item)
    doc_update = _latest_doc_update_line(memory_context.get("doc_updates_tail") or "")
    if doc_update:
        item = f"`shared_ops`: {_trim(doc_update)}"
        key = item.lower()
        if key not in seen:
            seen.add(key)
            lines.append(item)
    if focus_cards:
        titles = ", ".join(f"`{card.get('title')}`" for card in focus_cards if card.get("title"))
        if titles:
            item = f"Active PM focus: {titles}."
            key = item.lower()
            if key not in seen:
                seen.add(key)
                lines.append(item)
    if not lines:
        lines.append("No new material Chronicle delta landed; PM focus and heartbeat evidence remain the operating surface.")
    return lines[:3]


def _automation_health_lines(heartbeat_summary: str, pm_context: dict[str, Any], automation_context: dict[str, Any]) -> list[str]:
    lines = [f"Heartbeat: {_trim(heartbeat_summary, limit=220)}"]
    mismatch_count = int(automation_context.get("mismatch_count") or 0)
    if mismatch_count:
        lines.append(f"Automation mismatch report is not clean ({mismatch_count} active mismatch(es)).")
    else:
        lines.append("Automation mismatch report is clean with no active mismatch.")
    pm_source = str(pm_context.get("source") or "pm_unavailable")
    if pm_context.get("fallback_active"):
        lines.append(f"PM context is degraded on `{pm_source}`; keep the board under review.")
    else:
        lines.append(f"PM context source is `{pm_source}` with no fallback active.")
    return lines[:3]


def _finding_lines(
    entries: list[dict[str, Any]],
    focus_cards: list[dict[str, Any]],
    matched_card: dict[str, Any] | None,
    heartbeat_report: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    if matched_card:
        lines.append(
            f"Latest material Chronicle signal maps to PM card `{matched_card.get('id')}` `{matched_card.get('title')}`."
        )
    elif focus_cards:
        titles = ", ".join(f"`{card.get('title')}`" for card in focus_cards if card.get("title"))
        if titles:
            lines.append(f"Executive PM pressure is concentrated in {titles}.")
    discord = heartbeat_report.get("discord") or {}
    counts = discord.get("counts") or {}
    close_count = int(counts.get("closed", 0) or 0)
    reconnect_count = int(counts.get("reconnect", 0) or 0)
    if close_count or reconnect_count >= 6:
        lines.append(
            f"Discord gateway churn is elevated ({close_count} close / {reconnect_count} reconnect events in the last {discord.get('window_hours', 36)}h)."
        )
    elif entries:
        lines.append("Recent Chronicle motion is material and can be carried forward without relying on generic maintenance boilerplate.")
    else:
        lines.append("No new material Chronicle motion landed, so the PM board remains the main execution truth.")
    return lines[:3]


def _action_lines(
    primary: dict[str, Any] | None,
    focus_cards: list[dict[str, Any]],
    matched_card: dict[str, Any] | None,
    heartbeat_report: dict[str, Any],
) -> list[str]:
    owner = entry_owner(primary or {}, matched_card or (focus_cards[0] if focus_cards else None))
    lines = [f"Owner: {owner}"]
    lines.append(f"Next: {_trim(next_state_text(primary or {}, matched_card), limit=170)}")
    discord = heartbeat_report.get("discord") or {}
    counts = discord.get("counts") or {}
    close_count = int(counts.get("closed", 0) or 0)
    reconnect_count = int(counts.get("reconnect", 0) or 0)
    if close_count or reconnect_count >= 6:
        lines.append("Repair the repeated Discord stale-socket / reconnect churn before treating heartbeat as calm.")
    else:
        lines.append("Keep PM and Chronicle write-back aligned before the next Morning Daily Brief.")
    return lines[:3]


def build_payload() -> dict[str, Any]:
    now = _local_now()
    entries = _material_entries()
    primary = entries[-1] if entries else None
    runtime_context = load_runtime_context()
    pm_context = runtime_context.get("pm_context") or {}
    automation_context = runtime_context.get("automation_context") or {}
    focus_cards = recent_focus_cards(pm_context.get("cards") or [], limit=2)
    matched_card = match_pm_card(primary or {}, pm_context.get("cards") or []) if primary else None
    memory_payload = build_memory_tail_context(MEMORY_PATHS, max_chars=1800)
    memory_context = memory_payload["memory_context"]
    heartbeat_report = build_heartbeat_report(36.0)
    heartbeat_summary = render_heartbeat_summary(heartbeat_report)
    brain_context = build_brain_automation_context(signal_limit=4)

    snapshot_lines = _snapshot_lines(entries, focus_cards, memory_context)
    automation_lines = _automation_health_lines(heartbeat_summary, pm_context, automation_context)
    finding_lines = _finding_lines(entries, focus_cards, matched_card, heartbeat_report)
    action_lines = _action_lines(primary, focus_cards, matched_card, heartbeat_report)
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *brain_signal_lines(brain_context, limit=2),
        *source_intelligence_lines(brain_context, limit=1),
    ] or ["No active Brain Signal or portfolio blocker requires Dream Cycle promotion."]

    snapshot_markdown = "\n".join(
        [
            f"# Snapshot for {_long_date(now)}",
            "",
            "### Snapshot",
            *(f"- {item}" for item in snapshot_lines),
            "",
            "### Automation Health",
            *(f"- {item}" for item in automation_lines),
            "",
            "### Brain Context",
            *(f"- {item}" for item in brain_context_lines[:4]),
            "",
            "### Findings",
            *(f"- {item}" for item in finding_lines),
            "",
            "### Actions",
            *(f"- {item}" for item in action_lines),
        ]
    ).rstrip() + "\n"

    log_markdown = "\n".join(
        [
            f"# Dream Cycle Log - {_long_date(now)}",
            "",
            "**Key Findings**",
            *(f"{index}. {item}" for index, item in enumerate(finding_lines or snapshot_lines[:2], start=1)),
            "",
            "**Actions Taken**",
            f"- Updated `{RUNTIME_PERSISTENT_STATE_PATH}` from deterministic Dream Cycle inputs.",
            "- Canonical readers should keep resolving `memory/persistent_state.md` through the runtime lane instead of mirroring tracked content.",
            "- Grounded the daily snapshot in Chronicle, PM context, Brain Signals, portfolio snapshot state, automation status, and heartbeat diagnostics.",
            "",
            "**Next Steps**",
            *(f"- {item}" for item in action_lines),
        ]
    ).rstrip() + "\n"

    summary_markdown = "\n".join(
        [
            f"Dream Cycle — {_local_date(now)}",
            "Snapshot:",
            f"- {_trim(snapshot_lines[0], limit=160)}",
            "Automation Health:",
            f"- {_trim(automation_lines[0], limit=180)}",
            "Brain Context:",
            *(f"- {_trim(item, limit=160)}" for item in brain_context_lines[:2]),
            "Findings:",
            *(f"- {_trim(item, limit=160)}" for item in finding_lines[:2]),
            "Actions:",
            *(f"- {_trim(item, limit=160)}" for item in action_lines[:2]),
        ]
    )

    source_paths = [
        str(RUNTIME_PERSISTENT_STATE_PATH),
        str(DREAM_CYCLE_LOG_PATH),
        *(memory_payload.get("source_paths") or []),
        *(pm_context.get("source_ref") and [pm_context["source_ref"]] or []),
        *(automation_context.get("source_ref") and [automation_context["source_ref"]] or []),
        *(brain_context.get("source_paths") or []),
    ]

    return {
        "date": _local_date(now),
        "snapshot_markdown": snapshot_markdown,
        "log_markdown": log_markdown,
        "summary_markdown": summary_markdown,
        "source_paths": list(dict.fromkeys(source_paths)),
        "brain_context": brain_context,
    }


def _upsert_log(path: Path, block: str, heading_date: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    matches = list(LOG_HEADING_RE.finditer(existing))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(existing)
        sections.append((match.group(1), existing[start:end].strip()))

    replacement = block.strip()
    replaced = False
    rebuilt: list[str] = []
    for section_date, section_body in sections:
        if section_date == heading_date:
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


def write_payload(payload: dict[str, Any]) -> None:
    snapshot_markdown = str(payload["snapshot_markdown"])
    RUNTIME_PERSISTENT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PERSISTENT_STATE_PATH.write_text(snapshot_markdown, encoding="utf-8")
    _upsert_log(DREAM_CYCLE_LOG_PATH, str(payload["log_markdown"]), _long_date())


def main() -> int:
    maybe_reexec_with_workspace_venv()
    args = parse_args()
    payload = build_payload()
    if args.write:
        write_payload(payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["summary_markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
