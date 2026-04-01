from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import ExecutionQueueEntry, PMCard, PMCardCreate, PMCardDispatchRequest, PMCardDispatchResult, PMCardUpdate
from app.services.open_brain_db import get_pool
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
                    payload.title,
                    payload.owner,
                    payload.status or "todo",
                    payload.source,
                    payload.link_type,
                    payload.link_id,
                    payload.due_at,
                    Json(payload.payload or {}),
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
            "history": history[-12:],
        }
    )
    card_payload["execution"] = current_execution

    updated = update_card(card_id, PMCardUpdate(payload=card_payload))
    if updated is None:
        return None
    return PMCardDispatchResult(card=updated, queue_entry=build_execution_queue_entry(updated) or _fallback_execution_entry(updated))


def build_execution_queue_entry(card: PMCard) -> Optional[ExecutionQueueEntry]:
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


def _is_execution_candidate(card: PMCard) -> bool:
    if (card.status or "").lower() == "done":
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
        queued_at=card.updated_at,
        last_transition_at=card.updated_at,
    )
