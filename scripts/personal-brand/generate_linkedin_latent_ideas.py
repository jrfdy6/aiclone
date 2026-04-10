#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_idea_qualification import load_or_build_latent_idea_payload  # noqa: E402
from linkedin_strategy_utils import workspace_root  # noqa: E402


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the LinkedIn latent-idea artifacts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    payload = load_or_build_latent_idea_payload(workspace_dir)
    print(payload.get("summary") or {})


if __name__ == "__main__":
    main()
