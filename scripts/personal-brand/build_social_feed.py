#!/usr/bin/env python3
"""Compile LinkedIn workspace social feed artifacts from the backend source of truth."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_feed_builder_service import build_feed, discover_linkedin_workspace_root, write_feed_artifacts


def main() -> None:
    workspace_root = discover_linkedin_workspace_root()
    feed = build_feed(workspace_root)
    write_feed_artifacts(feed, workspace_root)


if __name__ == "__main__":
    main()
