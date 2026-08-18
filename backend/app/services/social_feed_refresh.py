from __future__ import annotations

import logging
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4


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

_state_lock = threading.Lock()
_state: dict[str, None | bool | datetime | str] = {
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


def _run_command(skip_fetch: bool, sources: Literal["safe", "all"]) -> None:
    if not SCRIPT_PATH.exists():
        logging.warning("Social feed refresh script is unavailable in this deployment; treating refresh as a no-op.")
        return
    cmd = ["python3", str(SCRIPT_PATH)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    cmd.append("--skip-brain-context-sync")
    cmd.append("--skip-strategy-refresh")
    cmd.append("--skip-content-bank")
    cmd.append("--skip-feezie-workspace-sync")
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
    from app.services.workspace_snapshot_service import workspace_snapshot_service

    workspace_snapshot_service.refresh_persisted_social_feed_state()


class SocialFeedRefreshService:
    def queue_refresh(self) -> dict[str, None | bool | datetime | str]:
        """Reserve one refresh attempt before the response queues its background task."""

        with _state_lock:
            if _state["running"]:
                raise InvalidRefreshState("Social feed refresh already running.")
            queued_at = datetime.now(timezone.utc)
            run_id = str(uuid4())
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

        with _state_lock:
            if _state["run_id"] != run_id or _state["state"] != "queued":
                raise InvalidRefreshState("Social feed refresh attempt is no longer queued.")
            _state["state"] = "running"
            _state["started_at"] = datetime.now(timezone.utc)

        try:
            _run_command(skip_fetch, sources)
            _persist_workspace_snapshots()
            with _state_lock:
                completed_at = datetime.now(timezone.utc)
                _state["last_run"] = completed_at
                _state["completed_at"] = completed_at
                _state["state"] = "succeeded"
        except Exception as exc:
            logging.exception("Social feed refresh failed", exc_info=exc)
            with _state_lock:
                _state["error"] = str(exc)
                _state["completed_at"] = datetime.now(timezone.utc)
                _state["state"] = "failed"
            raise
        finally:
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
        except InvalidRefreshState:
            pass

    def get_status(self) -> dict[str, None | bool | datetime | str]:
        with _state_lock:
            return dict(_state)


social_feed_refresh_service = SocialFeedRefreshService()
