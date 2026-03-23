#!/usr/bin/env python3
"""Create placeholder Reddit signal notes from the configured watchlist."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent / "workspaces" / "linkedin-content-os"
WATCHLIST = WORKSPACE_ROOT / "research" / "watchlists.yaml"
OUTPUT_DIR = WORKSPACE_ROOT / "research" / "market_signals"


def load_sources() -> list[dict[str, str]]:
    if not WATCHLIST.exists():
        return []
    data = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    return data.get("reddit_sources", [])


def build_signal_entry(source: dict[str, str]) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    slug = source.get("subreddit", "reddit").replace("r/", "").replace(" ", "-")
    return {
        "kind": "market_signal",
        "title": f"{source.get('subreddit')} signal snapshot",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_platform": "reddit",
        "source_type": "feed_snapshot",
        "source_url": f"https://reddit.com/{slug}",
        "author": "reddit-snapshot",
        "role_alignment": "role_anchored",
        "priority_lane": source.get("purpose", "market intelligence"),
        "summary": f"Placeholder capture for {source.get('subreddit')}.",
        "why_it_matters": source.get("purpose"),
        "watchlist_matches": ["reddit"],
        "topics": [source.get("purpose", "operator insight")],
    }


def write_signal(entry: dict, source: dict[str, str]) -> None:
    slug = source.get("subreddit", "reddit").replace("r/", "").replace(" ", "-")
    filename = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}__reddit__{slug}.md"
    path = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.dump(entry, sort_keys=False)
    path.write_text(f"---\n{frontmatter}---\n\n# Reddit placeholder\n\n{entry['summary']}\n", encoding="utf-8")


def main() -> None:
    for source in load_sources():
        write_signal(build_signal_entry(source), source)


if __name__ == "__main__":
    main()
