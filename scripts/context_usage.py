#!/usr/bin/env python3
"""Estimate active OpenClaw session context usage.

The original helper summed every markdown file in `memory/`, which measures
disk growth, not the live prompt/transcript size for an active session. This
version prefers the most recently updated non-cron, non-heartbeat session and
estimates transcript size from the last N message records.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OPENCLAW_ROOT = Path("/Users/neo/.openclaw")
SESSIONS_INDEX = OPENCLAW_ROOT / "agents" / "main" / "sessions" / "sessions.json"
DEFAULT_LAST_MESSAGES = 150
DEFAULT_ACTIVE_MAX_AGE_MINUTES = 180
APPROX_BYTES_PER_TOKEN = 4


@dataclass
class SessionCandidate:
    session_key: str
    session_file: Path
    updated_at_ms: int
    origin_provider: str | None
    last_channel: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate active OpenClaw session context usage.")
    parser.add_argument("--last", type=int, default=DEFAULT_LAST_MESSAGES, help="Number of recent message records to inspect.")
    parser.add_argument(
        "--active-max-age-minutes",
        type=int,
        default=DEFAULT_ACTIVE_MAX_AGE_MINUTES,
        help="Ignore sessions older than this many minutes when picking an active interactive session.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def load_sessions_index() -> dict[str, Any]:
    if not SESSIONS_INDEX.exists():
        raise FileNotFoundError(f"Missing sessions index: {SESSIONS_INDEX}")
    return json.loads(SESSIONS_INDEX.read_text())


def iter_candidates(index: dict[str, Any]) -> list[SessionCandidate]:
    candidates: list[SessionCandidate] = []
    for session_key, meta in index.items():
        if ":cron:" in session_key:
            continue
        origin = meta.get("origin") or {}
        if origin.get("provider") == "heartbeat":
            continue
        session_file = meta.get("sessionFile")
        updated_at_ms = meta.get("updatedAt")
        if not session_file or not updated_at_ms:
            continue
        path = Path(session_file)
        if not path.exists():
            continue
        candidates.append(
            SessionCandidate(
                session_key=session_key,
                session_file=path,
                updated_at_ms=int(updated_at_ms),
                origin_provider=origin.get("provider"),
                last_channel=meta.get("lastChannel"),
            )
        )
    return sorted(candidates, key=lambda item: item.updated_at_ms, reverse=True)


def choose_session(candidates: list[SessionCandidate], active_max_age_minutes: int) -> SessionCandidate | None:
    if not candidates:
        return None
    now_ms = time.time() * 1000
    age_limit_ms = active_max_age_minutes * 60 * 1000
    for candidate in candidates:
        if now_ms - candidate.updated_at_ms <= age_limit_ms:
            return candidate
    return None


def load_recent_messages(session_file: Path, limit: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in session_file.read_text(errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "message":
            continue
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        records.append(message)
    if limit <= 0:
        return records
    return records[-limit:]


def estimate_bytes(messages: list[dict[str, Any]]) -> int:
    total = 0
    for message in messages:
        total += len(json.dumps(message, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return total


def build_report(last: int, active_max_age_minutes: int) -> dict[str, Any]:
    candidates = iter_candidates(load_sessions_index())
    session = choose_session(candidates, active_max_age_minutes)
    if session is None:
        return {
            "status": "no-active-session",
            "session_key": None,
            "session_file": None,
            "messages_analyzed": 0,
            "approx_bytes": 0,
            "approx_tokens": 0,
            "notes": [
                f"No non-cron, non-heartbeat session updated within the last {active_max_age_minutes} minutes.",
            ],
        }

    messages = load_recent_messages(session.session_file, last)
    approx_bytes = estimate_bytes(messages)
    approx_tokens = round(approx_bytes / APPROX_BYTES_PER_TOKEN)
    threshold_tokens = 64000
    return {
        "status": "above-threshold" if approx_tokens >= threshold_tokens else "below-threshold",
        "session_key": session.session_key,
        "session_file": str(session.session_file),
        "origin_provider": session.origin_provider,
        "last_channel": session.last_channel,
        "messages_analyzed": len(messages),
        "approx_bytes": approx_bytes,
        "approx_tokens": approx_tokens,
        "threshold_tokens": threshold_tokens,
        "notes": [
            f"Estimated from the last {len(messages)} message records in the active session transcript.",
            "This is an approximation of live transcript size, not workspace memory file size.",
        ],
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"Status: {report['status']}")
    print(f"Session key: {report.get('session_key') or 'none'}")
    if report.get("session_file"):
        print(f"Session file: {report['session_file']}")
    print(f"Messages analyzed: {report['messages_analyzed']}")
    print(f"Approx transcript bytes: {report['approx_bytes']}")
    print(f"Approx transcript tokens: {report['approx_tokens']}")
    threshold = report.get("threshold_tokens")
    if threshold is not None:
        print(f"Alert threshold tokens: {threshold}")
    for note in report.get("notes") or []:
        print(f"Note: {note}")


def main() -> int:
    args = parse_args()
    report = build_report(last=args.last, active_max_age_minutes=args.active_max_age_minutes)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
