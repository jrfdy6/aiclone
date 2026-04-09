#!/usr/bin/env python3
"""Ingest an arbitrary webpage or text into the LinkedIn social feed pipeline."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "workspaces" / "linkedin-content-os").exists():
            return parent
    raise RuntimeError("Unable to locate workspace root for LinkedIn social feed ingestion.")


WORKSPACE_ROOT = resolve_workspace_root()
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_feed_preview_service import social_feed_preview_service
from app.services.social_signal_archive_service import sync_market_signal_archive_entry
from app.services.social_signal_utils import normalize_manual_signal

RESEARCH_ROOT = WORKSPACE_ROOT / "workspaces" / "linkedin-content-os" / "research" / "market_signals"


def sanitize(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-") or "signal"

def write_signal(signal: dict[str, object], metadata: dict[str, str]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    title = str(signal.get("title") or "signal")
    slug = sanitize(title)
    filename = f"{timestamp}__{slug}.md"
    path = RESEARCH_ROOT / filename
    RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
    frontmatter = "---\n"
    frontmatter += "kind: market_signal\n"
    for key, value in metadata.items():
        frontmatter += f"{key}: {value}\n"
    frontmatter += f"created_at: '{signal.get('captured_at') or datetime.now(timezone.utc).isoformat()}'\n"
    frontmatter += f"title: {title}\n"
    frontmatter += f"summary: {signal.get('summary') or ''}\n"
    if signal.get("author"):
        frontmatter += f"author: {signal.get('author')}\n"
    if signal.get("headline_candidates"):
        candidates = signal.get("headline_candidates") or []
        frontmatter += "headline_candidates:\n"
        for item in candidates[:2]:
            frontmatter += f"  - {item}\n"
    if signal.get("core_claim"):
        frontmatter += f"core_claim: {signal.get('core_claim')}\n"
    if signal.get("supporting_claims"):
        frontmatter += "supporting_claims:\n"
        for item in signal.get("supporting_claims") or []:
            frontmatter += f"  - {item}\n"
    if signal.get("topics"):
        frontmatter += "topics:\n"
        for item in signal.get("topics") or []:
            frontmatter += f"  - {item}\n"
    if signal.get("trust_notes"):
        frontmatter += "trust_notes:\n"
        for item in signal.get("trust_notes") or []:
            frontmatter += f"  - {item}\n"
    frontmatter += "---\n\n"
    body = str(signal.get("raw_text") or "").strip()
    content = frontmatter + "# Source\n\n" + body + "\n"
    path.write_text(content, encoding="utf-8")
    sync_market_signal_archive_entry(path, WORKSPACE_ROOT / "workspaces" / "linkedin-content-os")
    return path


def maybe_refresh():
    script = WORKSPACE_ROOT / "scripts" / "personal-brand" / "build_social_feed.py"
    subprocess.run(["python3", str(script)], cwd=str(WORKSPACE_ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a LinkedIn market signal from a webpage or text.")
    parser.add_argument("--url", help="HTTP URL to fetch and ingest.")
    parser.add_argument("--text-file", help="Path to a markdown/text file to ingest.")
    parser.add_argument("--text", help="Raw text string (useful for APIs).")
    parser.add_argument("--title", help="Override signal title.")
    parser.add_argument("--priority-lane", default="custom", help="Priority lane tag for the new signal.")
    parser.add_argument("--run-refresh", action="store_true", help="Rebuild the social feed snapshot after ingest.")
    args = parser.parse_args()

    if not (args.url or args.text_file or args.text):
        parser.error("Provide --url, --text, or --text-file.")

    extracted_title = args.title or ""
    author = "manual preview"
    extraction_method = "manual_text"
    if args.url:
        extracted = social_feed_preview_service.fetch_url_preview(args.url)
        raw_text = extracted.get("text", "")
        extracted_title = args.title or extracted.get("title") or ""
        author = extracted.get("author") or author
        extraction_method = "url_preview"
    elif args.text:
        raw_text = args.text
    else:
        raw_text = Path(args.text_file).read_text(encoding="utf-8")

    raw_text = raw_text.strip()
    if not raw_text:
        raise SystemExit("No extractable text found.")

    normalized_signal = normalize_manual_signal(
        raw_text=raw_text,
        title=extracted_title or raw_text.splitlines()[0][:120],
        url=args.url,
        author=author,
        priority_lane=args.priority_lane,
        source_type="page" if args.url else "note",
        extraction_method=extraction_method,
    )
    metadata = {
        "source_platform": normalized_signal.get("source_channel") or "manual",
        "source_type": normalized_signal.get("source_type") or "note",
        "source_url": args.url or "paste",
        "priority_lane": args.priority_lane,
        "role_alignment": "custom",
        "risk_level": "low",
        "publish_posture": "publish_now",
        "capture_method": "manual",
        "ingest_mode": "manual",
    }

    signal_payload = {
        "title": normalized_signal.get("title"),
        "summary": normalized_signal.get("summary"),
        "author": normalized_signal.get("author"),
        "headline_candidates": normalized_signal.get("standout_lines"),
        "core_claim": normalized_signal.get("core_claim"),
        "supporting_claims": normalized_signal.get("supporting_claims"),
        "topics": normalized_signal.get("topic_tags"),
        "trust_notes": normalized_signal.get("trust_notes"),
        "raw_text": normalized_signal.get("raw_text"),
        "captured_at": normalized_signal.get("captured_at"),
    }
    path = write_signal(signal=signal_payload, metadata=metadata)
    print(f"Wrote signal to {path}")

    if args.run_refresh:
        print("Running build_social_feed.py...")
        maybe_refresh()


if __name__ == "__main__":
    main()
