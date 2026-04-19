#!/usr/bin/env python3
"""Classify the git status output so Codex sessions stop treating memory files as "dirty."

Usage: ./scripts/worktree_doctor.py [--ignore <pattern>...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


CATEGORY_MATCHERS = [
    ("automation", ("automations/", "scripts/ops/", "scripts/runners/")),
    ("backend", ("backend/",)),
    ("frontend snaps", ("frontend/app/brain/workspaceSnapshot.ts", "frontend/legacy/content-pipeline/workspaceSnapshot.ts")),
    ("frontend", ("frontend/",)),
    ("memory", ("memory/", "daily-briefs.md", "dream_cycle_log.md", "persistent_state.md")),
    ("workspace", ("workspaces/", "workspace/")),
    ("generated", ("tmp/", ".next/", "frontend/.next/", "downloads/", "backups/", "__pycache__/", "memory/media_jobs/")),
    ("docs", ("docs/", "SOPs/", "knowledge/")),
    ("scripts", ("scripts/", "ingestion/")),
]
DEFAULT_REPORT_PATH = Path("memory/reports/live_workspace_git_reconciliation_latest.json")


def classify(path: str, ignore_patterns: Sequence[str]) -> str:
    if not path:
        return "unknown"
    for category, patterns in CATEGORY_MATCHERS:
        if any(path.startswith(pattern) for pattern in patterns):
            return category
    if any(path.startswith(p) for p in ignore_patterns):
        return "ignored-pattern"
    return "other"


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def read_status() -> list[str]:
    result = _run_git(["status", "--short"])
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def read_branch_status() -> str:
    result = _run_git(["status", "--short", "--branch"])
    for line in result.stdout.splitlines():
        if line.startswith("## "):
            return line.strip()
    return ""


def parse_branch_status(line: str) -> dict[str, Any]:
    raw = line.removeprefix("## ").strip()
    branch = raw
    upstream = ""
    ahead = 0
    behind = 0
    divergence = ""

    bracket_match = re.search(r"\[(?P<divergence>[^\]]+)\]", raw)
    if bracket_match:
        divergence = bracket_match.group("divergence")
        raw = raw[: bracket_match.start()].strip()
        ahead_match = re.search(r"ahead (?P<count>\d+)", divergence)
        behind_match = re.search(r"behind (?P<count>\d+)", divergence)
        ahead = int(ahead_match.group("count")) if ahead_match else 0
        behind = int(behind_match.group("count")) if behind_match else 0

    if "..." in raw:
        branch, upstream = [part.strip() for part in raw.split("...", 1)]
    elif raw:
        branch = raw

    return {
        "raw": line,
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "divergence": divergence,
    }


def _path_from_status(raw: str) -> str:
    path = raw[3:] if len(raw) > 3 else ""
    if " -> " in path:
        return path.split(" -> ", 1)[1].strip()
    return path.strip()


def _status_code(raw: str) -> str:
    return raw[:2].strip() or "unknown"


def read_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    root = result.stdout.strip()
    return Path(root) if root else Path.cwd()


def summarize(lines: Iterable[str], ignore_patterns: Sequence[str]) -> dict[str, list[str]]:
    buckets = defaultdict(list)
    for raw in lines:
        path = _path_from_status(raw)
        key = classify(path, ignore_patterns)
        buckets[key].append(raw)
    return buckets


def build_report(lines: list[str], ignore_patterns: Sequence[str], *, branch_line: str | None = None) -> dict[str, Any]:
    branch = parse_branch_status(branch_line or read_branch_status())
    buckets = summarize(lines, ignore_patterns)
    entries = [
        {
            "status": _status_code(raw),
            "path": _path_from_status(raw),
            "category": classify(_path_from_status(raw), ignore_patterns),
            "raw": raw,
        }
        for raw in lines
    ]
    dirty_count = len(entries)
    untracked_count = sum(1 for item in entries if item["status"] == "??")
    modified_count = dirty_count - untracked_count
    by_category = {category: len(items) for category, items in sorted(buckets.items())}
    behind = int(branch.get("behind") or 0)
    ahead = int(branch.get("ahead") or 0)
    if behind and dirty_count:
        push_recommendation = "blocked_reconcile_remote_first"
    elif behind:
        push_recommendation = "pull_or_rebase_before_push"
    elif dirty_count:
        push_recommendation = "review_and_stage_intentional_changes"
    elif ahead:
        push_recommendation = "safe_to_push_local_commits"
    else:
        push_recommendation = "clean_and_aligned"

    return {
        "schema_version": "worktree_reconciliation/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(read_repo_root()),
        "branch": branch,
        "counts": {
            "total": dirty_count,
            "modified": modified_count,
            "untracked": untracked_count,
            "by_category": by_category,
        },
        "push_recommendation": push_recommendation,
        "notes": [
            "Do not push from this worktree while it is both dirty and behind its upstream.",
            "Stage intentional code changes separately from runtime memory, analytics, and workspace artifacts.",
        ],
        "entries": entries,
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    parser.add_argument("--json", action="store_true", help="Print a machine-readable reconciliation report.")
    parser.add_argument("--write-report", action="store_true", help=f"Write a JSON report to {DEFAULT_REPORT_PATH}.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Report path used with --write-report.")
    args = parser.parse_args()

    lines = read_status()
    report = build_report(lines, args.ignore)
    if args.write_report:
        write_report(report, Path(args.report_path))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if not lines:
        print("Worktree is clean.")
        branch = report.get("branch") or {}
        if branch:
            print(
                f"Branch: {branch.get('branch') or 'unknown'}"
                f" -> {branch.get('upstream') or 'no upstream'}"
                f" (ahead {branch.get('ahead')}, behind {branch.get('behind')})"
            )
        return

    summary = summarize(lines, args.ignore)
    branch = report.get("branch") or {}
    print(
        f"Branch: {branch.get('branch') or 'unknown'}"
        f" -> {branch.get('upstream') or 'no upstream'}"
        f" (ahead {branch.get('ahead')}, behind {branch.get('behind')})"
    )
    print(f"Push recommendation: {report.get('push_recommendation')}")
    print_summary(summary)


if __name__ == "__main__":
    main()
