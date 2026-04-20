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
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs
from app.services.youtube_watchlist_service import build_youtube_watchlist_payload, sync_watchlist_auto_ingest


AUTOMATION_ID = "youtube_watchlist_auto_ingest"
AUTOMATION_NAME = "YouTube Watchlist Auto-Ingest"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
REPORT_PATH = WORKSPACE_ROOT / "memory/reports/youtube_watchlist_auto_ingest_latest.json"
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
    parser.add_argument("--api-url", default=os.getenv("AICLONE_API_URL", DEFAULT_API_URL), help="Backend API URL for Ops run mirroring.")
    parser.add_argument("--max-videos-per-run", type=int, default=None, help="Override the configured per-run ingest cap.")
    parser.add_argument("--per-channel-limit", type=int, default=None, help="Override the configured per-channel ingest cap.")
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip refreshing persisted FEEZIE snapshots after ingest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show runtime/readiness and candidate counts without ingesting new videos.",
    )
    parser.add_argument("--no-mirror", action="store_true", help="Do not mirror the run into Ops.")
    return parser.parse_args()


def _write_report(summary: dict[str, object]) -> bool:
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _mirror_summary(summary: dict[str, object], *, api_url: str, started_at: datetime, finished_at: datetime) -> bool:
    result = summary.get("result") if isinstance(summary.get("result"), dict) else {}
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    errors = result.get("errors") if isinstance(result.get("errors"), list) else []
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    run = build_run_payload(
        run_id=f"{AUTOMATION_ID}::{started_at.isoformat()}",
        automation_id=AUTOMATION_ID,
        automation_name=AUTOMATION_NAME,
        status="success" if not errors else "error",
        source="local_launchd_registry",
        runtime="launchd",
        delivered=None,
        run_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        error="; ".join(str(item.get("reason") or item) for item in errors[:3]) if errors else None,
        owner_agent="brain",
        session_target="brain/youtube-watchlist",
        scope="linkedin-os",
        workspace_key="linkedin-os",
        action_required=bool(errors),
        metadata={
            "mode": summary.get("mode"),
            "counts": counts,
            "warnings": warnings[:8],
            "warning_count": len(warnings),
            "errors": errors[:8],
            "error_count": len(errors),
            "runtime": summary.get("runtime") if isinstance(summary.get("runtime"), dict) else {},
            "easy_task_provider_order": summary.get("easy_task_provider_order"),
            "report_path": str(REPORT_PATH),
        },
    )
    return mirror_runs(api_url, [run])


def main() -> int:
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    applied_defaults = _apply_easy_task_defaults()
    generated_at = started_at.isoformat()

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
        _write_report(summary)
        print(json.dumps(summary, indent=2))
        return 0

    result = sync_watchlist_auto_ingest(
        max_videos_per_run=args.max_videos_per_run,
        per_channel_limit=args.per_channel_limit,
        run_refresh=not args.skip_refresh,
    )
    errors = result.get("errors") or []
    warnings = result.get("warnings") or []
    summary = {
        "ok": len(errors) == 0,
        "mode": "ingest",
        "generated_at": generated_at,
        "easy_task_defaults_applied": applied_defaults,
        "easy_task_provider_order": os.getenv("CONTENT_GENERATION_PROVIDER_ORDER", DEFAULT_PROVIDER_ORDER),
        "runtime": (build_youtube_watchlist_payload().get("runtime") or {}),
        "warning_count": len(warnings),
        "error_count": len(errors),
        "result": result,
    }
    finished_at = datetime.now(timezone.utc)
    summary["mirrored"] = True if args.no_mirror else _mirror_summary(summary, api_url=args.api_url, started_at=started_at, finished_at=finished_at)
    _write_report(summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
