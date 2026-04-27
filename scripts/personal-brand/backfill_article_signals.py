#!/usr/bin/env python3
"""Backfill saved RSS/Substack article signals from canonical source URLs."""
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

from app.services.social_source_fetch_service import backfill_article_signal_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill saved RSS/Substack article signals from source URLs.")
    parser.add_argument("--force", action="store_true", help="Refresh already-enriched article signals too.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(backfill_article_signal_sources(force=args.force))


if __name__ == "__main__":
    main()
