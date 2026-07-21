#!/usr/bin/env python3
"""Create a bounded private project snapshot and record local-first run truth."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone

from automation_run_mirror import build_run_payload, mirror_runs
from secure_backup import create_project_snapshot


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


def run(*, api_url: str = DEFAULT_API_URL, keep: int = 7) -> tuple[dict, bool]:
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    status = "success"
    error = None
    result: dict = {}
    try:
        result = create_project_snapshot(keep=keep)
    except Exception as exc:
        status = "error"
        error = str(exc)[:1200]
    finished = datetime.now(timezone.utc)
    metadata = {key: value for key, value in result.items() if key != "sha256"}
    if result.get("sha256"):
        metadata["sha256"] = result["sha256"]
    mirrored = mirror_runs(
        api_url,
        [
            build_run_payload(
                run_id=f"project_snapshot::{uuid.uuid4()}",
                automation_id="project_snapshot",
                automation_name="Secure Project Snapshot",
                status=status,
                source="codex_launchd_registry",
                runtime="launchd",
                run_at=started,
                finished_at=finished,
                duration_ms=round((time.monotonic() - clock) * 1000),
                error=error,
                action_required=status == "error",
                metadata={"local_first": True, **metadata},
            )
        ],
    )
    output = {"status": status, "remote_mirror": "ok" if mirrored else "deferred", **result}
    if error:
        output["error"] = error
    return output, status == "success"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--keep", type=int, default=7)
    args = parser.parse_args()
    result, ok = run(api_url=args.api_url, keep=args.keep)
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
