from __future__ import annotations

from typing import Iterable, List, Optional

try:
    from psycopg.errors import UndefinedTable
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover
    UndefinedTable = Exception  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    Json = None  # type: ignore[assignment]

from app.models.automations import AutomationRun
from app.services.automation_service import automation_source_of_truth, list_automation_runs


def _get_pool():
    from app.services.open_brain_db import get_pool

    return get_pool()


def list_runs(limit: int = 50, automation_id: Optional[str] = None) -> List[AutomationRun]:
    try:
        pool = _get_pool()
        clauses = []
        params = []
        if automation_id:
            clauses.append("automation_id = %s")
            params.append(automation_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        query = f"""
            SELECT id, automation_id, automation_name, source, runtime, status, delivered, delivery_channel,
                   delivery_target, run_at, finished_at, duration_ms, error, owner_agent, session_target,
                   scope, workspace_key, action_required, metadata
            FROM automation_runs
            {where}
            ORDER BY run_at DESC NULLS LAST, created_at DESC
            LIMIT %s
        """
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                rows = cur.fetchall() or []
        return [_row_to_run(row) for row in rows]
    except UndefinedTable:
        return list_automation_runs(limit=limit)
    except Exception:
        return list_automation_runs(limit=limit)


def sync_openclaw_run_mirror(limit: Optional[int] = None) -> int:
    if "openclaw_jobs_json" not in automation_source_of_truth():
        return 0

    runs = list_automation_runs(limit=limit)
    if not runs:
        return 0

    return upsert_runs(runs)


def upsert_runs(runs: Iterable[AutomationRun]) -> int:
    mirrored_runs = list(runs)
    if not mirrored_runs:
        return 0

    try:
        pool = _get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for run in mirrored_runs:
                    cur.execute(
                        """
                        INSERT INTO automation_runs (
                            id, automation_id, automation_name, source, runtime, status, delivered,
                            delivery_channel, delivery_target, run_at, finished_at, duration_ms, error,
                            owner_agent, session_target, scope, workspace_key, action_required, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            automation_id = EXCLUDED.automation_id,
                            automation_name = EXCLUDED.automation_name,
                            source = EXCLUDED.source,
                            runtime = EXCLUDED.runtime,
                            status = EXCLUDED.status,
                            delivered = EXCLUDED.delivered,
                            delivery_channel = EXCLUDED.delivery_channel,
                            delivery_target = EXCLUDED.delivery_target,
                            run_at = EXCLUDED.run_at,
                            finished_at = EXCLUDED.finished_at,
                            duration_ms = EXCLUDED.duration_ms,
                            error = EXCLUDED.error,
                            owner_agent = EXCLUDED.owner_agent,
                            session_target = EXCLUDED.session_target,
                            scope = EXCLUDED.scope,
                            workspace_key = EXCLUDED.workspace_key,
                            action_required = EXCLUDED.action_required,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        """,
                        (
                            run.id,
                            run.automation_id,
                            run.automation_name,
                            run.source,
                            run.runtime,
                            run.status,
                            run.delivered,
                            run.delivery_channel,
                            run.delivery_target,
                            run.run_at,
                            run.finished_at,
                            run.duration_ms,
                            run.error,
                            run.owner_agent,
                            run.session_target,
                            run.scope,
                            run.workspace_key,
                            run.action_required,
                            Json(run.metadata or {}) if Json else (run.metadata or {}),
                        ),
                    )
            conn.commit()
        return len(mirrored_runs)
    except Exception:
        return 0


def _row_to_run(row: dict) -> AutomationRun:
    return AutomationRun(
        id=str(row["id"]),
        automation_id=str(row.get("automation_id") or ""),
        automation_name=str(row.get("automation_name") or ""),
        source=str(row.get("source") or "static_registry"),
        runtime=row.get("runtime"),
        status=str(row.get("status") or "unknown"),
        delivered=row.get("delivered"),
        delivery_channel=row.get("delivery_channel"),
        delivery_target=row.get("delivery_target"),
        run_at=row.get("run_at"),
        finished_at=row.get("finished_at"),
        duration_ms=row.get("duration_ms"),
        error=row.get("error"),
        owner_agent=row.get("owner_agent"),
        session_target=row.get("session_target"),
        scope=str(row.get("scope") or "shared_ops"),
        workspace_key=row.get("workspace_key"),
        action_required=bool(row.get("action_required")),
        metadata=row.get("metadata") or {},
    )
