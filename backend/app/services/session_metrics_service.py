from __future__ import annotations

from typing import List

from psycopg.rows import dict_row

from app.models import ModelDistributionBucket, SessionMetrics, SessionRow, SessionTotals
from app.services.open_brain_db import get_pool


def _empty() -> SessionMetrics:
    return SessionMetrics(
        totals=SessionTotals(),
        model_distribution=[],
        top_sessions=[],
        sessions=[],
    )


def fetch_metrics(limit_top: int = 5, limit_rows: int = 50) -> SessionMetrics:
    try:
        pool = get_pool()
    except Exception:
        return _empty()

    totals = SessionTotals()
    model_distribution: List[ModelDistributionBucket] = []
    top_sessions: List[SessionRow] = []
    sessions: List[SessionRow] = []

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(COUNT(DISTINCT agent_name) FILTER (WHERE last_message_at >= NOW() - INTERVAL '24 HOURS'), 0) AS active_agents,
                    COALESCE(COUNT(DISTINCT model) FILTER (WHERE model IS NOT NULL), 0) AS models_deployed,
                    COALESCE(COUNT(*) FILTER (WHERE status = 'error' AND last_message_at >= NOW() - INTERVAL '24 HOURS'), 0) AS errors_24h
                FROM session_metrics
                """
            )
            row = cur.fetchone() or {}
            totals = SessionTotals(
                total_tokens=int(row.get("total_tokens") or 0),
                active_agents=int(row.get("active_agents") or 0),
                models_deployed=int(row.get("models_deployed") or 0),
                errors_24h=int(row.get("errors_24h") or 0),
            )

            cur.execute(
                """
                SELECT model, COALESCE(SUM(total_tokens), 0) AS tokens
                FROM session_metrics
                WHERE model IS NOT NULL
                GROUP BY model
                ORDER BY tokens DESC
                """
            )
            model_distribution = [
                ModelDistributionBucket(model=row["model"], tokens=int(row.get("tokens") or 0))
                for row in cur.fetchall() or []
            ]

            cur.execute(
                """
                SELECT id, agent_name, model, status, total_tokens, last_message_at, metadata
                FROM session_metrics
                ORDER BY total_tokens DESC NULLS LAST
                LIMIT %s
                """,
                (limit_top,),
            )
            top_sessions = [_row_to_session(row) for row in cur.fetchall() or []]

            cur.execute(
                """
                SELECT id, agent_name, model, status, total_tokens, last_message_at, metadata
                FROM session_metrics
                ORDER BY COALESCE(last_message_at, updated_at, created_at) DESC NULLS LAST
                LIMIT %s
                """,
                (limit_rows,),
            )
            sessions = [_row_to_session(row) for row in cur.fetchall() or []]

    return SessionMetrics(
        totals=totals,
        model_distribution=model_distribution,
        top_sessions=top_sessions,
        sessions=sessions,
    )


def _row_to_session(row: dict) -> SessionRow:
    return SessionRow(
        id=str(row.get("id")),
        agent_name=row.get("agent_name") or "unknown",
        model=row.get("model"),
        status=row.get("status") or "active",
        total_tokens=int(row.get("total_tokens") or 0),
        last_message_at=row.get("last_message_at"),
        metadata=row.get("metadata") or {},
    )
