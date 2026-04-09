#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import build_core_memory_snapshot  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture an exact tracked snapshot of the live core memory files.")
    parser.add_argument(
        "--snapshot-id",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Snapshot directory name under docs/runtime_snapshots/core_memory/",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a short text summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_core_memory_snapshot(WORKSPACE_ROOT, snapshot_id=args.snapshot_id)
    if args.json:
        print(json.dumps(manifest, indent=2))
    else:
        print(
            f"snapshot_id={manifest['snapshot_id']} files={sum(1 for item in manifest['files'] if item.get('exists'))} "
            f"root={manifest['snapshot_root']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
