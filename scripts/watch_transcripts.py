#!/usr/bin/env python3
"""Compatibility wrapper for the media intake watcher."""

from __future__ import annotations

import argparse
import sys

import ingest_transcripts_to_memory


def parse_args(argv: list[str] | None = None) -> tuple[list[str], bool]:
    parser = argparse.ArgumentParser(
        description="Watch media inboxes and normalize transcript/audio drops into knowledge ingestions."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending drops once and exit. Default behavior is to keep watching.",
    )
    args, passthrough = parser.parse_known_args(argv)
    return passthrough, args.once


def main(argv: list[str] | None = None) -> int:
    passthrough, once = parse_args(argv)
    if once:
        return ingest_transcripts_to_memory.main(passthrough)
    return ingest_transcripts_to_memory.main(["--watch", *passthrough])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
