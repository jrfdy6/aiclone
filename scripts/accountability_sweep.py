#!/usr/bin/env python3
"""Push stale meeting-created PM work down the pipeline and surface stale execution lanes."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
REPORT_ROOT = WORKSPACE_ROOT / "memory" / "reports"
FOLLOWUP_TITLE = "Executive review stale PM lanes from accountability sweep"
FOLLOWUP_SOURCE = "accountability_sweep:executive_followup"
FOLLOWUP_REASON = "Accountability sweep found stale review/running cards that need closure decisions."

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs
from app.services.pm_execution_contract_service import build_execution_contract


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _is_closed_status(status: object) -> bool:
    return str(status or "").strip().lower() in {"done", "closed", "cancelled"}


def _load_cards(api_url: str, fetch_json: Callable[..., Any]) -> list[dict[str, Any]]:
    payload = fetch_json(f"{api_url.rstrip('/')}/api/pm/cards?limit=400")
    return [item for item in payload if isinstance(item, dict)]


def _find_open_followup(cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    for card in cards:
        if card.get("title") != FOLLOWUP_TITLE:
            continue
        if card.get("source") != FOLLOWUP_SOURCE:
            continue
        if _is_closed_status(card.get("status")):
            continue
        return card
    return None


def _execution_state_for_card(card: dict[str, Any]) -> str:
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    return str(execution.get("state") or "").strip().lower()


def _tracked_followup_card_ids(card: dict[str, Any]) -> list[str]:
    payload = dict(card.get("payload") or {})
    tracked: list[str] = []
    for key in ("rerouted_card_ids", "stale_card_ids", "stale_review_card_ids", "stale_running_card_ids"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            normalized = str(item or "").strip()
            if normalized and normalized != str(card.get("id") or "") and normalized not in tracked:
                tracked.append(normalized)
    return tracked


def _card_is_execution_healthy(card: dict[str, Any] | None) -> bool:
    if card is None:
        return False
    status = str(card.get("status") or "").strip().lower()
    if status in {"review", "done", "closed", "cancelled"}:
        return True
    return _execution_state_for_card(card) in {"review", "done"}


def _reroute_reason(entry: dict[str, Any]) -> str:
    previous_state = str(entry.get("execution_state") or "review")
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    return (
        f"Accountability sweep rerouted this stale `{previous_state}` lane in `{workspace_key}` "
        "back to Jean-Claude for a required closure decision."
    )


def _reroute_stale_card(
    api_url: str,
    card: dict[str, Any],
    entry: dict[str, Any],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any]:
    payload = dict(card.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    previous_state = str(execution.get("state") or entry.get("execution_state") or "review")
    previous_target = str(execution.get("target_agent") or entry.get("target_agent") or "unknown")
    reroute_reason = _reroute_reason(entry)
    history.append(
        {
            "event": "accountability_reroute",
            "state": "queued",
            "requested_by": "Accountability Sweep",
            "target_agent": "Jean-Claude",
            "previous_state": previous_state,
            "previous_target_agent": previous_target,
            "required_decision": "closure_review",
            "at": now.isoformat(),
        }
    )
    workspace_agent = execution.get("workspace_agent")
    execution.update(
        {
            "lane": "codex",
            "state": "queued",
            "manager_agent": "Jean-Claude",
            "manager_attention_required": True,
            "target_agent": "Jean-Claude",
            "assigned_runner": "jean-claude",
            "execution_mode": "direct",
            "requested_by": "Accountability Sweep",
            "reason": reroute_reason,
            "queued_at": now.isoformat(),
            "last_transition_at": now.isoformat(),
            "execution_packet_path": None,
            "executor_status": None,
            "executor_worker_id": None,
            "executor_started_at": None,
            "executor_finished_at": None,
            "executor_last_error": None,
            "history": history[-12:],
        }
    )
    if workspace_agent:
        execution["workspace_agent"] = workspace_agent
    payload["execution"] = execution
    payload["accountability"] = {
        "stale_escalated_at": now.isoformat(),
        "stale_escalation_reason": reroute_reason,
        "previous_execution_state": previous_state,
        "previous_target_agent": previous_target,
        "requires_closure_decision": True,
    }
    updated = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards/{entry['card_id']}",
        method="PATCH",
        payload={
            "owner": "Jean-Claude",
            "status": "review",
            "payload": payload,
        },
    )
    return {
        "card_id": entry.get("card_id"),
        "title": entry.get("title"),
        "workspace_key": entry.get("workspace_key"),
        "previous_state": previous_state,
        "previous_target_agent": previous_target,
        "next_state": "queued",
        "next_target_agent": "Jean-Claude",
        "updated_status": updated.get("status") if isinstance(updated, dict) else "review",
    }


def _upsert_executive_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    stale_review: list[dict[str, Any]],
    stale_running: list[dict[str, Any]],
    rerouted_cards: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any]:
    stale_card_ids = [str(item.get("card_id")) for item in stale_review + stale_running if item.get("card_id")]
    summary = (
        f"Accountability sweep found {len(stale_review)} stale review cards and "
        f"{len(stale_running)} stale active cards that require executive closure."
    )
    contract = build_execution_contract(
        title=FOLLOWUP_TITLE,
        workspace_key="shared_ops",
        source="accountability_sweep",
        reason=FOLLOWUP_REASON,
        instructions=[
            "Review the rerouted stale PM lanes and decide whether each one should close, continue, or stay blocked.",
            "Use the rerouted card list as the source of truth instead of creating duplicate executive work.",
            "Write back a bounded PM result that explains which stale lanes were resolved and which still need attention.",
        ],
        acceptance_criteria=[
            "Every tracked stale PM lane is either resolved, re-routed cleanly, or left with an explicit blocker decision.",
            "The executive follow-up writes a bounded PM result instead of remaining a placeholder reminder.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "bounded executive review note or closure artifact when stale lanes need explanation",
        ],
    )
    execution = {
        "lane": "codex",
        "state": "queued",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "execution_mode": "direct",
        "requested_by": "Accountability Sweep",
        "assigned_runner": "codex",
        "reason": FOLLOWUP_REASON,
        "queued_at": now.isoformat(),
        "last_transition_at": now.isoformat(),
        "source": "accountability_sweep",
    }
    payload = {
        "workspace_key": "shared_ops",
        "scope": "shared_ops",
        "source_agent": "accountability_sweep",
        "created_from_accountability_sweep": True,
        "latest_report_generated_at": now.isoformat(),
        "stale_review_card_ids": [item.get("card_id") for item in stale_review],
        "stale_running_card_ids": [item.get("card_id") for item in stale_running],
        "stale_card_ids": stale_card_ids,
        "rerouted_card_ids": [item.get("card_id") for item in rerouted_cards],
        "alert_summary": summary,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": execution,
    }

    existing = _find_open_followup(cards)
    if existing is not None:
        existing_payload = dict(existing.get("payload") or {})
        existing_execution = dict(existing_payload.get("execution") or {})
        existing_state = str(existing_execution.get("state") or "").strip().lower()
        if existing_state in {"ready", "queued", "running", "review"}:
            execution.update(
                {
                    "state": existing_execution.get("state"),
                    "queued_at": existing_execution.get("queued_at") or execution.get("queued_at"),
                    "last_transition_at": existing_execution.get("last_transition_at") or execution.get("last_transition_at"),
                    "assigned_runner": existing_execution.get("assigned_runner") or execution.get("assigned_runner"),
                    "executor_status": existing_execution.get("executor_status"),
                    "executor_worker_id": existing_execution.get("executor_worker_id"),
                    "manager_attention_required": existing_execution.get("manager_attention_required"),
                }
            )
        payload["execution"] = execution
        updated = fetch_json(
            f"{api_url.rstrip('/')}/api/pm/cards/{existing['id']}",
            method="PATCH",
            payload={
                "owner": "Jean-Claude",
                "payload": {**existing_payload, **payload},
            },
        )
        card_id = updated.get("id") if isinstance(updated, dict) else existing.get("id")
        status = updated.get("status") if isinstance(updated, dict) else existing.get("status")
        return {"action": "updated", "card_id": card_id, "status": status, "title": FOLLOWUP_TITLE}

    created = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards",
        method="POST",
        payload={
            "title": FOLLOWUP_TITLE,
            "owner": "Jean-Claude",
            "status": "todo",
            "source": FOLLOWUP_SOURCE,
            "payload": payload,
        },
    )
    return {
        "action": "created",
        "card_id": created.get("id") if isinstance(created, dict) else None,
        "status": created.get("status") if isinstance(created, dict) else "todo",
        "title": FOLLOWUP_TITLE,
    }


def _resolve_executive_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any] | None:
    existing = _find_open_followup(cards)
    if existing is None:
        return None
    cards_by_id = {str(item.get("id")): item for item in cards if item.get("id")}
    tracked_card_ids = _tracked_followup_card_ids(existing)
    if tracked_card_ids:
        pending_card_ids = [card_id for card_id in tracked_card_ids if not _card_is_execution_healthy(cards_by_id.get(card_id))]
        if pending_card_ids:
            return {
                "action": "tracked",
                "card_id": existing.get("id"),
                "status": existing.get("status"),
                "title": FOLLOWUP_TITLE,
                "pending_card_ids": pending_card_ids,
            }

    payload = dict(existing.get("payload") or {})
    execution = dict(payload.get("execution") or {})
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": "accountability_resolved",
            "state": "done",
            "requested_by": "Accountability Sweep",
            "target_agent": "Jean-Claude",
            "at": now.isoformat(),
        }
    )
    execution.update(
        {
            "state": "done",
            "manager_attention_required": False,
            "target_agent": "Jean-Claude",
            "assigned_runner": "codex",
            "reason": (
                "Tracked stale lanes returned to review/done, so the executive follow-up was closed automatically."
                if tracked_card_ids
                else "Accountability sweep found no stale review or running lanes, so the executive follow-up was closed automatically."
            ),
            "last_transition_at": now.isoformat(),
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    payload["resolved_at"] = now.isoformat()
    payload["resolution_reason"] = (
        "Tracked rerouted cards are now back in review/done."
        if tracked_card_ids
        else "No stale review or running PM lanes remained."
    )
    updated = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards/{existing['id']}",
        method="PATCH",
        payload={
            "status": "done",
            "payload": payload,
        },
    )
    return {
        "action": "closed",
        "card_id": updated.get("id") if isinstance(updated, dict) else existing.get("id"),
        "status": updated.get("status") if isinstance(updated, dict) else "done",
        "title": FOLLOWUP_TITLE,
    }


def build_report(
    api_url: str,
    ready_age_minutes: int,
    review_age_hours: int,
    sync_live: bool,
    *,
    fetch_json: Callable[..., Any] = _fetch_json,
) -> dict[str, Any]:
    now = _now()
    queue = fetch_json(f"{api_url.rstrip('/')}/api/pm/execution-queue?limit=200")
    rows = [item for item in queue if isinstance(item, dict)]
    cards = _load_cards(api_url, fetch_json)
    cards_by_id = {str(item.get("id")): item for item in cards if item.get("id")}

    stale_ready_cutoff = now - timedelta(minutes=ready_age_minutes)
    stale_review_cutoff = now - timedelta(hours=review_age_hours)

    dispatched: list[dict[str, Any]] = []
    stale_review: list[dict[str, Any]] = []
    stale_running: list[dict[str, Any]] = []
    ready_candidates: list[dict[str, Any]] = []
    rerouted_cards: list[dict[str, Any]] = []

    for entry in rows:
        state = str(entry.get("execution_state") or "ready").lower()
        timestamp = _parse_datetime(entry.get("last_transition_at") or entry.get("queued_at"))
        if state == "ready":
            ready_candidates.append(entry)
            if timestamp is not None and timestamp <= stale_ready_cutoff and sync_live:
                result = fetch_json(
                    f"{api_url.rstrip('/')}/api/pm/cards/{entry['card_id']}/dispatch",
                    method="POST",
                    payload={
                        "target_agent": entry.get("target_agent") or "Jean-Claude",
                        "lane": "codex",
                        "requested_by": "Jean-Claude",
                        "execution_state": "queued",
                    },
                )
                dispatched.append(
                    {
                        "card_id": entry.get("card_id"),
                        "title": entry.get("title"),
                        "workspace_key": entry.get("workspace_key"),
                        "target_agent": entry.get("target_agent"),
                        "queued_state": result.get("queue_entry", {}).get("execution_state") if isinstance(result, dict) else "queued",
                    }
                )
        elif state == "review" and timestamp is not None and timestamp <= stale_review_cutoff:
            stale_review.append(
                {
                    "card_id": entry.get("card_id"),
                    "title": entry.get("title"),
                    "workspace_key": entry.get("workspace_key"),
                    "target_agent": entry.get("target_agent"),
                    "last_transition_at": entry.get("last_transition_at"),
                }
            )
        elif state in {"queued", "running"} and timestamp is not None and timestamp <= stale_review_cutoff:
            stale_running.append(
                {
                    "card_id": entry.get("card_id"),
                    "title": entry.get("title"),
                    "workspace_key": entry.get("workspace_key"),
                    "target_agent": entry.get("target_agent"),
                    "execution_state": state,
                    "last_transition_at": entry.get("last_transition_at"),
                }
            )

    stale_entries = stale_review + stale_running
    if sync_live:
        for entry in stale_entries:
            card = cards_by_id.get(str(entry.get("card_id")))
            if card is None:
                continue
            rerouted_cards.append(
                _reroute_stale_card(
                    api_url,
                    card,
                    entry,
                    now=now,
                    fetch_json=fetch_json,
                )
            )

    executive_followup_card: dict[str, Any] | None = None
    if stale_entries and sync_live:
        executive_followup_card = _upsert_executive_followup(
            api_url,
            cards,
            stale_review,
            stale_running,
            rerouted_cards,
            now=now,
            fetch_json=fetch_json,
        )
    elif sync_live:
        executive_followup_card = _resolve_executive_followup(
            api_url,
            cards,
            now=now,
            fetch_json=fetch_json,
        )

    return {
        "generated_at": _iso(now),
        "source": "accountability_sweep",
        "sync_live": sync_live,
        "ready_age_minutes": ready_age_minutes,
        "review_age_hours": review_age_hours,
        "ready_count": len(ready_candidates),
        "dispatched_count": len(dispatched),
        "stale_review_count": len(stale_review),
        "stale_running_count": len(stale_running),
        "rerouted_count": len(rerouted_cards),
        "dispatched_cards": dispatched,
        "stale_review_cards": stale_review,
        "stale_running_cards": stale_running,
        "rerouted_cards": rerouted_cards,
        "executive_followup_card": executive_followup_card,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Accountability Sweep Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Ready cards seen: `{report['ready_count']}`",
        f"- Dispatched to queue: `{report['dispatched_count']}`",
        f"- Stale review cards: `{report['stale_review_count']}`",
        f"- Stale active cards: `{report['stale_running_count']}`",
        f"- Rerouted back to Jean-Claude: `{report['rerouted_count']}`",
        "",
        "## Dispatched cards",
    ]
    if not report.get("dispatched_cards"):
        lines.append("- None.")
    else:
        for item in report["dispatched_cards"]:
            lines.append(f"- `{item['title']}` -> `{item['target_agent']}` in `{item['workspace_key']}`")
    lines.extend(["", "## Stale review cards"])
    if not report.get("stale_review_cards"):
        lines.append("- None.")
    else:
        for item in report["stale_review_cards"]:
            lines.append(f"- `{item['title']}` last changed at `{item['last_transition_at']}`")
    lines.extend(["", "## Stale active cards"])
    if not report.get("stale_running_cards"):
        lines.append("- None.")
    else:
        for item in report["stale_running_cards"]:
            lines.append(f"- `{item['title']}` is `{item['execution_state']}` since `{item['last_transition_at']}`")
    lines.extend(["", "## Rerouted cards"])
    if not report.get("rerouted_cards"):
        lines.append("- None.")
    else:
        for item in report["rerouted_cards"]:
            lines.append(
                f"- `{item['title']}` moved from `{item['previous_state']}` / `{item['previous_target_agent']}` "
                "back to `Jean-Claude` for closure review."
            )
    lines.extend(["", "## Executive follow-up"])
    followup = report.get("executive_followup_card")
    if not isinstance(followup, dict):
        lines.append("- None.")
    else:
        lines.append(
            f"- `{followup.get('title', FOLLOWUP_TITLE)}` -> `{followup.get('action', 'tracked')}` "
            f"(`{followup.get('status', 'unknown')}`)"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--ready-age-minutes", type=int, default=90)
    parser.add_argument("--review-age-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default=str(REPORT_ROOT / "accountability_sweep_latest.json"))
    parser.add_argument("--output-md", default=str(REPORT_ROOT / "accountability_sweep_latest.md"))
    args = parser.parse_args()

    started_at = _now()
    report = build_report(
        args.api_url,
        ready_age_minutes=args.ready_age_minutes,
        review_age_hours=args.review_age_hours,
        sync_live=not args.dry_run,
    )
    finished_at = _now()
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    if not args.dry_run:
        followup = report.get("executive_followup_card")
        mirror_runs(
            args.api_url,
            [
                build_run_payload(
                    run_id=f"accountability_sweep::{report['generated_at']}",
                    automation_id="accountability_sweep",
                    automation_name="Accountability Sweep",
                    status="ok",
                    run_at=started_at,
                    finished_at=finished_at,
                    duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                    scope="shared_ops",
                    action_required=bool(report.get("rerouted_count") or isinstance(followup, dict)),
                    metadata={
                        "ready_count": report["ready_count"],
                        "dispatched_count": report["dispatched_count"],
                        "stale_review_count": report["stale_review_count"],
                        "stale_running_count": report["stale_running_count"],
                        "rerouted_count": report["rerouted_count"],
                        "executive_followup_action": followup.get("action") if isinstance(followup, dict) else None,
                        "executive_followup_card_id": followup.get("card_id") if isinstance(followup, dict) else None,
                    },
                )
            ],
        )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
