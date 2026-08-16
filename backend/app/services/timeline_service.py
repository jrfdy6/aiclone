from __future__ import annotations

from typing import List

from psycopg.rows import dict_row

from app.models import TimelineEvent
from app.services.open_brain_db import get_pool


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
                SELECT id, owner, created_at, status
                FROM standups
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            for row in cur.fetchall() or []:
                events.append(
                    TimelineEvent(
                        id=f"standup::{row['id']}",
                        type="standup",
                        title=f"Standup → {row.get('owner')}",
                        occurred_at=row.get("created_at"),
                        source=row.get("status") or "",
                        payload={},
                    )
                )

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

    events.sort(key=lambda event: event.occurred_at or 0, reverse=True)
    return events[:limit]
