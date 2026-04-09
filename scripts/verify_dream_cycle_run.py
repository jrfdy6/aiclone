#!/usr/bin/env python3
"""Verify that a Dream Cycle cron run completed cleanly and updated durable state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


OPENCLAW_ROOT = Path("/Users/neo/.openclaw")
WORKSPACE_ROOT = OPENCLAW_ROOT / "workspace"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path

JOBS_PATH = OPENCLAW_ROOT / "cron" / "jobs.json"
CRON_RUNS_DIR = OPENCLAW_ROOT / "cron" / "runs"
GATEWAY_ERR_LOG = OPENCLAW_ROOT / "logs" / "gateway.err.log"
PERSISTENT_STATE = WORKSPACE_ROOT / "memory" / "persistent_state.md"
DREAM_CYCLE_LOG = resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/dream_cycle_log.md")
QMD_FRESHNESS_SCRIPT = WORKSPACE_ROOT / "scripts" / "qmd_freshness_check.py"
REPORT_GLOB = str(WORKSPACE_ROOT / "memory" / "reports" / "memory_health_*.md")

KNOWN_INPUT_FAILURES = (
    "memory/reports/memory_health_*.md",
    str(WORKSPACE_ROOT / "knowledge/"),
    "memory/YYYY-MM-DD.md",
)


@dataclass
class FileCheck:
    path: str
    exists: bool
    modified_local: str | None
    modified_utc: str | None
    updated_after_run: bool
    tail_mentions_target_date: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", dest="date_str", help="Target local date in YYYY-MM-DD. Defaults to today in --timezone.")
    parser.add_argument("--timezone", default="America/New_York", help="IANA timezone for schedule evaluation.")
    parser.add_argument("--schedule-time", default="06:15", help="Expected Dream Cycle local start time (HH:MM).")
    parser.add_argument("--run-grace-minutes", type=int, default=15, help="Allowed delay after the scheduled start.")
    parser.add_argument(
        "--error-window-minutes",
        type=int,
        default=15,
        help="How long after the scheduled start to scan gateway.err.log for known input failures.",
    )
    parser.add_argument("--job-name", default="Dream Cycle", help="Cron job name to verify.")
    parser.add_argument("--job-id", help="Override the Dream Cycle cron job id.")
    parser.add_argument("--report-out", help="Optional absolute markdown report path to write.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    return parser.parse_args()


def local_now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def resolve_target_date(args: argparse.Namespace, tz: ZoneInfo) -> date:
    if args.date_str:
        return date.fromisoformat(args.date_str)
    return local_now(tz).date()


def expected_run_datetime(target_date: date, schedule_time: str, tz: ZoneInfo) -> datetime:
    hour_str, minute_str = schedule_time.split(":", 1)
    scheduled = time(hour=int(hour_str), minute=int(minute_str))
    return datetime.combine(target_date, scheduled, tzinfo=tz)


def load_jobs() -> list[dict[str, Any]]:
    return json.loads(JOBS_PATH.read_text()).get("jobs", [])


def resolve_job_id(job_name: str, explicit_job_id: str | None) -> str | None:
    if explicit_job_id:
        return explicit_job_id
    for job in load_jobs():
        if job.get("name") == job_name:
            return job.get("id")
    return None


def load_run_records(job_id: str) -> list[dict[str, Any]]:
    run_path = CRON_RUNS_DIR / f"{job_id}.jsonl"
    if not run_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in run_path.read_text(errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            records.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return records


def choose_run(records: list[dict[str, Any]], start_ms: int, end_ms: int) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for record in records:
        if record.get("action") != "finished":
            continue
        run_at = int(record.get("runAtMs") or 0)
        if run_at < start_ms or run_at > end_ms:
            continue
        if best is None or run_at > int(best.get("runAtMs") or 0):
            best = record
    return best


def human_date_variants(target_date: date) -> tuple[str, str]:
    iso = target_date.isoformat()
    long = f"{target_date.strftime('%B')} {target_date.day}, {target_date.year}"
    return iso, long


def file_check(path: Path, run_at_ms: int | None, target_date: date, tz: ZoneInfo) -> FileCheck:
    exists = path.exists()
    modified_local = None
    modified_utc = None
    updated_after_run = False
    tail_mentions_target_date = False

    if exists:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        modified_local = modified.astimezone(tz).isoformat(timespec="seconds")
        modified_utc = modified.isoformat(timespec="seconds")
        updated_after_run = run_at_ms is not None and int(path.stat().st_mtime * 1000) >= run_at_ms
        iso, long = human_date_variants(target_date)
        tail = path.read_text(errors="replace")[-6000:]
        tail_mentions_target_date = iso in tail or long in tail

    return FileCheck(
        path=str(path),
        exists=exists,
        modified_local=modified_local,
        modified_utc=modified_utc,
        updated_after_run=updated_after_run,
        tail_mentions_target_date=tail_mentions_target_date,
    )


def parse_log_timestamp(line: str) -> datetime | None:
    head, _, _ = line.partition(" ")
    try:
        parsed = datetime.fromisoformat(head)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def find_known_failures(start: datetime, end: datetime) -> list[dict[str, str]]:
    if not GATEWAY_ERR_LOG.exists():
        return []
    failures: list[dict[str, str]] = []
    for line in GATEWAY_ERR_LOG.read_text(errors="replace").splitlines():
        ts = parse_log_timestamp(line)
        if ts is None:
            continue
        if ts < start.astimezone(timezone.utc) or ts > end.astimezone(timezone.utc):
            continue
        for pattern in KNOWN_INPUT_FAILURES:
            if pattern in line:
                failures.append(
                    {
                        "timestamp": ts.astimezone(start.tzinfo).isoformat(timespec="seconds"),
                        "pattern": pattern,
                        "line": line.strip(),
                    }
                )
                break
    return failures


def latest_memory_health_report() -> str | None:
    matches = sorted(Path(WORKSPACE_ROOT / "memory" / "reports").glob("memory_health_*.md"), key=lambda p: p.stat().st_mtime)
    if not matches:
        return None
    return str(matches[-1])


def qmd_status() -> dict[str, Any]:
    if not QMD_FRESHNESS_SCRIPT.exists():
        return {"available": False, "error": f"Missing {QMD_FRESHNESS_SCRIPT}"}

    result = subprocess.run(
        [sys.executable, str(QMD_FRESHNESS_SCRIPT)],
        capture_output=True,
        text=True,
    )
    payload: dict[str, Any] = {
        "available": True,
        "returncode": result.returncode,
    }
    try:
        payload.update(json.loads(result.stdout or "{}"))
    except json.JSONDecodeError:
        payload["parse_error"] = "Invalid JSON from qmd_freshness_check.py"
        payload["stdout"] = (result.stdout or "").strip()
    if result.stderr:
        payload["stderr"] = result.stderr.strip()
    return payload


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tz = ZoneInfo(args.timezone)
    target_date = resolve_target_date(args, tz)
    expected_local = expected_run_datetime(target_date, args.schedule_time, tz)
    expected_ms = int(expected_local.astimezone(timezone.utc).timestamp() * 1000)
    deadline_local = expected_local + timedelta(minutes=args.run_grace_minutes)
    deadline_ms = int(deadline_local.astimezone(timezone.utc).timestamp() * 1000)

    job_id = resolve_job_id(args.job_name, args.job_id)
    records = load_run_records(job_id) if job_id else []
    run = choose_run(records, expected_ms, deadline_ms) if job_id else None
    run_at_ms = int(run.get("runAtMs")) if run else None

    persistent = file_check(PERSISTENT_STATE, run_at_ms, target_date, tz)
    narrative = file_check(DREAM_CYCLE_LOG, run_at_ms, target_date, tz)
    failure_window_end = expected_local + timedelta(minutes=args.error_window_minutes)
    failures = find_known_failures(expected_local, failure_window_end)
    qmd = qmd_status()
    report_path = latest_memory_health_report()

    errors: list[str] = []
    warnings: list[str] = []

    if job_id is None:
        errors.append(f'Could not find cron job named "{args.job_name}".')
    if run is None:
        errors.append(
            f"No finished Dream Cycle run was recorded between {expected_local.isoformat(timespec='seconds')} and {deadline_local.isoformat(timespec='seconds')}."
        )
    elif run.get("status") != "ok":
        errors.append(f"Dream Cycle run status was {run.get('status')} instead of ok.")

    if run_at_ms is not None:
        if not persistent.updated_after_run:
            errors.append("persistent_state.md was not updated after the Dream Cycle run started.")
        if not narrative.updated_after_run:
            errors.append("dream_cycle_log.md was not updated after the Dream Cycle run started.")
    if not persistent.exists:
        errors.append("persistent_state.md is missing.")
    if not narrative.exists:
        errors.append("dream_cycle_log.md is missing.")
    if persistent.exists and not persistent.tail_mentions_target_date:
        warnings.append("persistent_state.md tail does not explicitly mention the target date.")
    if narrative.exists and not narrative.tail_mentions_target_date:
        warnings.append("dream_cycle_log.md tail does not explicitly mention the target date.")
    if failures:
        errors.append("Known Dream Cycle input failures were detected in gateway.err.log during the run window.")
    if report_path is None:
        errors.append("No memory_health_*.md report is available for Dream Cycle to ground against.")
    if not qmd.get("alias_ready", False):
        errors.append("QMD alias verification is not ready; Dream Cycle grounding remains degraded.")
    if qmd.get("vector_available") is False:
        warnings.append("QMD vector search is unavailable; lexical retrieval still works but semantic depth is reduced.")
    if errors:
        status = "ALERT"
    elif warnings:
        status = "WARN"
    else:
        status = "OK"

    report = {
        "status": status,
        "target_date": target_date.isoformat(),
        "timezone": args.timezone,
        "expected_run_local": expected_local.isoformat(timespec="seconds"),
        "verification_deadline_local": deadline_local.isoformat(timespec="seconds"),
        "verified_at_local": local_now(tz).isoformat(timespec="seconds"),
        "job_name": args.job_name,
        "job_id": job_id,
        "run_record": run,
        "persistent_state": asdict(persistent),
        "dream_cycle_log": asdict(narrative),
        "latest_memory_health_report": report_path,
        "qmd": qmd,
        "known_failures": failures,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"Dream Cycle Verification — {report['target_date']}",
        f"Status: {report['status']}",
        "",
        "Checks:",
        f"- Expected run: {report['expected_run_local']}",
        f"- Verification deadline: {report['verification_deadline_local']}",
    ]

    run = report.get("run_record")
    if run:
        lines.extend(
            [
                f"- Observed run: {datetime.fromtimestamp(run['runAtMs'] / 1000, tz=timezone.utc).astimezone(ZoneInfo(report['timezone'])).isoformat(timespec='seconds')}",
                f"- Cron status: {run.get('status')}",
                f"- Duration: {run.get('durationMs')} ms",
            ]
        )
    else:
        lines.append("- Observed run: missing")

    lines.extend(
        [
            f"- persistent_state updated after run: {report['persistent_state']['updated_after_run']}",
            f"- dream_cycle_log updated after run: {report['dream_cycle_log']['updated_after_run']}",
            f"- Latest memory health report: {report['latest_memory_health_report'] or 'missing'}",
            f"- QMD alias ready: {report['qmd'].get('alias_ready')}",
        ]
    )

    if report["errors"]:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {item}" for item in report["errors"])

    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item}" for item in report["warnings"])

    if report["known_failures"]:
        lines.extend(["", "Known Failure Hits:"])
        for hit in report["known_failures"]:
            lines.append(f"- {hit['timestamp']} :: {hit['pattern']}")

    lines.extend(
        [
            "",
            "Next Steps:",
            "- If status is ALERT, inspect gateway.err.log and the Dream Cycle cron run record immediately.",
            "- If status is WARN, verify whether the warning is expected for the current time window before changing the cron.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(path_str: str, body: str) -> None:
    target = Path(path_str).expanduser()
    if not target.is_absolute():
        raise SystemExit("--report-out must be an absolute path.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = build_report(args)
    markdown = render_markdown(report)

    if args.report_out:
        write_report(args.report_out, markdown)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(markdown.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
