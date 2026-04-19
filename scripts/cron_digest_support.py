#!/usr/bin/env python3
"""Shared helpers for deterministic cron digests."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from build_standup_prep import DEFAULT_API_URL, _load_automation_context, _load_pm_context, _normalize_status, _optional_backend_imports
from chronicle_signal_quality import clean_signal_text, looks_like_blocker, normalize_text


BACKTICK_TITLE_RE = re.compile(r"`([^`]+)`")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_lookup(value: Any) -> str:
    return NON_ALNUM_RE.sub(" ", normalize_text(value).lower()).strip()


def load_runtime_context(api_url: str = DEFAULT_API_URL) -> dict[str, Any]:
    imports = _optional_backend_imports()
    return {
        "pm_context": _load_pm_context(imports, "shared_ops", api_url),
        "automation_context": _load_automation_context(imports),
    }


def recent_focus_cards(cards: list[dict[str, Any]], *, limit: int = 2) -> list[dict[str, Any]]:
    def _key(card: dict[str, Any]) -> tuple[str, str]:
        updated_at = str(card.get("updated_at") or "")
        return (updated_at, str(card.get("id") or ""))

    filtered = []
    for card in cards:
        status = _normalize_status(str(card.get("status") or "ready"))
        if status == "done":
            continue
        filtered.append({**card, "status": status})
    return sorted(filtered, key=_key, reverse=True)[:limit]


def match_pm_card(entry: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not cards:
        return None

    candidates: list[str] = []
    summary = str(entry.get("summary") or "")
    candidates.extend(BACKTICK_TITLE_RE.findall(summary))
    for field in ("pm_candidates", "follow_ups", "project_updates", "decisions"):
        for item in entry.get(field) or []:
            text = clean_signal_text(item)
            if text:
                candidates.append(text)

    normalized_candidates = [_normalize_lookup(item) for item in candidates if _normalize_lookup(item)]
    for candidate in normalized_candidates:
        for card in cards:
            title = _normalize_lookup(card.get("title") or "")
            if not title:
                continue
            if candidate == title or candidate in title or title in candidate:
                return {**card, "status": _normalize_status(str(card.get("status") or "ready"))}
    return None


def entry_owner(entry: dict[str, Any], pm_card: dict[str, Any] | None = None) -> str:
    owner = normalize_text((pm_card or {}).get("owner"))
    if owner:
        return owner
    source = normalize_text(entry.get("source")).lower()
    if "jean-claude" in source:
        return "Jean-Claude"
    author_agent = normalize_text(entry.get("author_agent"))
    if author_agent:
        return author_agent.title()
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    return workspace_key


def standup_section(entry: dict[str, Any]) -> str:
    blockers = [clean_signal_text(item) for item in (entry.get("blockers") or []) if clean_signal_text(item)]
    if any(looks_like_blocker(item) for item in blockers):
        return "blockers"
    if entry.get("pm_candidates") or entry.get("follow_ups"):
        return "actions"
    return "updates"


def next_state_text(entry: dict[str, Any], pm_card: dict[str, Any] | None = None) -> str:
    if pm_card:
        status = _normalize_status(str(pm_card.get("status") or "ready"))
        if status == "done":
            return "confirm the closed PM card has durable write-back; reopen or create a fresh lane only if new work remains"
        if status == "blocked":
            return "resolve the blocker and move the card back into execution before the next standup"
        if status == "review":
            return "decide accept-or-return on the PM review lane"
        if status in {"in_progress", "queued", "ready"}:
            return "write the execution result back into PM and Chronicle"
        return f"advance the PM card from `{status}` to its next review state"
    if entry.get("blockers"):
        return "turn the blocker into a PM action and carry it into the next executive standup"
    if entry.get("follow_ups") or entry.get("pm_candidates"):
        return "promote the latest follow-up into PM or standup so it can close with evidence"
    return "review the latest Chronicle movement and decide whether it belongs in PM or standup"


def route_text(entry: dict[str, Any], pm_card: dict[str, Any] | None = None) -> str:
    section = standup_section(entry)
    if pm_card:
        return f"PM card `{pm_card.get('id')}` ({pm_card.get('status')}) -> executive standup `{section}`"
    workspace = str(entry.get("workspace_key") or "shared_ops")
    return f"`{workspace}` PM triage -> executive standup `{section}`"


def artifact_refs(entry: dict[str, Any], *, limit: int = 2) -> list[str]:
    refs: list[str] = []
    for item in entry.get("artifacts") or []:
        text = normalize_text(item)
        if text:
            refs.append(text)
        if len(refs) >= limit:
            break
    return refs


def chronicle_source_ref(entry: dict[str, Any]) -> str:
    created_at = normalize_text(entry.get("created_at")) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    source = normalize_text(entry.get("source")) or "chronicle"
    workspace = str(entry.get("workspace_key") or "shared_ops")
    return f"{created_at} {source} `{workspace}`"
