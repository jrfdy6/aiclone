#!/usr/bin/env python3
"""Print the most recently modified path matching a glob."""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the latest matching file for a glob pattern.")
    parser.add_argument("--glob", dest="pattern", required=True, help="Glob pattern to resolve.")
    args = parser.parse_args()

    matches = [Path(path) for path in glob.glob(args.pattern)]
    if not matches:
        print(f"No matches for glob: {args.pattern}", file=sys.stderr)
        return 1

    latest = max(matches, key=lambda path: path.stat().st_mtime)
    print(str(latest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
