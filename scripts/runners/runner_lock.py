"""Single-flight locks for local PM runner processes."""
from __future__ import annotations

import fcntl
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from automation_run_mirror import build_run_payload, mirror_runs

LOCK_DIR = Path("/tmp/openclaw-runner-locks")


class RunnerLockUnavailable(RuntimeError):
    """Raised when another runner process already owns the lock."""


class RunnerLock:
    def __init__(self, name: str) -> None:
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name)
        self.name = safe_name or "runner"
        self.path = LOCK_DIR / f"{self.name}.lock"
        self._handle = None

    def __enter__(self) -> "RunnerLock":
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RunnerLockUnavailable(f"Runner lock is already held: {self.path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "runner": self.name,
                    "pid": os.getpid(),
                    "started_at": _now().isoformat().replace("+00:00", "Z"),
                }
            )
            + "\n"
        )
        handle.flush()
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def api_url_from_argv(default: str) -> str:
    for index, value in enumerate(sys.argv):
        if value == "--api-url" and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        if value.startswith("--api-url="):
            return value.split("=", 1)[1]
    return default


def execute_with_runner_lock(
    *,
    lock_name: str,
    automation_id: str,
    automation_name: str,
    default_api_url: str,
    main_func: Callable[[], int],
    owner_agent: str | None = None,
    scope: str = "shared_ops",
    workspace_key: str | None = None,
) -> int:
    try:
        with RunnerLock(lock_name):
            return int(main_func() or 0)
    except RunnerLockUnavailable as exc:
        started_at = _now()
        finished_at = _now()
        api_url = api_url_from_argv(default_api_url)
        mirror_runs(
            api_url,
            [
                build_run_payload(
                    run_id=f"{automation_id}::{uuid.uuid4()}",
                    automation_id=automation_id,
                    automation_name=automation_name,
                    status="ok",
                    run_at=started_at,
                    finished_at=finished_at,
                    duration_ms=1,
                    owner_agent=owner_agent,
                    session_target="local_launchd",
                    scope=scope,
                    workspace_key=workspace_key,
                    action_required=False,
                    metadata={
                        "result": "noop_locked",
                        "summary": str(exc),
                        "lock_name": lock_name,
                    },
                )
            ],
        )
        print(json.dumps({"status": "ok", "result": "noop_locked", "lock_name": lock_name}))
        return 0
