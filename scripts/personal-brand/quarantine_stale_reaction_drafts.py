#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_idea_qualification import quarantine_stale_reaction_drafts  # noqa: E402
from linkedin_strategy_utils import workspace_root  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move stale reaction-seed drafts into archive.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    result = quarantine_stale_reaction_drafts(workspace_dir)
    print(result)


if __name__ == "__main__":
    main()
