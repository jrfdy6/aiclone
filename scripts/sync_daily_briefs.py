#!/usr/bin/env python3
"""Mirror local daily-brief markdown into the backend daily_briefs table."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")
WORKSPACE_ROOT = Path(os.getenv("OPENCLAW_WORKSPACE", "/Users/neo/.openclaw/workspace"))
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
DEFAULT_BRIEF_FILE = WORKSPACE_ROOT / "memory" / "daily-briefs.md"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync local daily-brief markdown into the backend API.")
    parser.add_argument("--brief-file", default=str(DEFAULT_BRIEF_FILE))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--source", default="workspace_markdown")
    parser.add_argument("--source-ref", default=None)
    parser.add_argument("--sync-origin", default="morning_daily_brief_automation")
    return parser.parse_args()


def _resolve_brief_path(path_str: str) -> Path:
    brief_path = Path(path_str).expanduser()
    if brief_path.exists():
        return brief_path
    try:
        relative = brief_path.resolve().relative_to(WORKSPACE_ROOT.resolve()).as_posix()
    except ValueError:
        return brief_path
    return resolve_snapshot_fallback_path(WORKSPACE_ROOT, relative)


def main() -> int:
    args = parse_args()
    brief_path = _resolve_brief_path(args.brief_file)
    if not brief_path.exists():
        print(json.dumps({"success": False, "error": f"Brief file not found: {brief_path}"}))
        return 1

    raw_markdown = brief_path.read_text()
    if not raw_markdown.strip():
        print(json.dumps({"success": False, "error": f"Brief file is empty: {brief_path}"}))
        return 1

    payload = {
        "raw_markdown": raw_markdown,
        "source": args.source,
        "source_ref": args.source_ref or str(brief_path),
        "metadata": {
            "sync_origin": args.sync_origin,
            "synced_via": "scripts/sync_daily_briefs.py",
        },
    }
    request = urllib.request.Request(
        f"{args.api_url.rstrip('/')}/api/briefs/sync",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(json.dumps({"success": False, "status": exc.code, "error": detail}))
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1

    try:
        parsed = json.loads(body or "{}")
    except json.JSONDecodeError:
        parsed = {"raw_response": body}
    parsed["success"] = True
    parsed["brief_file"] = str(brief_path)
    print(json.dumps(parsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
