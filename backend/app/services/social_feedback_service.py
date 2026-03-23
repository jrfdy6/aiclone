from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = ROOT / "workspaces" / "linkedin-content-os"
FEEDBACK_DIR = WORKSPACE_ROOT / "analytics"
FEEDBACK_PATH = FEEDBACK_DIR / "feed_feedback.md"


def ensure_feedback_dir() -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def append_feedback(entry: dict[str, str]) -> Path:
    ensure_feedback_dir()
    timestamp = datetime.now(timezone.utc).isoformat()
    line = (
        f"- {timestamp} | {entry['decision']} | {entry['feed_item_id']} | "
        f"{entry['platform']} | lens={entry.get('lens')} | {entry.get('title')}\n"
    )
    with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return FEEDBACK_PATH
