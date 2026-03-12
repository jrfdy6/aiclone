from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from psycopg.rows import dict_row

from app.services.open_brain_db import get_pool


def _base_response() -> Dict[str, Any]:
    return {
        "database_connected": False,
        "captures": {
            "total": 0,
            "last_24h": 0,
            "last_7d": 0,
        },
        "vectors": {
            "total": 0,
            "with_expiry": 0,
            "overdue": 0,
            "last_refresh_at": None,
        },
        "recent_captures": [],
    }


def fetch_metrics(limit_recent: int = 5) -> Dict[str, Any]:
    response = _base_response()

    try:
        pool = get_pool()
    except Exception:
        # Database is not configured; return zeros so the UI can still render
        return response

    response["database_connected"] = True

    try:
        with pool.connection() as conn:
            # Capture aggregates
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '24 HOURS' THEN 1 ELSE 0 END), 0) AS last_24h,
                        COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '7 DAYS' THEN 1 ELSE 0 END), 0) AS last_7d
                    FROM knowledge_capture
                    """
                )
                row = cur.fetchone()
                if row:
                    response["captures"].update(
                        {
                            "total": int(row["total"] or 0),
                            "last_24h": int(row["last_24h"] or 0),
                            "last_7d": int(row["last_7d"] or 0),
                        }
                    )

                # Recent captures with chunk counts
                cur.execute(
                    """
                    SELECT
                        kc.id,
                        kc.source,
                        kc.topic,
                        kc.importance,
                        kc.markdown_path,
                        kc.created_at,
                        COUNT(mv.id) AS chunk_count
                    FROM knowledge_capture kc
                    LEFT JOIN memory_vectors mv ON mv.capture_id = kc.id
                    GROUP BY kc.id
                    ORDER BY kc.created_at DESC
                    LIMIT %s
                    """,
                    (limit_recent,),
                )
                rows = cur.fetchall() or []
                response["recent_captures"] = [
                    {
                        "id": item["id"],
                        "source": item.get("source"),
                        "topics": item.get("topic") or [],
                        "importance": item.get("importance"),
                        "markdown_path": item.get("markdown_path"),
                        "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
                        "chunk_count": int(item.get("chunk_count") or 0),
                    }
                    for item in rows
                ]

                # Vector aggregates
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COALESCE(SUM(CASE WHEN expires_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS with_expiry,
                        COALESCE(SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 ELSE 0 END), 0) AS overdue,
                        MAX(last_refreshed_at) AS last_refresh_at
                    FROM memory_vectors
                    """
                )
                row = cur.fetchone()
                if row:
                    response["vectors"].update(
                        {
                            "total": int(row["total"] or 0),
                            "with_expiry": int(row["with_expiry"] or 0),
                            "overdue": int(row["overdue"] or 0),
                            "last_refresh_at": row["last_refresh_at"].isoformat() if row.get("last_refresh_at") else None,
                        }
                    )
    except Exception:
        # Swallow errors so telemetry endpoint never breaks prod dashboards
        return response

    return response
