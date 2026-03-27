#!/usr/bin/env python3
"""Ingest an arbitrary webpage or text into the LinkedIn social feed pipeline."""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = WORKSPACE_ROOT / "workspaces" / "linkedin-content-os" / "research" / "market_signals"


def sanitize(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-") or "signal"


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    blocks = article or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in blocks.find_all(["p", "li"]) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs[:20]).strip()


def summarize(text: str, sentences: int = 3) -> str:
    fragments = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(fragments[:sentences]).strip()


def write_signal(title: str, summary: str, body: str, metadata: dict[str, str]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = sanitize(title)
    filename = f"{timestamp}__{slug}.md"
    path = RESEARCH_ROOT / filename
    RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
    frontmatter = "---\n"
    frontmatter += "kind: market_signal\n"
    for key, value in metadata.items():
        frontmatter += f"{key}: {value}\n"
    frontmatter += f"created_at: '{datetime.now(timezone.utc).isoformat()}'\n"
    frontmatter += f"title: {title}\n"
    frontmatter += f"summary: {summary}\n"
    frontmatter += "---\n\n"
    content = frontmatter + "# Source\n\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def maybe_refresh():
    script = WORKSPACE_ROOT / "scripts" / "personal-brand" / "build_social_feed.py"
    subprocess.run(["python3", str(script)], cwd=str(WORKSPACE_ROOT), check=True)


def fetch_url(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a LinkedIn market signal from a webpage or text.")
    parser.add_argument("--url", help="HTTP URL to fetch and ingest.")
    parser.add_argument("--text-file", help="Path to a markdown/text file to ingest.")
    parser.add_argument("--text", help="Raw text string (useful for APIs).")
    parser.add_argument("--title", help="Override signal title.")
    parser.add_argument("--priority-lane", default="custom", help="Priority lane tag for the new signal.")
    parser.add_argument("--run-refresh", action="store_true", help="Rebuild the social feed snapshot after ingest.")
    args = parser.parse_args()

    if not (args.url or args.text_file):
        parser.error("Provide --url or --text-file.")

    if args.url:
        html = fetch_url(args.url)
        raw_text = extract_text(html)
    elif args.text:
        raw_text = args.text
    else:
        raw_text = Path(args.text_file).read_text(encoding="utf-8")

    raw_text = raw_text.strip()
    if not raw_text:
        raise SystemExit("No extractable text found.")

    title = args.title or raw_text.splitlines()[0][:120]
    summary = summarize(raw_text)
    metadata = {
        "source_platform": "custom-web",
        "source_type": "page",
        "source_url": args.url or "paste",
        "priority_lane": args.priority_lane,
        "role_alignment": "custom",
        "risk_level": "low",
        "publish_posture": "publish_now",
    }

    path = write_signal(title=title, summary=summary, body=raw_text, metadata=metadata)
    print(f"Wrote signal to {path}")

    if args.run_refresh:
        print("Running build_social_feed.py...")
        maybe_refresh()


if __name__ == "__main__":
    main()
