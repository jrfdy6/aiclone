from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.services.open_brain_db import database_configured
from app.services.social_feed_refresh_status_store import social_feed_refresh_status_store


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/")]
    seen: set[Path] = set()
    for parent in candidates:
        if parent in seen:
            continue
        seen.add(parent)
        if (parent / "scripts" / "personal-brand" / "refresh_social_feed.py").exists():
            return parent
    return current.parents[3]


ROOT = resolve_workspace_root()
SCRIPT_PATH = ROOT / "scripts" / "personal-brand" / "refresh_social_feed.py"
REFRESH_TIMEOUT_SECONDS = max(30, int(os.getenv("SOCIAL_FEED_REFRESH_TIMEOUT_SECONDS", "180")))
REFRESH_LEASE_SECONDS = max(
    REFRESH_TIMEOUT_SECONDS + 60,
    int(os.getenv("SOCIAL_FEED_REFRESH_LEASE_SECONDS", str(REFRESH_TIMEOUT_SECONDS + 60))),
)

_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "state": "idle",
    "run_id": None,
    "queued_at": None,
    "last_run": None,
    "started_at": None,
    "completed_at": None,
    "error": None,
}


class InvalidRefreshState(Exception):
    pass


class SocialFeedPersistenceError(RuntimeError):
    """Raised when a refresh does not produce and durably store a usable feed."""


class RefreshStatusStoreUnavailable(RuntimeError):
    """Raised when a configured shared refresh authority cannot be reached."""


def _durable_status_enabled() -> bool:
    return database_configured()


def _status_with_error_marker(status: dict[str, Any]) -> dict[str, Any]:
    projected = dict(status)
    error_code = str(projected.get("error_code") or "").strip()
    projected["error"] = error_code or projected.get("error")
    return projected


def _sync_process_state(status: dict[str, Any]) -> dict[str, Any]:
    normalized = _status_with_error_marker(status)
    with _state_lock:
        _state.clear()
        _state.update(normalized)
    return dict(normalized)


def _bounded_failure_code(exc: Exception) -> str:
    if isinstance(exc, SocialFeedPersistenceError):
        return "social_feed_persistence_failed"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "social_feed_refresh_timeout"
    if isinstance(exc, subprocess.CalledProcessError):
        return "social_feed_refresh_process_failed"
    if isinstance(exc, FileNotFoundError):
        return "social_feed_refresh_runtime_unavailable"
    if isinstance(exc, InvalidRefreshState):
        return "social_feed_refresh_state_conflict"
    return "social_feed_refresh_failed"


def _run_command(skip_fetch: bool, sources: Literal["safe", "all"]) -> None:
    if not SCRIPT_PATH.exists():
        raise FileNotFoundError("Social feed refresh script is unavailable in this deployment.")
    # Use the interpreter that loaded the API so the refresh sees the exact
    # dependency environment installed for the Railway backend image.
    cmd = [sys.executable, str(SCRIPT_PATH)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    cmd.append("--skip-brain-context-sync")
    cmd.append("--skip-strategy-refresh")
    cmd.append("--skip-content-bank")
    cmd.append("--skip-feezie-workspace-sync")
    cmd.append("--skip-market-archive")
    cmd.append("--compact-output")
    if sources != "safe":
        cmd.extend(["--sources", sources])
    environment = os.environ.copy()
    python_path = [str(ROOT)]
    existing_python_path = environment.get("PYTHONPATH", "")
    if existing_python_path:
        python_path.extend(
            entry
            for entry in existing_python_path.split(os.pathsep)
            if entry and entry != str(ROOT)
        )
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        timeout=REFRESH_TIMEOUT_SECONDS,
        env=environment,
    )


def _persist_workspace_snapshots() -> None:
    from app.services import workspace_snapshot_service as snapshot_module
    from app.services import workspace_snapshot_store

    refreshed = snapshot_module.workspace_snapshot_service.refresh_persisted_social_feed_state(
        require_usable_feed=True,
        require_durable=True,
    )
    refreshed_feed = refreshed.get(snapshot_module.SNAPSHOT_SOCIAL_FEED)
    if not isinstance(refreshed_feed, dict) or not snapshot_module._snapshot_is_usable(
        snapshot_module.SNAPSHOT_SOCIAL_FEED,
        refreshed_feed,
    ):
        raise SocialFeedPersistenceError(
            "Social feed refresh did not produce a usable feed for durable storage."
        )

    persisted = workspace_snapshot_store.get_snapshot(
        snapshot_module.WORKSPACE_KEY,
        snapshot_module.SNAPSHOT_SOCIAL_FEED,
    )
    persisted_payload = (persisted or {}).get("payload")
    persisted_metadata = (persisted or {}).get("metadata")
    expected_generated_at = refreshed_feed.get("generated_at")
    if (
        not (persisted or {}).get("id")
        or not isinstance(persisted_payload, dict)
        or not snapshot_module._snapshot_is_usable(
            snapshot_module.SNAPSHOT_SOCIAL_FEED,
            persisted_payload,
        )
        or persisted_payload != refreshed_feed
        or not isinstance(persisted_metadata, dict)
        or not expected_generated_at
        or persisted_payload.get("generated_at") != expected_generated_at
        or persisted_metadata.get("source") != "social_feed_refresh"
        or persisted_metadata.get("payload_generated_at") != expected_generated_at
    ):
        raise SocialFeedPersistenceError(
            "Social feed refresh could not verify the durable feed snapshot."
        )


class SocialFeedRefreshService:
    def queue_refresh(self) -> dict[str, Any]:
        """Reserve one refresh attempt before the response queues its background task."""

        queued_at = datetime.now(timezone.utc)
        run_id = str(uuid4())
        if _durable_status_enabled():
            try:
                reserved = social_feed_refresh_status_store.reserve(
                    run_id=run_id,
                    queued_at=queued_at,
                    lease_expires_at=queued_at + timedelta(seconds=REFRESH_LEASE_SECONDS),
                )
            except Exception as exc:
                logging.exception("Shared social-feed refresh reservation failed", exc_info=exc)
                raise RefreshStatusStoreUnavailable(
                    "Shared social-feed refresh status is unavailable."
                ) from exc
            if reserved is None:
                raise InvalidRefreshState("Social feed refresh already running.")
            return _sync_process_state(reserved)

        with _state_lock:
            if _state["running"]:
                raise InvalidRefreshState("Social feed refresh already running.")
            _state["running"] = True
            _state["state"] = "queued"
            _state["run_id"] = run_id
            _state["queued_at"] = queued_at
            _state["started_at"] = None
            _state["completed_at"] = None
            _state["error"] = None
            return dict(_state)

    def run_refresh(
        self,
        skip_fetch: bool = False,
        sources: Literal["safe", "all"] = "safe",
        *,
        run_id: str | None = None,
    ) -> None:
        if run_id is None:
            queued = self.queue_refresh()
            run_id = str(queued["run_id"])

        durable = _durable_status_enabled()
        started_at = datetime.now(timezone.utc)
        if durable:
            try:
                started = social_feed_refresh_status_store.start(
                    run_id=run_id,
                    started_at=started_at,
                    lease_expires_at=started_at + timedelta(seconds=REFRESH_LEASE_SECONDS),
                )
            except Exception as exc:
                logging.exception("Shared social-feed refresh start failed", exc_info=exc)
                raise RefreshStatusStoreUnavailable(
                    "Shared social-feed refresh status is unavailable."
                ) from exc
            if started is None:
                raise InvalidRefreshState("Social feed refresh attempt is no longer queued.")
            _sync_process_state(started)
        else:
            with _state_lock:
                if _state["run_id"] != run_id or _state["state"] != "queued":
                    raise InvalidRefreshState("Social feed refresh attempt is no longer queued.")
                _state["state"] = "running"
                _state["started_at"] = started_at

        try:
            _run_command(skip_fetch, sources)
            _persist_workspace_snapshots()
            completed_at = datetime.now(timezone.utc)
            if durable:
                completed = social_feed_refresh_status_store.succeed(
                    run_id=run_id,
                    completed_at=completed_at,
                )
                if completed is None:
                    raise InvalidRefreshState("Social feed refresh attempt was superseded before completion.")
                _sync_process_state(completed)
            else:
                with _state_lock:
                    _state["last_run"] = completed_at
                    _state["completed_at"] = completed_at
                    _state["state"] = "succeeded"
        except Exception as exc:
            logging.exception("Social feed refresh failed", exc_info=exc)
            completed_at = datetime.now(timezone.utc)
            if durable:
                try:
                    failed = social_feed_refresh_status_store.fail(
                        run_id=run_id,
                        completed_at=completed_at,
                        error_code=_bounded_failure_code(exc),
                    )
                    if failed is not None:
                        _sync_process_state(failed)
                except Exception as status_exc:
                    logging.exception(
                        "Shared social-feed refresh failure receipt could not be committed",
                        exc_info=status_exc,
                    )
            else:
                with _state_lock:
                    _state["error"] = str(exc)
                    _state["completed_at"] = completed_at
                    _state["state"] = "failed"
            raise
        finally:
            if not durable:
                with _state_lock:
                    _state["running"] = False

    def run_refresh_background(
        self,
        run_id: str,
        skip_fetch: bool = False,
        sources: Literal["safe", "all"] = "safe",
    ) -> None:
        try:
            self.run_refresh(skip_fetch, sources, run_id=run_id)
        except Exception:
            # ``run_refresh`` has already logged the failure and committed the
            # exact terminal state.  Background-task failures happen after the
            # queued HTTP response has been sent, so letting them escape only
            # mislabels an honestly degraded run as an unhandled request error.
            pass

    def get_status(self) -> dict[str, Any]:
        if _durable_status_enabled():
            try:
                return _sync_process_state(social_feed_refresh_status_store.get_status())
            except Exception as exc:
                logging.exception("Shared social-feed refresh status read failed", exc_info=exc)
                return {
                    "running": False,
                    "state": "failed",
                    "run_id": None,
                    "queued_at": None,
                    "last_run": None,
                    "started_at": None,
                    "completed_at": None,
                    "error": "refresh_status_store_unavailable",
                    "error_code": "refresh_status_store_unavailable",
                }
        with _state_lock:
            return dict(_state)


social_feed_refresh_service = SocialFeedRefreshService()
