from __future__ import annotations

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
from app.services.trigger_identity_service import build_pm_trigger_key
from app.services.workspace_runtime_contract_service import execution_defaults_for_workspace as runtime_execution_defaults_for_workspace


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

    status, card_payload = build_card_action_update(
        card,
        action=payload.action,
        requested_by=payload.requested_by,
        reason=payload.reason,
        resolution_mode=payload.resolution_mode,
        next_title=payload.next_title,
        next_reason=payload.next_reason,
    )
    updated = update_card(card_id, PMCardUpdate(status=status, payload=card_payload))
    if updated is None:
        return None
    successor_card: PMCard | None = None
    if payload.action == "approve" and payload.resolution_mode == "close_and_spawn_next":
        successor_card = _create_resolution_successor_card(
            card,
            requested_by=payload.requested_by,
            next_title=payload.next_title,
            next_reason=payload.next_reason,
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
        refreshed = update_card(card_id, PMCardUpdate(status=updated.status, payload=updated_payload))
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
    successor_payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "reason": successor_reason,
        "source_agent": requested_by,
        "front_door_agent": requested_by,
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

    return create_card(
        PMCardCreate(
            title=cleaned_title,
            owner=card.owner or execution_defaults_for_workspace(workspace_key)["manager_agent"],
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
        effective_execution = {
            **defaults,
            "lane": "codex",
            "state": "ready",
            "requested_by": _payload_value(payload, "source_agent") or card.owner or defaults["manager_agent"],
            "assigned_runner": "codex",
            "reason": _payload_value(payload, "reason")
            or (
                "Standup promoted this card and it is ready for Jean-Claude to open a direct SOP."
                if defaults["execution_mode"] == "direct"
                else "Standup promoted this card and it is ready for Jean-Claude to open a delegated SOP for the workspace agent."
            ),
            "last_transition_at": _datetime_to_iso(card.updated_at),
        }
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


def _execution_payload(card: PMCard) -> dict | None:
    payload = card.payload or {}
    execution = payload.get("execution")
    return dict(execution) if isinstance(execution, dict) else None


def execution_defaults_for_workspace(workspace_key: str) -> dict[str, object]:
    return runtime_execution_defaults_for_workspace(workspace_key)


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


def _is_closed_pm_status(status: Optional[str]) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {"done", "closed", "cancelled"}


def _is_execution_candidate(card: PMCard) -> bool:
    if _is_closed_pm_status(card.status):
        return False
    payload = card.payload or {}
    return bool(
        card.link_type == "standup"
        or (card.source or "").startswith("standup-prep:")
        or payload.get("created_from_standup_id")
    )


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
    return value if isinstance(value, str) and value.strip() else None


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
