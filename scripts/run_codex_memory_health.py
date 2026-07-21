#!/usr/bin/env python3
"""Run the deterministic daily memory-health launchd job."""
from __future__ import annotations

import argparse
import json

from scheduled_automation_runtime import DEFAULT_API_URL, run_scheduled_task
from scheduled_automation_tasks import build_memory_health


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--mirror-attempts", type=int, default=3)
    args = parser.parse_args()
    result, ok = run_scheduled_task(
        automation_id="memory_health_check",
        automation_name="Memory Health Check",
        api_url=args.api_url,
        mirror_attempts=args.mirror_attempts,
        task=lambda: build_memory_health(timeout_seconds=args.timeout_seconds),
    )
    print(json.dumps(result, indent=2))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
