from __future__ import annotations

from typing import Any

from app.security.execution_authorization import execution_signing_configured
from app.services.open_brain_db import database_configured, get_pool
from app.services.pm_worker_readiness_service import (
    integrated_action_worker_readiness,
    integrated_actions_worker_readiness,
)


READINESS_SCHEMA = "integrated_controller_queue_readiness/v1"
QUEUE_BACKED_ACTIONS = frozenset(
    {
        "canonical_decision_create",
        "canonical_decision_transition",
        "integrated_content_learning",
        "integrated_content_manual_edit",
        "integrated_content_variant",
        "integrated_owner_post",
        "integrated_persona_reversal",
    }
)
SIGNED_JOB_AUTHORIZATION_UNAVAILABLE = "signed_job_authorization_unavailable"
CONTROLLER_DATABASE_UNAVAILABLE = "controller_database_unavailable"
CONTROLLER_QUEUE_UNAVAILABLE = "controller_queue_unavailable"
CONTROLLER_WORKER_UNAVAILABLE = "controller_worker_unavailable"

READINESS_MESSAGES = {
    SIGNED_JOB_AUTHORIZATION_UNAVAILABLE: (
        "This action is unavailable because signed local execution is not configured."
    ),
    CONTROLLER_DATABASE_UNAVAILABLE: (
        "This action is unavailable because the durable controller database is not ready."
    ),
    CONTROLLER_QUEUE_UNAVAILABLE: (
        "This action is temporarily unavailable because the signed local-action queue is not ready."
    ),
    CONTROLLER_WORKER_UNAVAILABLE: (
        "This action is temporarily unavailable because the local execution worker is not ready."
    ),
}


def _unavailable(reason_code: str) -> dict[str, Any]:
    return {
        "schema_version": READINESS_SCHEMA,
        "ready": False,
        "reason_code": reason_code,
        "message": READINESS_MESSAGES[reason_code],
    }


def integrated_controller_queue_readiness(
    action: str | None = None,
) -> dict[str, Any]:
    """Return readiness for one exact action or the full browser controller set."""

    try:
        signing_ready = execution_signing_configured()
    except Exception:
        signing_ready = False
    if not signing_ready:
        return _unavailable(SIGNED_JOB_AUTHORIZATION_UNAVAILABLE)
    try:
        database_ready = database_configured()
    except Exception:
        database_ready = False
    if not database_ready:
        return _unavailable(CONTROLLER_DATABASE_UNAVAILABLE)
    try:
        pool = get_pool()
        with pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('pm_cards') IS NOT NULL")
                row = cursor.fetchone()
    except Exception:
        return _unavailable(CONTROLLER_DATABASE_UNAVAILABLE)
    if not row or row[0] is not True:
        return _unavailable(CONTROLLER_QUEUE_UNAVAILABLE)
    try:
        if action is None:
            worker = integrated_actions_worker_readiness(
                QUEUE_BACKED_ACTIONS,
                _pool=pool,
            )
        else:
            worker = integrated_action_worker_readiness(action, _pool=pool)
    except Exception:
        return _unavailable(CONTROLLER_WORKER_UNAVAILABLE)
    if worker.get("ready") is not True:
        return _unavailable(CONTROLLER_WORKER_UNAVAILABLE)
    return {
        "schema_version": READINESS_SCHEMA,
        "ready": True,
        "reason_code": None,
        "message": None,
    }
