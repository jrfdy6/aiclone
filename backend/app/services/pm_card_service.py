from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import (
    ExecutionQueueEntry,
    PMCard,
    PMCardActionRequest,
    PMCardActionResult,
    PMCardCreate,
    PMCardDispatchRequest,
    PMCardDispatchResult,
    PMCardUpdate,
)
from app.services.open_brain_db import get_pool
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.pm_review_hygiene_audit_service import list_review_hygiene_audit, record_review_hygiene_audit
from app.services.trigger_identity_service import build_pm_trigger_key
from app.services.workspace_runtime_contract_service import (
    execution_defaults_for_workspace as runtime_execution_defaults_for_workspace,
    pm_review_policy_for_workspace as runtime_pm_review_policy_for_workspace,
)

AUTO_RESOLVE_REQUESTED_BY = "PM Auto Resolve Policy"
AUTO_PROGRESS_REQUESTED_BY = "Codex PM Review Worker"
AUTO_CONTRACT_RETRY_LIMIT = 2
HOST_ACTION_PREFIX = re.compile(r"^\s*(?:[-*]\s*)?(?:\d+\.\s*)?(?:host(?:\s+action)?)\s*:\s*(.+?)\s*$", re.IGNORECASE)
HOST_ACTION_DELAYED_PATTERNS = (
    re.compile(r"\bwithin\s+\d+\s*(?:hours?|hrs?|h)\b", re.IGNORECASE),
    re.compile(r"\bfirst[-\s]24h\b", re.IGNORECASE),
    re.compile(r"\bfirst[-\s]24[-\s]hour\b", re.IGNORECASE),
    re.compile(r"\bafter\s+publish\b", re.IGNORECASE),
    re.compile(r"\bonce\s+the\s+post\s+(?:is\s+)?live\b", re.IGNORECASE),
    re.compile(r"\bafter\s+slot\s*0\b", re.IGNORECASE),
    re.compile(r"\bafter\s+the\s+real\s+slot\s*0\b", re.IGNORECASE),
)
HOST_ACTION_PUBLISH_PATTERNS = (
    re.compile(r"\bpublish\b", re.IGNORECASE),
    re.compile(r"\bafter\s+publish\b", re.IGNORECASE),
    re.compile(r"\bpublished?\b", re.IGNORECASE),
    re.compile(r"\bpost\s+(?:is\s+)?live\b", re.IGNORECASE),
    re.compile(r"\bgo[-\s]?live\b", re.IGNORECASE),
)
HOST_ACTION_SCHEDULE_PATTERNS = (
    re.compile(r"\bschedule(?:d|r|ing)?\b", re.IGNORECASE),
    re.compile(r"\bnative\s+scheduler\b", re.IGNORECASE),
    re.compile(r"\bslot\s*0\b", re.IGNORECASE),
)
HOST_ACTION_TIMESTAMP_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*(?:ET|EST|EDT|UTC)?\b", re.IGNORECASE),
)
NEW_YORK_TZ = ZoneInfo("America/New_York")


def list_cards(
    limit: int = 100,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    workspace_key: Optional[str] = None,
) -> List[PMCard]:
    pool = get_pool()
    clauses = []
    params = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if workspace_key:
        clauses.append(
            "COALESCE(payload->>'workspace_key', payload->>'workspace', payload->>'belongs_to_workspace', 'shared_ops') = %s"
        )
        params.append(workspace_key)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    query = f"""
        SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
        FROM pm_cards
        {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_card(row) for row in rows]


def create_card(payload: PMCardCreate) -> PMCard:
    normalized_payload = _normalize_card_create_payload(payload)
    trigger_key = _payload_value(normalized_payload.payload, "trigger_key")
    if trigger_key:
        existing = find_active_card_by_trigger_key(trigger_key)
        if existing is not None:
            existing_payload = dict(existing.payload or {})
            existing_payload["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
            existing_payload["trigger_replays"] = int(existing_payload.get("trigger_replays") or 0) + 1
            existing_payload["latest_trigger_origin"] = _payload_value(normalized_payload.payload, "trigger_origin")
            updated = update_card(existing.id, PMCardUpdate(payload=existing_payload))
            return updated or existing

    pool = get_pool()
    card_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pm_cards (id, title, owner, status, source, link_type, link_id, due_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    card_id,
                    normalized_payload.title,
                    normalized_payload.owner,
                    normalized_payload.status or "todo",
                    normalized_payload.source,
                    normalized_payload.link_type,
                    normalized_payload.link_id,
                    normalized_payload.due_at,
                    Json(normalized_payload.payload or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_card(row)


def update_card(card_id: str, payload: PMCardUpdate) -> Optional[PMCard]:
    pool = get_pool()
    fields = []
    values = []
    if payload.title is not None:
        fields.append("title = %s")
        values.append(payload.title)
    if payload.owner is not None:
        fields.append("owner = %s")
        values.append(payload.owner)
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
    if payload.source is not None:
        fields.append("source = %s")
        values.append(payload.source)
    if payload.link_type is not None:
        fields.append("link_type = %s")
        values.append(payload.link_type)
    if payload.link_id is not None:
        fields.append("link_id = %s")
        values.append(payload.link_id)
    if payload.due_at is not None:
        fields.append("due_at = %s")
        values.append(payload.due_at)
    if payload.payload is not None:
        fields.append("payload = %s")
        values.append(Json(payload.payload))

    if not fields:
        return get_card(card_id)

    fields.append("updated_at = NOW()")
    values.append(card_id)

    query = f"""
        UPDATE pm_cards
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_card(row) if row else None


def get_card(card_id: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                """,
                (card_id,),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def _row_to_card(row: dict) -> PMCard:
    if not row:
        raise ValueError("PM card row is empty")
    return PMCard(
        id=str(row["id"]),
        title=row.get("title") or "Untitled",
        owner=row.get("owner"),
        status=row.get("status") or "todo",
        source=row.get("source"),
        link_type=row.get("link_type"),
        link_id=str(row.get("link_id")) if row.get("link_id") else None,
        due_at=row.get("due_at"),
        payload=row.get("payload") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def find_card_by_signature(title: str, source: Optional[str]) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if source is None:
                cur.execute(
                    """
                    SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                    FROM pm_cards
                    WHERE title = %s AND source IS NULL
                    LIMIT 1
                    """,
                    (title,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                    FROM pm_cards
                    WHERE title = %s AND source = %s
                    LIMIT 1
                    """,
                    (title, source),
                )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def find_active_card_by_title(title: str, workspace_key: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE title = %s
                  AND COALESCE(payload->>'workspace_key', payload->>'workspace', payload->>'belongs_to_workspace', 'shared_ops') = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (title, workspace_key),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def find_active_card_by_trigger_key(trigger_key: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE payload->>'trigger_key' = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (trigger_key,),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def list_execution_queue(
    limit: int = 100,
    target_agent: Optional[str] = None,
    manager_agent: Optional[str] = None,
    workspace_key: Optional[str] = None,
    execution_state: Optional[str] = None,
) -> List[ExecutionQueueEntry]:
    repair_execution_contracts(limit=max(limit, 250), workspace_key=workspace_key)
    cards = list_cards(limit=limit, workspace_key=workspace_key)
    entries: List[ExecutionQueueEntry] = []
    for card in cards:
        entry = build_execution_queue_entry(card)
        if entry is None:
            continue
        if manager_agent and entry.manager_agent.lower() != manager_agent.lower():
            continue
        if target_agent and entry.target_agent.lower() != target_agent.lower():
            continue
        if execution_state and entry.execution_state.lower() != execution_state.lower():
            continue
        entries.append(entry)
    entries.sort(
        key=lambda entry: (
            _execution_sort_rank(entry.execution_state),
            entry.last_transition_at or entry.queued_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return entries[:limit]


def dispatch_card(card_id: str, payload: PMCardDispatchRequest) -> Optional[PMCardDispatchResult]:
    card = get_card(card_id)
    if card is None:
        return None
    if _is_host_action_required_card(card):
        raise ValueError("Host-action cards cannot be dispatched into execution. Confirm, return, or block the host step instead.")

    now = datetime.now(timezone.utc)
    card_payload = dict(card.payload or {})
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    current_execution = dict(_execution_payload(card) or {})
    if not current_execution:
        current_execution.update(defaults)
    else:
        current_execution = _merge_execution_defaults(current_execution, defaults)
    requested_by = payload.requested_by or current_execution.get("requested_by") or card.owner or defaults["manager_agent"]
    effective_target_agent = payload.target_agent or current_execution.get("target_agent") or defaults["target_agent"]
    history = list(current_execution.get("history") or [])
    history.append(
        {
            "event": "dispatch",
            "state": payload.execution_state,
            "target_agent": effective_target_agent,
            "requested_by": requested_by,
            "at": now.isoformat(),
        }
    )

    current_execution.update(
        {
            "lane": payload.lane or current_execution.get("lane") or "codex",
            "state": payload.execution_state or current_execution.get("state") or "queued",
            "manager_agent": current_execution.get("manager_agent") or defaults["manager_agent"],
            "target_agent": effective_target_agent,
            "workspace_agent": current_execution.get("workspace_agent") or defaults.get("workspace_agent"),
            "execution_mode": current_execution.get("execution_mode") or defaults["execution_mode"],
            "requested_by": requested_by,
            "assigned_runner": current_execution.get("assigned_runner") or "codex",
            "reason": current_execution.get("reason")
            or _payload_value(card_payload, "reason")
            or "Queued from PM board for Codex execution.",
            "queued_at": current_execution.get("queued_at") or now.isoformat(),
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
    card_payload["execution"] = current_execution

    updated = update_card(card_id, PMCardUpdate(payload=card_payload))
    if updated is None:
        return None
    return PMCardDispatchResult(card=updated, queue_entry=build_execution_queue_entry(updated) or _fallback_execution_entry(updated))


def act_on_card(card_id: str, payload: PMCardActionRequest) -> Optional[PMCardActionResult]:
    card = get_card(card_id)
    if card is None:
        return None
    return _apply_card_action(
        card,
        action=payload.action,
        requested_by=payload.requested_by,
        reason=payload.reason,
        resolution_mode=payload.resolution_mode,
        next_title=payload.next_title,
        next_reason=payload.next_reason,
        proof_items=payload.proof_items,
    )


def _apply_card_action(
    card: PMCard,
    *,
    action: str,
    requested_by: str,
    reason: str | None = None,
    resolution_mode: str | None = None,
    next_title: str | None = None,
    next_reason: str | None = None,
    proof_items: list[str] | None = None,
    review_metadata: dict[str, Any] | None = None,
) -> Optional[PMCardActionResult]:
    host_action_completion: dict[str, Any] | None = None
    host_action_followup: dict[str, Any] | None = None
    host_action_followup_gate: dict[str, Any] | None = None
    if action == "approve" and _is_host_action_required_card(card):
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        host_action_completion = _build_host_action_completion_payload(
            card,
            requested_by=requested_by,
            completion_note=reason,
            proof_items=proof_items,
        )
        if isinstance(host_action_followup, dict):
            host_action_followup_gate = _evaluate_host_action_followup_readiness(host_action_followup, host_action_completion)
    status, card_payload = build_card_action_update(
        card,
        action=action,
        requested_by=requested_by,
        reason=reason,
        resolution_mode=resolution_mode,
        next_title=next_title,
        next_reason=next_reason,
    )
    if host_action_completion is not None:
        card_payload["host_action_completion"] = host_action_completion
    if host_action_followup_gate is not None and not bool(host_action_followup_gate.get("ready")):
        card_payload["host_action_followup_pending"] = host_action_followup_gate
    updated = update_card(card.id, PMCardUpdate(status=status, payload=card_payload))
    if updated is None:
        return None

    successor_card: PMCard | None = None
    if action == "approve" and resolution_mode == "close_and_spawn_next":
        successor_card = _create_resolution_successor_card(
            card,
            requested_by=requested_by,
            next_title=next_title,
            next_reason=next_reason,
        )
        updated_payload = dict(updated.payload or {})
        latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
        latest_manual_review["successor_card_id"] = successor_card.id
        latest_manual_review["successor_card_title"] = successor_card.title
        updated_payload["latest_manual_review"] = latest_manual_review
        updated_payload["resolution_successor"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        refreshed = update_card(card.id, PMCardUpdate(status=updated.status, payload=updated_payload))
        if refreshed is not None:
            updated = refreshed

    if (
        action == "approve"
        and host_action_completion is not None
        and isinstance(host_action_followup, dict)
        and bool((host_action_followup_gate or {}).get("ready"))
    ):
        successor_card = _create_host_action_required_card(
            updated,
            requested_by=requested_by,
            host_action_required=host_action_followup,
            due_at=host_action_followup_gate.get("due_at") if isinstance(host_action_followup_gate, dict) else None,
        )
        updated_payload = dict(updated.payload or {})
        host_completion = dict(updated_payload.get("host_action_completion") or host_action_completion)
        host_completion["follow_up_card_id"] = successor_card.id
        host_completion["follow_up_card_title"] = successor_card.title
        updated_payload["host_action_completion"] = host_completion
        updated_payload["host_action_followup_spawned"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        updated_payload.pop("host_action_followup_pending", None)
        refreshed = update_card(card.id, PMCardUpdate(status=updated.status, payload=updated_payload))
        if refreshed is not None:
            updated = refreshed

    if review_metadata:
        updated_payload = dict(updated.payload or {})
        latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
        latest_manual_review.update(review_metadata)
        updated_payload["latest_manual_review"] = latest_manual_review
        refreshed = update_card(card.id, PMCardUpdate(status=updated.status, payload=updated_payload))
        if refreshed is not None:
            updated = refreshed

    return PMCardActionResult(card=updated, queue_entry=build_execution_queue_entry(updated), successor_card=successor_card)


def _create_resolution_successor_card(
    card: PMCard,
    *,
    requested_by: str,
    next_title: str | None,
    next_reason: str | None,
) -> PMCard:
    cleaned_title = str(next_title or "").strip()
    if not cleaned_title:
        raise ValueError("A next card title is required when resolving with a spawned follow-up.")

    source_payload = dict(card.payload or {})
    workspace_key = _workspace_key_from_card(card)
    successor_reason = str(next_reason or "").strip() or f"Follow-on work spawned from resolving '{card.title}'."
    execution_defaults = execution_defaults_for_workspace(workspace_key)
    contract = build_execution_contract(
        title=cleaned_title,
        workspace_key=workspace_key,
        source="pm_review_resolution",
        reason=successor_reason,
        instructions=[
            f"Continue the PM loop after resolving `{card.title}`.",
            "Use the predecessor PM card and latest execution result as the source of truth for this next lane.",
            "Write back a bounded result with outcomes, blockers, and follow-up actions.",
        ],
        acceptance_criteria=[
            f"`{cleaned_title}` advances to a concrete next state instead of remaining a placeholder.",
            "PM write-back includes a bounded summary and at least one concrete outcome or artifact.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "bounded workspace artifact or execution memo when the next lane produces one",
        ],
    )
    successor_payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "reason": successor_reason,
        "source_agent": requested_by,
        "front_door_agent": requested_by,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": {
            "lane": "codex",
            "state": "queued",
            "manager_agent": execution_defaults["manager_agent"],
            "target_agent": execution_defaults["target_agent"],
            "workspace_agent": execution_defaults.get("workspace_agent"),
            "execution_mode": execution_defaults["execution_mode"],
            "requested_by": requested_by,
            "assigned_runner": "jean-claude" if str(execution_defaults["execution_mode"]) == "direct" else "codex",
            "reason": successor_reason,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "last_transition_at": datetime.now(timezone.utc).isoformat(),
            "source": "pm_review_resolution",
        },
        "resolution_predecessor": {
            "card_id": card.id,
            "title": card.title,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    for key in [
        "created_from_standup_id",
        "created_from_standup_kind",
        "created_from_standup_workspace",
        "created_from_prep_id",
        "recommendation_path",
    ]:
        value = source_payload.get(key)
        if value is not None:
            successor_payload[key] = value

    successor_payload["trigger_key"] = _build_trigger_key(
        title=cleaned_title,
        workspace_key=workspace_key,
        source="pm_review_resolution",
        payload=successor_payload,
    )
    existing = find_active_card_by_trigger_key(str(successor_payload["trigger_key"]))
    if existing is not None:
        return existing

    return create_card(
        PMCardCreate(
            title=cleaned_title,
            owner=card.owner or execution_defaults["manager_agent"],
            status="todo",
            source="pm_review_resolution",
            link_type=card.link_type,
            link_id=card.link_id,
            payload=successor_payload,
        )
    )


def build_card_action_update(
    card: PMCard,
    *,
    action: str,
    requested_by: str = "Neo",
    reason: str | None = None,
    resolution_mode: str | None = None,
    next_title: str | None = None,
    next_reason: str | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = dict(card.payload or {})
    current_execution = dict(_execution_payload(card) or {})
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    queue_entry = build_execution_queue_entry(card)
    now = datetime.now(timezone.utc).isoformat()
    history = list(current_execution.get("history") or [])
    cleaned_resolution_mode = str(resolution_mode or "").strip() or None
    cleaned_next_title = str(next_title or "").strip()
    cleaned_next_reason = str(next_reason or "").strip()

    next_status = card.status or "review"
    next_state = str(current_execution.get("state") or (queue_entry.execution_state if queue_entry else "review"))
    next_target = str(current_execution.get("target_agent") or (queue_entry.target_agent if queue_entry else defaults["target_agent"]))
    next_assigned_runner = str(current_execution.get("assigned_runner") or (queue_entry.assigned_runner if queue_entry else "codex"))
    next_execution_mode = str(current_execution.get("execution_mode") or (queue_entry.execution_mode if queue_entry else defaults["execution_mode"]))
    manager_attention_required = bool(current_execution.get("manager_attention_required"))
    effective_reason = str(
        reason
        or current_execution.get("reason")
        or (queue_entry.reason if queue_entry else "")
        or _payload_value(payload, "reason")
        or ""
    ).strip()

    if action == "approve":
        if cleaned_resolution_mode not in {"close_only", "close_and_spawn_next"}:
            raise ValueError("Resolve requires an explicit next-step mode.")
        if cleaned_resolution_mode == "close_and_spawn_next" and not cleaned_next_title:
            raise ValueError("A next card title is required when resolving with a spawned follow-up.")
        next_status = "done"
        next_state = "done"
        manager_attention_required = False
    elif action == "return":
        next_status = "todo"
        next_state = "queued"
        next_target = "Jean-Claude"
        next_assigned_runner = "jean-claude"
        next_execution_mode = "direct"
        manager_attention_required = False
        if not effective_reason:
            effective_reason = "Returned to Jean-Claude for another pass."
    elif action == "blocked":
        next_status = "blocked"
        next_state = "queued"
        next_target = "Jean-Claude"
        next_assigned_runner = "jean-claude"
        next_execution_mode = "direct"
        manager_attention_required = True
        if not effective_reason:
            effective_reason = "Marked blocked during manual review. Jean-Claude needs a closure decision."
    else:
        raise ValueError(f"Unsupported PM card action: {action}")

    history.append(
        {
            "event": (
                "manual_approve"
                if action == "approve"
                else "manual_return"
                if action == "return"
                else "manual_blocked"
            ),
            "state": next_state,
            "requested_by": requested_by,
            "at": now,
        }
    )

    payload["execution"] = {
        **defaults,
        **current_execution,
        "lane": str(current_execution.get("lane") or (queue_entry.lane if queue_entry else "codex")),
        "state": next_state,
        "manager_agent": str(current_execution.get("manager_agent") or (queue_entry.manager_agent if queue_entry else defaults["manager_agent"])),
        "target_agent": next_target,
        "workspace_agent": current_execution.get("workspace_agent") or (queue_entry.workspace_agent if queue_entry else defaults.get("workspace_agent")),
        "execution_mode": next_execution_mode,
        "requested_by": requested_by,
        "assigned_runner": next_assigned_runner,
        "queued_at": current_execution.get("queued_at") if action == "approve" else now,
        "last_transition_at": now,
        "manager_attention_required": manager_attention_required,
        "execution_packet_path": None if action in {"return", "blocked"} else current_execution.get("execution_packet_path"),
        "executor_status": None if action in {"return", "blocked"} else current_execution.get("executor_status"),
        "executor_worker_id": None if action in {"return", "blocked"} else current_execution.get("executor_worker_id"),
        "executor_started_at": None if action in {"return", "blocked"} else current_execution.get("executor_started_at"),
        "executor_finished_at": None if action in {"return", "blocked"} else current_execution.get("executor_finished_at"),
        "executor_last_error": None if action in {"return", "blocked"} else current_execution.get("executor_last_error"),
        "returned_from_agent": (
            str(current_execution.get("target_agent") or (queue_entry.target_agent if queue_entry else ""))
            if action == "blocked"
            else current_execution.get("returned_from_agent")
        ),
        "reason": effective_reason,
        "history": history[-12:],
    }

    latest_execution_result = payload.get("latest_execution_result")
    if isinstance(latest_execution_result, dict):
        updated_result = dict(latest_execution_result)
        updated_result["review_resolution"] = action
        updated_result["reviewed_at"] = now
        payload["latest_execution_result"] = updated_result

    payload["latest_manual_review"] = {
        "action": action,
        "reviewed_at": now,
        "reviewed_by": requested_by,
        "from_lane": queue_entry.execution_state if queue_entry else (card.status or "todo"),
        "resolution_mode": cleaned_resolution_mode,
        "next_title": cleaned_next_title or None,
        "next_reason": cleaned_next_reason or None,
    }

    return next_status, payload


def auto_resolve_review_cards(limit: int = 250) -> dict[str, Any]:
    cards = list_cards(limit=limit)
    resolved: list[dict[str, Any]] = []

    for card in cards:
        policy = _auto_resolve_review_policy(card)
        if policy is None:
            continue
        result = _apply_card_action(
            card,
            action="approve",
            requested_by=AUTO_RESOLVE_REQUESTED_BY,
            reason=policy["reason"],
            resolution_mode="close_only",
            review_metadata={
                "auto_resolved": True,
                "policy_rule": policy["rule"],
                "worker_action": "close_only",
            },
        )
        if result is None:
            continue
        updated = result.card
        resolved.append(
            {
                "card_id": updated.id,
                "title": updated.title,
                "workspace_key": _workspace_key_from_card(updated),
                "rule": policy["rule"],
                "reason": policy["reason"],
            }
        )

    return {
        "resolved_count": len(resolved),
        "resolved": resolved,
    }


def auto_progress_review_cards(limit: int = 250) -> dict[str, Any]:
    repair_result = repair_execution_contracts(limit=limit)
    cards = list_cards(limit=limit)
    processed: list[dict[str, Any]] = []

    for card in cards:
        stale_policy = _auto_resolve_review_policy(card)
        if stale_policy is not None:
            result = _apply_card_action(
                card,
                action="approve",
                requested_by=AUTO_PROGRESS_REQUESTED_BY,
                reason=stale_policy["reason"],
                resolution_mode="close_only",
                review_metadata={
                    "auto_resolved": True,
                    "auto_progressed": True,
                    "policy_rule": stale_policy["rule"],
                    "worker_action": "close_only",
                    "worker_id": AUTO_PROGRESS_REQUESTED_BY,
                },
            )
            if result is None:
                continue
            processed.append(
                {
                    "card_id": result.card.id,
                    "title": result.card.title,
                    "workspace_key": _workspace_key_from_card(result.card),
                    "resolution_mode": "close_only",
                    "rule": stale_policy["rule"],
                    "reason": stale_policy["reason"],
                }
            )
            continue

        progression = _autonomous_review_progression(card)
        if progression is None:
            continue
        action = str(progression.get("action") or "approve")
        review_metadata = {
            "auto_progressed": True,
            "policy_rule": progression["rule"],
            "worker_action": progression.get("worker_action") or progression.get("resolution_mode") or action,
            "worker_id": AUTO_PROGRESS_REQUESTED_BY,
        }
        contract_assessment = progression.get("contract_assessment")
        if isinstance(contract_assessment, dict):
            review_metadata["contract_assessment"] = contract_assessment
        if progression.get("contract_auto_return_count") is not None:
            review_metadata["contract_auto_return_count"] = progression.get("contract_auto_return_count")
        result = _apply_card_action(
            card,
            action=action,
            requested_by=AUTO_PROGRESS_REQUESTED_BY,
            reason=progression["reason"],
            resolution_mode=progression.get("resolution_mode"),
            next_title=progression.get("next_title"),
            next_reason=progression.get("next_reason"),
            proof_items=None,
            review_metadata=review_metadata,
        )
        if result is None:
            continue
        host_action_card: PMCard | None = None
        host_action_required = progression.get("host_action_required")
        if action == "approve" and isinstance(host_action_required, dict):
            host_action_card = _create_host_action_required_card(
                result.card,
                requested_by=AUTO_PROGRESS_REQUESTED_BY,
                host_action_required=host_action_required,
            )
            if host_action_card is not None:
                updated_payload = dict(result.card.payload or {})
                latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
                latest_manual_review["host_action_card_id"] = host_action_card.id
                latest_manual_review["host_action_card_title"] = host_action_card.title
                updated_payload["latest_manual_review"] = latest_manual_review
                updated_payload["host_action_successor"] = {
                    "card_id": host_action_card.id,
                    "title": host_action_card.title,
                    "created_at": _datetime_to_iso(host_action_card.created_at),
                    "workspace_key": _workspace_key_from_card(host_action_card),
                }
                refreshed = update_card(result.card.id, PMCardUpdate(status=result.card.status, payload=updated_payload))
                if refreshed is not None:
                    result = PMCardActionResult(
                        card=refreshed,
                        queue_entry=build_execution_queue_entry(refreshed),
                        successor_card=result.successor_card,
                    )
        processed.append(
            {
                "card_id": result.card.id,
                "title": result.card.title,
                "workspace_key": _workspace_key_from_card(result.card),
                "action": action,
                "resolution_mode": progression.get("resolution_mode"),
                "rule": progression["rule"],
                "reason": progression["reason"],
                "successor_card_id": result.successor_card.id if result.successor_card else None,
                "successor_card_title": result.successor_card.title if result.successor_card else None,
                "host_action_card_id": host_action_card.id if host_action_card else None,
                "host_action_card_title": host_action_card.title if host_action_card else None,
            }
        )

    result = {
        "repair_count": int(repair_result.get("repaired_count") or 0),
        "repaired": repair_result.get("repaired") or [],
        "processed_count": len(processed),
        "advanced_count": sum(1 for item in processed if item.get("action") == "approve"),
        "returned_count": sum(1 for item in processed if item.get("action") == "return"),
        "escalated_count": sum(1 for item in processed if item.get("action") == "blocked"),
        "closed_count": sum(1 for item in processed if item.get("resolution_mode") == "close_only"),
        "continued_count": sum(1 for item in processed if item.get("resolution_mode") == "close_and_spawn_next"),
        "processed": processed,
    }
    audit_entry = record_review_hygiene_audit(result)
    if audit_entry is not None:
        result["audit_entry"] = audit_entry
    return result


def review_hygiene_audit(limit: int = 12, hours: int = 24) -> dict[str, Any]:
    return list_review_hygiene_audit(limit=limit, hours=hours)


def decorate_card_for_client(card: PMCard | None) -> PMCard | None:
    if card is None:
        return None
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    normalized_status = card.status
    if isinstance(host_action_required, dict):
        phases = _split_host_action_timeline(host_action_required)
        current_phase = phases.get("current")
        follow_up_phase = _normalize_host_action_payload(payload.get("host_action_followup")) or phases.get("follow_up")
        if current_phase is not None:
            proof_required = _dedupe_nonempty_strings(current_phase.get("proof_required"))
            payload["host_action_required"] = {
                **host_action_required,
                **current_phase,
                "proof_fields": _build_host_action_proof_fields(proof_required),
            }
        if follow_up_phase is not None:
            payload["host_action_followup"] = {
                **follow_up_phase,
                "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
            }
        activation = _host_action_activation_status(card)
        if activation is not None:
            payload["host_action_activation"] = activation
        execution = dict(payload.get("execution") or {}) if isinstance(payload.get("execution"), dict) else {}
        if not _is_closed_pm_status(card.status):
            if str(card.status or "").strip().lower() in {"queued", "running", "in_progress", "review", "failed"}:
                normalized_status = "todo"
            payload["execution"] = {
                **execution,
                "state": "host_step_only",
                "manager_attention_required": False,
                "executor_status": None,
                "executor_worker_id": None,
                "executor_last_error": None,
                "execution_packet_path": None,
                "sop_path": None,
                "briefing_path": None,
            }
    payload["pm_review_policy"] = _build_client_review_policy(card)
    return card.model_copy(update={"status": normalized_status, "payload": payload})


def decorate_cards_for_client(cards: List[PMCard]) -> List[PMCard]:
    return [decorate_card_for_client(card) or card for card in cards]


def build_execution_queue_entry(card: PMCard) -> Optional[ExecutionQueueEntry]:
    if _is_closed_pm_status(card.status):
        return None
    if _is_host_action_required_card(card):
        return None
    payload = dict(card.payload or {})
    execution = _execution_payload(card)
    if not execution and not _is_execution_candidate(card):
        return None

    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    effective_execution = dict(execution or {})
    if not effective_execution:
        default_state = _default_execution_state_for_card(card)
        effective_execution = {
            **defaults,
            "lane": "codex",
            "state": default_state,
            "requested_by": _payload_value(payload, "source_agent") or card.owner or defaults["manager_agent"],
            "assigned_runner": "jean-claude" if str(defaults["execution_mode"]) == "direct" else "codex",
            "reason": _payload_value(payload, "reason")
            or (
                "Standup promoted this card and it is ready for Jean-Claude to open a direct SOP."
                if defaults["execution_mode"] == "direct"
                else "Standup promoted this card and it is ready for Jean-Claude to open a delegated SOP for the workspace agent."
            ),
            "last_transition_at": _datetime_to_iso(card.updated_at),
        }
        if default_state == "queued":
            effective_execution["queued_at"] = _datetime_to_iso(card.updated_at)
    else:
        effective_execution = _merge_execution_defaults(effective_execution, defaults)

    latest_execution_result = payload.get("latest_execution_result")
    latest_result = latest_execution_result if isinstance(latest_execution_result, dict) else {}
    latest_result_artifacts = latest_result.get("artifacts")
    artifact_items = (
        [str(item).strip() for item in latest_result_artifacts if isinstance(item, str) and str(item).strip()]
        if isinstance(latest_result_artifacts, list)
        else []
    )

    return ExecutionQueueEntry(
        card_id=card.id,
        title=card.title,
        workspace_key=_workspace_key_from_card(card),
        pm_status=card.status or "todo",
        execution_state=str(effective_execution.get("state") or "ready"),
        manager_agent=str(effective_execution.get("manager_agent") or defaults["manager_agent"]),
        target_agent=str(effective_execution.get("target_agent") or defaults["target_agent"]),
        workspace_agent=_optional_str(effective_execution.get("workspace_agent")),
        execution_mode=str(effective_execution.get("execution_mode") or defaults["execution_mode"]),
        requested_by=_optional_str(effective_execution.get("requested_by")),
        assigned_runner=_optional_str(effective_execution.get("assigned_runner")),
        lane=str(effective_execution.get("lane") or "codex"),
        reason=_optional_str(effective_execution.get("reason")),
        source=card.source,
        link_type=card.link_type,
        front_door_agent=_optional_str(payload.get("front_door_agent")),
        trigger_key=_optional_str(payload.get("trigger_key")),
        manager_attention_required=bool(effective_execution.get("manager_attention_required")),
        executor_status=_optional_str(effective_execution.get("executor_status")),
        executor_worker_id=_optional_str(effective_execution.get("executor_worker_id")),
        execution_packet_path=(
            _optional_str(effective_execution.get("execution_packet_path"))
            or _optional_str(effective_execution.get("workspace_agent_packet_path"))
        ),
        sop_path=_optional_str(effective_execution.get("sop_path")),
        briefing_path=(
            _optional_str(effective_execution.get("briefing_path"))
            or _optional_str(effective_execution.get("workspace_agent_briefing_path"))
        ),
        latest_result_status=_optional_str(latest_result.get("status")),
        latest_result_summary=_optional_str(latest_result.get("summary")),
        latest_result_artifacts=artifact_items,
        queued_at=_parse_datetime(effective_execution.get("queued_at")),
        last_transition_at=_parse_datetime(effective_execution.get("last_transition_at")) or card.updated_at,
    )


def _auto_resolve_review_policy(card: PMCard) -> dict[str, str] | None:
    if _is_closed_pm_status(card.status):
        return None
    if str(card.status or "").strip().lower() != "review":
        return None

    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    if not bool(workspace_policy.get("auto_resolve_review_residue")):
        return None

    payload = dict(card.payload or {})
    execution = _execution_payload(card) or {}
    if bool(execution.get("manager_attention_required")):
        return None
    if _is_owner_decision_gate(card):
        return None

    reason_text = str(
        execution.get("reason")
        or _payload_value(payload, "reason")
        or ""
    ).strip().lower()

    if "accountability sweep rerouted this stale" in reason_text:
        return {
            "rule": "accountability_stale_review_autoclose",
            "reason": "Auto-closed stale accountability-sweep review residue that did not require an owner decision.",
        }

    review_reference = (
        _parse_datetime(execution.get("last_transition_at"))
        or _parse_datetime(execution.get("queued_at"))
        or card.updated_at
        or card.created_at
    )
    age_hours = 0.0
    if review_reference is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - review_reference.astimezone(timezone.utc)).total_seconds() / 3600)
    if age_hours >= 168:
        return {
            "rule": "aged_review_autoclose",
            "reason": "Auto-closed an old review card in a self-managed workspace because no explicit owner gate was present.",
        }

    return None


def _autonomous_review_progression(card: PMCard) -> dict[str, Any] | None:
    if _is_closed_pm_status(card.status):
        return None
    if str(card.status or "").strip().lower() != "review":
        return None

    execution = _execution_payload(card) or {}
    if bool(execution.get("manager_attention_required")):
        return None
    if _is_owner_decision_gate(card):
        return None

    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    interrupt_policy = str(workspace_policy.get("interrupt_policy") or "manual_review")
    if interrupt_policy not in {"owner_gate_only", "manager_attention_only"}:
        return None

    contract_assessment = _completion_contract_assessment(card)
    if contract_assessment is not None and not bool(contract_assessment.get("satisfied")):
        retry_limit = int(contract_assessment.get("auto_return_limit") or AUTO_CONTRACT_RETRY_LIMIT)
        current_retry_count = _completion_contract_auto_retry_count(card)
        assessment_summary = _contract_assessment_summary(contract_assessment)
        if current_retry_count >= retry_limit:
            return {
                "action": "blocked",
                "rule": "completion_contract_escalation_after_retries",
                "reason": (
                    "Codex review worker could not satisfy the PM completion contract after repeated automatic passes. "
                    + assessment_summary
                ),
                "worker_action": "escalate_for_attention",
                "contract_assessment": contract_assessment,
            }
        return {
            "action": "return",
            "rule": "completion_contract_return_for_rework",
            "reason": (
                "Codex review worker returned this card to execution because the PM completion contract was not met yet. "
                + assessment_summary
            ),
            "worker_action": "return_to_execution",
            "contract_assessment": contract_assessment,
            "contract_auto_return_count": current_retry_count + 1,
        }

    host_action_required = _extract_host_action_required(card)
    if host_action_required is not None:
        return {
            "action": "approve",
            "rule": "completion_contract_host_action_required",
            "reason": "Codex review worker accepted the internal execution result and routed the remaining external step into a host action card.",
            "resolution_mode": "close_only",
            "contract_assessment": contract_assessment,
            "host_action_required": host_action_required,
        }

    auto_resolve_policy = _auto_resolve_review_policy(card)
    if auto_resolve_policy is not None:
        return {
            "action": "approve",
            "rule": str(auto_resolve_policy.get("rule") or "auto_resolve_review_residue"),
            "reason": str(auto_resolve_policy.get("reason") or "Automatically resolved routine review residue."),
            "resolution_mode": "close_only",
            "worker_action": "close_only",
            "contract_assessment": contract_assessment,
        }

    resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode")) or "close_only"
    next_title: str | None = None
    next_reason: str | None = None
    if resolution_mode == "close_and_spawn_next":
        suggestion = _suggest_review_followup(card, workspace_policy)
        if suggestion is None or not str(suggestion.get("title") or "").strip():
            return None
        next_title = str(suggestion.get("title") or "").strip()
        next_reason = str(suggestion.get("reason") or "").strip() or None

    if resolution_mode == "close_and_spawn_next":
        return {
            "action": "approve",
            "rule": "workspace_policy_accept_and_continue",
            "reason": "Codex review worker accepted this routine review result and opened the next PM lane under the workspace review policy.",
            "resolution_mode": resolution_mode,
            "next_title": next_title or "",
            "next_reason": next_reason or "",
            "contract_assessment": contract_assessment,
        }

    return {
        "action": "approve",
        "rule": "workspace_policy_accept_and_close",
        "reason": "Codex review worker accepted this routine review result and closed the lane under the workspace review policy.",
        "resolution_mode": resolution_mode,
        "contract_assessment": contract_assessment,
    }


def _completion_contract_assessment(card: PMCard) -> dict[str, Any] | None:
    payload = dict(card.payload or {})
    contract = payload.get("completion_contract")
    if not isinstance(contract, dict) or not contract:
        return None

    latest_result = payload.get("latest_execution_result")
    done_when = [
        str(item).strip()
        for item in contract.get("done_when") or []
        if str(item).strip()
    ]
    requirements = dict(contract.get("result_requirements") or {})
    summary_min_length = max(1, int(requirements.get("summary_min_length") or 20))
    require_outcome_or_artifact = bool(requirements.get("require_outcome_or_artifact", True))
    require_writeback = bool(requirements.get("require_writeback", True))
    allow_blockers = bool(requirements.get("allow_blockers", False))

    missing: list[str] = []
    summary = ""
    status = ""
    outcomes: list[str] = []
    artifacts: list[str] = []
    blockers: list[str] = []

    if not isinstance(latest_result, dict):
        if require_writeback:
            missing.append("No execution result has been written back yet.")
    else:
        summary = str(latest_result.get("summary") or "").strip()
        status = str(latest_result.get("status") or "").strip().lower()
        outcomes = [str(item).strip() for item in latest_result.get("outcomes") or [] if str(item).strip()]
        artifacts = [str(item).strip() for item in latest_result.get("artifacts") or [] if str(item).strip()]
        blockers = [str(item).strip() for item in latest_result.get("blockers") or [] if str(item).strip()]
        if len(summary) < summary_min_length:
            missing.append("Result summary is too thin to prove completion.")
        if require_outcome_or_artifact and not outcomes and not artifacts:
            missing.append("Result is missing a concrete outcome or artifact.")
        if not allow_blockers and blockers:
            missing.append("Result still contains unresolved blockers.")
        if status == "blocked":
            missing.append("Result reported a blocked status.")

    return {
        "active": True,
        "satisfied": not missing,
        "missing": missing,
        "done_when": done_when,
        "summary": summary,
        "status": status,
        "auto_return_limit": max(0, int(contract.get("auto_return_limit") or AUTO_CONTRACT_RETRY_LIMIT)),
    }


def _extract_host_action_required(card: PMCard) -> dict[str, Any] | None:
    payload = dict(card.payload or {})
    latest_result = payload.get("latest_execution_result")
    if not isinstance(latest_result, dict):
        return None

    steps: list[str] = []
    proof_required: list[str] = []
    detected_from = "follow_up_prefix"

    explicit_host_actions = latest_result.get("host_actions")
    if isinstance(explicit_host_actions, list):
        detected_from = "explicit_host_actions"
        for item in explicit_host_actions:
            if isinstance(item, dict):
                summary = _optional_str(item.get("summary"))
                if summary:
                    steps.append(summary)
                steps.extend(_normalize_string_list(item.get("steps")))
                proof_required.extend(_normalize_string_list(item.get("proof_required")))
            else:
                normalized = str(item).strip()
                if normalized:
                    steps.append(normalized)

    if not steps:
        for follow_up in _normalize_string_list(latest_result.get("follow_ups")):
            match = HOST_ACTION_PREFIX.match(follow_up)
            if match:
                normalized = str(match.group(1) or "").strip()
                if normalized:
                    steps.append(normalized)

    proof_required.extend(_normalize_string_list(latest_result.get("host_action_proof")))
    deduped_steps = _dedupe_nonempty_strings(steps)
    if not deduped_steps:
        return None

    return {
        "summary": deduped_steps[0],
        "steps": deduped_steps,
        "proof_required": _dedupe_nonempty_strings(proof_required),
        "source_result_id": _optional_str(latest_result.get("result_id")),
        "source_result_summary": _optional_str(latest_result.get("summary")),
        "detected_from": detected_from,
    }


def _is_delayed_host_action_text(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_DELAYED_PATTERNS)


def _normalize_host_action_payload(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    summary = _optional_str(value.get("summary"))
    steps = _dedupe_nonempty_strings(value.get("steps"))
    proof_required = _dedupe_nonempty_strings(value.get("proof_required"))
    normalized: dict[str, Any] = {
        "summary": summary or (steps[0] if steps else (proof_required[0] if proof_required else None)),
        "steps": steps,
        "proof_required": proof_required,
        "source_card_id": _optional_str(value.get("source_card_id")),
        "source_card_title": _optional_str(value.get("source_card_title")),
        "source_result_id": _optional_str(value.get("source_result_id")),
        "source_result_summary": _optional_str(value.get("source_result_summary")),
        "detected_from": _optional_str(value.get("detected_from")),
    }
    return normalized if normalized.get("summary") else None


def _split_host_action_timeline(host_action_required: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    current = _normalize_host_action_payload(host_action_required)
    if current is None:
        return {"current": None, "follow_up": None}

    existing_follow_up = _normalize_host_action_payload(host_action_required.get("follow_up_host_action"))
    if existing_follow_up is not None:
        return {"current": current, "follow_up": existing_follow_up}

    steps = _dedupe_nonempty_strings(current.get("steps"))
    proof_required = _dedupe_nonempty_strings(current.get("proof_required"))
    current_steps = [item for item in steps if not _is_delayed_host_action_text(item)]
    follow_up_steps = [item for item in steps if _is_delayed_host_action_text(item)]
    current_proof = [item for item in proof_required if not _is_delayed_host_action_text(item)]
    follow_up_proof = [item for item in proof_required if _is_delayed_host_action_text(item)]
    current_summary = _optional_str(current.get("summary"))

    if current_summary and _is_delayed_host_action_text(current_summary):
        if follow_up_steps and current_summary not in follow_up_steps:
            follow_up_steps.insert(0, current_summary)
        current_summary = current_steps[0] if current_steps else None
    elif current_summary and not current_steps:
        current_steps = [current_summary]

    if not current_steps and not current_proof:
        return {"current": current, "follow_up": None}

    if not current_summary:
        current_summary = current_steps[0] if current_steps else (current_proof[0] if current_proof else None)

    follow_up_summary = follow_up_steps[0] if follow_up_steps else (follow_up_proof[0] if follow_up_proof else None)
    follow_up = None
    if follow_up_summary:
        follow_up = {
            "summary": follow_up_summary,
            "steps": follow_up_steps,
            "proof_required": follow_up_proof,
            "source_card_id": current.get("source_card_id"),
            "source_card_title": current.get("source_card_title"),
            "source_result_id": current.get("source_result_id"),
            "source_result_summary": current.get("source_result_summary"),
            "detected_from": current.get("detected_from"),
        }

    return {
        "current": {
            "summary": current_summary,
            "steps": current_steps,
            "proof_required": current_proof,
            "source_card_id": current.get("source_card_id"),
            "source_card_title": current.get("source_card_title"),
            "source_result_id": current.get("source_result_id"),
            "source_result_summary": current.get("source_result_summary"),
            "detected_from": current.get("detected_from"),
        },
        "follow_up": follow_up,
    }


def _host_action_text_items(host_action: dict[str, Any] | None) -> list[str]:
    if not isinstance(host_action, dict):
        return []
    items = [_optional_str(host_action.get("summary"))]
    items.extend(_dedupe_nonempty_strings(host_action.get("steps")))
    items.extend(_dedupe_nonempty_strings(host_action.get("proof_required")))
    return [item for item in items if item]


def _host_action_text_blob(host_action: dict[str, Any] | None) -> str:
    return "\n".join(_host_action_text_items(host_action))


def _host_action_requires_publish_state(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_PUBLISH_PATTERNS) and _is_delayed_host_action_text(text)


def _host_action_mentions_publish(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_PUBLISH_PATTERNS)


def _host_action_mentions_scheduling(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_SCHEDULE_PATTERNS)


def _host_action_required_state_key(host_action: dict[str, Any] | None) -> str | None:
    if _host_action_requires_publish_state(host_action):
        return "published_at"
    if _is_delayed_host_action_text(_host_action_text_blob(host_action)) and _host_action_mentions_scheduling(host_action):
        return "scheduled_at"
    return None


def _parse_host_action_datetime(value: str | None) -> datetime | None:
    text = _optional_str(value)
    if not text:
        return None

    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=NEW_YORK_TZ)

    normalized = re.sub(r"\s+", " ", text.strip())
    timezone_hint = None
    upper = normalized.upper()
    for suffix in (" EDT", " EST", " ET", " UTC"):
        if upper.endswith(suffix):
            timezone_hint = suffix.strip()
            normalized = normalized[: -len(suffix)].strip()
            break
    normalized = normalized.replace("T", " ")
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if timezone_hint == "UTC":
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.replace(tzinfo=NEW_YORK_TZ)
    return None


def _extract_host_action_datetime(text_values: list[str]) -> str | None:
    for raw in text_values:
        text = _optional_str(raw)
        if not text:
            continue
        for pattern in HOST_ACTION_TIMESTAMP_PATTERNS:
            for match in pattern.findall(text):
                parsed = _parse_host_action_datetime(match)
                if parsed is not None:
                    return parsed.astimezone(timezone.utc).isoformat()
        parsed_full = _parse_host_action_datetime(text)
        if parsed_full is not None:
            return parsed_full.astimezone(timezone.utc).isoformat()
    return None


def _extract_host_action_external_state(
    host_action_required: dict[str, Any] | None,
    *,
    completion_note: str | None,
    proof_items: list[str] | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    evidence_items = [item for item in [completion_note, *list(proof_items or [])] if _optional_str(item)]
    timestamp = _extract_host_action_datetime([str(item) for item in evidence_items])
    if not timestamp:
        return state
    if _host_action_mentions_publish(host_action_required):
        state["published_at"] = timestamp
    elif _host_action_mentions_scheduling(host_action_required):
        state["scheduled_at"] = timestamp
    return state


def _host_action_followup_due_at(host_action: dict[str, Any] | None, external_state: dict[str, Any]) -> datetime | None:
    required_state_key = _host_action_required_state_key(host_action)
    if not required_state_key:
        return None
    state_value = _optional_str(external_state.get(required_state_key))
    anchor = _parse_host_action_datetime(state_value)
    if anchor is None:
        return None
    text = _host_action_text_blob(host_action)
    if not text:
        return anchor
    hours_match = re.search(r"\bwithin\s+(\d+)\s*(?:hours?|hrs?|h)\b", text, re.IGNORECASE)
    if hours_match:
        return anchor + timedelta(hours=int(hours_match.group(1)))
    if re.search(r"\bfirst[-\s]24h\b|\bfirst[-\s]24[-\s]hour\b", text, re.IGNORECASE):
        return anchor + timedelta(hours=24)
    return anchor


def _evaluate_host_action_followup_readiness(
    host_action: dict[str, Any] | None,
    completion_payload: dict[str, Any],
) -> dict[str, Any]:
    follow_up = _normalize_host_action_payload(host_action)
    if follow_up is None:
        return {"ready": False, "reason": "No delayed host follow-up is attached."}
    required_state_key = _host_action_required_state_key(follow_up)
    external_state = dict(completion_payload.get("external_state") or {})
    if required_state_key is None:
        return {
            "ready": True,
            "required_state_key": None,
            "due_at": None,
            "reason": "This follow-up does not depend on a delayed external state token.",
        }
    state_value = _optional_str(external_state.get(required_state_key))
    if not state_value:
        return {
            "ready": False,
            "required_state_key": required_state_key,
            "due_at": None,
            "reason": f"Waiting on explicit `{required_state_key}` before the delayed host follow-up can exist.",
        }
    return {
        "ready": True,
        "required_state_key": required_state_key,
        "state_value": state_value,
        "due_at": _host_action_followup_due_at(follow_up, external_state),
        "reason": f"Delayed host follow-up unlocked by `{required_state_key}`.",
    }


def _host_action_activation_status(card: PMCard) -> dict[str, Any] | None:
    if not _is_host_action_required_card(card):
        return None
    payload = dict(card.payload or {})
    host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
    if host_action_required is None:
        return None
    required_state_key = _host_action_required_state_key(host_action_required)
    if required_state_key is None:
        return None
    now = datetime.now(timezone.utc)
    due_at = card.due_at
    if due_at is None:
        return {
            "state": "waiting_on_prerequisite",
            "required_state_key": required_state_key,
            "reason": f"This delayed host follow-up should wait until `{required_state_key}` is recorded upstream.",
        }
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if due_at > now:
        return {
            "state": "not_due_yet",
            "required_state_key": required_state_key,
            "due_at": due_at.isoformat(),
            "reason": f"This delayed host follow-up is not due until `{due_at.astimezone(timezone.utc).isoformat()}`.",
        }
    return {
        "state": "due",
        "required_state_key": required_state_key,
        "due_at": due_at.isoformat(),
        "reason": "This delayed host follow-up is now due.",
    }


def _resolved_host_action_phases(card: PMCard) -> dict[str, dict[str, Any] | None]:
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    current = _normalize_host_action_payload(host_action_required)
    if current is None:
        return {"current": None, "follow_up": None}

    host_action_followup = _normalize_host_action_payload(payload.get("host_action_followup"))
    if host_action_followup is not None:
        return {"current": current, "follow_up": host_action_followup}
    return _split_host_action_timeline(current)


def _completion_contract_auto_retry_count(card: PMCard) -> int:
    payload = dict(card.payload or {})
    latest_manual_review = payload.get("latest_manual_review")
    if not isinstance(latest_manual_review, dict):
        return 0
    return max(0, int(latest_manual_review.get("contract_auto_return_count") or 0))


def _contract_assessment_summary(assessment: dict[str, Any]) -> str:
    missing = [
        str(item).strip()
        for item in assessment.get("missing") or []
        if str(item).strip()
    ]
    if missing:
        return "Missing: " + "; ".join(missing[:3])
    done_when = [
        str(item).strip()
        for item in assessment.get("done_when") or []
        if str(item).strip()
    ]
    if done_when:
        return "Expected: " + "; ".join(done_when[:2])
    return "The completion contract did not pass."


def _is_owner_decision_gate(card: PMCard) -> bool:
    payload = dict(card.payload or {})
    owner_review_payload = payload.get("owner_review")
    normalized_status = str(card.status or "").strip().lower()
    if isinstance(owner_review_payload, dict):
        queue_id = str(owner_review_payload.get("queue_id") or "").strip()
        sync_state = str(owner_review_payload.get("sync_state") or "").strip().lower()
        decision = str(owner_review_payload.get("decision") or "").strip().lower()
        if decision:
            return False
        if sync_state == "pending_owner_review" and queue_id:
            return True
        if queue_id and normalized_status == "review":
            return True
    if isinstance(card.source, str) and "workspace-owner-review" in card.source and normalized_status == "review":
        return True
    return False


def _execution_payload(card: PMCard) -> dict | None:
    payload = card.payload or {}
    execution = payload.get("execution")
    return dict(execution) if isinstance(execution, dict) else None


def execution_defaults_for_workspace(workspace_key: str) -> dict[str, object]:
    return runtime_execution_defaults_for_workspace(workspace_key)


def review_policy_for_workspace(workspace_key: str) -> dict[str, object]:
    return runtime_pm_review_policy_for_workspace(workspace_key)


def _merge_execution_defaults(current_execution: dict, defaults: dict[str, object]) -> dict:
    merged = dict(current_execution)
    for key, value in defaults.items():
        if merged.get(key) in (None, "", []):
            merged[key] = value
    if (
        merged.get("source") == "standup_promotion"
        and str(merged.get("target_agent") or "").strip().lower() == "neo"
        and str(merged.get("manager_agent") or "").strip() == ""
    ):
        merged["manager_agent"] = defaults["manager_agent"]
        merged["target_agent"] = defaults["target_agent"]
        merged["workspace_agent"] = defaults["workspace_agent"]
        merged["execution_mode"] = defaults["execution_mode"]
    return merged


def _workspace_key_from_card(card: PMCard) -> str:
    payload = card.payload or {}
    for key in ("workspace_key", "workspace", "belongs_to_workspace"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "shared_ops"


def _build_client_review_policy(card: PMCard) -> dict[str, Any]:
    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    execution = dict(_execution_payload(card) or {})
    normalized_status = str(card.status or "").strip().lower()
    owner_gate = _is_owner_decision_gate(card)
    host_action_required = _is_host_action_required_card(card)
    host_action_activation = _host_action_activation_status(card)
    auto_resolve_policy = _auto_resolve_review_policy(card)
    attention_class = "fyi"
    attention_reason = "This card is visible for context, but it does not currently need your judgment."
    recommended_resolution_mode: str | None = None
    suggested_next_title: str | None = None
    suggested_next_reason: str | None = None
    interrupt_policy = str(workspace_policy.get("interrupt_policy") or "manual_review")

    if _is_closed_pm_status(card.status):
        attention_reason = "This card is already closed and kept here as traceable history."
    elif owner_gate:
        attention_class = "needs_owner"
        attention_reason = "This card is an explicit owner gate and should wait for your call."
    elif host_action_activation is not None and str(host_action_activation.get("state") or "").strip() in {
        "waiting_on_prerequisite",
        "not_due_yet",
    }:
        attention_class = "autonomous"
        attention_reason = _optional_str(host_action_activation.get("reason")) or (
            "This delayed host follow-up is waiting on an upstream state change and should stay out of your action surface."
        )
    elif host_action_required:
        attention_class = "needs_host"
        attention_reason = "This card requires a host action outside the runtime before the loop can fully close."
    elif (
        interrupt_policy in {"owner_gate_only", "manager_attention_only"}
        and not owner_gate
        and not host_action_required
        and (
            str(execution.get("state") or "").strip().lower() == "failed"
            or str(execution.get("executor_status") or "").strip().lower() == "failed"
        )
    ):
        attention_class = "autonomous"
        attention_reason = "This autonomous execution lane failed and should go back through Codex or Jean-Claude, not your owner inbox."
    elif bool(execution.get("manager_attention_required")) or normalized_status in {"blocked", "failed"}:
        attention_class = "needs_owner"
        attention_reason = "This lane is blocked or flagged for manager attention and needs a human decision."
    elif auto_resolve_policy is not None:
        attention_class = "stale"
        attention_reason = auto_resolve_policy["reason"]
    elif normalized_status == "review":
        if interrupt_policy == "manual_review":
            attention_class = "needs_owner"
            attention_reason = "This workspace expects a human review before a returned result is accepted or continued."
        elif interrupt_policy == "owner_gate_only":
            attention_class = "autonomous"
            attention_reason = "Routine review results in this workspace should keep moving unless they hit an owner gate or blocker."
            recommended_resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode"))
        elif interrupt_policy == "manager_attention_only":
            attention_class = "autonomous"
            attention_reason = "Routine review residue in this workspace should close quietly unless manager attention is required."
            recommended_resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode"))
    elif normalized_status in {"queued", "running", "in_progress"}:
        attention_reason = "This card is active system work. You usually only need to step in if it blocks or priorities change."

    if recommended_resolution_mode == "close_and_spawn_next":
        suggestion = _suggest_review_followup(card, workspace_policy)
        if suggestion is not None:
            suggested_next_title = suggestion.get("title")
            suggested_next_reason = suggestion.get("reason")

    return {
        "attention_class": attention_class,
        "attention_reason": attention_reason,
        "policy_label": _optional_str(workspace_policy.get("policy_label")),
        "interrupt_policy": _optional_str(workspace_policy.get("interrupt_policy")),
        "recommended_resolution_mode": recommended_resolution_mode,
        "suggested_next_title": suggested_next_title,
        "suggested_next_reason": suggested_next_reason,
        "auto_resolve_eligible": auto_resolve_policy is not None,
        "owner_decision_gate": owner_gate,
        "host_action_activation": host_action_activation,
    }


def _is_closed_pm_status(status: Optional[str]) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {"done", "closed", "cancelled"}


def _is_execution_candidate(card: PMCard) -> bool:
    if _is_closed_pm_status(card.status):
        return False
    return _execution_contract_source(card) is not None


def repair_execution_contracts(limit: int = 250, workspace_key: str | None = None) -> dict[str, Any]:
    cards = list_cards(limit=limit, workspace_key=workspace_key)
    deduped = _dedupe_active_pm_review_resolution_cards(cards)
    host_followup_repairs = _repair_legacy_host_action_cards(cards)
    closed_duplicate_ids = {str(item.get("card_id")) for item in deduped}
    cards = [card for card in cards if card.id not in closed_duplicate_ids]
    repaired: list[dict[str, Any]] = []

    for card in cards:
        patched_payload = _build_missing_execution_contract_payload(card)
        if patched_payload is None:
            continue
        updated = update_card(card.id, PMCardUpdate(payload=patched_payload))
        effective = updated or card.model_copy(update={"payload": patched_payload})
        repaired.append(
            {
                "card_id": effective.id,
                "title": effective.title,
                "workspace_key": _workspace_key_from_card(effective),
                "status": effective.status,
                "source": effective.source,
                "contract_source": _payload_contract_source(effective.payload or {}),
            }
        )

    return {
        "deduped_count": len(deduped),
        "deduped": deduped,
        "host_followup_repaired_count": len(host_followup_repairs),
        "host_followup_repaired": host_followup_repairs,
        "repaired_count": len(repaired),
        "repaired": repaired,
    }


def _repair_legacy_host_action_cards(cards: list[PMCard]) -> list[dict[str, Any]]:
    cards_by_id = {card.id: card for card in cards}
    repaired: list[dict[str, Any]] = []
    requested_by = "PM Host Action Repair"

    def apply_card_update(card: PMCard, *, status: str | None = None, payload: dict[str, Any] | None = None) -> PMCard:
        updated = update_card(card.id, PMCardUpdate(status=status, payload=payload))
        effective = updated or card.model_copy(
            update={
                "status": status if status is not None else card.status,
                "payload": payload if payload is not None else dict(card.payload or {}),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        cards_by_id[effective.id] = effective
        return effective

    def clear_source_followup_references(source_payload: dict[str, Any], follow_up_card_id: str) -> dict[str, Any]:
        completion = dict(source_payload.get("host_action_completion") or {})
        if _optional_str(completion.get("follow_up_card_id")) == follow_up_card_id:
            completion.pop("follow_up_card_id", None)
            completion.pop("follow_up_card_title", None)
        if completion:
            source_payload["host_action_completion"] = completion
        else:
            source_payload.pop("host_action_completion", None)
        spawned = dict(source_payload.get("host_action_followup_spawned") or {})
        if _optional_str(spawned.get("card_id")) == follow_up_card_id:
            source_payload.pop("host_action_followup_spawned", None)
        return source_payload

    def persist_resolved_host_action_phases(card: PMCard, payload: dict[str, Any]) -> dict[str, Any]:
        phases = _resolved_host_action_phases(card)
        current_phase = phases.get("current")
        follow_up_phase = phases.get("follow_up")
        if current_phase is not None:
            payload["host_action_required"] = {
                **current_phase,
                "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(current_phase.get("proof_required"))),
            }
        if follow_up_phase is not None:
            payload["host_action_followup"] = {
                **follow_up_phase,
                "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
            }
        else:
            payload.pop("host_action_followup", None)
        return payload

    def build_host_execution_payload(
        current_execution: dict[str, Any],
        *,
        state: str,
        event: str,
        reason: str,
    ) -> dict[str, Any]:
        history = list(current_execution.get("history") or [])
        history.append(
            {
                "event": event,
                "state": state,
                "requested_by": requested_by,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            **current_execution,
            "state": state,
            "requested_by": requested_by,
            "manager_attention_required": False,
            "executor_status": None,
            "executor_worker_id": None,
            "executor_last_error": None,
            "execution_packet_path": None,
            "executor_started_at": None,
            "executor_finished_at": None,
            "briefing_path": None,
            "sop_path": None,
            "reason": reason,
            "last_transition_at": datetime.now(timezone.utc).isoformat(),
            "history": history[-12:],
        }

    def should_reopen_source(
        source_card: PMCard,
        *,
        required_state_key: str | None,
        follow_up_card_id: str,
    ) -> bool:
        if not _is_closed_pm_status(source_card.status):
            return False
        payload = dict(source_card.payload or {})
        completion = dict(payload.get("host_action_completion") or {})
        if _optional_str(completion.get("host_confirmation_mode")) != "confirmed_without_context":
            return False
        external_state = dict(completion.get("external_state") or {})
        if required_state_key and _optional_str(external_state.get(required_state_key)):
            return False
        spawned = dict(payload.get("host_action_followup_spawned") or {})
        references_followup = _optional_str(completion.get("follow_up_card_id")) == follow_up_card_id or _optional_str(
            spawned.get("card_id")
        ) == follow_up_card_id
        return references_followup

    # First, cancel legacy delayed follow-up cards that should not exist yet.
    for card in cards:
        current = cards_by_id.get(card.id, card)
        if _is_closed_pm_status(current.status) or not _is_host_action_required_card(current):
            continue
        activation = _host_action_activation_status(current)
        if not isinstance(activation, dict) or str(activation.get("state") or "").strip() != "waiting_on_prerequisite":
            continue

        payload = dict(current.payload or {})
        host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
        if host_action_required is None:
            continue
        current_completion = dict(payload.get("host_action_completion") or {})
        current_follow_up = _resolved_host_action_phases(current).get("follow_up")
        required_state_key = _optional_str(activation.get("required_state_key"))
        source_card_id = _optional_str(host_action_required.get("source_card_id"))
        source_card = cards_by_id.get(source_card_id) if source_card_id else None
        source_is_host_action = source_card is not None and _is_host_action_required_card(source_card)
        has_follow_up_context = current_follow_up is not None or bool(
            _optional_str(current_completion.get("follow_up_card_id"))
        ) or bool(dict(payload.get("host_action_followup_spawned") or {}))
        if not source_is_host_action and has_follow_up_context:
            continue
        source_payload = dict(source_card.payload or {}) if source_card is not None else {}
        source_follow_up = _resolved_host_action_phases(source_card).get("follow_up") if source_card is not None else None
        source_completion = dict(source_payload.get("host_action_completion") or {}) if source_card is not None else {}
        follow_up_gate = (
            _evaluate_host_action_followup_readiness(source_follow_up, source_completion)
            if source_card is not None and source_follow_up is not None
            else None
        )

        cancel_reason = (
            f"Cancelled legacy delayed host follow-up because `{required_state_key}` was never recorded upstream."
            if required_state_key
            else "Cancelled legacy delayed host follow-up because its prerequisite state was missing upstream."
        )
        cancel_payload = dict(payload)
        cancel_payload["execution"] = build_host_execution_payload(
            dict(cancel_payload.get("execution") or {}),
            state="cancelled",
            event="legacy_host_followup_cancelled",
            reason=cancel_reason,
        )
        cancel_payload["legacy_host_repair"] = {
            "action": "cancel_invalid_delayed_followup",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "required_state_key": required_state_key,
            "source_card_id": source_card_id,
            "reason": cancel_reason,
        }
        apply_card_update(current, status="cancelled", payload=cancel_payload)

        reopened_source: PMCard | None = None
        replacement_followup: PMCard | None = None

        if source_card is not None:
            source_payload = clear_source_followup_references(dict(source_payload), current.id)
            if should_reopen_source(source_card, required_state_key=required_state_key, follow_up_card_id=current.id):
                source_payload.pop("host_action_followup_pending", None)
                source_payload = persist_resolved_host_action_phases(source_card, source_payload)
                source_payload["execution"] = build_host_execution_payload(
                    dict(source_payload.get("execution") or {}),
                    state="host_step_only",
                    event="legacy_host_source_reopened",
                    reason="Reopened host step because a delayed follow-up had been spawned without any recorded external state.",
                )
                source_payload["legacy_host_repair"] = {
                    "action": "reopen_source_host_step",
                    "repaired_at": datetime.now(timezone.utc).isoformat(),
                    "repaired_by": requested_by,
                    "cancelled_followup_card_id": current.id,
                    "required_state_key": required_state_key,
                    "reason": "Reopened the source host step because it had been confirmed without context and no prerequisite external state was recorded.",
                }
                reopened_source = apply_card_update(source_card, status="todo", payload=source_payload)
            else:
                if isinstance(follow_up_gate, dict):
                    source_payload["host_action_followup_pending"] = follow_up_gate
                source_payload["legacy_host_repair"] = {
                    "action": "normalize_followup_pending",
                    "repaired_at": datetime.now(timezone.utc).isoformat(),
                    "repaired_by": requested_by,
                    "cancelled_followup_card_id": current.id,
                    "required_state_key": required_state_key,
                    "reason": "Removed a legacy delayed host follow-up and restored the pending gate on the source host step.",
                }
                source_card = apply_card_update(source_card, status=source_card.status, payload=source_payload)
                cards_by_id[source_card.id] = source_card
                if isinstance(follow_up_gate, dict) and bool(follow_up_gate.get("ready")) and source_follow_up is not None:
                    replacement_followup = _create_host_action_required_card(
                        source_card,
                        requested_by=requested_by,
                        host_action_required=source_follow_up,
                        due_at=follow_up_gate.get("due_at"),
                    )
                    replacement_payload = dict(source_card.payload or {})
                    completion = dict(replacement_payload.get("host_action_completion") or {})
                    completion["follow_up_card_id"] = replacement_followup.id
                    completion["follow_up_card_title"] = replacement_followup.title
                    replacement_payload["host_action_completion"] = completion
                    replacement_payload["host_action_followup_spawned"] = {
                        "card_id": replacement_followup.id,
                        "title": replacement_followup.title,
                        "created_at": _datetime_to_iso(replacement_followup.created_at),
                        "workspace_key": _workspace_key_from_card(replacement_followup),
                    }
                    replacement_payload.pop("host_action_followup_pending", None)
                    source_card = apply_card_update(source_card, status=source_card.status, payload=replacement_payload)

        repaired.append(
            {
                "card_id": current.id,
                "title": current.title,
                "action": "cancelled_invalid_delayed_followup",
                "workspace_key": _workspace_key_from_card(current),
                "source_card_id": source_card_id,
                "reopened_source_card_id": reopened_source.id if reopened_source is not None else None,
                "replacement_followup_card_id": replacement_followup.id if replacement_followup is not None else None,
            }
        )

    # Then, reopen malformed legacy source host cards that were closed without any usable external state.
    for card in list(cards_by_id.values()):
        if not _is_closed_pm_status(card.status) or not _is_host_action_required_card(card):
            continue
        payload = dict(card.payload or {})
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        if host_action_followup is None:
            continue
        completion = dict(payload.get("host_action_completion") or {})
        if _optional_str(completion.get("host_confirmation_mode")) != "confirmed_without_context":
            continue
        required_state_key = _host_action_required_state_key(host_action_followup)
        external_state = dict(completion.get("external_state") or {})
        if required_state_key and _optional_str(external_state.get(required_state_key)):
            continue
        spawned = dict(payload.get("host_action_followup_spawned") or {})
        follow_up_card_id = _optional_str(completion.get("follow_up_card_id")) or _optional_str(spawned.get("card_id"))
        follow_up_card = cards_by_id.get(follow_up_card_id) if follow_up_card_id else None
        if follow_up_card is not None and not _is_closed_pm_status(follow_up_card.status):
            continue
        reopened_payload = clear_source_followup_references(dict(payload), follow_up_card_id or "")
        reopened_payload.pop("host_action_followup_pending", None)
        reopened_payload = persist_resolved_host_action_phases(card, reopened_payload)
        reopened_payload["execution"] = build_host_execution_payload(
            dict(reopened_payload.get("execution") or {}),
            state="host_step_only",
            event="legacy_host_source_reopened",
            reason="Reopened host step because the legacy closure did not record the external state needed for follow-through.",
        )
        reopened_payload["legacy_host_repair"] = {
            "action": "reopen_source_host_step",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "cancelled_followup_card_id": follow_up_card_id,
            "required_state_key": required_state_key,
            "reason": "Reopened the source host step because it had been confirmed without context and no prerequisite external state was recorded.",
        }
        apply_card_update(card, status="todo", payload=reopened_payload)
        repaired.append(
            {
                "card_id": card.id,
                "title": card.title,
                "action": "reopened_legacy_source_host_step",
                "workspace_key": _workspace_key_from_card(card),
                "followup_card_id": follow_up_card_id,
            }
        )

    # Then, activate any delayed follow-up that is now ready from explicit external state.
    for card in list(cards_by_id.values()):
        if not _is_closed_pm_status(card.status) or not _is_host_action_required_card(card):
            continue
        payload = dict(card.payload or {})
        pending_gate = dict(payload.get("host_action_followup_pending") or {})
        if not pending_gate:
            continue
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        if host_action_followup is None:
            continue
        completion = dict(payload.get("host_action_completion") or {})
        follow_up_gate = _evaluate_host_action_followup_readiness(host_action_followup, completion)
        if not bool(follow_up_gate.get("ready")):
            continue
        successor_card = _create_host_action_required_card(
            card,
            requested_by=requested_by,
            host_action_required=host_action_followup,
            due_at=follow_up_gate.get("due_at"),
        )
        updated_payload = dict(payload)
        completion["follow_up_card_id"] = successor_card.id
        completion["follow_up_card_title"] = successor_card.title
        updated_payload["host_action_completion"] = completion
        updated_payload["host_action_followup_spawned"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        updated_payload.pop("host_action_followup_pending", None)
        updated_payload["legacy_host_repair"] = {
            "action": "activate_ready_delayed_followup",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "spawned_followup_card_id": successor_card.id,
            "required_state_key": follow_up_gate.get("required_state_key"),
            "reason": "Activated a delayed host follow-up because the prerequisite external state is now recorded.",
        }
        apply_card_update(card, status=card.status, payload=updated_payload)
        cards_by_id[successor_card.id] = successor_card
        repaired.append(
            {
                "card_id": card.id,
                "title": card.title,
                "action": "activated_ready_delayed_followup",
                "workspace_key": _workspace_key_from_card(card),
                "spawned_followup_card_id": successor_card.id,
            }
        )

    return repaired


def _build_missing_execution_contract_payload(card: PMCard) -> dict[str, Any] | None:
    if _is_closed_pm_status(card.status):
        return None

    payload = dict(card.payload or {})
    contract_source = _execution_contract_source(card)
    if contract_source is None:
        return None

    current_contract = payload.get("completion_contract")
    current_execution = _execution_payload(card)
    needs_contract = not isinstance(current_contract, dict) or not current_contract
    needs_execution = not isinstance(current_execution, dict) or not current_execution

    if not needs_contract and not needs_execution:
        return None

    workspace_key = _workspace_key_from_card(card)
    existing_reason = _payload_value(payload, "reason") or _optional_str((current_execution or {}).get("reason"))
    normalized_reason = existing_reason or f"Autonomous PM execution for `{card.title}` in `{workspace_key}`."
    contract = build_execution_contract(
        title=card.title,
        workspace_key=workspace_key,
        source=contract_source,
        reason=normalized_reason,
        instructions=payload.get("instructions"),
        acceptance_criteria=payload.get("acceptance_criteria"),
        artifacts_expected=payload.get("artifacts_expected"),
    )

    updated_payload = dict(payload)
    if needs_contract:
        updated_payload["instructions"] = contract["instructions"]
        updated_payload["acceptance_criteria"] = contract["acceptance_criteria"]
        updated_payload["artifacts_expected"] = contract["artifacts_expected"]
        updated_payload["completion_contract"] = contract["completion_contract"]

    if needs_execution:
        defaults = execution_defaults_for_workspace(workspace_key)
        now_iso = datetime.now(timezone.utc).isoformat()
        state = _default_execution_state_for_card(card)
        updated_payload["execution"] = {
            "lane": "codex",
            "state": state,
            "manager_agent": defaults["manager_agent"],
            "target_agent": defaults["target_agent"],
            "workspace_agent": defaults.get("workspace_agent"),
            "execution_mode": defaults["execution_mode"],
            "requested_by": _payload_value(payload, "requested_by")
            or _payload_value(payload, "source_agent")
            or card.owner
            or defaults["manager_agent"],
            "assigned_runner": "jean-claude" if str(defaults["execution_mode"]) == "direct" else "codex",
            "reason": normalized_reason,
            "last_transition_at": now_iso,
            "source": contract_source,
        }
        if state == "queued":
            updated_payload["execution"]["queued_at"] = now_iso

    return updated_payload


def _dedupe_active_pm_review_resolution_cards(cards: list[PMCard]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[PMCard]] = {}
    for card in cards:
        if _is_closed_pm_status(card.status):
            continue
        if str(card.source or "").strip() != "pm_review_resolution":
            continue
        workspace_key = _workspace_key_from_card(card)
        group_key = (workspace_key, str(card.source or "").strip(), str(card.title or "").strip().lower())
        groups.setdefault(group_key, []).append(card)

    deduped: list[dict[str, Any]] = []
    for siblings in groups.values():
        if len(siblings) <= 1:
            continue
        ranked = sorted(siblings, key=_pm_resolution_dedupe_rank, reverse=True)
        keep = ranked[0]
        for duplicate in ranked[1:]:
            payload = dict(duplicate.payload or {})
            payload["duplicate_resolution"] = {
                "kept_card_id": keep.id,
                "kept_card_title": keep.title,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Closed duplicate pm_review_resolution lane because an equivalent active successor card already exists.",
            }
            updated = update_card(duplicate.id, PMCardUpdate(status="done", payload=payload))
            effective = updated or duplicate.model_copy(update={"status": "done", "payload": payload})
            deduped.append(
                {
                    "card_id": effective.id,
                    "title": effective.title,
                    "workspace_key": _workspace_key_from_card(effective),
                    "kept_card_id": keep.id,
                    "kept_card_title": keep.title,
                }
            )
    return deduped


def _pm_resolution_dedupe_rank(card: PMCard) -> tuple[int, int, datetime]:
    execution = _execution_payload(card) or {}
    execution_state = str(execution.get("state") or "").strip().lower()
    status = str(card.status or "").strip().lower()
    status_rank = {
        "in_progress": 4,
        "running": 4,
        "queued": 3,
        "todo": 2,
        "review": 1,
    }.get(status, 0)
    execution_rank = _execution_sort_rank(execution_state)
    updated_at = card.updated_at or card.created_at or datetime.min.replace(tzinfo=timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (status_rank, execution_rank, updated_at)


def _execution_contract_source(card: PMCard) -> str | None:
    payload = dict(card.payload or {})
    source = str(card.source or "").strip()
    if _is_owner_decision_gate(card):
        return None
    if source == "pm_host_action_required" or _is_host_action_required_card(card):
        return None
    if source == "pm_review_resolution":
        return "pm_review_resolution"
    if source.startswith("brain-triage:"):
        return "brain_triage"
    if source.startswith("accountability_sweep"):
        return "accountability_sweep"
    if source == "openclaw:workspace-owner-review":
        return "owner_review_followup"
    if source == "openclaw:thin-trigger" or str(payload.get("trigger_origin") or "").strip() == "openclaw_thin_trigger":
        return "openclaw_thin_trigger"
    if card.link_type == "standup" or source.startswith("standup-prep:") or payload.get("created_from_standup_id"):
        return "standup_promotion"
    return None


def _payload_contract_source(payload: dict[str, Any]) -> str | None:
    contract = payload.get("completion_contract")
    if not isinstance(contract, dict):
        return None
    return _optional_str(contract.get("source"))


def _default_execution_state_for_card(card: PMCard) -> str:
    normalized_status = str(card.status or "").strip().lower()
    if normalized_status in {"queued", "review", "blocked", "failed"}:
        return normalized_status
    if normalized_status in {"running", "in_progress"}:
        return "running"
    payload = dict(card.payload or {})
    contract = payload.get("completion_contract")
    autostart = isinstance(contract, dict) and bool(contract.get("autostart"))
    if autostart or _execution_contract_source(card) is not None:
        return "queued"
    return "ready"


def _is_host_action_required_card(card: PMCard) -> bool:
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    return isinstance(host_action_required, dict) and bool(host_action_required)


def _create_host_action_required_card(
    source_card: PMCard,
    *,
    requested_by: str,
    host_action_required: dict[str, Any],
    due_at: datetime | None = None,
) -> PMCard:
    workspace_key = _workspace_key_from_card(source_card)
    phases = _split_host_action_timeline(host_action_required)
    current_phase = phases.get("current") or {}
    follow_up_phase = phases.get("follow_up")
    steps = _dedupe_nonempty_strings(current_phase.get("steps"))
    summary = _optional_str(current_phase.get("summary")) or (steps[0] if steps else f"Complete host action for {source_card.title}")
    proof_required = _dedupe_nonempty_strings(current_phase.get("proof_required"))
    proof_fields = _build_host_action_proof_fields(proof_required)
    title = _truncate_pm_card_title(f"Host action required - {summary}")
    reason = (
        "Codex completed the internal PM lane, but the last external step still needs to happen outside the runtime. "
        + summary
    )
    payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "reason": reason,
        "source_agent": requested_by,
        "front_door_agent": requested_by,
        "host_action_required": {
            "summary": summary,
            "steps": steps,
            "proof_required": proof_required,
            "proof_fields": proof_fields,
            "source_card_id": source_card.id,
            "source_card_title": source_card.title,
            "source_result_id": _optional_str(current_phase.get("source_result_id")),
            "source_result_summary": _optional_str(current_phase.get("source_result_summary")),
            "detected_from": _optional_str(current_phase.get("detected_from")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        # These fields make the trigger key stable without turning the card into an execution candidate.
        "instructions": steps,
        "acceptance_criteria": proof_required,
    }
    if follow_up_phase is not None:
        payload["host_action_followup"] = {
            **follow_up_phase,
            "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
        }
    payload["trigger_key"] = _build_trigger_key(
        title=title,
        workspace_key=workspace_key,
        source="pm_host_action_required",
        payload=payload,
    )
    existing = find_active_card_by_trigger_key(str(payload["trigger_key"]))
    if existing is not None:
        return existing

    return create_card(
        PMCardCreate(
            title=title,
            owner="Neo",
            status="todo",
            source="pm_host_action_required",
            link_type=source_card.link_type,
            link_id=source_card.link_id,
            due_at=due_at,
            payload=payload,
        )
    )


def _build_host_action_proof_fields(proof_required: list[str]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for requirement in proof_required:
        normalized = requirement.lower()
        if "screenshot" in normalized:
            fields.append(
                {
                    "kind": "screenshot_path",
                    "label": "Screenshot path",
                    "placeholder": "Enter the screenshot path or link.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "timestamp" in normalized or "scheduled" in normalized:
            fields.append(
                {
                    "kind": "scheduled_timestamp",
                    "label": "Scheduled timestamp",
                    "placeholder": "Enter the exact scheduled timestamp or confirmation detail.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "url" in normalized:
            fields.append(
                {
                    "kind": "publish_url",
                    "label": "Publish URL",
                    "placeholder": "Enter the publish URL or confirmation link.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "path" in normalized or "artifact" in normalized:
            fields.append(
                {
                    "kind": "artifact_path",
                    "label": "Artifact update path",
                    "placeholder": "Enter the updated file path or artifact reference.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "metric" in normalized or "analytics" in normalized:
            fields.append(
                {
                    "kind": "metric_reference",
                    "label": "Metric log reference",
                    "placeholder": "Enter where the metric or analytics proof was recorded.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        else:
            fields.append(
                {
                    "kind": "proof_note",
                    "label": "Proof note",
                    "placeholder": "Enter the proof that satisfies this requirement.",
                    "multiline": True,
                    "requirement": requirement,
                }
            )
    return fields


def _build_host_action_completion_payload(
    card: PMCard,
    *,
    requested_by: str,
    completion_note: str | None,
    proof_items: list[str] | None,
) -> dict[str, Any]:
    payload = dict(card.payload or {})
    phases = _resolved_host_action_phases(card)
    host_action_required = dict(phases.get("current") or payload.get("host_action_required") or {})
    follow_up_host_action = dict(phases.get("follow_up") or payload.get("host_action_followup") or {})
    required = _dedupe_nonempty_strings(host_action_required.get("proof_required"))
    provided = _dedupe_nonempty_strings(proof_items or [])
    note = _optional_str(completion_note)
    external_state = _extract_host_action_external_state(
        host_action_required,
        completion_note=note,
        proof_items=provided,
    )
    follow_up_gate = _evaluate_host_action_followup_readiness(follow_up_host_action, {"external_state": external_state})

    return {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_by": requested_by,
        "completion_note": note,
        "proof_items": provided,
        "proof_required": required,
        "external_state": external_state,
        "source_card_id": _optional_str(host_action_required.get("source_card_id")),
        "source_card_title": _optional_str(host_action_required.get("source_card_title")),
        "follow_up_summary": _optional_str(follow_up_host_action.get("summary")),
        "follow_up_proof_required": _dedupe_nonempty_strings(follow_up_host_action.get("proof_required")),
        "follow_up_gate": follow_up_gate,
        "host_confirmation_mode": "confirmed_with_context" if note or provided else "confirmed_without_context",
    }


def _execution_sort_rank(state: str) -> int:
    normalized = state.lower()
    if normalized == "running":
        return 4
    if normalized == "queued":
        return 3
    if normalized == "review":
        return 2
    if normalized == "ready":
        return 1
    if normalized in {"failed", "blocked"}:
        return 0
    return 0


def _payload_value(payload: dict, key: str) -> Optional[str]:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _optional_str(value: object) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _dedupe_nonempty_strings(values: object) -> list[str]:
    if isinstance(values, list):
        source = values
    else:
        source = []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in source:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _truncate_pm_card_title(value: str, limit: int = 108) -> str:
    cleaned = str(value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _valid_resolution_mode(value: object) -> str | None:
    normalized = str(value or "").strip()
    if normalized in {"close_only", "close_and_spawn_next"}:
        return normalized
    return None


def _suggest_review_followup(card: PMCard, workspace_policy: dict[str, object]) -> dict[str, str] | None:
    payload = dict(card.payload or {})
    execution = dict(_execution_payload(card) or {})
    latest_result = payload.get("latest_execution_result")
    latest_summary = ""
    if isinstance(latest_result, dict):
        latest_summary = str(latest_result.get("summary") or "").strip()
    haystack = " ".join(
        item
        for item in [
            card.title,
            str(payload.get("reason") or "").strip(),
            str(execution.get("reason") or "").strip(),
            latest_summary,
        ]
        if item
    ).lower()

    templates = workspace_policy.get("followup_templates")
    if isinstance(templates, list):
        for template in templates:
            if not isinstance(template, dict):
                continue
            keywords = [str(item).strip().lower() for item in (template.get("match_any") or []) if str(item).strip()]
            if keywords and any(keyword in haystack for keyword in keywords):
                title = _optional_str(template.get("title"))
                if title:
                    return {
                        "title": title,
                        "reason": _optional_str(template.get("reason")) or f"Follow-on work continues after accepting '{card.title}'.",
                    }

    fallback_title = _optional_str(workspace_policy.get("default_next_title"))
    if fallback_title:
        return {
            "title": fallback_title,
            "reason": _optional_str(workspace_policy.get("default_next_reason")) or f"Follow-on work continues after accepting '{card.title}'.",
        }
    return None


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _fallback_execution_entry(card: PMCard) -> ExecutionQueueEntry:
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    return ExecutionQueueEntry(
        card_id=card.id,
        title=card.title,
        workspace_key=_workspace_key_from_card(card),
        pm_status=card.status or "todo",
        execution_state="queued",
        manager_agent=str(defaults["manager_agent"]),
        target_agent=str(defaults["target_agent"]),
        workspace_agent=_optional_str(defaults.get("workspace_agent")),
        execution_mode=str(defaults["execution_mode"]),
        requested_by=card.owner or "Jean-Claude",
        assigned_runner="codex",
        lane="codex",
        reason="Queued from PM board for Codex execution.",
        source=card.source,
        link_type=card.link_type,
        front_door_agent=_payload_value(card.payload or {}, "front_door_agent"),
        trigger_key=_payload_value(card.payload or {}, "trigger_key"),
        queued_at=card.updated_at,
        last_transition_at=card.updated_at,
    )


def _normalize_card_create_payload(payload: PMCardCreate) -> PMCardCreate:
    card_payload = dict(payload.payload or {})
    execution = dict(card_payload.get("execution") or {})
    source = str(payload.source or "").strip() or None
    workspace_key = _payload_value(card_payload, "workspace_key") or "shared_ops"
    card_payload["workspace_key"] = workspace_key

    if _is_human_front_door_payload(source, card_payload):
        card_payload["front_door_agent"] = "Neo"
        card_payload["source_agent"] = "Neo"
        card_payload["requested_by"] = "Neo"
        if not execution.get("requested_by"):
            execution["requested_by"] = "Neo"

    if execution:
        card_payload["execution"] = execution

    trigger_key = _payload_value(card_payload, "trigger_key")
    if not trigger_key and _is_human_front_door_payload(source, card_payload):
        card_payload["trigger_key"] = _build_trigger_key(
            title=payload.title,
            workspace_key=workspace_key,
            source=source,
            payload=card_payload,
        )
        card_payload["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
        card_payload["trigger_replays"] = int(card_payload.get("trigger_replays") or 0)

    owner = payload.owner or ("Neo" if card_payload.get("front_door_agent") == "Neo" else payload.owner)
    return payload.model_copy(update={"owner": owner, "payload": card_payload, "source": source})


def _is_human_front_door_payload(source: str | None, payload: dict[str, Any]) -> bool:
    front_door_agent = _payload_value(payload, "front_door_agent")
    source_agent = _payload_value(payload, "source_agent")
    trigger_origin = _payload_value(payload, "trigger_origin")
    normalized_source = str(source or "").strip().lower()
    return bool(
        front_door_agent == "Neo"
        or source_agent == "Neo"
        or trigger_origin == "openclaw_thin_trigger"
        or normalized_source.startswith("openclaw:")
    )


def _build_trigger_key(*, title: str, workspace_key: str, source: str | None, payload: dict[str, Any]) -> str:
    return build_pm_trigger_key(title=title, workspace_key=workspace_key, source=source, payload=payload)
