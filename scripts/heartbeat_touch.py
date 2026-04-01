#!/usr/bin/env python3
"""Update canonical heartbeat state and optionally append a daily log note."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
STATE_PATH = WORKSPACE_ROOT / "memory" / "heartbeat-state.json"
MEMORY_DIR = WORKSPACE_ROOT / "memory"
DEFAULT_CHECKS = [
    "automation_health",
    "discord_gateway",
    "pm_blockers",
    "workspace_state",
]
TZ = ZoneInfo("America/New_York")


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "lastChecks": {key: None for key in DEFAULT_CHECKS},
        "lastHeartbeatStatus": None,
        "lastHeartbeatNote": None,
    }


def append_daily_log(now: datetime, status: str, note: str, checks: list[str]) -> None:
    log_path = MEMORY_DIR / f"{now.date().isoformat()}.md"
    local_stamp = now.strftime("%Y-%m-%d %H:%M %Z")
    utc_stamp = now.astimezone(ZoneInfo("UTC")).isoformat()
    lines = [
        "",
        f"## Heartbeat — {local_stamp}",
        f"- UTC: `{utc_stamp}`",
        f"- Status: `{status}`",
        f"- Checks: `{', '.join(checks)}`",
        f"- Note: {note}",
        "",
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", default="ok", choices=["ok", "alert"])
    parser.add_argument("--note", default="HEARTBEAT_OK")
    parser.add_argument("--checks", default=",".join(DEFAULT_CHECKS))
    parser.add_argument("--append-log", action="store_true")
    args = parser.parse_args()

    checks = [part.strip() for part in args.checks.split(",") if part.strip()]
    if not checks:
        checks = list(DEFAULT_CHECKS)

    now = datetime.now(TZ)
    now_ts = int(now.timestamp())

    state = load_state()
    last_checks = state.setdefault("lastChecks", {})
    for key in checks:
        last_checks[key] = now_ts
    state["lastHeartbeatStatus"] = args.status
    state["lastHeartbeatNote"] = args.note

    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    should_append = args.append_log or args.status != "ok" or args.note.strip() not in {"", "HEARTBEAT_OK"}
    if should_append:
        append_daily_log(now, args.status, args.note, checks)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
