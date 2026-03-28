from __future__ import annotations

import logging
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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
    if not SCRIPT_PATH.exists():
        logging.warning("Social feed refresh script is unavailable in this deployment; treating refresh as a no-op.")
        return
    cmd = ["python3", str(SCRIPT_PATH)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    if sources != "safe":
        cmd.extend(["--sources", sources])
    subprocess.run(cmd, cwd=ROOT, check=True)


class SocialFeedRefreshService:
    def run_refresh(self, skip_fetch: bool = False, sources: Literal["safe", "all"] = "safe") -> None:
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

    def run_refresh_background(self, skip_fetch: bool = False, sources: Literal["safe", "all"] = "safe") -> None:
        try:
            self.run_refresh(skip_fetch, sources)
        except InvalidRefreshState:
            pass

    def get_status(self) -> dict[str, None | bool | datetime | str]:
        with _state_lock:
            return dict(_state)


social_feed_refresh_service = SocialFeedRefreshService()
