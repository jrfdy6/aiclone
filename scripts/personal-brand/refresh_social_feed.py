#!/usr/bin/env python3
"""Refresh the LinkedIn workspace social feed (and optional safe sources)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "personal-brand"

for candidate in (REPO_ROOT / "backend", REPO_ROOT):
    if (candidate / "app").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from app.services.youtube_watchlist_service import sync_watchlist_auto_ingest


def run_fetcher(fetcher: Literal["reddit", "rss"]) -> None:
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / f"fetch_{fetcher}_signals.py")], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the LinkedIn social feed.")
    parser.add_argument("--skip-fetch", action="store_true", help="Build from existing signals only.")
    parser.add_argument("--sources", choices=["safe", "all"], default="safe", help="Which fetchers to run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_fetch:
        sync_watchlist_auto_ingest(run_refresh=False)
        run_fetcher("reddit")
        run_fetcher("rss")
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "build_social_feed.py")], check=True)
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "refresh_linkedin_strategy.py")], check=True)


if __name__ == "__main__":
    main()
