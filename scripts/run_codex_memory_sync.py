#!/usr/bin/env python3
"""Refresh Codex durable memory and record local-first automation truth."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

from automation_run_mirror import build_run_payload, mirror_runs
from codex_memory_freshness_check import build_report


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run(*, api_url: str = DEFAULT_API_URL) -> tuple[dict[str, object], bool]:
    started = _utcnow()
    started_clock = time.monotonic()
    report = build_report(sync=True)
    finished = _utcnow()
    status = "success" if report.get("status") == "ok" else "failed"
    payload = build_run_payload(
        run_id=f"codex-memory-sync-{started.strftime('%Y%m%dT%H%M%S%fZ')}",
        automation_id="codex_memory_sync",
        automation_name="Codex Durable Memory Sync",
        status=status,
        source="codex_launchd_registry",
        run_at=started,
        finished_at=finished,
        duration_ms=round((time.monotonic() - started_clock) * 1000),
        action_required=status != "success",
        error=None if status == "success" else "Memory freshness verification failed.",
        metadata={
            "backend": report.get("backend"),
            "files": report.get("files"),
            "probe_result_count": report.get("probe_result_count"),
            "local_first": True,
        },
    )
    mirrored = mirror_runs(api_url, [payload])
    output: dict[str, object] = {
        "schema_version": "codex_memory_sync_run/v1",
        "status": report.get("status"),
        "remote_mirror": "ok" if mirrored else "deferred",
        "report": report,
    }
    return output, status == "success"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()
    result, ok = run(api_url=args.api_url)
    print(json.dumps(result, indent=2))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
