#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill and refresh first-class BrainSignal intake.")
    parser.add_argument("--skip-source-intelligence", action="store_true", help="Do not ingest source-intelligence index entries.")
    parser.add_argument("--skip-workspace-attention", action="store_true", help="Do not ingest portfolio workspace attention state.")
    parser.add_argument("--skip-automation-outputs", action="store_true", help="Do not ingest automation report outputs.")
    parser.add_argument("--include-quiet-automation", action="store_true", help="Register automation reports even when no alert marker is active.")
    parser.add_argument("--source-limit", type=int, default=None, help="Limit source-intelligence entries for test runs.")
    args = parser.parse_args()

    from app.services.brain_signal_intake_service import run_brain_signal_intake

    result = run_brain_signal_intake(
        include_source_intelligence=not args.skip_source_intelligence,
        include_workspace_attention=not args.skip_workspace_attention,
        include_automation_outputs=not args.skip_automation_outputs,
        source_limit=args.source_limit,
        include_quiet_automation=args.include_quiet_automation,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
