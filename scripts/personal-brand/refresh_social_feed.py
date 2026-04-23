#!/usr/bin/env python3
"""Refresh the LinkedIn workspace social feed (and optional safe sources)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "personal-brand"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"

for candidate in (REPO_ROOT / "backend", REPO_ROOT):
    if (candidate / "app").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from app.services.youtube_watchlist_service import sync_watchlist_auto_ingest


def run_script(script_path: Path, *extra_args: str, required: bool = True) -> bool:
    command = [sys.executable, str(script_path), *extra_args]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        if required:
            raise
        relative_path = script_path.relative_to(REPO_ROOT)
        print(f"warning: optional step failed ({relative_path}): exit={exc.returncode}", file=sys.stderr)
        return False
    return True


def run_fetcher(fetcher: Literal["reddit", "rss"]) -> None:
    run_script(SCRIPTS_ROOT / f"fetch_{fetcher}_signals.py")


def run_market_signal_archive_sync() -> None:
    run_script(SCRIPTS_ROOT / "sync_market_signal_archive.py")


def run_brain_source_flow(*, sync_context: bool, require_context_sync: bool, api_url: str) -> None:
    run_script(SCRIPTS_DIR / "source_intelligence_register_existing.py")
    run_script(SCRIPTS_DIR / "brain_signal_intake.py")
    if sync_context:
        run_script(
            SCRIPTS_DIR / "brain_canonical_memory_sync.py",
            "--api-url",
            api_url,
            required=require_context_sync,
        )


def run_content_bank() -> None:
    run_script(SCRIPTS_ROOT / "bank_autonomous_posts.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the LinkedIn social feed.")
    parser.add_argument("--skip-fetch", action="store_true", help="Build from existing signals only.")
    parser.add_argument("--sources", choices=["safe", "all"], default="safe", help="Which fetchers to run.")
    parser.add_argument(
        "--skip-market-archive",
        action="store_true",
        help="Skip resyncing the tracked market-signal archive before feed rebuild.",
    )
    parser.add_argument(
        "--skip-brain-flow",
        action="store_true",
        help="Skip source-intelligence registration, BrainSignal intake, and immediate Brain context sync.",
    )
    parser.add_argument(
        "--skip-brain-context-sync",
        action="store_true",
        help="Update source intelligence and BrainSignals, but leave canonical context sync to its launchd cadence.",
    )
    parser.add_argument(
        "--require-brain-context-sync",
        action="store_true",
        help="Fail the refresh if the optional immediate Brain context sync cannot publish.",
    )
    parser.add_argument(
        "--brain-api-url",
        default=os.getenv("AICLONE_API_URL", DEFAULT_API_URL),
        help="Backend API URL used by the optional immediate Brain context sync.",
    )
    parser.add_argument(
        "--skip-content-bank",
        action="store_true",
        help="Skip the final append-only content-bank terminal event.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_fetch:
        sync_watchlist_auto_ingest(run_refresh=False)
        run_fetcher("reddit")
        run_fetcher("rss")
    if not args.skip_market_archive:
        run_market_signal_archive_sync()
    run_script(SCRIPTS_ROOT / "build_social_feed.py")
    run_script(SCRIPTS_ROOT / "refresh_linkedin_strategy.py")
    if not args.skip_brain_flow:
        run_brain_source_flow(
            sync_context=not args.skip_brain_context_sync,
            require_context_sync=args.require_brain_context_sync,
            api_url=args.brain_api_url,
        )
    if not args.skip_content_bank:
        run_content_bank()


if __name__ == "__main__":
    main()
