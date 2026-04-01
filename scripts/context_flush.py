#!/usr/bin/env python3
"""Append a structured context flush note to today's memory log."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_DIR = WORKSPACE_ROOT / "memory"


def add_argument(parser: argparse.ArgumentParser, name: str) -> None:
    parser.add_argument(f"--{name}", action="append", default=[], help=f"Add {name.replace('-', ' ')} entries")


def render_list(items: list[str], default: str = "- none") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return default
    return "\n".join(f"- {item}" for item in cleaned)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a structured flush note to today's memory log.")
    parser.add_argument("--task", default="Context flush")
    for field in ("insights", "decisions", "structural-changes", "blockers", "next-steps"):
        add_argument(parser, field)
    args = parser.parse_args()

    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)
    daily_path = MEMORY_DIR / f"{now_local:%Y-%m-%d}.md"
    daily_path.parent.mkdir(parents=True, exist_ok=True)

    block = (
        f"\n## Context Flush — {now_local:%Y-%m-%d %H:%M %Z}\n"
        f"- UTC: `{now_utc.isoformat()}`\n"
        f"- Task: {args.task}\n\n"
        f"### Insights\n{render_list(args.insights)}\n\n"
        f"### Decisions\n{render_list(args.decisions)}\n\n"
        f"### Structural Changes\n{render_list(args.structural_changes)}\n\n"
        f"### Blockers\n{render_list(args.blockers)}\n\n"
        f"### Next Steps\n{render_list(args.next_steps)}\n"
    )

    with daily_path.open("a", encoding="utf-8") as handle:
        handle.write(block)

    print(f"Appended context flush to {daily_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
