from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.rows import dict_row


PM_WORKER_HEARTBEAT_SCHEMA = "pm_worker_heartbeat/v1"
PM_WORKER_HEARTBEAT_RECEIPT_SCHEMA = "pm_worker_heartbeat_receipt/v1"
PM_WORKER_READINESS_SCHEMA = "pm_worker_readiness/v1"
PM_WORKER_RUNNER_ID = "codex-workspace-execution"
PM_WORKER_LEASE_INTERVAL_MULTIPLIER = 2.5

INTEGRATED_ACTION_CAPABILITIES = frozenset(
    {
        "integrated_content_variant",
        "integrated_owner_post",
        "integrated_content_manual_edit",
        "integrated_content_learning",
        "integrated_persona_reversal",
        "canonical_decision_create",
        "canonical_decision_transition",
    }
)

WorkerCapability = Literal[
    "integrated_content_variant",
    "integrated_owner_post",
    "integrated_content_manual_edit",
    "integrated_content_learning",
    "integrated_persona_reversal",
    "canonical_decision_create",
    "canonical_decision_transition",
]


class PMWorkerHeartbeatRequest(BaseModel):
    """Bounded liveness update from the authenticated local PM runner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_worker_heartbeat/v1"] = PM_WORKER_HEARTBEAT_SCHEMA
    worker_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    runner_id: Literal["codex-workspace-execution"] = PM_WORKER_RUNNER_ID
    heartbeat_kind: Literal["startup", "poll"]
    capabilities: list[WorkerCapability] = Field(min_length=1, max_length=16)
    poll_interval_seconds: int = Field(default=60, ge=15, le=120)
    queue_depth: int | None = Field(default=None, ge=0, le=1_000)

    @model_validator(mode="after")
    def validate_heartbeat(self) -> "PMWorkerHeartbeatRequest":
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("Worker heartbeat capabilities must be unique.")
        self.capabilities = sorted(self.capabilities)
        if self.heartbeat_kind == "poll" and self.queue_depth is None:
            raise ValueError("Poll heartbeats require queue_depth, including zero for an empty queue.")
        if self.heartbeat_kind == "startup" and self.queue_depth is not None:
            raise ValueError("Startup heartbeats must not include queue_depth.")
        return self


class PMWorkerHeartbeatReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_worker_heartbeat_receipt/v1"] = PM_WORKER_HEARTBEAT_RECEIPT_SCHEMA
    recorded: Literal[True] = True
    worker_id: str
    runner_id: Literal["codex-workspace-execution"]
    heartbeat_kind: Literal["startup", "poll"]
    capabilities: list[WorkerCapability]
    poll_interval_seconds: int
    queue_depth: int | None = None
    process_started_at: datetime
    last_seen_at: datetime
    last_poll_at: datetime | None = None
    lease_expires_at: datetime | None = None


class PMWorkerHeartbeatStorageUnavailable(RuntimeError):
    """Raised when Railway cannot durably upsert the compact worker lease."""


def _now_utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Worker heartbeat timestamps must be timezone-aware.")
    return current.astimezone(timezone.utc)


def _lease_seconds(poll_interval_seconds: int) -> int:
    return int(math.ceil(int(poll_interval_seconds) * PM_WORKER_LEASE_INTERVAL_MULTIPLIER))


def _database_configured() -> bool:
    from app.services.open_brain_db import database_configured

    return database_configured()


def _get_pool():
    from app.services.open_brain_db import get_pool

    return get_pool()


def _mapping_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise PMWorkerHeartbeatStorageUnavailable("Worker heartbeat storage returned an invalid row.")
    return dict(row)


def record_pm_worker_heartbeat(
    request: PMWorkerHeartbeatRequest | dict[str, Any],
    *,
    now: datetime | None = None,
    _pool: Any | None = None,
) -> PMWorkerHeartbeatReceipt:
    """Upsert exactly one current heartbeat/lease row for a worker identity."""

    heartbeat = PMWorkerHeartbeatRequest.model_validate(request)
    observed_at = _now_utc(now)
    last_poll_at = observed_at if heartbeat.heartbeat_kind == "poll" else None
    lease_expires_at = (
        observed_at
        + timedelta(seconds=_lease_seconds(heartbeat.poll_interval_seconds))
        if heartbeat.heartbeat_kind == "poll"
        else None
    )
    pool = _pool
    if pool is None:
        if not _database_configured():
            raise PMWorkerHeartbeatStorageUnavailable("Worker heartbeat storage is unavailable.")
        try:
            pool = _get_pool()
        except Exception as exc:
            raise PMWorkerHeartbeatStorageUnavailable(
                "Worker heartbeat storage is unavailable."
            ) from exc

    try:
        with pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO pm_worker_heartbeats (
                        worker_id,
                        runner_id,
                        protocol_version,
                        capabilities,
                        poll_interval_seconds,
                        heartbeat_kind,
                        queue_depth,
                        process_started_at,
                        last_seen_at,
                        last_poll_at,
                        lease_expires_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (worker_id) DO UPDATE SET
                        runner_id = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                            THEN EXCLUDED.runner_id ELSE pm_worker_heartbeats.runner_id END,
                        protocol_version = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                            THEN EXCLUDED.protocol_version ELSE pm_worker_heartbeats.protocol_version END,
                        capabilities = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                                 AND EXCLUDED.heartbeat_kind = 'poll'
                            THEN EXCLUDED.capabilities ELSE pm_worker_heartbeats.capabilities END,
                        poll_interval_seconds = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                                 AND EXCLUDED.heartbeat_kind = 'poll'
                            THEN EXCLUDED.poll_interval_seconds ELSE pm_worker_heartbeats.poll_interval_seconds END,
                        heartbeat_kind = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                            THEN EXCLUDED.heartbeat_kind ELSE pm_worker_heartbeats.heartbeat_kind END,
                        queue_depth = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                            THEN EXCLUDED.queue_depth ELSE pm_worker_heartbeats.queue_depth END,
                        process_started_at = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                                 AND EXCLUDED.heartbeat_kind = 'startup'
                            THEN EXCLUDED.process_started_at
                            ELSE pm_worker_heartbeats.process_started_at END,
                        last_seen_at = GREATEST(
                            pm_worker_heartbeats.last_seen_at,
                            EXCLUDED.last_seen_at
                        ),
                        last_poll_at = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                                 AND EXCLUDED.heartbeat_kind = 'poll'
                            THEN EXCLUDED.last_poll_at
                            ELSE pm_worker_heartbeats.last_poll_at END,
                        lease_expires_at = CASE
                            WHEN EXCLUDED.last_seen_at >= pm_worker_heartbeats.last_seen_at
                                 AND EXCLUDED.heartbeat_kind = 'poll'
                            THEN EXCLUDED.lease_expires_at
                            ELSE pm_worker_heartbeats.lease_expires_at END,
                        updated_at = GREATEST(
                            pm_worker_heartbeats.updated_at,
                            EXCLUDED.updated_at
                        )
                    RETURNING
                        worker_id,
                        runner_id,
                        capabilities,
                        poll_interval_seconds,
                        heartbeat_kind,
                        queue_depth,
                        process_started_at,
                        last_seen_at,
                        last_poll_at,
                        lease_expires_at
                    """,
                    (
                        heartbeat.worker_id,
                        heartbeat.runner_id,
                        heartbeat.schema_version,
                        list(heartbeat.capabilities),
                        heartbeat.poll_interval_seconds,
                        heartbeat.heartbeat_kind,
                        heartbeat.queue_depth,
                        observed_at,
                        observed_at,
                        last_poll_at,
                        lease_expires_at,
                        observed_at,
                        observed_at,
                    ),
                )
                row = _mapping_row(cursor.fetchone())
            connection.commit()
    except PMWorkerHeartbeatStorageUnavailable:
        raise
    except Exception as exc:
        raise PMWorkerHeartbeatStorageUnavailable(
            "Worker heartbeat storage is unavailable."
        ) from exc

    try:
        return PMWorkerHeartbeatReceipt(
            worker_id=str(row["worker_id"]),
            runner_id=str(row["runner_id"]),
            heartbeat_kind=str(row["heartbeat_kind"]),
            capabilities=list(row["capabilities"] or []),
            poll_interval_seconds=int(row["poll_interval_seconds"]),
            queue_depth=row.get("queue_depth"),
            process_started_at=row["process_started_at"],
            last_seen_at=row["last_seen_at"],
            last_poll_at=row.get("last_poll_at"),
            lease_expires_at=row.get("lease_expires_at"),
        )
    except Exception as exc:
        raise PMWorkerHeartbeatStorageUnavailable(
            "Worker heartbeat storage returned an invalid row."
        ) from exc


def _readiness_unavailable(
    required_capabilities: tuple[str, ...],
    checked_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": PM_WORKER_READINESS_SCHEMA,
        "ready": False,
        "state": "unavailable",
        "reason_code": "worker_heartbeat_store_unavailable",
        "required_capability": (
            required_capabilities[0] if len(required_capabilities) == 1 else None
        ),
        "required_capabilities": list(required_capabilities),
        "checked_at": checked_at.isoformat(),
        "last_seen_at": None,
        "lease_expires_at": None,
        "age_seconds": None,
        "stale_after_seconds": None,
        "poll_interval_seconds": None,
    }


def _pm_worker_readiness(
    required_capabilities: tuple[str, ...],
    *,
    now: datetime | None = None,
    _pool: Any | None = None,
) -> dict[str, Any]:
    """Return readiness only when one worker advertises the entire required set."""

    checked_at = _now_utc(now)
    pool = _pool
    if pool is None:
        if not _database_configured():
            return _readiness_unavailable(required_capabilities, checked_at)
        try:
            pool = _get_pool()
        except Exception:
            return _readiness_unavailable(required_capabilities, checked_at)

    try:
        with pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        capabilities,
                        poll_interval_seconds,
                        heartbeat_kind,
                        queue_depth,
                        last_seen_at,
                        last_poll_at,
                        lease_expires_at
                    FROM pm_worker_heartbeats
                    WHERE runner_id = %s
                      AND protocol_version = %s
                      AND capabilities @> %s::TEXT[]
                    ORDER BY lease_expires_at DESC NULLS LAST,
                             last_poll_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (
                        PM_WORKER_RUNNER_ID,
                        PM_WORKER_HEARTBEAT_SCHEMA,
                        list(required_capabilities),
                    ),
                )
                raw_row = cursor.fetchone()
    except Exception:
        return _readiness_unavailable(required_capabilities, checked_at)

    if raw_row is None:
        return {
            **_readiness_unavailable(required_capabilities, checked_at),
            "state": "absent",
            "reason_code": "capable_worker_absent",
        }

    try:
        row = _mapping_row(raw_row)
        if row.get("last_poll_at") is None or row.get("lease_expires_at") is None:
            return {
                **_readiness_unavailable(required_capabilities, checked_at),
                "state": "absent",
                "reason_code": "capable_worker_poll_absent",
            }
        last_seen_at = _now_utc(row["last_poll_at"])
        lease_expires_at = _now_utc(row["lease_expires_at"])
        poll_interval_seconds = int(row["poll_interval_seconds"])
        stale_after_seconds = _lease_seconds(poll_interval_seconds)
        if not 15 <= poll_interval_seconds <= 120:
            raise ValueError("Stored poll interval is outside the closed contract.")
        if not set(required_capabilities).issubset(set(row["capabilities"] or [])):
            raise ValueError("Stored capabilities do not match the readiness query.")
        if lease_expires_at <= last_seen_at:
            raise ValueError("Stored worker lease is invalid.")
    except Exception:
        return _readiness_unavailable(required_capabilities, checked_at)

    fresh = lease_expires_at > checked_at
    return {
        "schema_version": PM_WORKER_READINESS_SCHEMA,
        "ready": fresh,
        "state": "fresh" if fresh else "stale",
        "reason_code": None if fresh else "capable_worker_stale",
        "required_capability": (
            required_capabilities[0] if len(required_capabilities) == 1 else None
        ),
        "required_capabilities": list(required_capabilities),
        "checked_at": checked_at.isoformat(),
        "last_seen_at": last_seen_at.isoformat(),
        "lease_expires_at": lease_expires_at.isoformat(),
        "age_seconds": max(0, int((checked_at - last_seen_at).total_seconds())),
        "stale_after_seconds": stale_after_seconds,
        "poll_interval_seconds": poll_interval_seconds,
    }


def pm_worker_readiness(
    required_capability: str,
    *,
    now: datetime | None = None,
    _pool: Any | None = None,
) -> dict[str, Any]:
    """Return a browser-safe fresh/stale/absent view for one exact capability."""

    capability = str(required_capability or "").strip()
    if capability not in INTEGRATED_ACTION_CAPABILITIES:
        raise ValueError("Unsupported PM worker capability.")
    return _pm_worker_readiness((capability,), now=now, _pool=_pool)


def integrated_actions_worker_readiness(
    required_actions: Collection[str],
    *,
    now: datetime | None = None,
    _pool: Any | None = None,
) -> dict[str, Any]:
    """Require one fresh worker capable of every requested controller action."""

    if isinstance(required_actions, (str, bytes)):
        raise ValueError("Integrated controller actions must be a collection.")
    try:
        normalized = tuple(
            sorted({str(action or "").strip() for action in required_actions})
        )
    except TypeError as exc:
        raise ValueError("Integrated controller actions must be a collection.") from exc
    if not normalized or any(
        action not in INTEGRATED_ACTION_CAPABILITIES for action in normalized
    ):
        raise ValueError("Unsupported integrated controller action set.")
    return _pm_worker_readiness(normalized, now=now, _pool=_pool)


def integrated_action_worker_readiness(
    action: str,
    *,
    now: datetime | None = None,
    _pool: Any | None = None,
) -> dict[str, Any]:
    """Integration seam for controller readiness without importing the queue service."""

    normalized_action = str(action or "").strip()
    if normalized_action not in INTEGRATED_ACTION_CAPABILITIES:
        raise ValueError("Unsupported integrated controller action.")
    return pm_worker_readiness(normalized_action, now=now, _pool=_pool)
