#!/usr/bin/env python3
"""Refresh the LinkedIn workspace social feed (and optional safe sources)."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "personal-brand"


def run_fetcher(fetcher: Literal["reddit", "rss"]) -> None:
    subprocess.run(["python3", str(SCRIPTS_ROOT / f"fetch_{fetcher}_signals.py")], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the LinkedIn social feed.")
    parser.add_argument("--skip-fetch", action="store_true", help="Build from existing signals only.")
    parser.add_argument("--sources", choices=["safe", "all"], default="safe", help="Which fetchers to run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_fetch:
        run_fetcher("reddit")
        run_fetcher("rss")
    subprocess.run(["python3", str(SCRIPTS_ROOT / "build_social_feed.py")], check=True)


if __name__ == "__main__":
    main()
