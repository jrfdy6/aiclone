#!/usr/bin/env python3
"""Emit the shared recent-chronicle plus durable-memory contract for cron jobs."""
from __future__ import annotations

import argparse
import json

from chronicle_memory_contract import DEFAULT_MEMORY_PATHS, build_workspace_memory_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--query", action="append", default=[], help="Seed query text for durable memory recall.")
    parser.add_argument("--memory-path", action="append", default=[], help="Relative memory path; supports {today}.")
    parser.add_argument("--chronicle-limit", type=int, default=8)
    parser.add_argument("--max-tail-chars", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_workspace_memory_contract(
        args.workspace_key,
        seed_texts=args.query,
        chronicle_limit=args.chronicle_limit,
        memory_paths=args.memory_path or DEFAULT_MEMORY_PATHS,
        max_tail_chars=args.max_tail_chars,
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
