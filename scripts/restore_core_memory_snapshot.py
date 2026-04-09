#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import restore_core_memory_snapshot  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore live core memory files from the tracked snapshot lane.")
    parser.add_argument("--snapshot-id", help="Snapshot id under docs/runtime_snapshots/core_memory/. Defaults to latest.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a short text summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = restore_core_memory_snapshot(WORKSPACE_ROOT, snapshot_id=args.snapshot_id)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"snapshot_id={result['snapshot_id']} restored={result['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
