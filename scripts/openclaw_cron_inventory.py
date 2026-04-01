#!/usr/bin/env python3
"""Export a baseline inventory for the live OpenClaw cron layer."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openclaw_cron_utils import JOBS_JSON, OPENCLAW_ROOT, extract_references, load_jobs, schedule_label

LOG_PATTERNS = {
    "edit_failed": re.compile(r"\[tools\] edit failed", re.IGNORECASE),
    "read_failed": re.compile(r"\[tools\] read failed", re.IGNORECASE),
    "message_failed": re.compile(r"\[tools\] message failed", re.IGNORECASE),
    "lane_wait_exceeded": re.compile(r"lane wait exceeded", re.IGNORECASE),
    "discord_gateway_error": re.compile(r"\[discord\] gateway error", re.IGNORECASE),
    "ws_unauthorized": re.compile(r"\[ws\] unauthorized", re.IGNORECASE),
}


def _iso_from_ms(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def _summarize_log(log_path: Path) -> dict:
    if not log_path.exists():
        return {"path": str(log_path), "missing": True, "counts": {}, "samples": {}}

    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {key: [] for key in LOG_PATTERNS}
    for raw_line in log_path.read_text(errors="replace").splitlines():
        for key, pattern in LOG_PATTERNS.items():
            if pattern.search(raw_line):
                counts[key] += 1
                if len(samples[key]) < 5:
                    samples[key].append(raw_line)
    return {
        "path": str(log_path),
        "counts": dict(counts),
        "samples": {key: value for key, value in samples.items() if value},
    }


def build_inventory(jobs_file: Path, log_path: Path) -> dict:
    jobs = load_jobs(jobs_file)
    rows = []
    for job in jobs:
        payload = job.get("payload") or {}
        state = job.get("state") or {}
        delivery = job.get("delivery") or {}
        message = payload.get("message", "")
        rows.append(
            {
                "id": job.get("id"),
                "name": job.get("name"),
                "enabled": bool(job.get("enabled")),
                "agent_id": job.get("agentId"),
                "session_key": job.get("sessionKey"),
                "session_target": job.get("sessionTarget"),
                "wake_mode": job.get("wakeMode"),
                "schedule": schedule_label(job),
                "delivery_channel": delivery.get("channel"),
                "delivery_target": delivery.get("to"),
                "delivery_mode": delivery.get("mode"),
                "model": payload.get("model"),
                "last_status": state.get("lastStatus"),
                "last_run_status": state.get("lastRunStatus"),
                "last_delivered": state.get("lastDelivered"),
                "last_delivery_status": state.get("lastDeliveryStatus"),
                "last_error": state.get("lastError"),
                "last_run_at": _iso_from_ms(state.get("lastRunAtMs")),
                "next_run_at": _iso_from_ms(state.get("nextRunAtMs")),
                "last_duration_ms": state.get("lastDurationMs"),
                "reference_count": len(extract_references(message)),
                "references": extract_references(message),
            }
        )

    failing = [row for row in rows if row.get("last_status") == "error"]
    undelivered = [row for row in rows if row.get("last_status") == "ok" and row.get("last_delivered") is False]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs_file": str(jobs_file),
        "job_count": len(rows),
        "jobs": rows,
        "summary": {
            "enabled_jobs": sum(1 for row in rows if row["enabled"]),
            "jobs_with_errors": len(failing),
            "jobs_ok_but_not_delivered": len(undelivered),
            "discord_jobs": sum(1 for row in rows if row["delivery_channel"] == "discord"),
            "webchat_jobs": sum(1 for row in rows if row["delivery_channel"] == "webchat"),
            "agent_turn_jobs": sum(1 for row in rows if row["model"]),
        },
        "known_problem_jobs": {
            "errors": [{"name": row["name"], "last_error": row["last_error"]} for row in failing],
            "undelivered": [{"name": row["name"], "delivery_target": row["delivery_target"]} for row in undelivered],
        },
        "log_summary": _summarize_log(log_path),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# OpenClaw Cron Inventory Baseline",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Jobs file: `{report['jobs_file']}`",
        f"- Job count: `{report['job_count']}`",
        "",
        "## Summary",
        f"- Enabled jobs: `{report['summary']['enabled_jobs']}`",
        f"- Jobs with errors: `{report['summary']['jobs_with_errors']}`",
        f"- Jobs ok but not delivered: `{report['summary']['jobs_ok_but_not_delivered']}`",
        f"- Discord delivery jobs: `{report['summary']['discord_jobs']}`",
        f"- Webchat delivery jobs: `{report['summary']['webchat_jobs']}`",
        f"- Agent-turn jobs: `{report['summary']['agent_turn_jobs']}`",
        "",
        "## Job Table",
        "",
        "| Job | Schedule | Delivery | Last Status | Delivered | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["jobs"]:
        delivery = f"{row['delivery_channel']}->{row['delivery_target']}"
        note = row["last_error"] or ""
        lines.append(
            f"| {row['name']} | `{row['schedule']}` | `{delivery}` | `{row['last_status']}` | `{row['last_delivered']}` | {note} |"
        )

    log_summary = report.get("log_summary", {})
    counts = log_summary.get("counts", {})
    if counts:
        lines.extend(
            [
                "",
                "## Recent Log Pattern Counts",
                "",
            ]
        )
        for key in sorted(counts):
            lines.append(f"- `{key}`: `{counts[key]}`")

    known_problem_jobs = report.get("known_problem_jobs", {})
    if known_problem_jobs.get("errors"):
        lines.extend(["", "## Jobs Currently In Error", ""])
        for item in known_problem_jobs["errors"]:
            lines.append(f"- `{item['name']}`: {item['last_error']}")
    if known_problem_jobs.get("undelivered"):
        lines.extend(["", "## Jobs Currently Ok But Not Delivered", ""])
        for item in known_problem_jobs["undelivered"]:
            lines.append(f"- `{item['name']}` -> `{item['delivery_target']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a baseline inventory of OpenClaw cron jobs.")
    parser.add_argument("--jobs-file", type=Path, default=JOBS_JSON)
    parser.add_argument("--log-file", type=Path, default=OPENCLAW_ROOT / "logs" / "gateway.err.log")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args()

    report = build_inventory(args.jobs_file, args.log_file)
    markdown = render_markdown(report)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    else:
        print(json.dumps(report, indent=2))

    if args.md_out:
        args.md_out.write_text(markdown)
    elif not args.json_out:
        print("\n" + markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
