#!/usr/bin/env python3
"""Classify the git status output so Codex sessions stop treating memory files as "dirty."

Usage: ./scripts/worktree_doctor.py [--ignore <pattern>...]
"""

from __future__ import annotations

import argparse
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence


CATEGORY_MATCHERS = [
    ("memory", ("memory/", "daily-briefs.md", "dream_cycle_log.md", "persistent_state.md")),
    ("workspace", ("workspaces/", "workspace/")),
    ("frontend snaps", ("frontend/app/brain/workspaceSnapshot.ts", "frontend/legacy/content-pipeline/workspaceSnapshot.ts")),
    ("generated", ("tmp/", ".next/", "frontend/.next/", "downloads/", "backups/", "__pycache__/", "memory/media_jobs/")),
    ("docs", ("docs/", "SOPs/", "knowledge/")),
    ("scripts", ("scripts/", "ingestion/")),
]


def classify(path: str, ignore_patterns: Sequence[str]) -> str:
    if not path:
        return "unknown"
    for category, patterns in CATEGORY_MATCHERS:
        if any(path.startswith(pattern) for pattern in patterns):
            return category
    if any(path.startswith(p) for p in ignore_patterns):
        return "ignored-pattern"
    return "other"


def read_status() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def summarize(lines: Iterable[str], ignore_patterns: Sequence[str]) -> dict[str, list[str]]:
    buckets = defaultdict(list)
    for raw in lines:
        if raw.startswith("??"):
            path = raw[3:]
        else:
            path = raw[3:]
        key = classify(path, ignore_patterns)
        buckets[key].append(raw)
    return buckets


def print_summary(buckets: dict[str, list[str]]) -> None:
    total = sum(len(v) for v in buckets.values())
    print(f"Worktree entries: {total}")
    for category in sorted(buckets.keys()):
        names = buckets[category]
        print(f"  {category:>12}: {len(names)}")
    for category in sorted(buckets.keys()):
        print(f"\n== {category} ({len(buckets[category])}) ==")
        for entry in buckets[category]:
            print(entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify git status output.")
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Extra path prefixes to treat as ignored.",
    )
    args = parser.parse_args()

    lines = read_status()
    if not lines:
        print("Worktree is clean.")
        return

    summary = summarize(lines, args.ignore)
    print_summary(summary)


if __name__ == "__main__":
    main()
