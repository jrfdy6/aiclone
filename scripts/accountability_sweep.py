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
SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_paths import PROJECT_ROOT, memory_state_path


WORKSPACE_ROOT = PROJECT_ROOT
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
REPORT_ROOT = memory_state_path("reports")
FOLLOWUP_TITLE = "Executive review stale PM lanes from accountability sweep"
FOLLOWUP_SOURCE = "accountability_sweep:executive_followup"
FOLLOWUP_REASON = "Accountability sweep found stale review/running cards that need closure decisions."
STANDUP_STARVATION_FOLLOWUP_TITLE = "Executive review starved standups from accountability sweep"
STANDUP_STARVATION_FOLLOWUP_SOURCE = "accountability_sweep:standup_starvation_followup"
STANDUP_STARVATION_FOLLOWUP_REASON = (
    "Accountability sweep found completed standups that still have no qualifying downstream execution lane."
)
DEFAULT_STANDUP_LIMIT = 200
WORKSPACE_STARVATION_SOURCE_PREFIX = "accountability_sweep:workspace_starvation:"
WORKSPACE_LABELS = {
    "shared_ops": "Shared Ops",
    "feezie-os": "FEEZIE OS",
    "linkedin-os": "FEEZIE OS",
    "fusion-os": "Fusion OS",
    "easyoutfitapp": "Easy Outfit App",
    "ai-swag-store": "AI Swag Store",
    "agc": "AGC",
}

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime_http import control_plane_headers
from automation_run_mirror import build_run_payload, mirror_runs
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_runtime_contract_service import execution_defaults_for_workspace
from brain_automation_context import (
    brain_signal_lines,
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
)


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
        headers=control_plane_headers({"Accept": "application/json", "Content-Type": "application/json"}),
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


def _load_standups(api_url: str, fetch_json: Callable[..., Any], *, limit: int = DEFAULT_STANDUP_LIMIT) -> list[dict[str, Any]]:
    payload = fetch_json(f"{api_url.rstrip('/')}/api/standups/?limit={limit}")
    return [item for item in payload if isinstance(item, dict)]


def _find_open_followup(cards: list[dict[str, Any]], *, title: str = FOLLOWUP_TITLE, source: str = FOLLOWUP_SOURCE) -> dict[str, Any] | None:
    for card in cards:
        if card.get("title") != title:
            continue
        if card.get("source") != source:
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


def _normalize_pm_status(status: object) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"in_progress", "in-progress"}:
        return "in_progress"
    if normalized == "review":
        return "review"
    if normalized in {"cancelled", "canceled", "done", "closed"}:
        return "done"
    if normalized in {"failed", "blocked", "error"}:
        return "blocked"
    return "todo"


def _standup_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else {}


def _pm_card_payload(card: dict[str, Any]) -> dict[str, Any]:
    payload = card.get("payload")
    return payload if isinstance(payload, dict) else {}


def _pm_card_execution(card: dict[str, Any]) -> dict[str, Any]:
    execution = _pm_card_payload(card).get("execution")
    return execution if isinstance(execution, dict) else {}


def _standup_kind(entry: dict[str, Any]) -> str:
    payload = _standup_payload(entry)
    value = payload.get("standup_kind")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return str(entry.get("workspace_key") or "shared_ops").strip().lower()


def _standup_is_strategy_only(entry: dict[str, Any]) -> bool:
    return _standup_kind(entry) == "saturday_vision"


def _standup_is_starvation_candidate(entry: dict[str, Any]) -> bool:
    if str(entry.get("status") or "").strip().lower() != "completed":
        return False
    if _standup_is_strategy_only(entry):
        return False
    return _standup_kind(entry) in {"workspace_sync", "executive_ops"}


def _linked_cards_for_standup(entry: dict[str, Any], cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    standup_id = str(entry.get("id") or "").strip()
    if not standup_id:
        return []
    linked: list[dict[str, Any]] = []
    for card in cards:
        payload = _pm_card_payload(card)
        if card.get("link_id") == standup_id or payload.get("created_from_standup_id") == standup_id:
            linked.append(card)
            continue
        carry_forward_ids = payload.get("carry_forward_standup_ids")
        if isinstance(carry_forward_ids, list) and any(str(item or "").strip() == standup_id for item in carry_forward_ids):
            linked.append(card)
            continue
        starvation_ids = payload.get("starved_standup_ids")
        if isinstance(starvation_ids, list) and any(str(item or "").strip() == standup_id for item in starvation_ids):
            linked.append(card)
    return linked


def _pm_card_is_host_action(card: dict[str, Any]) -> bool:
    return isinstance(_pm_card_payload(card).get("host_action_required"), dict)


def _pm_card_is_owner_review(card: dict[str, Any]) -> bool:
    payload = _pm_card_payload(card)
    return card.get("link_type") == "owner_review" or isinstance(payload.get("owner_review"), dict)


def _standup_low_value_card_title(card: dict[str, Any]) -> bool:
    normalized = " ".join(str(card.get("title") or "").split()).strip().lower()
    if not normalized:
        return False
    return (
        normalized.startswith("review ")
        or normalized.startswith("decide whether ")
        or normalized.startswith("define next concrete opportunity ")
        or normalized.startswith("confirm the next move for ")
        or normalized.startswith("bring this back ")
        or normalized.startswith("bring ")
        or normalized.startswith("keep ")
        or normalized == "nothing to report"
    )


def _standup_card_successor_ids(card: dict[str, Any]) -> list[str]:
    payload = _pm_card_payload(card)
    latest_manual_review = payload.get("latest_manual_review")
    spawned_followup = payload.get("host_action_followup_spawned")
    values = [
        latest_manual_review.get("successor_card_id") if isinstance(latest_manual_review, dict) else None,
        latest_manual_review.get("host_action_card_id") if isinstance(latest_manual_review, dict) else None,
        spawned_followup.get("card_id") if isinstance(spawned_followup, dict) else None,
    ]
    seen: list[str] = []
    for item in values:
        normalized = str(item or "").strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _standup_card_source_ids(card: dict[str, Any]) -> list[str]:
    host_action = _pm_card_payload(card).get("host_action_required")
    if not isinstance(host_action, dict):
        return []
    normalized = str(host_action.get("source_card_id") or "").strip()
    return [normalized] if normalized else []


def _collect_related_cards_for_standup(entry: dict[str, Any], cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direct_cards = _linked_cards_for_standup(entry, cards)
    cards_by_id = {str(card.get("id") or ""): card for card in cards if card.get("id")}
    cards_by_source_id: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        for source_id in _standup_card_source_ids(card):
            cards_by_source_id.setdefault(source_id, []).append(card)

    related: dict[str, dict[str, Any]] = {}
    queue: list[dict[str, Any]] = list(direct_cards)
    while queue:
        card = queue.pop(0)
        card_id = str(card.get("id") or "").strip()
        if not card_id or card_id in related:
            continue
        related[card_id] = card
        for child in cards_by_source_id.get(card_id, []):
            child_id = str(child.get("id") or "").strip()
            if child_id and child_id not in related:
                queue.append(child)
        for successor_id in _standup_card_successor_ids(card):
            successor = cards_by_id.get(successor_id)
            if successor is not None and successor_id not in related:
                queue.append(successor)

    return direct_cards, list(related.values())


def _standup_card_counts_as_runnable_execution(
    card: dict[str, Any],
    execution_by_card_id: dict[str, dict[str, Any]],
) -> bool:
    if _pm_card_is_host_action(card) or _pm_card_is_owner_review(card) or _standup_low_value_card_title(card):
        return False
    execution_state = str(_pm_card_execution(card).get("state") or "").strip().lower()
    status = _normalize_pm_status(card.get("status"))
    return bool(execution_by_card_id.get(str(card.get("id") or "")) or execution_state or status in {"in_progress", "review", "done"})


def _workspace_label(workspace_key: str) -> str:
    normalized = str(workspace_key or "").strip() or "shared_ops"
    return WORKSPACE_LABELS.get(normalized, normalized)


def _standup_section_lines(entry: dict[str, Any], key: str) -> list[str]:
    sections = dict(_standup_payload(entry).get("standup_sections") or {})
    values = sections.get(key)
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _standup_text_sections(entry: dict[str, Any]) -> list[str]:
    values: list[str] = []
    payload = _standup_payload(entry)
    collections = [
        payload.get("artifact_deltas"),
        _standup_section_lines(entry, "content_produced"),
        _standup_section_lines(entry, "opportunities_created"),
        _standup_section_lines(entry, "next_focus"),
        entry.get("commitments"),
        entry.get("needs"),
    ]
    for collection in collections:
        if not isinstance(collection, list):
            continue
        for item in collection:
            normalized = str(item).strip()
            if normalized:
                values.append(normalized)
    return values


def _starvation_remediation_title(entry: dict[str, Any]) -> str:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    text_blob = " ".join(_standup_text_sections(entry)).lower()
    if workspace_key == "shared_ops":
        return "Resolve the carried Executive lane from the latest standup context"
    if workspace_key in {"feezie-os", "linkedin-os"}:
        return "Run the current FEEZIE owner-review packet and record decisions"
    if workspace_key == "fusion-os":
        if "leadership pov" in text_blob:
            return "Schedule the next Fusion leadership POV move and capture proof"
        return "Resolve the carried Fusion OS content lane from the latest workspace briefing"
    if workspace_key == "easyoutfitapp":
        return "Capture the first Easy Outfit App traffic baseline proof"
    if workspace_key == "ai-swag-store":
        return "Capture the first AI Swag Store traffic baseline proof"
    if workspace_key == "agc":
        if "write-back" in text_blob or "write back" in text_blob:
            return "Write back the AGC capability experiment result to PM"
        return "Advance the next AGC opportunity lane from the latest workspace briefing"
    return f"Resolve the carried {_workspace_label(workspace_key)} lane from the latest standup context"


def _starvation_remediation_reason(entry: dict[str, Any], item: dict[str, Any]) -> str:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    category = str(item.get("output_category") or "no_output")
    return (
        f"Accountability sweep forced a real `{workspace_key}` lane because standup `{entry.get('id')}` "
        f"completed with `{category}` instead of a qualifying downstream execution path."
    )


def _starvation_remediation_payload(entry: dict[str, Any], item: dict[str, Any], title: str, *, now: datetime) -> dict[str, Any]:
    workspace_key = str(entry.get("workspace_key") or "shared_ops")
    defaults = execution_defaults_for_workspace(workspace_key)
    transition_at = now.isoformat()
    text_sections = _standup_text_sections(entry)
    instructions = [
        f"Advance `{title}` inside `{workspace_key}` without opening a parallel lane.",
        "Use the linked standup and current workspace artifacts as the source of truth.",
    ]
    if text_sections:
        instructions.append(f"Anchor the next move in this standup evidence: {text_sections[0]}")
    instructions.append("Write back one bounded result with the exact next artifact, proof, or blocker.")
    acceptance_criteria = [
        f"`{title}` becomes a real downstream lane instead of leaving the standup starved.",
        "The result cites the local workspace context that justified the move.",
        "PM write-back names the exact artifact, proof step, or blocker next.",
    ]
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="accountability_sweep",
        reason=_starvation_remediation_reason(entry, item),
        instructions=instructions,
        acceptance_criteria=acceptance_criteria,
        artifacts_expected=[
            "updated PM execution result",
            "bounded workspace artifact, host-proof step, or explicit blocker decision",
        ],
    )
    return {
        "workspace_key": workspace_key,
        "scope": "workspace",
        "source_agent": "Jean-Claude",
        "created_from_standup_id": entry.get("id"),
        "created_from_standup_kind": _standup_kind(entry),
        "created_from_standup_workspace": workspace_key,
        "reason": _starvation_remediation_reason(entry, item),
        "participants": _standup_payload(entry).get("participants") or [],
        "accountability_starved_standup_id": str(entry.get("id") or "").strip(),
        "accountability_starvation_output_category": str(item.get("output_category") or "no_output"),
        "carry_forward_required": True,
        "carry_forward_standup_ids": [str(entry.get("id") or "").strip()],
        "execution": {
            "lane": "codex",
            "state": "queued",
            "manager_agent": defaults["manager_agent"],
            "target_agent": defaults["target_agent"],
            "workspace_agent": defaults.get("workspace_agent"),
            "execution_mode": defaults["execution_mode"],
            "requested_by": "Jean-Claude",
            "assigned_runner": "codex",
            "reason": _starvation_remediation_reason(entry, item),
            "queued_at": transition_at,
            "last_transition_at": transition_at,
            "source": "accountability_sweep",
        },
        **contract,
    }


def _find_workspace_starvation_remediation_card(
    cards: list[dict[str, Any]],
    *,
    standup_id: str | None,
    workspace_key: str,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict) or _is_closed_status(card.get("status")):
            continue
        if not str(card.get("source") or "").startswith(WORKSPACE_STARVATION_SOURCE_PREFIX):
            continue
        payload = _pm_card_payload(card)
        if str(payload.get("workspace_key") or card.get("workspace_key") or "").strip() != workspace_key:
            continue
        tracked_ids = {
            str(payload.get("accountability_starved_standup_id") or "").strip(),
            *[
                str(item).strip()
                for item in payload.get("accountability_starved_standup_ids") or []
                if str(item).strip()
            ],
        }
        if standup_id and standup_id not in tracked_ids:
            continue
        candidates.append(card)
    if not candidates:
        return None
    candidates.sort(
        key=lambda card: _parse_datetime(card.get("updated_at"))
        or _parse_datetime(card.get("created_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return candidates[0]


def _standup_needs_direct_remediation_lane(item: dict[str, Any]) -> bool:
    standup_kind = str(item.get("standup_kind") or "").strip()
    workspace_key = str(item.get("workspace_key") or "shared_ops").strip()
    if standup_kind == "workspace_sync":
        return True
    return standup_kind == "executive_ops" and workspace_key == "shared_ops"


def _active_workspace_starvation_remediation_cards(
    cards: list[dict[str, Any]],
    *,
    workspace_key: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict) or _is_closed_status(card.get("status")):
            continue
        if not str(card.get("source") or "").startswith(WORKSPACE_STARVATION_SOURCE_PREFIX):
            continue
        payload = _pm_card_payload(card)
        if str(payload.get("workspace_key") or card.get("workspace_key") or "").strip() != workspace_key:
            continue
        candidates.append(card)
    candidates.sort(
        key=lambda card: _parse_datetime(card.get("updated_at"))
        or _parse_datetime(card.get("created_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return candidates


def _merge_tracked_standup_ids(existing_payload: dict[str, Any], standup_id: str) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [
        existing_payload.get("accountability_starved_standup_id"),
        *(existing_payload.get("accountability_starved_standup_ids") or []),
        *(existing_payload.get("carry_forward_standup_ids") or []),
        standup_id,
    ]:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def _select_low_value_refresh_card(entry: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    _, related_cards = _collect_related_cards_for_standup(entry, cards)
    candidates = [
        card
        for card in related_cards
        if not _pm_card_is_host_action(card)
        and not _pm_card_is_owner_review(card)
        and _standup_low_value_card_title(card)
        and not _is_closed_status(card.get("status"))
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda card: _parse_datetime(card.get("updated_at"))
        or _parse_datetime(card.get("created_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return candidates[0]


def _replace_cached_card(cards: list[dict[str, Any]], updated_card: dict[str, Any]) -> None:
    updated_id = str(updated_card.get("id") or "").strip()
    if not updated_id:
        return
    for index, card in enumerate(cards):
        if str(card.get("id") or "").strip() == updated_id:
            cards[index] = updated_card
            return
    cards.append(updated_card)


def _upsert_workspace_starvation_remediation_cards(
    api_url: str,
    standups: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    starved_standups: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> list[dict[str, Any]]:
    standups_by_id = {
        str(entry.get("id") or "").strip(): entry
        for entry in standups
        if isinstance(entry, dict) and str(entry.get("id") or "").strip()
    }
    latest_by_workspace: dict[str, dict[str, Any]] = {}
    for item in starved_standups:
        if not _standup_needs_direct_remediation_lane(item):
            continue
        workspace_key = str(item.get("workspace_key") or "shared_ops").strip()
        existing = latest_by_workspace.get(workspace_key)
        if existing is None:
            latest_by_workspace[workspace_key] = item
            continue
        existing_created = _parse_datetime(existing.get("created_at"))
        candidate_created = _parse_datetime(item.get("created_at"))
        if (candidate_created or datetime.min.replace(tzinfo=timezone.utc)) >= (
            existing_created or datetime.min.replace(tzinfo=timezone.utc)
        ):
            latest_by_workspace[workspace_key] = item
    results: list[dict[str, Any]] = []
    ordered_items = sorted(
        latest_by_workspace.values(),
        key=lambda item: _parse_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for item in ordered_items:
        workspace_key = str(item.get("workspace_key") or "shared_ops").strip()
        standup_id = str(item.get("standup_id") or "").strip()
        entry = standups_by_id.get(standup_id)
        if entry is None:
            continue
        existing = _find_workspace_starvation_remediation_card(cards, standup_id=standup_id, workspace_key=workspace_key)
        if existing is None:
            existing = _find_workspace_starvation_remediation_card(cards, standup_id=None, workspace_key=workspace_key)
        if existing is not None:
            existing_payload = dict(existing.get("payload") or {})
            merged_standup_ids = _merge_tracked_standup_ids(existing_payload, standup_id)
            updated = fetch_json(
                f"{api_url.rstrip('/')}/api/pm/cards/{existing['id']}",
                method="PATCH",
                payload={
                    "title": _starvation_remediation_title(entry),
                    "owner": "Jean-Claude",
                    "status": "todo",
                    "source": f"{WORKSPACE_STARVATION_SOURCE_PREFIX}{standup_id}",
                    "link_type": "standup",
                    "link_id": standup_id,
                    "payload": {
                        **existing_payload,
                        **_starvation_remediation_payload(entry, item, _starvation_remediation_title(entry), now=now),
                        "accountability_starved_standup_ids": merged_standup_ids,
                        "carry_forward_standup_ids": merged_standup_ids,
                    },
                },
            )
            if isinstance(updated, dict):
                _replace_cached_card(cards, updated)
                results.append(
                    {
                        "action": "tracked" if str(existing.get("id")) == str(updated.get("id")) and standup_id in merged_standup_ids else "refreshed",
                        "card_id": updated.get("id"),
                        "status": updated.get("status"),
                        "title": updated.get("title"),
                        "workspace_key": workspace_key,
                        "standup_id": standup_id,
                    }
                )
            continue
        title = _starvation_remediation_title(entry)
        payload = _starvation_remediation_payload(entry, item, title, now=now)
        payload["accountability_starved_standup_ids"] = [standup_id]
        payload["carry_forward_standup_ids"] = [standup_id]
        refresh_target = _select_low_value_refresh_card(entry, cards)
        if refresh_target is not None:
            updated = fetch_json(
                f"{api_url.rstrip('/')}/api/pm/cards/{refresh_target['id']}",
                method="PATCH",
                payload={
                    "title": title,
                    "owner": "Jean-Claude",
                    "status": "todo",
                    "source": f"{WORKSPACE_STARVATION_SOURCE_PREFIX}{standup_id}",
                    "link_type": "standup",
                    "link_id": standup_id,
                    "payload": {**dict(refresh_target.get("payload") or {}), **payload},
                },
            )
            if isinstance(updated, dict):
                _replace_cached_card(cards, updated)
                results.append(
                    {
                        "action": "refreshed",
                        "card_id": updated.get("id"),
                        "status": updated.get("status"),
                        "title": updated.get("title"),
                        "workspace_key": workspace_key,
                        "standup_id": standup_id,
                    }
                )
            continue
        created = fetch_json(
            f"{api_url.rstrip('/')}/api/pm/cards",
            method="POST",
            payload={
                "title": title,
                "owner": "Jean-Claude",
                "status": "todo",
                "source": f"{WORKSPACE_STARVATION_SOURCE_PREFIX}{standup_id}",
                "link_type": "standup",
                "link_id": standup_id,
                "payload": payload,
            },
        )
        if isinstance(created, dict):
            cards.append(created)
            results.append(
                {
                    "action": "created",
                    "card_id": created.get("id"),
                    "status": created.get("status"),
                    "title": created.get("title"),
                    "workspace_key": workspace_key,
                    "standup_id": standup_id,
                }
            )
    return results


def _collapse_workspace_starvation_remediation_duplicates(
    api_url: str,
    cards: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> list[dict[str, Any]]:
    by_workspace: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        if not isinstance(card, dict) or _is_closed_status(card.get("status")):
            continue
        if not str(card.get("source") or "").startswith(WORKSPACE_STARVATION_SOURCE_PREFIX):
            continue
        payload = _pm_card_payload(card)
        workspace_key = str(payload.get("workspace_key") or card.get("workspace_key") or "shared_ops").strip()
        by_workspace.setdefault(workspace_key, []).append(card)

    results: list[dict[str, Any]] = []
    for workspace_key, workspace_cards in by_workspace.items():
        workspace_cards.sort(
            key=lambda card: _parse_datetime(card.get("updated_at"))
            or _parse_datetime(card.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        keeper = workspace_cards[0]
        for duplicate in workspace_cards[1:]:
            duplicate_payload = dict(duplicate.get("payload") or {})
            duplicate_execution = dict(duplicate_payload.get("execution") or {})
            duplicate_history = list(duplicate_execution.get("history") or [])
            duplicate_history.append(
                {
                    "event": "duplicate_workspace_starvation_lane_closed",
                    "state": "done",
                    "requested_by": "Accountability Sweep",
                    "target_agent": duplicate_execution.get("target_agent") or "Jean-Claude",
                    "at": now.isoformat(),
                    "superseded_by_pm_card_id": keeper.get("id"),
                }
            )
            duplicate_execution.update(
                {
                    "state": "done",
                    "manager_attention_required": False,
                    "reason": f"Duplicate workspace starvation remediation lane closed automatically; `{keeper.get('title')}` remains active for `{workspace_key}`.",
                    "last_transition_at": now.isoformat(),
                    "history": duplicate_history[-12:],
                }
            )
            duplicate_payload["execution"] = duplicate_execution
            duplicate_payload["resolved_at"] = now.isoformat()
            duplicate_payload["resolution_reason"] = (
                f"Duplicate workspace starvation remediation lane closed automatically in favor of `{keeper.get('id')}`."
            )
            duplicate_payload["superseded_by_pm_card_id"] = keeper.get("id")
            updated = fetch_json(
                f"{api_url.rstrip('/')}/api/pm/cards/{duplicate['id']}",
                method="PATCH",
                payload={
                    "status": "done",
                    "payload": duplicate_payload,
                },
            )
            if isinstance(updated, dict):
                _replace_cached_card(cards, updated)
                results.append(
                    {
                        "action": "closed_duplicate",
                        "card_id": updated.get("id"),
                        "status": updated.get("status"),
                        "title": updated.get("title"),
                        "workspace_key": workspace_key,
                        "superseded_by_card_id": keeper.get("id"),
                    }
                )
    return results


def _classify_starved_standup(
    entry: dict[str, Any],
    cards: list[dict[str, Any]],
    execution_by_card_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    direct_cards, related_cards = _collect_related_cards_for_standup(entry, cards)
    if any(_pm_card_is_host_action(card) for card in related_cards):
        return None
    if any(_pm_card_is_owner_review(card) for card in related_cards):
        return None
    if any(_standup_card_counts_as_runnable_execution(card, execution_by_card_id) for card in related_cards):
        return None

    low_value_titles = [
        str(card.get("title") or "").strip()
        for card in related_cards
        if not _pm_card_is_host_action(card) and not _pm_card_is_owner_review(card) and _standup_low_value_card_title(card)
    ]
    output_category = "low_value" if low_value_titles else "no_output"
    detail = (
        f"Only low-value PM output came out of this standup: {' · '.join(low_value_titles[:2])}."
        if output_category == "low_value"
        else "No runnable execution lane, host-action lane, or owner-review lane came out of this standup yet."
    )
    return {
        "standup_id": str(entry.get("id") or "").strip(),
        "workspace_key": str(entry.get("workspace_key") or "shared_ops"),
        "standup_kind": _standup_kind(entry),
        "created_at": entry.get("created_at"),
        "summary": str(_standup_payload(entry).get("summary") or "").strip(),
        "output_category": output_category,
        "detail": detail,
        "linked_card_ids": [str(card.get("id") or "").strip() for card in direct_cards if card.get("id")],
        "related_card_ids": [str(card.get("id") or "").strip() for card in related_cards if card.get("id")],
        "low_value_titles": [title for title in low_value_titles if title],
    }


def _collect_starved_standups(
    standups: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    queue_rows: list[dict[str, Any]],
    *,
    now: datetime,
    standup_age_minutes: int,
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(minutes=standup_age_minutes)
    execution_by_card_id = {
        str(item.get("card_id") or "").strip(): item
        for item in queue_rows
        if isinstance(item, dict) and str(item.get("card_id") or "").strip()
    }
    starved: list[dict[str, Any]] = []
    for entry in standups:
        if not _standup_is_starvation_candidate(entry):
            continue
        created_at = _parse_datetime(entry.get("created_at"))
        if created_at is None or created_at > cutoff:
            continue
        classified = _classify_starved_standup(entry, cards, execution_by_card_id)
        if classified is not None:
            starved.append(classified)
    return starved


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


def _upsert_standup_starvation_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    starved_standups: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any]:
    summary = (
        f"Accountability sweep found {len(starved_standups)} completed standup"
        f"{'' if len(starved_standups) == 1 else 's'} without qualifying downstream execution."
    )
    contract = build_execution_contract(
        title=STANDUP_STARVATION_FOLLOWUP_TITLE,
        workspace_key="shared_ops",
        source="accountability_sweep",
        reason=STANDUP_STARVATION_FOLLOWUP_REASON,
        instructions=[
            "Review each starved standup and force exactly one qualifying downstream lane: runnable execution, host action, or owner review.",
            "If the standup only produced placeholder planning work, replace it with a sharper execution lane instead of adding another summary card.",
            "Write back which starved standups were converted and which still need explicit executive judgment.",
        ],
        acceptance_criteria=[
            "Every tracked standup has a qualifying downstream lane or an explicit executive blocker decision.",
            "The follow-up closes only after each tracked standup stops showing up as low-value or no-output.",
        ],
        artifacts_expected=[
            "updated PM lane links for each starved standup",
            "bounded executive review note describing any remaining blockers",
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
        "reason": STANDUP_STARVATION_FOLLOWUP_REASON,
        "queued_at": now.isoformat(),
        "last_transition_at": now.isoformat(),
        "source": "accountability_sweep",
    }
    payload = {
        "workspace_key": "shared_ops",
        "scope": "shared_ops",
        "source_agent": "accountability_sweep",
        "created_from_accountability_sweep": True,
        "accountability_followup_type": "standup_starvation",
        "latest_report_generated_at": now.isoformat(),
        "starved_standup_ids": [item.get("standup_id") for item in starved_standups],
        "starved_standups": starved_standups,
        "alert_summary": summary,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": execution,
    }

    existing = _find_open_followup(
        cards,
        title=STANDUP_STARVATION_FOLLOWUP_TITLE,
        source=STANDUP_STARVATION_FOLLOWUP_SOURCE,
    )
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
        return {
            "action": "updated",
            "card_id": card_id,
            "status": status,
            "title": STANDUP_STARVATION_FOLLOWUP_TITLE,
        }

    created = fetch_json(
        f"{api_url.rstrip('/')}/api/pm/cards",
        method="POST",
        payload={
            "title": STANDUP_STARVATION_FOLLOWUP_TITLE,
            "owner": "Jean-Claude",
            "status": "todo",
            "source": STANDUP_STARVATION_FOLLOWUP_SOURCE,
            "payload": payload,
        },
    )
    return {
        "action": "created",
        "card_id": created.get("id") if isinstance(created, dict) else None,
        "status": created.get("status") if isinstance(created, dict) else "todo",
        "title": STANDUP_STARVATION_FOLLOWUP_TITLE,
    }


def _resolve_standup_starvation_followup(
    api_url: str,
    cards: list[dict[str, Any]],
    *,
    now: datetime,
    fetch_json: Callable[..., Any],
) -> dict[str, Any] | None:
    existing = _find_open_followup(
        cards,
        title=STANDUP_STARVATION_FOLLOWUP_TITLE,
        source=STANDUP_STARVATION_FOLLOWUP_SOURCE,
    )
    if existing is None:
        return None
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
            "reason": "Tracked standups now have qualifying downstream output, so the starvation follow-up was closed automatically.",
            "last_transition_at": now.isoformat(),
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    payload["resolved_at"] = now.isoformat()
    payload["resolution_reason"] = "Tracked standups now have runnable execution, host-action, or owner-review coverage."
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
        "title": STANDUP_STARVATION_FOLLOWUP_TITLE,
    }


def build_report(
    api_url: str,
    ready_age_minutes: int,
    review_age_hours: int,
    sync_live: bool,
    *,
    standup_age_minutes: int = 120,
    fetch_json: Callable[..., Any] = _fetch_json,
    brain_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    brain_context = brain_context or build_brain_automation_context(signal_limit=5)
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *brain_signal_lines(brain_context, limit=3),
        *source_intelligence_lines(brain_context, limit=1),
    ]
    queue = fetch_json(f"{api_url.rstrip('/')}/api/pm/execution-queue?limit=200")
    rows = [item for item in queue if isinstance(item, dict)]
    cards = _load_cards(api_url, fetch_json)
    standups = _load_standups(api_url, fetch_json)
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

    starved_standups = _collect_starved_standups(
        standups,
        cards,
        rows,
        now=now,
        standup_age_minutes=standup_age_minutes,
    )
    workspace_starvation_remediation_cards: list[dict[str, Any]] = []
    workspace_starvation_duplicate_cleanup_cards: list[dict[str, Any]] = []
    if starved_standups and sync_live:
        workspace_starvation_remediation_cards = _upsert_workspace_starvation_remediation_cards(
            api_url,
            standups,
            cards,
            starved_standups,
            now=now,
            fetch_json=fetch_json,
        )
    if sync_live:
        workspace_starvation_duplicate_cleanup_cards = _collapse_workspace_starvation_remediation_duplicates(
            api_url,
            cards,
            now=now,
            fetch_json=fetch_json,
        )
    standup_starvation_followup_card: dict[str, Any] | None = None
    if starved_standups and sync_live:
        standup_starvation_followup_card = _upsert_standup_starvation_followup(
            api_url,
            cards,
            starved_standups,
            now=now,
            fetch_json=fetch_json,
        )
    elif sync_live:
        standup_starvation_followup_card = _resolve_standup_starvation_followup(
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
        "standup_age_minutes": standup_age_minutes,
        "ready_count": len(ready_candidates),
        "dispatched_count": len(dispatched),
        "stale_review_count": len(stale_review),
        "stale_running_count": len(stale_running),
        "rerouted_count": len(rerouted_cards),
        "starved_standup_count": len(starved_standups),
        "dispatched_cards": dispatched,
        "stale_review_cards": stale_review,
        "stale_running_cards": stale_running,
        "rerouted_cards": rerouted_cards,
        "starved_standups": starved_standups,
        "workspace_starvation_remediation_count": len(workspace_starvation_remediation_cards),
        "workspace_starvation_remediation_cards": workspace_starvation_remediation_cards,
        "workspace_starvation_duplicate_cleanup_count": len(workspace_starvation_duplicate_cleanup_cards),
        "workspace_starvation_duplicate_cleanup_cards": workspace_starvation_duplicate_cleanup_cards,
        "executive_followup_card": executive_followup_card,
        "standup_starvation_followup_card": standup_starvation_followup_card,
        "brain_context": brain_context,
        "brain_context_lines": brain_context_lines,
        "source_paths": list(
            dict.fromkeys(
                [
                    f"{api_url.rstrip('/')}/api/pm/execution-queue?limit=200",
                    f"{api_url.rstrip('/')}/api/pm/cards?limit=400",
                    f"{api_url.rstrip('/')}/api/standups/?limit={DEFAULT_STANDUP_LIMIT}",
                    *(brain_context.get("source_paths") or []),
                ]
            )
        ),
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
        f"- Standups without qualifying output: `{report.get('starved_standup_count', 0)}`",
        f"- Workspace remediation lanes forced: `{report.get('workspace_starvation_remediation_count', 0)}`",
        f"- Duplicate remediation lanes closed: `{report.get('workspace_starvation_duplicate_cleanup_count', 0)}`",
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
    lines.extend(["", "## Starved standups"])
    if not report.get("starved_standups"):
        lines.append("- None.")
    else:
        for item in report["starved_standups"]:
            summary = str(item.get("summary") or "").strip()
            suffix = f" — {summary}" if summary else ""
            lines.append(
                f"- `{item['standup_kind']}` / `{item['workspace_key']}` at `{item['created_at']}` is `{item['output_category']}`{suffix}"
            )
    lines.extend(["", "## Workspace remediation"])
    if not report.get("workspace_starvation_remediation_cards"):
        lines.append("- None.")
    else:
        for item in report["workspace_starvation_remediation_cards"]:
            lines.append(
                f"- `{item.get('workspace_key')}` / standup `{item.get('standup_id')}` -> "
                f"`{item.get('title')}` (`{item.get('action')}` / `{item.get('status')}`)"
            )
    lines.extend(["", "## Duplicate remediation cleanup"])
    if not report.get("workspace_starvation_duplicate_cleanup_cards"):
        lines.append("- None.")
    else:
        for item in report["workspace_starvation_duplicate_cleanup_cards"]:
            lines.append(
                f"- `{item.get('workspace_key')}` / `{item.get('title')}` -> "
                f"`{item.get('action')}` (`{item.get('status')}`), kept `{item.get('superseded_by_card_id')}` active"
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
    lines.extend(["", "## Standup starvation follow-up"])
    starvation_followup = report.get("standup_starvation_followup_card")
    if not isinstance(starvation_followup, dict):
        lines.append("- None.")
    else:
        lines.append(
            f"- `{starvation_followup.get('title', STANDUP_STARVATION_FOLLOWUP_TITLE)}` -> "
            f"`{starvation_followup.get('action', 'tracked')}` (`{starvation_followup.get('status', 'unknown')}`)"
        )
    lines.extend(["", "## Brain Context"])
    brain_context_lines = report.get("brain_context_lines") or ["No active Brain Signal or portfolio blocker changed this sweep."]
    for item in brain_context_lines:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--ready-age-minutes", type=int, default=90)
    parser.add_argument("--review-age-hours", type=int, default=24)
    parser.add_argument("--standup-age-minutes", type=int, default=120)
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
        standup_age_minutes=args.standup_age_minutes,
    )
    finished_at = _now()
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    if not args.dry_run:
        followup = report.get("executive_followup_card")
        starvation_followup = report.get("standup_starvation_followup_card")
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
                    action_required=bool(
                        report.get("rerouted_count")
                        or report.get("starved_standup_count")
                        or isinstance(followup, dict)
                        or isinstance(starvation_followup, dict)
                    ),
                    metadata={
                        "ready_count": report["ready_count"],
                        "dispatched_count": report["dispatched_count"],
                        "stale_review_count": report["stale_review_count"],
                        "stale_running_count": report["stale_running_count"],
                        "rerouted_count": report["rerouted_count"],
                        "starved_standup_count": report.get("starved_standup_count", 0),
                        "executive_followup_action": followup.get("action") if isinstance(followup, dict) else None,
                        "executive_followup_card_id": followup.get("card_id") if isinstance(followup, dict) else None,
                        "standup_starvation_followup_action": (
                            starvation_followup.get("action") if isinstance(starvation_followup, dict) else None
                        ),
                        "standup_starvation_followup_card_id": (
                            starvation_followup.get("card_id") if isinstance(starvation_followup, dict) else None
                        ),
                        "brain_context_source_paths": report.get("source_paths") or [],
                    },
                )
            ],
        )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
