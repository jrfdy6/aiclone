from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import uuid4

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
    if action == "approve" and _is_host_action_required_card(card):
        host_action_completion = _build_host_action_completion_payload(
            card,
            requested_by=requested_by,
            completion_note=reason,
            proof_items=proof_items,
        )
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
    payload["pm_review_policy"] = _build_client_review_policy(card)
    return card.model_copy(update={"payload": payload})


def decorate_cards_for_client(cards: List[PMCard]) -> List[PMCard]:
    return [decorate_card_for_client(card) or card for card in cards]


def build_execution_queue_entry(card: PMCard) -> Optional[ExecutionQueueEntry]:
    if _is_closed_pm_status(card.status):
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
    auto_resolve_policy = _auto_resolve_review_policy(card)
    attention_class = "fyi"
    attention_reason = "This card is visible for context, but it does not currently need your judgment."
    recommended_resolution_mode: str | None = None
    suggested_next_title: str | None = None
    suggested_next_reason: str | None = None

    if _is_closed_pm_status(card.status):
        attention_reason = "This card is already closed and kept here as traceable history."
    elif owner_gate:
        attention_class = "needs_owner"
        attention_reason = "This card is an explicit owner gate and should wait for your call."
    elif bool(execution.get("manager_attention_required")) or normalized_status in {"blocked", "failed"}:
        attention_class = "needs_owner"
        attention_reason = "This lane is blocked or flagged for manager attention and needs a human decision."
    elif host_action_required:
        attention_class = "needs_host"
        attention_reason = "This card requires a host action outside the runtime before the loop can fully close."
    elif auto_resolve_policy is not None:
        attention_class = "stale"
        attention_reason = auto_resolve_policy["reason"]
    elif normalized_status == "review":
        interrupt_policy = str(workspace_policy.get("interrupt_policy") or "manual_review")
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
        "repaired_count": len(repaired),
        "repaired": repaired,
    }


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
) -> PMCard:
    workspace_key = _workspace_key_from_card(source_card)
    steps = _dedupe_nonempty_strings(host_action_required.get("steps"))
    summary = _optional_str(host_action_required.get("summary")) or (steps[0] if steps else f"Complete host action for {source_card.title}")
    proof_required = _dedupe_nonempty_strings(host_action_required.get("proof_required"))
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
            "source_card_id": source_card.id,
            "source_card_title": source_card.title,
            "source_result_id": _optional_str(host_action_required.get("source_result_id")),
            "source_result_summary": _optional_str(host_action_required.get("source_result_summary")),
            "detected_from": _optional_str(host_action_required.get("detected_from")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        # These fields make the trigger key stable without turning the card into an execution candidate.
        "instructions": steps,
        "acceptance_criteria": proof_required,
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
            payload=payload,
        )
    )


def _build_host_action_completion_payload(
    card: PMCard,
    *,
    requested_by: str,
    completion_note: str | None,
    proof_items: list[str] | None,
) -> dict[str, Any]:
    payload = dict(card.payload or {})
    host_action_required = dict(payload.get("host_action_required") or {})
    required = _dedupe_nonempty_strings(host_action_required.get("proof_required"))
    provided = _dedupe_nonempty_strings(proof_items or [])
    note = _optional_str(completion_note)

    if note is None:
        raise ValueError("Closing a host action card requires a completion note.")
    if required and len(provided) < len(required):
        raise ValueError(
            f"Closing this host action card requires at least {len(required)} proof item(s) because explicit proof was requested."
        )

    return {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_by": requested_by,
        "completion_note": note,
        "proof_items": provided,
        "proof_required": required,
        "source_card_id": _optional_str(host_action_required.get("source_card_id")),
        "source_card_title": _optional_str(host_action_required.get("source_card_title")),
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
