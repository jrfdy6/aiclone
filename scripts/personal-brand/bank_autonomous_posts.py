#!/usr/bin/env python3
"""Append drafted autonomous content candidates into the durable content bank."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_content_bank import run_autonomous_content_bank  # noqa: E402
from linkedin_strategy_utils import workspace_root  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bank autonomous LinkedIn post candidates.")
    parser.add_argument("--workspace", help="Override workspace root.")
    parser.add_argument("--dry-run", action="store_true", help="Build the terminal report without writing artifacts.")
    parser.add_argument(
        "--skip-backlog-projection",
        action="store_true",
        help="Write bank JSONL/status artifacts without appending backlog.md projection rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_dir = Path(args.workspace).resolve() if args.workspace else workspace_root()
    report = run_autonomous_content_bank(
        workspace_dir=workspace_dir,
        repo_root=REPO_ROOT,
        write=not args.dry_run,
        project_backlog=not args.skip_backlog_projection,
    )
    print(json.dumps(report.get("summary") or {}, sort_keys=True))


if __name__ == "__main__":
    main()
