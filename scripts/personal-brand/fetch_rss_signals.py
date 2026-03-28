#!/usr/bin/env python3
"""Fetch real RSS signals from the configured watchlist."""
from __future__ import annotations

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
    fetch_rss_signals()


if __name__ == "__main__":
    main()
