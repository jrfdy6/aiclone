#!/usr/bin/env python3
"""Append transcript-ingest notes to the canonical roadmap."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROADMAP_PATH = WORKSPACE_ROOT / "memory" / "roadmap.md"
SECTION_HEADING = "## Transcript Intake Notes"
TZ = ZoneInfo("America/New_York")


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def append_transcript_intake_entry(
    *,
    roadmap_path: Path,
    title: str,
    summary: str,
    source_path: str,
    normalized_path: str,
) -> bool:
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else ""
    dedupe_keys = [item for item in [source_path.strip(), normalized_path.strip()] if item]
    if any(key in existing for key in dedupe_keys):
        return False

    timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")
    lines = [f"- `{timestamp}` {title.strip()}"]
    if source_path.strip():
        lines.append(f"  Source: `{source_path.strip()}`")
    if normalized_path.strip():
        lines.append(f"  Ingestion: `{normalized_path.strip()}`")
    cleaned_summary = _clean(summary)
    if cleaned_summary:
        lines.append(f"  Summary: {cleaned_summary}")
    block = "\n".join(lines).rstrip() + "\n"

    if not existing.strip():
        roadmap_path.write_text(f"{SECTION_HEADING}\n{block}", encoding="utf-8")
        return True

    pieces = [existing.rstrip()]
    if SECTION_HEADING not in existing:
        pieces.append(SECTION_HEADING)
    pieces.append(block.rstrip())
    roadmap_path.write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--normalized-path", default="")
    parser.add_argument("--roadmap-path", default=str(DEFAULT_ROADMAP_PATH))
    args = parser.parse_args()

    changed = append_transcript_intake_entry(
        roadmap_path=Path(args.roadmap_path).expanduser(),
        title=args.title,
        summary=args.summary,
        source_path=args.source_path,
        normalized_path=args.normalized_path,
    )
    if changed:
        print(f"Updated roadmap: {args.roadmap_path}")
    else:
        print(f"Roadmap already contains source or ingestion path: {args.source_path or args.normalized_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
