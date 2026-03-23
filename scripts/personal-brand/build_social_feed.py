#!/usr/bin/env python3
"""Compile the LinkedIn workspace social feed artifacts for the LinkedIn workspace."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = ROOT / "workspaces" / "linkedin-content-os"
RESEARCH_ROOT = WORKSPACE_ROOT / "research" / "market_signals"
PLANS_ROOT = WORKSPACE_ROOT / "plans"
WATCHLIST_PATH = WORKSPACE_ROOT / "research" / "watchlists.yaml"


def load_watchlist() -> dict[str, Any]:
    if not WATCHLIST_PATH.exists():
        return {}
    with WATCHLIST_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def read_signals() -> list[dict[str, Any]]:
    signals = []
    for path in sorted(RESEARCH_ROOT.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        meta["source_path"] = path.relative_to(WORKSPACE_ROOT).as_posix()
        meta["id"] = path.stem
        signals.append(meta)
    return signals


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_signal(signal: dict[str, Any], watchlist: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    created_dt = parse_datetime(signal.get("created_at")) or now
    age_hours = max(0, round((now - created_dt).total_seconds() / 3600))
    topics = signal.get("topics") or []
    lenses: list[str] = []
    priority_people = watchlist.get("priority_people", [])
    priority_weight = 0.5

    author = signal.get("author", "Unknown")
    for person in priority_people:
        if person.get("name") and person["name"].lower() in str(author).lower():
            priority_weight = max(priority_weight, person.get("priority_weight", 0.6))
            lenses.extend(person.get("lenses", []))

    if priority_lane := signal.get("priority_lane"):
        lenses.append(priority_lane.lower().replace(" ", "-"))

    topic_match = len(set(topics) & set(watchlist.get("topics", [])))

    ranking = {
        "priority_network": round(priority_weight * 100, 1),
        "topic_match": topic_match * 10,
        "recency": max(0, 100 - age_hours),
        "engagement": signal.get("engagement", {}).get("likes", 0) * 0.1,
        "persona_fit": 10 if signal.get("role_alignment") else 0,
    }
    ranking["total"] = sum(ranking.values())

    return {
        "id": f"{signal.get('source_platform', 'unknown')}__{signal.get('id')}",
        "platform": signal.get("source_platform", "linkedin"),
        "source_lane": signal.get("source_kind", "market_signal"),
        "capture_method": signal.get("capture_method", "manual"),
        "title": signal.get("title") or (signal.get("headline_candidates") or ["Untitled"])[0],
        "author": author,
        "source_url": signal.get("source_url"),
        "source_path": signal.get("source_path"),
        "published_at": signal.get("created_at"),
        "captured_at": signal.get("captured_at") or signal.get("created_at"),
        "summary": signal.get("summary"),
        "standout_lines": (signal.get("headline_candidates") or [])[:2],
        "engagement": signal.get("engagement", {"likes": 0, "comments": 0, "shares": 0}),
        "ranking": ranking,
        "lenses": list(dict.fromkeys(lenses)),
        "comment_draft": signal.get("comment_angle") or "Draft a thoughtful, concise comment with operator context.",
        "repost_draft": signal.get("post_angle") or signal.get("summary") or "",
        "why_it_matters": signal.get("why_it_matters"),
        "notes": signal.get("language_patterns", []),
    }


def build_feed() -> dict[str, Any]:
    watchlist = load_watchlist()
    signals = read_signals()
    items = [normalize_signal(signal, watchlist) for signal in signals]
    items.sort(key=lambda item: item["ranking"]["total"], reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "items": items,
    }


def write_artifacts(feed: dict[str, Any]) -> None:
    json_path = PLANS_ROOT / "social_feed.json"
    md_path = PLANS_ROOT / "social_feed.md"
    PLANS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(feed, indent=2), encoding="utf-8")

    lines = ["# LinkedIn Social Feed", f"Updated {feed['generated_at']}", ""]
    for item in feed["items"]:
        lines.append(f"- {item['platform']} · {item['title']} ({item['author']})")
        if item.get("source_url"):
            lines.append(f"  - {item['source_url']}")
        lines.append(f"  - score: {item['ranking']['total']:.1f}")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    feed = build_feed()
    write_artifacts(feed)


if __name__ == "__main__":
    main()
