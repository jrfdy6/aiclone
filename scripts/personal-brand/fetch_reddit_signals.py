#!/usr/bin/env python3
"""Fetch real Reddit signals from the configured watchlist."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_source_fetch_service import fetch_reddit_signals


def main() -> None:
    fetch_reddit_signals()


if __name__ == "__main__":
    main()
