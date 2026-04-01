#!/usr/bin/env python3
"""Print a compact operator context pack for OpenClaw cron and startup flows."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")

SECTION_FILES = {
    "sop": [
        WORKSPACE_ROOT / "CODEX_STARTUP.md",
        WORKSPACE_ROOT / "SOURCE_OF_TRUTH.md",
        WORKSPACE_ROOT / "AGENTS.md",
    ],
    "roadmap": [
        WORKSPACE_ROOT / "memory" / "roadmap.md",
    ],
    "memory": [
        WORKSPACE_ROOT / "memory" / "persistent_state.md",
        WORKSPACE_ROOT / "memory" / "LEARNINGS.md",
    ],
}


def read_excerpt(path: Path, max_lines: int) -> str:
    lines = path.read_text(errors="replace").splitlines()
    excerpt = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        excerpt += "\n... [truncated]"
    return excerpt


def emit_section(label: str, paths: list[Path], max_lines: int) -> tuple[int, int]:
    loaded = 0
    missing = 0
    print(f"## {label.upper()}")
    for path in paths:
        print(f"\n### {path.relative_to(WORKSPACE_ROOT)}")
        if not path.exists():
            print(f"[missing] {path}")
            missing += 1
            continue
        print(read_excerpt(path, max_lines))
        loaded += 1
    print()
    return loaded, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Load a compact context pack from canonical workspace files.")
    parser.add_argument("--sop", action="store_true", help="Load startup/SOP context")
    parser.add_argument("--roadmap", action="store_true", help="Load roadmap context")
    parser.add_argument("--memory", action="store_true", help="Load memory context")
    parser.add_argument("--max-lines", type=int, default=60, help="Maximum lines per file excerpt")
    args = parser.parse_args()

    requested = []
    if args.sop:
        requested.append("sop")
    if args.roadmap:
        requested.append("roadmap")
    if args.memory:
        requested.append("memory")
    if not requested:
        requested = ["sop", "memory"]

    total_loaded = 0
    total_missing = 0
    for section in requested:
        loaded, missing = emit_section(section, SECTION_FILES[section], args.max_lines)
        total_loaded += loaded
        total_missing += missing

    print(f"Loaded files: {total_loaded}")
    if total_missing:
        print(f"Missing files: {total_missing}", file=sys.stderr)
    return 0 if total_loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
