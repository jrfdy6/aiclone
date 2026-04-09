#!/usr/bin/env python3
"""Gate Progress Pulse delivery on real signal changes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
RUN_LOG = Path("/Users/neo/.openclaw/cron/runs/717f5346-f58f-4eac-ac30-014d8774a6c7.jsonl")
HANDOFF_LOG = WORKSPACE_ROOT / "memory" / "codex_session_handoff.jsonl"
PERSISTENT_STATE = WORKSPACE_ROOT / "memory" / "persistent_state.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            rows.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return rows


def _parse_iso_ts(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _latest_delivered_run_ms() -> int | None:
    latest: int | None = None
    for row in _parse_jsonl(RUN_LOG):
        if row.get("action") != "finished":
            continue
        if not row.get("delivered"):
            continue
        run_at = row.get("runAtMs")
        if isinstance(run_at, int):
            latest = run_at
    return latest


def _new_handoff_entries(since_ms: int | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in _parse_jsonl(HANDOFF_LOG):
        created_at_ms = _parse_iso_ts(row.get("created_at"))
        if since_ms is None or (created_at_ms is not None and created_at_ms > since_ms):
            entries.append(row)
    return entries


def _persistent_state_newer(since_ms: int | None) -> bool:
    if since_ms is None or not PERSISTENT_STATE.exists():
        return since_ms is None and PERSISTENT_STATE.exists()
    return int(PERSISTENT_STATE.stat().st_mtime * 1000) > since_ms


def build_report() -> dict[str, Any]:
    last_delivered_run_ms = _latest_delivered_run_ms()
    new_handoffs = _new_handoff_entries(last_delivered_run_ms)
    persistent_state_newer = _persistent_state_newer(last_delivered_run_ms)

    reasons: list[str] = []
    if last_delivered_run_ms is None:
        reasons.append("no prior delivered Progress Pulse run found")
    if new_handoffs:
        reasons.append(f"{len(new_handoffs)} new handoff entries landed since the last delivered digest")
    if persistent_state_newer:
        reasons.append("persistent_state.md changed since the last delivered digest")

    should_deliver = bool(reasons)
    latest_handoff = new_handoffs[-1] if new_handoffs else None
    latest_handoff_created_at = latest_handoff.get("created_at") if latest_handoff else None
    latest_handoff_summary = latest_handoff.get("summary") if latest_handoff else None
    report = {
        "should_deliver": should_deliver,
        "reasons": reasons,
        "last_delivered_run_at_ms": last_delivered_run_ms,
        "new_handoff_count": len(new_handoffs),
        "latest_handoff_created_at": latest_handoff_created_at,
        "latest_handoff_summary": latest_handoff_summary,
        "persistent_state_newer": persistent_state_newer,
        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return report


def print_text(report: dict[str, Any]) -> None:
    if not report["should_deliver"]:
        print("NO_REPLY")
        return
    print(json.dumps(report, indent=2))


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
