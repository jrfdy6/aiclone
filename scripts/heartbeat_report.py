#!/usr/bin/env python3
"""Produce a short Codex-native runtime health report for operators."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_paths import (  # noqa: E402
    AUTOMATION_RUNS_ROOT,
    MEMORY_INDEX_PATH,
    PROJECT_ROOT,
    STATE_ROOT,
    resolve_memory_read_path,
)


WORKSPACE_ROOT = PROJECT_ROOT
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
for import_root in (BACKEND_ROOT,):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path


STATE_PATH = STATE_ROOT / "heartbeat" / "heartbeat-state.json"
RUN_LOG = AUTOMATION_RUNS_ROOT / "all.jsonl"
LAUNCHD_AUDIT = resolve_memory_read_path("reports/launchd_health_audit_latest.json")
DAILY_BRIEFS = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/daily-briefs.md")
EXECUTION_LOG = WORKSPACE_ROOT / "workspaces" / "shared-ops" / "memory" / "execution_log.md"
TZ = ZoneInfo("America/New_York")


@dataclass
class ArtifactSpec:
    label: str
    path: Path


ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("automation_run_ledger", RUN_LOG),
    ArtifactSpec("memory_index", MEMORY_INDEX_PATH),
    ArtifactSpec("launchd_health_audit", LAUNCHD_AUDIT),
    ArtifactSpec("daily_briefs", DAILY_BRIEFS),
    ArtifactSpec("execution_log_shared_ops", EXECUTION_LOG),
)


def _now() -> datetime:
    return datetime.now(tz=TZ)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _age_minutes(now: datetime, then: datetime | None) -> float | None:
    if then is None:
        return None
    delta = now.astimezone(timezone.utc) - then.astimezone(timezone.utc)
    return max(delta.total_seconds() / 60.0, 0)


def _format_ts(dt: datetime | None, tz: ZoneInfo = TZ) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(tz).isoformat(timespec="seconds")


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_state(now: datetime) -> dict[str, Any]:
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    except (json.JSONDecodeError, OSError):
        state = {}

    last_checks = state.get("lastChecks") or {}
    check_rows = []
    for key in sorted(last_checks):
        raw = last_checks.get(key)
        dt = datetime.fromtimestamp(float(raw), tz=timezone.utc) if isinstance(raw, (int, float)) else None
        check_rows.append(
            {
                "name": key,
                "timestamp": _format_ts(dt),
                "age_minutes": _age_minutes(now, dt),
            }
        )
    return {
        "checks": check_rows,
        "status": state.get("lastHeartbeatStatus"),
        "note": state.get("lastHeartbeatNote"),
        "path": str(STATE_PATH),
    }


def analyze_runtime(now: datetime, hours: float) -> dict[str, Any]:
    rows = _parse_jsonl(RUN_LOG)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=hours)
    within_window: list[tuple[datetime, dict[str, Any]]] = []
    latest: tuple[datetime, dict[str, Any]] | None = None
    latest_success: tuple[datetime, dict[str, Any]] | None = None

    for row in rows:
        timestamp = _parse_timestamp(row.get("finished_at")) or _parse_timestamp(row.get("run_at"))
        if timestamp is None:
            continue
        if latest is None or timestamp > latest[0]:
            latest = (timestamp, row)
        if str(row.get("status") or "").lower() in {"ok", "success", "completed"}:
            if latest_success is None or timestamp > latest_success[0]:
                latest_success = (timestamp, row)
        if timestamp.astimezone(timezone.utc) >= cutoff:
            within_window.append((timestamp, row))

    status_counts: dict[str, int] = {}
    automation_ids: set[str] = set()
    for _, row in within_window:
        status = str(row.get("status") or "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1
        automation_id = str(row.get("automation_id") or "").strip()
        if automation_id:
            automation_ids.add(automation_id)

    def snapshot(item: tuple[datetime, dict[str, Any]] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        timestamp, row = item
        return {
            "timestamp_local": _format_ts(timestamp),
            "timestamp_utc": timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "age_minutes": _age_minutes(now, timestamp),
            "automation_id": row.get("automation_id"),
            "automation_name": row.get("automation_name"),
            "status": row.get("status"),
            "runtime": row.get("runtime"),
            "action_required": bool(row.get("action_required")),
        }

    return {
        "path": str(RUN_LOG),
        "missing": not RUN_LOG.exists(),
        "window_hours": hours,
        "runs_within_hours": len(within_window),
        "automation_count": len(automation_ids),
        "status_counts": status_counts,
        "action_required_count": sum(1 for _, row in within_window if row.get("action_required")),
        "latest_activity": snapshot(latest),
        "latest_success": snapshot(latest_success),
    }


def analyze_launchd_audit(now: datetime) -> dict[str, Any]:
    if not LAUNCHD_AUDIT.exists():
        return {"path": str(LAUNCHD_AUDIT), "missing": True}
    try:
        payload = json.loads(LAUNCHD_AUDIT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"path": str(LAUNCHD_AUDIT), "missing": False, "invalid": True}
    generated_at = _parse_timestamp(payload.get("generated_at"))
    return {
        "path": str(LAUNCHD_AUDIT),
        "missing": False,
        "invalid": False,
        "generated_at": _format_ts(generated_at),
        "age_minutes": _age_minutes(now, generated_at),
        "counts": payload.get("counts") or {},
        "mirrored": payload.get("mirrored"),
    }


def artifact_snapshots(now: datetime, extra_paths: Iterable[Path] | None = None) -> list[dict[str, Any]]:
    paths = list(ARTIFACTS)
    if extra_paths:
        paths.extend(ArtifactSpec(f"extra_{idx}", path) for idx, path in enumerate(extra_paths))
    snapshots: list[dict[str, Any]] = []
    for spec in paths:
        entry: dict[str, Any] = {"label": spec.label, "path": str(spec.path), "exists": spec.path.exists()}
        if spec.path.exists():
            mtime = datetime.fromtimestamp(spec.path.stat().st_mtime, tz=timezone.utc)
            entry.update(
                {
                    "modified_local": _format_ts(mtime),
                    "modified_utc": mtime.isoformat(timespec="seconds"),
                    "age_minutes": _age_minutes(now, mtime),
                }
            )
        snapshots.append(entry)
    return snapshots


def build_report(hours: float) -> dict[str, Any]:
    now = _now()
    today_log = WORKSPACE_ROOT / "memory" / f"{now.date().isoformat()}.md"
    return {
        "generated_at_local": _format_ts(now),
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "state": load_state(now),
        "runtime": analyze_runtime(now, hours),
        "launchd": analyze_launchd_audit(now),
        "artifacts": artifact_snapshots(now, [today_log]),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Codex Runtime Health Report",
        "",
        f"- Generated (local): `{report['generated_at_local']}`",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        "",
        "## Heartbeat State",
    ]
    state = report.get("state") or {}
    lines.append(f"- Status: `{state.get('status') or 'unknown'}`")
    if state.get("note"):
        lines.append(f"- Note: `{state['note']}`")
    for check in state.get("checks") or []:
        lines.append(f"- `{check['name']}`: `{check.get('timestamp') or 'never'}` (age={_format_age(check.get('age_minutes'))})")

    runtime = report.get("runtime") or {}
    lines.extend(["", "## Local Automation Runtime"])
    lines.append(f"- Runs in last `{runtime.get('window_hours', 0)}`h: `{runtime.get('runs_within_hours', 0)}` across `{runtime.get('automation_count', 0)}` automations")
    lines.append(f"- Status counts: `{json.dumps(runtime.get('status_counts') or {}, sort_keys=True)}`")
    lines.append(f"- Action-required runs: `{runtime.get('action_required_count', 0)}`")
    latest = runtime.get("latest_activity")
    if latest:
        lines.append(f"- Latest: `{latest.get('automation_id')}` `{latest.get('status')}` at `{latest.get('timestamp_local')}` (age={_format_age(latest.get('age_minutes'))})")
    else:
        lines.append("- No local automation runs have been recorded yet.")

    launchd = report.get("launchd") or {}
    lines.extend(["", "## Launchd"])
    if launchd.get("missing"):
        lines.append("- No launchd audit has been recorded yet.")
    elif launchd.get("invalid"):
        lines.append("- The latest launchd audit is unreadable.")
    else:
        counts = launchd.get("counts") or {}
        lines.append(f"- Installed: `{counts.get('installed_labels', 0)}`; loaded: `{counts.get('loaded_labels', 0)}`; errors: `{counts.get('errors', 0)}`; warnings: `{counts.get('warnings', 0)}`")
        lines.append(f"- Audit age: `{_format_age(launchd.get('age_minutes'))}`")

    lines.extend(["", "## Watched Artifacts"])
    for artifact in report.get("artifacts") or []:
        if artifact.get("exists"):
            lines.append(f"- `{artifact['label']}` updated `{artifact.get('modified_local')}` (age={_format_age(artifact.get('age_minutes'))})")
        else:
            lines.append(f"- `{artifact['label']}` missing -> {artifact['path']}")
    return "\n".join(lines) + "\n"


def _format_short_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    parsed = _parse_timestamp(ts)
    return parsed.astimezone(TZ).strftime("%H:%M %Z") if parsed else ts


def _format_age(age: float | int | None) -> str:
    if age is None:
        return "n/a"
    return f"{age / 60:.1f}h" if age >= 90 else f"{age:.0f}m"


def _find_check(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((check for check in state.get("checks") or [] if check.get("name") == name), None)


def _find_artifact(report: dict[str, Any], label: str) -> dict[str, Any] | None:
    return next((item for item in report.get("artifacts") or [] if item.get("label") == label), None)


def render_summary(report: dict[str, Any]) -> str:
    state = report.get("state") or {}
    prefix = state.get("note") or state.get("status") or "RUNTIME"
    parts: list[str] = []
    primary_check = _find_check(state, "automation_health") or next(iter(state.get("checks") or []), None)
    if primary_check:
        parts.append(f"checks {_format_short_ts(primary_check.get('timestamp')) or 'never'} (age {_format_age(primary_check.get('age_minutes'))})")

    runtime = report.get("runtime") or {}
    latest = runtime.get("latest_activity")
    if latest:
        parts.append(f"runtime `{latest.get('automation_id')}` {latest.get('status')} (age {_format_age(latest.get('age_minutes'))})")
    else:
        parts.append("runtime has no recorded runs")
    status_counts = runtime.get("status_counts") or {}
    parts.append(f"runs {runtime.get('runs_within_hours', 0)}; errors {status_counts.get('error', 0)}; action-required {runtime.get('action_required_count', 0)}")

    launchd = report.get("launchd") or {}
    counts = launchd.get("counts") or {}
    if not launchd.get("missing"):
        parts.append(f"launchd {counts.get('loaded_labels', 0)}/{counts.get('installed_labels', 0)} loaded; {counts.get('errors', 0)} errors")

    memory_index = _find_artifact(report, "memory_index")
    if memory_index and memory_index.get("exists"):
        parts.append(f"memory index age {_format_age(memory_index.get('age_minutes'))}")
    return f"{prefix} — " + "; ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=36.0, help="Automation run lookback window in hours.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument("--summary", action="store_true", help="Print a condensed single-line summary.")
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
