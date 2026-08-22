from __future__ import annotations

from typing import Iterable, List, Optional

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover
    dict_row = None  # type: ignore[assignment]
    Json = None  # type: ignore[assignment]

from app.models.automations import AutomationRun
from app.services.automation_service import is_codex_run, list_automation_runs
from app.services.railway_retention_service import RETENTION_LOCK_ID

CODEX_RUN_SOURCES = ["codex_launchd_registry", "local_launchd_registry"]
CODEX_RUN_RUNTIMES = ["launchd", "codex_exec"]


class AutomationRunMirrorError(RuntimeError):
    """Raised when Railway cannot durably store a non-empty run mirror."""


def _get_pool():
    from app.services.open_brain_db import get_pool

    return get_pool()


def list_runs(limit: int = 50, automation_id: Optional[str] = None) -> List[AutomationRun]:
    try:
        pool = _get_pool()
        clauses = ["(source = ANY(%s) OR runtime = ANY(%s))"]
        params = [CODEX_RUN_SOURCES, CODEX_RUN_RUNTIMES]
        if automation_id:
            clauses.append("automation_id = %s")
            params.append(automation_id)
        where = f"WHERE {' AND '.join(clauses)}"
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
    except Exception:
        runs = list_automation_runs()
        if automation_id:
            runs = [run for run in runs if run.automation_id == automation_id]
        return runs[:limit]


def sync_codex_run_ledger(limit: Optional[int] = None) -> int:
    """Upsert the local Codex JSONL ledger into the backend run mirror."""

    runs = list_automation_runs(limit=limit)
    if not runs:
        return 0

    return upsert_runs(runs)


def upsert_runs(runs: Iterable[AutomationRun]) -> int:
    """Acknowledge every valid mirror row, including retained replay suppressions."""

    mirrored_runs = [run for run in runs if is_codex_run(run)]
    if not mirrored_runs:
        return 0

    try:
        pool = _get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (RETENTION_LOCK_ID,))
                acknowledged = 0
                for run in mirrored_runs:
                    cur.execute(
                        """SELECT 1 FROM automation_run_daily_receipts
                        WHERE source_row_ids @> jsonb_build_array(%s::text) LIMIT 1""",
                        (run.id,),
                    )
                    if cur.fetchone():
                        acknowledged += 1
                        continue
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
                    acknowledged += 1
            conn.commit()
        return acknowledged
    except Exception as exc:
        raise AutomationRunMirrorError("Automation run mirror storage is unavailable.") from exc


def _row_to_run(row: dict) -> AutomationRun:
    return AutomationRun(
        id=str(row["id"]),
        automation_id=str(row.get("automation_id") or ""),
        automation_name=str(row.get("automation_name") or ""),
        source=str(row.get("source") or "local_launchd_registry"),
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
