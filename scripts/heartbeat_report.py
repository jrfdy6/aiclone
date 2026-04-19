#!/usr/bin/env python3
"""Produce a short heartbeat/Discord diagnostics report for operators."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path

STATE_PATH = WORKSPACE_ROOT / "memory" / "heartbeat-state.json"
GATEWAY_LOG = Path.home() / ".openclaw" / "logs" / "gateway.log"
CRON_PRUNE = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/cron-prune.md")
DAILY_BRIEFS = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/daily-briefs.md")
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
    last_activity: dict | None = None
    window_count = 0
    for line in reversed(lines):
        ts = _timestamp_from_line(line)
        if ts is None:
            continue
        if last_activity is None:
            last_activity = {
                "timestamp_local": _format_ts(ts),
                "timestamp_utc": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "age_minutes": _age_minutes(now, ts),
                "line": line.strip(),
            }
        if last_entry is None and HEARTBEAT_PATTERN.search(line):
            last_entry = {
                "timestamp_local": _format_ts(ts),
                "timestamp_utc": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "age_minutes": _age_minutes(now, ts),
                "line": line.strip(),
            }
        if ts.astimezone(timezone.utc) >= cutoff:
            window_count += 1

    return {
        "path": str(GATEWAY_LOG),
        "missing": False,
        "last_activity": last_activity,
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
    last_activity = gateway.get("last_activity")
    if last_activity:
        lines.append(
            f"- Latest gateway activity: `{last_activity['timestamp_local']}` (age={last_activity['age_minutes']:.1f}m)"
        )
    last_entry = gateway.get("last_entry")
    if last_entry:
        lines.append(
            f"- Latest `[heartbeat] started` bootstrap: `{last_entry['timestamp_local']}` (age={last_entry['age_minutes']:.1f}m)"
        )
    elif not last_activity:
        lines.append("- No heartbeat or gateway activity entries found in gateway log.")
    lines.append(
        f"- Gateway log entries within last `{gateway.get('window_hours', 0)}`h: `{gateway.get('entries_within_hours', 0)}`"
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


def _format_short_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    return dt.astimezone(TZ).strftime("%H:%M %Z")


def _format_age(age: float | int | None) -> str:
    if age is None:
        return "n/a"
    if age >= 90:
        return f"{age / 60:.1f}h"
    return f"{age:.0f}m"


def _find_check(state: dict, name: str) -> dict | None:
    for check in state.get("checks") or []:
        if check.get("name") == name:
            return check
    return None


def _find_artifact(report: dict, label: str) -> dict | None:
    for artifact in report.get("artifacts") or []:
        if artifact.get("label") == label:
            return artifact
    return None


def render_summary(report: dict) -> str:
    state = report.get("state") or {}
    prefix = state.get("note") or state.get("status") or "HEARTBEAT"
    parts: list[str] = []

    primary_check = _find_check(state, "automation_health")
    if not primary_check and state.get("checks"):
        primary_check = state["checks"][0]
    if primary_check:
        ts = _format_short_ts(primary_check.get("timestamp"))
        age = _format_age(primary_check.get("age_minutes"))
        parts.append(f"checks {ts or 'never'} (age {age})")

    gateway = report.get("gateway") or {}
    gateway_freshness = gateway.get("last_activity") or gateway.get("last_entry")
    if gateway_freshness:
        ts = _format_short_ts(gateway_freshness.get("timestamp_local"))
        age = _format_age(gateway_freshness.get("age_minutes"))
        label = "gateway activity" if gateway.get("last_activity") else "gateway run"
        parts.append(f"{label} {ts or 'unknown'} (age {age})")

    discord = report.get("discord") or {}
    counts = discord.get("counts") or {}
    window = discord.get("window_hours")
    latest = discord.get("latest")
    counts_str = f"{counts.get('closed', 0)}/{counts.get('reconnect', 0)} closes/reconnects"
    window_str = f"{window:.0f}h" if isinstance(window, (int, float)) else "n/a"
    discord_bits = f"discord {counts_str} ({window_str})"
    if latest:
        ts = _format_short_ts(latest.get("timestamp_local"))
        discord_bits += f"; last {latest.get('type')} {ts or 'unknown'}"
    parts.append(discord_bits)

    exec_log = _find_artifact(report, "execution_log_shared_ops")
    if exec_log and exec_log.get("exists"):
        ts = _format_short_ts(exec_log.get("modified_local"))
        age = _format_age(exec_log.get("age_minutes"))
        parts.append(f"exec log {ts or 'never'} (age {age})")

    cron = _find_artifact(report, "cron_prune")
    if cron and cron.get("exists"):
        ts = _format_short_ts(cron.get("modified_local"))
        parts.append(f"cron {ts or 'never'}")

    today_log = _find_artifact(report, "extra_0")
    if today_log and today_log.get("exists"):
        ts = _format_short_ts(today_log.get("modified_local"))
        parts.append(f"daily log {ts or 'never'}")

    if not parts:
        parts.append("no diagnostics found")
    return f"{prefix} — " + "; ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=float,
        default=36.0,
        help="Log lookback window for heartbeat/Discord stats (hours).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a condensed single-line summary suitable for Discord.",
    )
    args = parser.parse_args()

    report = build_report(args.hours)
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.summary:
        print(render_summary(report))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
