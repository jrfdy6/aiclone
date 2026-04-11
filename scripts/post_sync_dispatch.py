#!/usr/bin/env python3
"""Ensure completed standups leave concrete PM artifacts and dispatch metadata."""
from __future__ import annotations

import argparse
import json
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
        "document ",
        "make ",
        "promote ",
        "refine ",
        "run ",
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


def _candidate_titles(entry: dict[str, Any]) -> list[str]:
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


def _card_titles(cards: list[dict[str, Any]]) -> set[str]:
    return {
        str(card.get("title") or "").strip().lower()
        for card in cards
        if isinstance(card, dict) and str(card.get("title") or "").strip()
    }


def _build_card_payload(entry: dict[str, Any], title: str) -> dict[str, Any]:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    payload = entry.get("payload") or {}
    defaults = _execution_defaults(workspace_key)
    transition_at = _iso(_now())
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="post_sync_dispatch",
        reason="Post-sync dispatch created this card from a completed standup commitment.",
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
        candidates = _candidate_titles(entry)
        board_titles = _card_titles(cards_list)
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
        existing_count += len(linked)
        payload = dict(entry.get("payload") or {})
        payload["post_sync_dispatch"] = {
            "ran_at": _iso(now),
            "linked_card_ids": [card.get("id") for card in linked if isinstance(card, dict)],
            "created_card_ids": [card.get("id") for card in created_cards if isinstance(card, dict)],
            "commitment_titles": unresolved_candidates,
            "status": "strategy_only" if _is_strategy_only(entry) else ("ok" if linked else "no_action"),
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
