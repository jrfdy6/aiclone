from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import PMCard, PMCardCreate, StandupCreate, StandupEntry, StandupPromotionRequest, StandupPromotionResult, StandupUpdate
from app.services.open_brain_db import get_pool
from app.services import pm_card_service


def list_standups(limit: int = 50, owner: Optional[str] = None, workspace_key: Optional[str] = None) -> List[StandupEntry]:
    pool = get_pool()
    clauses = []
    params = []
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if workspace_key:
        clauses.append("workspace_key = %s")
        params.append(workspace_key)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    query = f"""
        SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
        FROM standups
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_entry(row) for row in rows]


def create_standup(payload: StandupCreate) -> StandupEntry:
    pool = get_pool()
    entry_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO standups (id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                """,
                (
                    entry_id,
                    payload.owner,
                    payload.workspace_key,
                    payload.status,
                    payload.blockers,
                    payload.commitments,
                    payload.needs,
                    payload.source,
                    payload.conversation_path,
                    Json(payload.payload or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_entry(row)


def update_standup(entry_id: str, payload: StandupUpdate) -> Optional[StandupEntry]:
    pool = get_pool()
    fields = []
    values = []
    if payload.workspace_key is not None:
        fields.append("workspace_key = %s")
        values.append(payload.workspace_key)
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
    if payload.blockers is not None:
        fields.append("blockers = %s")
        values.append(payload.blockers)
    if payload.commitments is not None:
        fields.append("commitments = %s")
        values.append(payload.commitments)
    if payload.needs is not None:
        fields.append("needs = %s")
        values.append(payload.needs)
    if payload.source is not None:
        fields.append("source = %s")
        values.append(payload.source)
    if payload.conversation_path is not None:
        fields.append("conversation_path = %s")
        values.append(payload.conversation_path)
    if payload.payload is not None:
        fields.append("payload = %s")
        values.append(Json(payload.payload))

    if not fields:
        return get_standup(entry_id)

    values.append(entry_id)
    query = f"""
        UPDATE standups
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_entry(row) if row else None


def get_standup(entry_id: str) -> Optional[StandupEntry]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                FROM standups
                WHERE id = %s
                """,
                (entry_id,),
            )
            row = cur.fetchone()
    return _row_to_entry(row) if row else None


def promote_standup(payload: StandupPromotionRequest) -> StandupPromotionResult:
    discussion = list(payload.discussion_rounds or [])
    if not discussion:
        if payload.jean_claude_note:
            discussion.append({"round": 1, "speaker": "Jean-Claude", "role": "workspace-president", "note": payload.jean_claude_note})
        if payload.neo_note:
            discussion.append({"round": 2, "speaker": "Neo", "role": "system-operator", "note": payload.neo_note})
        if payload.yoda_note:
            discussion.append({"round": 3, "speaker": "Yoda", "role": "strategic-overlay", "note": payload.yoda_note})

    standup = create_standup(
        StandupCreate(
            owner=payload.owner,
            workspace_key=payload.workspace_key,
            status="completed",
            blockers=payload.blockers,
            commitments=payload.commitments,
            needs=payload.needs,
            source=payload.source,
            conversation_path=payload.conversation_path,
            payload={
                "standup_kind": payload.standup_kind,
                "summary": payload.summary,
                "agenda": payload.agenda,
                "decisions": payload.decisions,
                "owners": payload.owners,
                "artifact_deltas": payload.artifact_deltas,
                "pm_snapshot": payload.pm_snapshot,
                "participants": payload.participants,
                "source_paths": payload.source_paths,
                "memory_promotions": payload.memory_promotions,
                "discussion": discussion,
                "prep_id": payload.prep_id,
                "recommendation_path": payload.recommendation_path,
                "pm_recommendation_count": len(payload.pm_updates),
            },
        )
    )

    created_cards: List[PMCard] = []
    existing_cards: List[PMCard] = []
    source_signature = f"standup-prep:{payload.prep_id}" if payload.prep_id else f"standup:{standup.id}"

    for update in payload.pm_updates:
        existing = pm_card_service.find_card_by_signature(update.title, source_signature)
        if existing is None:
            existing = pm_card_service.find_active_card_by_title(update.title, update.workspace_key or payload.workspace_key)
        if existing:
            existing_cards.append(existing)
            continue

        execution_defaults = pm_card_service.execution_defaults_for_workspace(update.workspace_key or payload.workspace_key)
        card_payload = dict(update.payload or {})
        card_payload.update(
            {
                "workspace_key": update.workspace_key or payload.workspace_key,
                "scope": update.scope,
                "source_agent": update.owner_agent,
                "created_from_standup_id": standup.id,
                "created_from_standup_kind": payload.standup_kind,
                "created_from_standup_workspace": payload.workspace_key,
                "participants": payload.participants,
                "reason": update.reason,
                "execution": {
                    "lane": "codex",
                    "state": "ready",
                    "manager_agent": execution_defaults["manager_agent"],
                    "target_agent": execution_defaults["target_agent"],
                    "workspace_agent": execution_defaults.get("workspace_agent"),
                    "execution_mode": execution_defaults["execution_mode"],
                    "requested_by": payload.owner,
                    "assigned_runner": "codex",
                    "reason": update.reason,
                    "last_transition_at": datetime.now(timezone.utc).isoformat(),
                    "source": "standup_promotion",
                },
            }
        )
        created_cards.append(
            pm_card_service.create_card(
                PMCardCreate(
                    title=update.title,
                    owner=_display_agent_name(update.owner_agent),
                    status=update.status or "todo",
                    source=source_signature,
                    link_type="standup",
                    link_id=standup.id,
                    payload=card_payload,
                )
            )
        )

    return StandupPromotionResult(standup=standup, created_cards=created_cards, existing_cards=existing_cards)


def _row_to_entry(row: dict) -> StandupEntry:
    if not row:
        raise ValueError("Standup row is empty")
    return StandupEntry(
        id=str(row["id"]),
        owner=row.get("owner") or "unknown",
        workspace_key=row.get("workspace_key") or "shared_ops",
        status=row.get("status"),
        blockers=row.get("blockers") or [],
        commitments=row.get("commitments") or [],
        needs=row.get("needs") or [],
        source=row.get("source"),
        conversation_path=row.get("conversation_path"),
        payload=row.get("payload") or {},
        created_at=row.get("created_at"),
    )


def _display_agent_name(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "jean-claude":
        return "Jean-Claude"
    if normalized == "neo":
        return "Neo"
    if normalized == "yoda":
        return "Yoda"
    return value
