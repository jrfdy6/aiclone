#!/usr/bin/env python3
"""Run the deterministic daily external-service health launchd job."""
from __future__ import annotations

import argparse
import json

from scheduled_automation_runtime import DEFAULT_API_URL, run_scheduled_task
from scheduled_automation_tasks import DEFAULT_FRONTEND_URL, check_external_services


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--mirror-attempts", type=int, default=3)
    args = parser.parse_args()
    result, ok = run_scheduled_task(
        automation_id="external_service_health",
        automation_name="External Service Health",
        api_url=args.api_url,
        mirror_attempts=args.mirror_attempts,
        task=lambda: check_external_services(
            api_url=args.api_url,
            frontend_url=args.frontend_url,
            timeout_seconds=args.timeout_seconds,
        ),
    )
    print(json.dumps(result, indent=2))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
