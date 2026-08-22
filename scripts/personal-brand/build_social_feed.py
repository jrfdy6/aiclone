#!/usr/bin/env python3
"""Compile LinkedIn workspace social feed artifacts from the backend source of truth."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for candidate in (ROOT / "backend", ROOT):
    if (candidate / "app").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from app.services.social_feed_builder_service import build_feed, discover_linkedin_workspace_root, write_feed_artifacts
from scripts.runtime_paths import workspace_state_root


def main() -> None:
    source_workspace_root = discover_linkedin_workspace_root()
    generated_workspace_root = workspace_state_root("feezie-os")
    feed = build_feed(
        generated_workspace_root,
        source_workspace_root=source_workspace_root,
    )
    write_feed_artifacts(feed, generated_workspace_root)


if __name__ == "__main__":
    main()
