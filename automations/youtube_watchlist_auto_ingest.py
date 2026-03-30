#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.youtube_watchlist_service import build_youtube_watchlist_payload, sync_watchlist_auto_ingest


DEFAULT_PROVIDER_ORDER = "ollama,gemini,openai"
DEFAULT_OLLAMA_MODEL = "llama3.1:latest"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_PATH_PREFIXES = [
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
]


def _apply_easy_task_defaults() -> dict[str, str]:
    applied: dict[str, str] = {}
    current_path = os.getenv("PATH", "")
    path_parts = [part for part in current_path.split(":") if part]
    merged_parts: list[str] = []
    seen: set[str] = set()
    for part in [*DEFAULT_PATH_PREFIXES, *path_parts]:
        if part in seen:
            continue
        seen.add(part)
        merged_parts.append(part)
    os.environ["PATH"] = ":".join(merged_parts)
    defaults = {
        "CONTENT_GENERATION_PROVIDER_ORDER": DEFAULT_PROVIDER_ORDER,
        "CONTENT_GENERATION_OLLAMA_FAST_MODEL": DEFAULT_OLLAMA_MODEL,
        "CONTENT_GENERATION_OLLAMA_EDITOR_MODEL": DEFAULT_OLLAMA_MODEL,
        "CONTENT_GENERATION_GEMINI_FAST_MODEL": DEFAULT_GEMINI_MODEL,
        "CONTENT_GENERATION_GEMINI_EDITOR_MODEL": DEFAULT_GEMINI_MODEL,
    }
    for key, value in defaults.items():
        if not os.getenv(key):
            os.environ[key] = value
            applied[key] = value
    return applied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-ingest fresh YouTube watchlist videos on the local machine.")
    parser.add_argument("--max-videos-per-run", type=int, default=None, help="Override the configured per-run ingest cap.")
    parser.add_argument("--per-channel-limit", type=int, default=None, help="Override the configured per-channel ingest cap.")
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip refreshing persisted LinkedIn OS snapshots after ingest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show runtime/readiness and candidate counts without ingesting new videos.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    applied_defaults = _apply_easy_task_defaults()
    generated_at = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        payload = build_youtube_watchlist_payload()
        summary = {
            "ok": True,
            "mode": "dry_run",
            "generated_at": generated_at,
            "runtime": payload.get("runtime") or {},
            "auto_ingest": payload.get("auto_ingest") or {},
            "channel_count": ((payload.get("counts") or {}).get("channels")) or 0,
            "video_count": ((payload.get("counts") or {}).get("videos")) or 0,
            "already_ingested": ((payload.get("counts") or {}).get("already_ingested")) or 0,
            "easy_task_defaults_applied": applied_defaults,
            "easy_task_provider_order": os.getenv("CONTENT_GENERATION_PROVIDER_ORDER", DEFAULT_PROVIDER_ORDER),
        }
        print(json.dumps(summary, indent=2))
        return 0

    result = sync_watchlist_auto_ingest(
        max_videos_per_run=args.max_videos_per_run,
        per_channel_limit=args.per_channel_limit,
        run_refresh=not args.skip_refresh,
    )
    summary = {
        "ok": len(result.get("errors") or []) == 0,
        "mode": "ingest",
        "generated_at": generated_at,
        "easy_task_defaults_applied": applied_defaults,
        "easy_task_provider_order": os.getenv("CONTENT_GENERATION_PROVIDER_ORDER", DEFAULT_PROVIDER_ORDER),
        "runtime": (build_youtube_watchlist_payload().get("runtime") or {}),
        "result": result,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
