#!/usr/bin/env python3
"""Fetch real RSS signals from the configured watchlist."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for candidate in (ROOT / "backend", ROOT):
    if (candidate / "app").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from app.services.social_source_fetch_service import fetch_rss_signals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-legacy-workspace-projection",
        action="store_true",
        help="Rollback only: also write the historical market-signal Markdown/archive projection.",
    )
    args = parser.parse_args()
    fetch_rss_signals(write_compatibility_projection=args.include_legacy_workspace_projection)


if __name__ == "__main__":
    main()
