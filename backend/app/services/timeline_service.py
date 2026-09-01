from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from psycopg.rows import dict_row

from app.models import TimelineEvent
from app.services.open_brain_db import get_pool
from app.services.standup_truth_service import is_verified_meeting_record
from app.utils.ai_clone_clock import resolve_payload_observation, utc_iso


_SEMANTIC_OBSERVATION_SOURCES = {
    "semantic_observed_at",
    "semantic_cycle_observation",
}


def _aware_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coordination_event(row: dict[str, Any]) -> TimelineEvent:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    workspace_key = str(row.get("workspace_key") or "shared_ops")
    owner = str(row.get("owner") or workspace_key)
    persisted_at = _aware_utc(row.get("created_at"))
    observed_at, observation_source = resolve_payload_observation(
        payload,
        created_at=row.get("created_at"),
    )
    has_semantic_observation = (
        observed_at is not None
        and observation_source in _SEMANTIC_OBSERVATION_SOURCES
    )
    bounded_payload = {
        "workspace_key": workspace_key,
        "record_kind": payload.get("record_kind"),
        "meeting_held": payload.get("meeting_held"),
        "evaluation_only": payload.get("evaluation_only"),
        "observation_source": observation_source,
        "observed_at": utc_iso(observed_at) if has_semantic_observation else None,
        "persisted_at": utc_iso(persisted_at),
    }
    source = str(row.get("source") or row.get("status") or "")
    event_id = str(row.get("id") or "")

    if (
        payload.get("record_kind") == "workspace_cycle_plan"
        or payload.get("evaluation_only") is True
        or payload.get("meeting_held") is False
    ):
        return TimelineEvent(
            id=f"cycle_evaluation::{event_id}",
            type="workspace_cycle_evaluation",
            title=f"Workspace cycle evaluation → {owner}",
            occurred_at=observed_at if has_semantic_observation else persisted_at,
            source=source,
            payload={
                **bounded_payload,
                "timestamp_meaning": (
                    "workspace_evaluation_observed_at"
                    if has_semantic_observation
                    else "persistence_created_at_reference_only"
                ),
            },
        )

    structurally_meeting = (
        payload.get("record_kind") == "standup"
        and payload.get("meeting_held") is True
        and payload.get("evaluation_only") is False
        and isinstance(payload.get("meeting_evidence"), dict)
    )
    verified_meeting = structurally_meeting and is_verified_meeting_record(
        payload,
        source=row.get("source"),
        workspace_key=workspace_key,
    )
    if verified_meeting and has_semantic_observation:
        return TimelineEvent(
            id=f"standup::{event_id}",
            type="standup",
            title=f"Verified standup meeting → {owner}",
            occurred_at=observed_at,
            source=source,
            payload={**bounded_payload, "timestamp_meaning": "meeting_observed_at"},
        )
    if verified_meeting:
        return TimelineEvent(
            id=f"standup_reference::{event_id}",
            type="standup_reference",
            title=f"Stored verified meeting; observation unavailable → {owner}",
            occurred_at=persisted_at,
            source=source,
            payload={
                **bounded_payload,
                "timestamp_meaning": "persistence_created_at_reference_only",
            },
        )
    return TimelineEvent(
        id=f"coordination_record::{event_id}",
        type="unverified_standup_record",
        title=f"Stored unverified coordination record → {owner}",
        occurred_at=persisted_at,
        source=source,
        payload={
            **bounded_payload,
            "timestamp_meaning": "persistence_created_at_reference_only",
        },
    )


def list_events(limit: int = 50) -> List[TimelineEvent]:
    pool = get_pool()
    events: List[TimelineEvent] = []

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Persona deltas
            cur.execute(
                """
                SELECT id, persona_target AS title, created_at AS occurred_at, status, metadata
                FROM persona_deltas
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            for row in cur.fetchall() or []:
                events.append(
                    TimelineEvent(
                        id=f"persona::{row['id']}",
                        type="persona",
                        title=f"Persona update → {row.get('title')}",
                        occurred_at=row.get("occurred_at"),
                        source=row.get("status") or "draft",
                        payload=row.get("metadata") or {},
                    )
                )

            # Standups
            cur.execute(
                """
                SELECT id, owner, workspace_key, created_at, status, source, payload
                FROM standups
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            for row in cur.fetchall() or []:
                events.append(_coordination_event(row))

            # PM cards
            cur.execute(
                """
                SELECT id, title, updated_at, status, source
                FROM pm_cards
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            for row in cur.fetchall() or []:
                events.append(
                    TimelineEvent(
                        id=f"pm::{row['id']}",
                        type="pm_card",
                        title=row.get("title") or "Untitled card",
                        occurred_at=row.get("updated_at"),
                        source=row.get("source") or row.get("status") or "pm",
                        payload={"status": row.get("status")},
                    )
                )

    events.sort(key=lambda event: _aware_utc(event.occurred_at), reverse=True)
    return events[:limit]
