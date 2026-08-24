from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.services.open_brain_db import get_pool


WORKSPACE_KEY = "linkedin-content-os"
SNAPSHOT_TYPE = "social_feed_refresh_status"
SCHEMA_VERSION = "social_feed_refresh_status/v1"
ACTIVE_STATES = {"queued", "running"}
TERMINAL_STATES = {"succeeded", "failed"}
VALID_STATES = {"idle", *ACTIVE_STATES, *TERMINAL_STATES}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _status_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        return None
    state = str(value.get("state") or "").strip().lower()
    if state not in VALID_STATES:
        return None
    run_id = str(value.get("run_id") or "").strip() or None
    if state != "idle" and run_id is None:
        return None
    queued_at = _parse_timestamp(value.get("queued_at"))
    started_at = _parse_timestamp(value.get("started_at"))
    completed_at = _parse_timestamp(value.get("completed_at"))
    lease_expires_at = _parse_timestamp(value.get("lease_expires_at"))
    if state in ACTIVE_STATES and (queued_at is None or lease_expires_at is None):
        return None
    if state == "running" and started_at is None:
        return None
    if state in TERMINAL_STATES and completed_at is None:
        return None
    return {
        "schema_version": SCHEMA_VERSION,
        "running": state in ACTIVE_STATES,
        "state": state,
        "run_id": run_id,
        "queued_at": _iso(queued_at),
        "last_run": _iso(_parse_timestamp(value.get("last_run"))),
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "error_code": str(value.get("error_code") or "").strip() or None,
        "lease_expires_at": _iso(lease_expires_at),
    }


def _idle_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "running": False,
        "state": "idle",
        "run_id": None,
        "queued_at": None,
        "last_run": None,
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "lease_expires_at": None,
    }


class SocialFeedRefreshStatusStore:
    """One atomic shared refresh lease and bounded status in Railway Postgres."""

    def __init__(self, pool=None) -> None:
        self._explicit_pool = pool

    def _pool(self):
        return self._explicit_pool or get_pool()

    @staticmethod
    def _read_locked(cursor) -> tuple[str | None, dict[str, Any] | None]:
        cursor.execute(
            """
            SELECT id::text, payload
            FROM workspace_snapshots
            WHERE workspace_key=%s AND snapshot_type=%s
            FOR UPDATE
            """,
            (WORKSPACE_KEY, SNAPSHOT_TYPE),
        )
        row = cursor.fetchone()
        if not row:
            return None, None
        return str(row["id"]), _status_payload(row.get("payload"))

    @staticmethod
    def _write(cursor, *, snapshot_id: str | None, payload: dict[str, Any]) -> None:
        metadata = {
            "source": "social_feed_refresh_control",
            "schema_version": SCHEMA_VERSION,
            "data_policy": "bounded_status_only",
        }
        if snapshot_id is None:
            cursor.execute(
                """
                INSERT INTO workspace_snapshots(id,workspace_key,snapshot_type,payload,metadata)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (str(uuid4()), WORKSPACE_KEY, SNAPSHOT_TYPE, Jsonb(payload), Jsonb(metadata)),
            )
            return
        cursor.execute(
            """
            UPDATE workspace_snapshots
            SET payload=%s, metadata=%s, updated_at=NOW()
            WHERE id::text=%s
            """,
            (Jsonb(payload), Jsonb(metadata), snapshot_id),
        )

    def reserve(
        self,
        *,
        run_id: str,
        queued_at: datetime,
        lease_expires_at: datetime,
    ) -> dict[str, Any] | None:
        queued = _utc(queued_at)
        lease = _utc(lease_expires_at)
        if not str(run_id or "").strip() or lease <= queued:
            raise ValueError("A valid run ID and future refresh lease are required.")
        with self._pool().connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                snapshot_id, current = self._read_locked(cursor)
                if snapshot_id is not None and current is None:
                    raise ValueError("Stored social-feed refresh status is malformed.")
                current = current or _idle_payload()
                current_lease = _parse_timestamp(current.get("lease_expires_at"))
                if (
                    current.get("state") in ACTIVE_STATES
                    and current_lease is not None
                    and current_lease > queued
                ):
                    return None
                payload = {
                    "schema_version": SCHEMA_VERSION,
                    "running": True,
                    "state": "queued",
                    "run_id": run_id,
                    "queued_at": _iso(queued),
                    "last_run": current.get("last_run"),
                    "started_at": None,
                    "completed_at": None,
                    "error_code": None,
                    "lease_expires_at": _iso(lease),
                }
                self._write(cursor, snapshot_id=snapshot_id, payload=payload)
            connection.commit()
        return payload

    def _transition(
        self,
        *,
        run_id: str,
        expected_state: str,
        state: str,
        at: datetime,
        lease_expires_at: datetime | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any] | None:
        if expected_state not in ACTIVE_STATES or state not in {"running", *TERMINAL_STATES}:
            raise ValueError("Unsupported refresh-state transition.")
        changed_at = _utc(at)
        with self._pool().connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                snapshot_id, current = self._read_locked(cursor)
                if snapshot_id is not None and current is None:
                    raise ValueError("Stored social-feed refresh status is malformed.")
                if (
                    snapshot_id is None
                    or current is None
                    or current.get("run_id") != run_id
                    or current.get("state") != expected_state
                ):
                    return None
                payload = dict(current)
                payload["state"] = state
                payload["running"] = state in ACTIVE_STATES
                if state == "running":
                    if lease_expires_at is None or _utc(lease_expires_at) <= changed_at:
                        raise ValueError("A running refresh requires a future lease.")
                    payload["started_at"] = _iso(changed_at)
                    payload["lease_expires_at"] = _iso(_utc(lease_expires_at))
                else:
                    payload["completed_at"] = _iso(changed_at)
                    payload["lease_expires_at"] = None
                    payload["error_code"] = str(error_code or "").strip() or None
                    if state == "succeeded":
                        payload["last_run"] = _iso(changed_at)
                self._write(cursor, snapshot_id=snapshot_id, payload=payload)
            connection.commit()
        return payload

    def start(
        self,
        *,
        run_id: str,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> dict[str, Any] | None:
        return self._transition(
            run_id=run_id,
            expected_state="queued",
            state="running",
            at=started_at,
            lease_expires_at=lease_expires_at,
        )

    def succeed(self, *, run_id: str, completed_at: datetime) -> dict[str, Any] | None:
        return self._transition(
            run_id=run_id,
            expected_state="running",
            state="succeeded",
            at=completed_at,
        )

    def fail(
        self,
        *,
        run_id: str,
        completed_at: datetime,
        error_code: str,
    ) -> dict[str, Any] | None:
        return self._transition(
            run_id=run_id,
            expected_state="running",
            state="failed",
            at=completed_at,
            error_code=error_code,
        )

    def get_status(self, *, now: datetime | None = None) -> dict[str, Any]:
        checked_at = _utc(now or datetime.now(timezone.utc))
        with self._pool().connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                snapshot_id, current = self._read_locked(cursor)
                if snapshot_id is None:
                    return _idle_payload()
                if current is None:
                    raise ValueError("Stored social-feed refresh status is malformed.")
                lease = _parse_timestamp(current.get("lease_expires_at"))
                if current.get("state") in ACTIVE_STATES and (lease is None or lease <= checked_at):
                    current["running"] = False
                    current["state"] = "failed"
                    current["completed_at"] = _iso(checked_at)
                    current["error_code"] = "refresh_attempt_lease_expired"
                    current["lease_expires_at"] = None
                    self._write(cursor, snapshot_id=snapshot_id, payload=current)
            connection.commit()
        return current


social_feed_refresh_status_store = SocialFeedRefreshStatusStore()
