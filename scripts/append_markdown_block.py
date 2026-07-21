#!/usr/bin/env python3
"""Append a markdown block to a file without relying on brittle edit matching."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _read_body(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        return Path(args.body_file).read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Absolute path to the markdown file to append to.")
    parser.add_argument("--heading", help="Optional markdown heading to prepend before the body.")
    parser.add_argument("--body", help="Inline markdown body to append.")
    parser.add_argument("--body-file", help="Path to a file containing the markdown body.")
    args = parser.parse_args()

    target = Path(args.path).expanduser()
    if not target.is_absolute():
        raise SystemExit("Target path must be absolute.")
    if not target.parent.exists():
        raise SystemExit(f"Parent directory does not exist: {target.parent}")

    body = _read_body(args).strip()
    heading = (args.heading or "").strip()
    pieces = [piece for piece in [heading, body] if piece]
    if not pieces:
        raise SystemExit("Nothing to append.")

    block = "\n\n".join(pieces).rstrip() + "\n"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    prefix = ""
    if existing:
        prefix = "\n" if existing.endswith("\n") else "\n\n"
        if existing.endswith("\n\n"):
            prefix = ""

    with target.open("a", encoding="utf-8") as handle:
        handle.write(prefix + block)

    print(f"Appended markdown block to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
