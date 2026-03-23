from __future__ import annotations

import logging
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "personal-brand" / "refresh_social_feed.py"

_state_lock = threading.Lock()
_state: dict[str, None | bool | datetime | str] = {
    "running": False,
    "last_run": None,
    "started_at": None,
    "error": None,
}


class InvalidRefreshState(Exception):
    pass


def _run_command(skip_fetch: bool, sources: Literal["safe", "all"]) -> None:
    cmd = ["python3", str(SCRIPT_PATH)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    if sources != "safe":
        cmd.extend(["--sources", sources])
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_refresh(skip_fetch: bool = False, sources: Literal["safe", "all"] = "safe") -> None:
    with _state_lock:
        if _state["running"]:
            raise InvalidRefreshState("Social feed refresh already running.")
        _state["running"] = True
        _state["started_at"] = datetime.now(timezone.utc)
        _state["error"] = None

    try:
        _run_command(skip_fetch, sources)
        with _state_lock:
            _state["last_run"] = datetime.now(timezone.utc)
    except Exception as exc:
        logging.exception("Social feed refresh failed", exc_info=exc)
        with _state_lock:
            _state["error"] = str(exc)
        raise
    finally:
        with _state_lock:
            _state["running"] = False


def run_refresh_background(skip_fetch: bool = False, sources: Literal["safe", "all"] = "safe") -> None:
    try:
        run_refresh(skip_fetch, sources)
    except InvalidRefreshState:
        pass


def get_status() -> dict[str, None | bool | datetime | str]:
    with _state_lock:
        return dict(_state)
