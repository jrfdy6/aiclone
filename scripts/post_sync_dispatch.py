#!/usr/bin/env python3
"""Ensure completed standups leave concrete PM artifacts and dispatch metadata."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
REPORT_ROOT = WORKSPACE_ROOT / "memory" / "reports"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_runtime_contract_service import execution_defaults_for_workspace as shared_execution_defaults_for_workspace

WORKSPACE_LABELS = {
    "shared_ops": "Shared Ops",
    "feezie-os": "FEEZIE OS",
    "fusion-os": "Fusion OS",
    "easyoutfitapp": "Easy Outfit App",
    "ai-swag-store": "AI Swag Store",
    "agc": "AGC",
    "linkedin-os": "LinkedIn OS",
}
WORKSPACE_SCOPE_ALIASES = {
    "feezie-os": {"feezie-os", "linkedin-os", "linkedin-content-os"},
    "linkedin-os": {"feezie-os", "linkedin-os", "linkedin-content-os"},
    "linkedin-content-os": {"feezie-os", "linkedin-os", "linkedin-content-os"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _standup_kind(entry: dict[str, Any]) -> str:
    payload = entry.get("payload") or {}
    value = payload.get("standup_kind")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return str(entry.get("workspace_key") or "shared_ops")


def _execution_defaults(workspace_key: str) -> dict[str, Any]:
    return dict(shared_execution_defaults_for_workspace(workspace_key))


def _normalize_title(text: str) -> str:
    normalized = " ".join(text.replace("`", "").split()).strip(" -.")
    if normalized.lower().startswith("decide whether to "):
        normalized = normalized[17:]
    if normalized.lower().startswith("confirm the next move for "):
        normalized = normalized[26:]
    if normalized.lower().startswith("resolve the top blocker: "):
        normalized = f"Resolve blocker: {normalized[25:]}"
    if normalized.lower().startswith("nothing to report"):
        return ""
    return normalized[:120]


def _is_actionable_title(title: str) -> bool:
    normalized = " ".join(title.split()).strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    disallowed_prefixes = (
        "decide whether ",
        "review ",
        "create or queue ",
        "confirm the next move for ",
        "keep ",
        "nothing to report",
    )
    if lowered.startswith(disallowed_prefixes):
        return False
    allowed_prefixes = (
        "align ",
        "backfill ",
        "build ",
        "clarify ",
        "create ",
        "define ",
        "draft ",
        "document ",
        "make ",
        "plan ",
        "promote ",
        "refine ",
        "run ",
        "ship ",
        "standardize ",
        "tighten ",
        "turn ",
        "verify ",
        "wire ",
    )
    return lowered.startswith(allowed_prefixes)


def _extract_create_queue_title(item: str) -> str:
    normalized = " ".join(item.split()).strip()
    lowered = normalized.lower()
    prefix = "create or queue "
    suffix = " on the pm board."
    if lowered.startswith(prefix) and lowered.endswith(suffix):
        core = normalized[len(prefix) : -len(suffix)]
        return _normalize_title(core)
    return ""


def _workspace_label(workspace_key: str) -> str:
    normalized = str(workspace_key or "").strip()
    if not normalized:
        return "Workspace"
    if normalized in WORKSPACE_LABELS:
        return WORKSPACE_LABELS[normalized]
    return " ".join(part.capitalize() for part in normalized.replace("_", "-").split("-") if part)


def _entry_section_lines(entry: dict[str, Any], key: str) -> list[str]:
    payload = entry.get("payload") or {}
    sections = payload.get("standup_sections") or {}
    values = sections.get(key)
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _entry_text_sections(entry: dict[str, Any]) -> list[str]:
    payload = entry.get("payload") or {}
    values: list[str] = []
    for collection in (
        payload.get("artifact_deltas"),
        payload.get("source_paths"),
        _entry_section_lines(entry, "signals_captured"),
        _entry_section_lines(entry, "content_produced"),
        _entry_section_lines(entry, "audience_response"),
        _entry_section_lines(entry, "opportunities_created"),
        _entry_section_lines(entry, "next_focus"),
        entry.get("commitments"),
        entry.get("needs"),
    ):
        if not isinstance(collection, list):
            continue
        for item in collection:
            normalized = str(item).strip()
            if normalized:
                values.append(normalized)
    return values


def _extract_path_from_text(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    path_match = re.search(r"(/Users/[^\s`]+|workspaces/[^\s`]+)", normalized)
    if path_match:
        return path_match.group(1)
    return ""


def _extract_paths_from_text(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    return re.findall(r"(/Users/[^\s`]+|workspaces/[^\s`]+)", normalized)


def _path_matches_workspace_scope(path: str, workspace_key: str) -> bool:
    normalized_path = str(path or "").strip().replace("\\", "/")
    normalized_workspace = str(workspace_key or "shared_ops").strip() or "shared_ops"
    if not normalized_path or normalized_workspace == "shared_ops":
        return bool(normalized_path)
    scope_keys = _workspace_scope_keys(normalized_workspace)
    for scope_key in scope_keys:
        fragment = f"/workspaces/{scope_key}/"
        relative_fragment = f"workspaces/{scope_key}/"
        if fragment in normalized_path or relative_fragment in normalized_path:
            return True
    return False


def _entry_artifact_path(entry: dict[str, Any], marker: str, *, workspace_key: str | None = None) -> str:
    marker = marker.strip().lower()
    normalized_workspace = str(workspace_key or "").strip() or str(entry.get("workspace_key") or "shared_ops")
    fallback_path = ""
    for item in _entry_text_sections(entry):
        if marker not in item.lower():
            continue
        for path in _extract_paths_from_text(item):
            if _path_matches_workspace_scope(path, normalized_workspace):
                return path
            if not fallback_path:
                fallback_path = path
    if normalized_workspace == "shared_ops":
        return fallback_path
    return ""


def _workspace_has_active_cards(cards: list[dict[str, Any]], workspace_key: str) -> bool:
    for card in cards:
        if not isinstance(card, dict) or not _workspace_scope_matches(workspace_key, _card_workspace_key(card)):
            continue
        status = str(card.get("status") or "").strip().lower()
        if status not in {"done", "cancelled", "canceled"}:
            return True
    return False


def _workspace_focus_candidate(entry: dict[str, Any]) -> str:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    workspace_label = _workspace_label(workspace_key)
    for item in _entry_section_lines(entry, "next_focus"):
        title = _normalize_title(item)
        if title and _is_actionable_title(title):
            return title
    for item in _entry_section_lines(entry, "opportunities_created"):
        normalized = str(item).strip()
        title = _normalize_title(normalized)
        if title and _is_actionable_title(title):
            return title
        lowered = normalized.lower()
        if "next concrete opportunity" in lowered or "underrepresented" in lowered or "cadence" in lowered:
            return f"Define next concrete opportunity for {workspace_label}"
    briefing_path = _entry_artifact_path(entry, "/briefings/", workspace_key=workspace_key)
    if briefing_path:
        return f"Define next concrete opportunity for {workspace_label}"
    return ""


def _candidate_titles(entry: dict[str, Any], cards: list[dict[str, Any]] | None = None) -> list[str]:
    payload = entry.get("payload") or {}
    titles: list[str] = []
    seen: set[str] = set()

    for item in payload.get("pm_updates") or []:
        if not isinstance(item, dict):
            continue
        title = _normalize_title(str(item.get("title") or ""))
        if not title or not _is_actionable_title(title):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) >= 2:
            return titles

    for item in payload.get("decisions") or entry.get("decisions") or []:
        if not isinstance(item, str):
            continue
        title = _extract_create_queue_title(item)
        if not title or not _is_actionable_title(title):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) >= 2:
            return titles
    if titles:
        return titles
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    if cards is not None and _standup_kind(entry) == "workspace_sync" and workspace_key != "shared_ops":
        if _workspace_has_active_cards(cards, workspace_key):
            return titles
        fallback_title = _workspace_focus_candidate(entry)
        if fallback_title:
            titles.append(fallback_title)
    return titles


def _is_strategy_only(entry: dict[str, Any]) -> bool:
    return _standup_kind(entry) == "saturday_vision"


def _linked_cards(cards: list[dict[str, Any]], standup_id: str) -> list[dict[str, Any]]:
    linked: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        payload = card.get("payload") or {}
        if card.get("link_id") == standup_id or payload.get("created_from_standup_id") == standup_id:
            linked.append(card)
    return linked


def _card_titles(cards: list[dict[str, Any]], *, workspace_key: str | None = None) -> set[str]:
    return {
        str(card.get("title") or "").strip().lower()
        for card in cards
        if isinstance(card, dict)
        and str(card.get("title") or "").strip()
        and (workspace_key is None or _workspace_scope_matches(workspace_key, _card_workspace_key(card)))
    }


def _card_workspace_key(card: dict[str, Any]) -> str:
    payload = card.get("payload") if isinstance(card.get("payload"), dict) else {}
    value = payload.get("workspace_key")
    if isinstance(value, str) and value.strip():
        return value.strip()
    value = card.get("workspace_key")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "shared_ops"


def _workspace_scope_keys(workspace_key: str) -> set[str]:
    normalized = str(workspace_key or "shared_ops").strip() or "shared_ops"
    return set(WORKSPACE_SCOPE_ALIASES.get(normalized, {normalized}))


def _workspace_scope_matches(expected: str, candidate: str) -> bool:
    return str(candidate or "").strip() in _workspace_scope_keys(expected)


def _cards_matching_titles(cards: list[dict[str, Any]], titles: list[str], workspace_key: str) -> list[dict[str, Any]]:
    wanted = {title.strip().lower() for title in titles if title.strip()}
    if not wanted:
        return []
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        title = str(card.get("title") or "").strip().lower()
        card_id = str(card.get("id") or "").strip()
        if not _workspace_scope_matches(workspace_key, _card_workspace_key(card)) or title not in wanted or not card_id or card_id in seen:
            continue
        seen.add(card_id)
        matched.append(card)
    return matched


def _build_card_payload(entry: dict[str, Any], title: str) -> dict[str, Any]:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    payload = entry.get("payload") or {}
    defaults = _execution_defaults(workspace_key)
    transition_at = _iso(_now())
    workspace_label = _workspace_label(workspace_key)
    briefing_path = _entry_artifact_path(entry, "/briefings/", workspace_key=workspace_key)
    execution_log_path = _entry_artifact_path(entry, "execution_log.md", workspace_key=workspace_key)
    audience_feedback_path = _entry_artifact_path(entry, "audience feedback snapshot", workspace_key=workspace_key)
    analytics_path = _entry_artifact_path(entry, "/analytics/", workspace_key=workspace_key)
    focus_lines = _entry_section_lines(entry, "next_focus") or _entry_section_lines(entry, "opportunities_created")
    instructions = [f"Advance `{title}` inside `{workspace_key}` without expanding scope beyond the standup-backed next move."]
    if briefing_path:
        instructions.append(f"Use `{briefing_path}` as the primary briefing artifact for `{workspace_label}`.")
    if execution_log_path:
        instructions.append(f"Check `{execution_log_path}` before proposing new work so the result reflects what actually shipped.")
    if focus_lines:
        instructions.append(f"Anchor the next move in this standup signal: {focus_lines[0]}")
    if audience_feedback_path or analytics_path:
        instructions.append(
            f"Pressure-test the choice against `{audience_feedback_path or analytics_path}` before writing back the next move."
        )
    acceptance = [
        f"`{title}` resolves into one bounded next move for `{workspace_label}` instead of staying a placeholder.",
        "The result cites the latest briefing or execution log that justified the next move.",
        "PM write-back names the exact next artifact, deliverable, or blocker.",
    ]
    artifacts_expected = [
        "updated PM execution result",
        *(item for item in (briefing_path, execution_log_path, audience_feedback_path or analytics_path) if item),
    ]
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="post_sync_dispatch",
        reason="Post-sync dispatch created this card from a completed standup commitment.",
        instructions=instructions,
        acceptance_criteria=acceptance,
        artifacts_expected=artifacts_expected,
    )
    return {
        "workspace_key": workspace_key,
        "scope": "workspace" if workspace_key != "shared_ops" else "shared_ops",
        "source_agent": "Jean-Claude",
        "created_from_standup_id": entry.get("id"),
        "created_from_standup_kind": _standup_kind(entry),
        "created_from_standup_workspace": workspace_key,
        "participants": payload.get("participants") or [],
        "reason": "Post-sync dispatch created this card from a completed standup commitment.",
        "execution": {
            "lane": "codex",
            "state": "queued",
            "manager_agent": defaults["manager_agent"],
            "target_agent": defaults["target_agent"],
            "workspace_agent": defaults["workspace_agent"],
            "execution_mode": defaults["execution_mode"],
            "requested_by": "Jean-Claude",
            "assigned_runner": "codex",
            "reason": "Post-sync dispatch promoted a standup commitment into the execution lane.",
            "queued_at": transition_at,
            "last_transition_at": transition_at,
            "source": "post_sync_dispatch",
        },
        "dispatch_source_title": title,
        **contract,
    }


def build_report(api_url: str, lookback_days: int, limit: int, sync_live: bool) -> dict[str, Any]:
    now = _now()
    standups = _fetch_json(f"{api_url.rstrip('/')}/api/standups/?limit={limit}")
    cards = _fetch_json(f"{api_url.rstrip('/')}/api/pm/cards?limit=200")
    rows = [item for item in standups if isinstance(item, dict)]
    cards_list = [item for item in cards if isinstance(item, dict)]
    cutoff = now - timedelta(days=lookback_days)

    processed: list[dict[str, Any]] = []
    created_count = 0
    existing_count = 0

    for entry in rows:
        created_at = _parse_datetime(entry.get("created_at"))
        if created_at is None or created_at < cutoff:
            continue
        if str(entry.get("status") or "") != "completed":
            continue

        linked = _linked_cards(cards_list, str(entry.get("id")))
        candidates = _candidate_titles(entry, cards_list)
        workspace_key = str(entry.get("workspace_key") or "shared_ops")
        board_titles = _card_titles(cards_list, workspace_key=workspace_key)
        covered_cards = _cards_matching_titles(cards_list, candidates, workspace_key)
        unresolved_candidates = [title for title in candidates if title.lower() not in board_titles]
        created_cards: list[dict[str, Any]] = []

        if not linked and unresolved_candidates and sync_live and not _is_strategy_only(entry):
            for title in unresolved_candidates[:1]:
                created_card = _fetch_json(
                    f"{api_url.rstrip('/')}/api/pm/cards",
                    method="POST",
                    payload={
                        "title": title,
                        "owner": "Jean-Claude",
                        "status": "todo",
                        "source": f"post-sync-dispatch:{entry['id']}",
                        "link_type": "standup",
                        "link_id": entry["id"],
                        "payload": _build_card_payload(entry, title),
                    },
                )
                if isinstance(created_card, dict):
                    cards_list.append(created_card)
                    created_cards.append(created_card)
                    created_count += 1

        linked = _linked_cards(cards_list, str(entry.get("id")))
        covered_cards = _cards_matching_titles(cards_list, candidates, workspace_key)
        existing_count += len(linked)
        covered_card_ids = [card.get("id") for card in covered_cards if isinstance(card, dict) and card.get("id")]
        payload = dict(entry.get("payload") or {})
        payload["post_sync_dispatch"] = {
            "ran_at": _iso(now),
            "linked_card_ids": [card.get("id") for card in linked if isinstance(card, dict)],
            "created_card_ids": [card.get("id") for card in created_cards if isinstance(card, dict)],
            "covered_card_ids": covered_card_ids,
            "commitment_titles": unresolved_candidates,
            "candidate_titles": candidates,
            "status": (
                "strategy_only"
                if _is_strategy_only(entry)
                else ("ok" if linked else ("covered_by_existing_cards" if covered_cards else "no_action"))
            ),
        }
        if sync_live:
            _fetch_json(
                f"{api_url.rstrip('/')}/api/standups/{entry['id']}",
                method="PATCH",
                payload={"payload": payload},
            )
        processed.append(
            {
                "standup_id": entry.get("id"),
                "standup_kind": _standup_kind(entry),
                "workspace_key": entry.get("workspace_key") or "shared_ops",
                "created_at": entry.get("created_at"),
                "linked_card_ids": [card.get("id") for card in linked if isinstance(card, dict)],
                "created_card_ids": [card.get("id") for card in created_cards if isinstance(card, dict)],
                "covered_card_ids": covered_card_ids,
                "candidate_titles": unresolved_candidates,
                "strategy_only": _is_strategy_only(entry),
            }
        )

    return {
        "generated_at": _iso(now),
        "source": "post_sync_dispatch",
        "lookback_days": lookback_days,
        "sync_live": sync_live,
        "processed_count": len(processed),
        "created_count": created_count,
        "linked_count": existing_count,
        "standups": processed,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Post-Sync Dispatch Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Processed standups: `{report['processed_count']}`",
        f"- Linked cards: `{report['linked_count']}`",
        f"- Created fallback cards: `{report['created_count']}`",
        "",
        "## Standups",
    ]
    for item in report.get("standups") or []:
        lines.append(f"- `{item['standup_kind']}` / `{item['workspace_key']}` — standup `{item['standup_id']}`")
        lines.append(f"  - Linked cards: {', '.join(item.get('linked_card_ids') or []) or 'None'}")
        if item.get("created_card_ids"):
            lines.append(f"  - Created: {', '.join(item['created_card_ids'])}")
        if item.get("candidate_titles"):
            lines.append(f"  - Candidates: {'; '.join(item['candidate_titles'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default=str(REPORT_ROOT / "post_sync_dispatch_latest.json"))
    parser.add_argument("--output-md", default=str(REPORT_ROOT / "post_sync_dispatch_latest.md"))
    args = parser.parse_args()

    report = build_report(args.api_url, args.lookback_days, args.limit, sync_live=not args.dry_run)
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
