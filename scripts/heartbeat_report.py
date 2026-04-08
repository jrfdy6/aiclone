#!/usr/bin/env python3
"""Produce a short heartbeat/Discord diagnostics report for operators."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
STATE_PATH = WORKSPACE_ROOT / "memory" / "heartbeat-state.json"
GATEWAY_LOG = Path.home() / ".openclaw" / "logs" / "gateway.log"
CRON_PRUNE = WORKSPACE_ROOT / "memory" / "cron-prune.md"
DAILY_BRIEFS = WORKSPACE_ROOT / "memory" / "daily-briefs.md"
EXECUTION_LOG = WORKSPACE_ROOT / "workspaces" / "shared-ops" / "memory" / "execution_log.md"

TZ = ZoneInfo("America/New_York")
HEARTBEAT_PATTERN = re.compile(r"\[heartbeat\]\s+started", re.IGNORECASE)
DISCORD_PATTERN = re.compile(r"\[discord\]\s+gateway:(.*)", re.IGNORECASE)


@dataclass
class ArtifactSpec:
    label: str
    path: Path


ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("cron_prune", CRON_PRUNE),
    ArtifactSpec("daily_briefs", DAILY_BRIEFS),
    ArtifactSpec("execution_log_shared_ops", EXECUTION_LOG),
)


def _now() -> datetime:
    return datetime.now(tz=TZ)


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(errors="replace").splitlines()


def _parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _timestamp_from_line(line: str) -> datetime | None:
    head, _, _ = line.partition(" ")
    return _parse_timestamp(head)


def _age_minutes(now: datetime, then: datetime | None) -> float | None:
    if then is None:
        return None
    delta = now.astimezone(timezone.utc) - then.astimezone(timezone.utc)
    return max(delta.total_seconds() / 60.0, 0)


def _format_ts(dt: datetime | None, tz: ZoneInfo = TZ) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(tz).isoformat(timespec="seconds")


def load_state(now: datetime) -> dict:
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}

    last_checks = state.get("lastChecks") or {}
    check_rows = []
    for key in sorted(last_checks):
        raw = last_checks.get(key)
        dt = None
        if isinstance(raw, (int, float)):
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        check_rows.append(
            {
                "name": key,
                "timestamp": _format_ts(dt),
                "age_minutes": _age_minutes(now, dt) if dt else None,
            }
        )

    return {
        "checks": check_rows,
        "status": state.get("lastHeartbeatStatus"),
        "note": state.get("lastHeartbeatNote"),
        "path": str(STATE_PATH),
    }


def analyze_gateway(now: datetime, hours: float) -> dict:
    lines = _read_lines(GATEWAY_LOG)
    if not lines:
        return {"path": str(GATEWAY_LOG), "missing": True}

    cutoff = now.astimezone(timezone.utc) - timedelta(hours=hours)
    last_entry: dict | None = None
    window_count = 0
    for line in reversed(lines):
        if not HEARTBEAT_PATTERN.search(line):
            continue
        ts = _timestamp_from_line(line)
        if ts is None:
            continue
        if last_entry is None:
            last_entry = {
                "timestamp_local": _format_ts(ts),
                "timestamp_utc": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "age_minutes": _age_minutes(now, ts),
                "line": line.strip(),
            }
        if ts.astimezone(timezone.utc) >= cutoff:
            window_count += 1
        else:
            # Older than cutoff; remaining entries will also be older.
            break

    return {
        "path": str(GATEWAY_LOG),
        "missing": False,
        "last_entry": last_entry,
        "entries_within_hours": window_count,
        "window_hours": hours,
    }


def analyze_discord(now: datetime, hours: float) -> dict:
    lines = _read_lines(GATEWAY_LOG)
    if not lines:
        return {"path": str(GATEWAY_LOG), "missing": True}

    cutoff = now.astimezone(timezone.utc) - timedelta(hours=hours)
    counts = {"closed": 0, "reconnect": 0, "other": 0}
    latest_overall: dict | None = None
    latest_by_type: dict[str, dict] = {}

    for line in reversed(lines):
        if "[discord]" not in line:
            continue
        match = DISCORD_PATTERN.search(line)
        if not match:
            continue
        ts = _timestamp_from_line(line)
        if ts is None:
            continue

        msg = match.group(1).strip().lower()
        if "websocket closed" in msg:
            event_type = "closed"
        elif "reconnect" in msg:
            event_type = "reconnect"
        else:
            event_type = "other"

        snapshot = {
            "type": event_type,
            "timestamp_local": _format_ts(ts),
            "timestamp_utc": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "age_minutes": _age_minutes(now, ts),
            "line": line.strip(),
        }

        if latest_overall is None:
            latest_overall = snapshot
        if event_type not in latest_by_type:
            latest_by_type[event_type] = snapshot

        if ts.astimezone(timezone.utc) >= cutoff:
            counts[event_type] += 1
        else:
            # Remaining entries are older than the cutoff.
            if latest_overall is not None and ts.astimezone(timezone.utc) < cutoff:
                break

    return {
        "path": str(GATEWAY_LOG),
        "missing": False,
        "window_hours": hours,
        "counts": counts,
        "latest": latest_overall,
        "latest_by_type": latest_by_type,
    }


def artifact_snapshots(now: datetime, extra_paths: Iterable[Path] | None = None) -> list[dict]:
    paths = list(ARTIFACTS)
    if extra_paths:
        for idx, path in enumerate(extra_paths):
            paths.append(ArtifactSpec(f"extra_{idx}", path))

    snapshots: list[dict] = []
    for spec in paths:
        entry = {"label": spec.label, "path": str(spec.path)}
        if spec.path.exists():
            mtime = datetime.fromtimestamp(spec.path.stat().st_mtime, tz=timezone.utc)
            entry.update(
                {
                    "exists": True,
                    "modified_local": _format_ts(mtime),
                    "modified_utc": mtime.isoformat(timespec="seconds"),
                    "age_minutes": _age_minutes(now, mtime),
                }
            )
        else:
            entry["exists"] = False
        snapshots.append(entry)
    return snapshots


def build_report(hours: float) -> dict:
    now = _now()
    today_log = WORKSPACE_ROOT / "memory" / f"{now.date().isoformat()}.md"
    extras = [today_log]
    return {
        "generated_at_local": _format_ts(now),
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "state": load_state(now),
        "gateway": analyze_gateway(now, hours),
        "discord": analyze_discord(now, hours),
        "artifacts": artifact_snapshots(now, extras),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Heartbeat Sensor Report",
        "",
        f"- Generated (local): `{report['generated_at_local']}`",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        "",
        "## Heartbeat State",
    ]

    state = report.get("state") or {}
    status = state.get("status") or "unknown"
    note = state.get("note") or ""
    lines.append(f"- Status: `{status}`")
    if note:
        lines.append(f"- Note: `{note}`")
    if state.get("checks"):
        for check in state["checks"]:
            age = check.get("age_minutes")
            age_str = f"{age:.1f}m" if isinstance(age, (int, float)) else "n/a"
            lines.append(
                f"  - `{check['name']}` → `{check.get('timestamp') or 'never'}` (age={age_str})"
            )

    lines.extend(["", "## Gateway Heartbeat" ])
    gateway = report.get("gateway") or {}
    last_entry = gateway.get("last_entry")
    if last_entry:
        lines.append(
            f"- Last `[heartbeat] started`: `{last_entry['timestamp_local']}` (age={last_entry['age_minutes']:.1f}m)"
        )
    else:
        lines.append("- No heartbeat runs found in gateway log.")
    lines.append(
        f"- Entries within last `{gateway.get('window_hours', 0)}`h: `{gateway.get('entries_within_hours', 0)}`"
    )

    lines.extend(["", "## Discord Gateway" ])
    discord = report.get("discord") or {}
    counts = discord.get("counts") or {}
    lines.append(
        f"- Close events last `{discord.get('window_hours', 0)}`h: `{counts.get('closed', 0)}`"
    )
    lines.append(
        f"- Reconnect events last `{discord.get('window_hours', 0)}`h: `{counts.get('reconnect', 0)}`"
    )
    lines.append(
        f"- Other gateway events last `{discord.get('window_hours', 0)}`h: `{counts.get('other', 0)}`"
    )
    latest = discord.get("latest")
    if latest:
        lines.append(
            f"- Latest gateway event: `{latest['type']}` at `{latest['timestamp_local']}` (age={latest['age_minutes']:.1f}m)"
        )

    lines.extend(["", "## Watched Artifacts" ])
    for artifact in report.get("artifacts") or []:
        if not artifact.get("exists"):
            lines.append(f"- `{artifact['label']}` missing → {artifact['path']}")
            continue
        age = artifact.get("age_minutes")
        age_str = f"{age:.1f}m" if isinstance(age, (int, float)) else "n/a"
        lines.append(
            f"- `{artifact['label']}` updated `{artifact.get('modified_local')}` (age={age_str})"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=float,
        default=36.0,
        help="Log lookback window for heartbeat/Discord stats (hours).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    args = parser.parse_args()

    report = build_report(args.hours)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
