#!/usr/bin/env python3
"""Validate human-facing cron digests before they are delivered."""
from __future__ import annotations

from typing import Iterable, NamedTuple


REQUIRED_SECTIONS: tuple[str, ...] = (
    "What Changed",
    "Why It Matters",
    "Action Now",
    "Routing",
    "Source",
    "Alerts",
)

DISALLOWED_PHRASES: tuple[str, ...] = (
    "no additional actions required",
    "no additional action required",
    "no further action needed",
    "no further action is needed",
    "daily log input processing completed without errors",
    "processing completed without errors",
    "latest heartbeats are syncing",
    "successfully delivered",
    "digest delivered based on new handoff signals",
    "latest signal:",
    "latest handoff summary:",
    "follow-up status:",
    "status update -",
)

MAX_LENGTH_BY_KIND = {
    "progress_pulse": 1800,
    "morning_daily_brief": 1800,
}


class DigestValidationReport(NamedTuple):
    ok: bool
    issues: tuple[str, ...]


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.endswith(":") and stripped[:-1] in REQUIRED_SECTIONS:
            current = stripped[:-1]
            sections.setdefault(current, [])
            continue
        if current is not None and stripped:
            sections[current].append(stripped)
    return sections


def _section_has_prefix(lines: Iterable[str], prefix: str) -> bool:
    normalized = prefix.lower()
    for line in lines:
        content = line[2:].strip() if line.startswith("- ") else line.strip()
        if content.lower().startswith(normalized):
            return True
    return False


def validate_digest(kind: str, text: str) -> DigestValidationReport:
    normalized = text.strip()
    issues: list[str] = []
    if not normalized:
        issues.append("Digest is empty.")
        return DigestValidationReport(ok=False, issues=tuple(issues))

    lowered = normalized.lower()
    for phrase in DISALLOWED_PHRASES:
        if phrase in lowered:
            issues.append(f"Digest contains banned boilerplate: `{phrase}`.")

    max_length = MAX_LENGTH_BY_KIND.get(kind)
    if max_length is not None and len(normalized) > max_length:
        issues.append(f"Digest exceeds {max_length} characters.")

    sections = _split_sections(normalized)
    for heading in REQUIRED_SECTIONS:
        if heading not in sections:
            issues.append(f"Missing required section `{heading}`.")
            continue
        if not sections[heading]:
            issues.append(f"Section `{heading}` is empty.")

    action_lines = sections.get("Action Now") or []
    if action_lines:
        if not _section_has_prefix(action_lines, "Owner:"):
            issues.append("`Action Now` must name an owner.")
        if not _section_has_prefix(action_lines, "Next:"):
            issues.append("`Action Now` must name the next state change.")

    routing_lines = sections.get("Routing") or []
    if routing_lines:
        if not _section_has_prefix(routing_lines, "Workspace:"):
            issues.append("`Routing` must name at least one workspace.")
        if not _section_has_prefix(routing_lines, "Route:"):
            issues.append("`Routing` must explain where the signal was routed.")

    source_lines = sections.get("Source") or []
    if source_lines and not any("`" in line or "/" in line or "PM card" in line for line in source_lines):
        issues.append("`Source` must cite a concrete artifact, path, or PM card.")

    return DigestValidationReport(ok=not issues, issues=tuple(issues))


def ensure_digest(kind: str, text: str) -> str:
    report = validate_digest(kind, text)
    if not report.ok:
        raise ValueError("; ".join(report.issues))
    return text
