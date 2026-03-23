#!/usr/bin/env python3
"""Create placeholder RSS signal notes from the configured watchlist."""
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
    return data.get("rss_sources", [])


def build_signal_entry(source: dict[str, str]) -> dict:
    label = source.get("label", "rss-feed")
    return {
        "kind": "market_signal",
        "title": f"{label} roundup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_platform": "rss",
        "source_type": "feed",
        "source_url": source.get("url"),
        "author": label,
        "role_alignment": "initiative",
        "priority_lane": "Market intelligence",
        "summary": f"RSS capture for {label}.",
        "why_it_matters": source.get("label"),
        "watchlist_matches": ["rss"],
        "topics": ["content", "strategy"],
    }


def write_signal(entry: dict, source: dict[str, str]) -> None:
    slug = source.get("label", "rss").replace(" ", "-").lower()
    filename = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}__rss__{slug}.md"
    path = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.dump(entry, sort_keys=False)
    path.write_text(f"---\n{frontmatter}---\n\n# RSS placeholder\n\n{entry['summary']}\n", encoding="utf-8")


def main() -> None:
    for source in load_sources():
        write_signal(build_signal_entry(source), source)


if __name__ == "__main__":
    main()
