#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.operator_story_signal_service import (  # noqa: E402
    DEFAULT_WORKSPACE_KEY,
    MEMORY_ROOT,
    REPORT_ROOT,
    build_operator_story_signals_payload,
    render_operator_story_signals_markdown,
)


DEFAULT_API_URL = os.getenv("AICLONE_API_URL", "https://aiclone-production-32dc.up.railway.app")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Distill raw OpenClaw memory into bounded operator-story signals.")
    parser.add_argument("--workspace-key", default=DEFAULT_WORKSPACE_KEY)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--memory-root", default=str(MEMORY_ROOT))
    parser.add_argument("--reports-dir", default=str(REPORT_ROOT))
    parser.add_argument("--source", default="operator_story_signal_distiller")
    parser.add_argument("--no-sync", action="store_true", help="Write local reports only.")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload without writing files or syncing.")
    return parser.parse_args()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _sync_payload(api_url: str, payload: dict[str, Any], source: str) -> dict[str, Any]:
    request_payload = {
        "generated_at": payload.get("generated_at"),
        "source": source,
        "workspace_key": payload.get("workspace"),
        "signal_count": (payload.get("counts") or {}).get("total", 0),
        "source_paths": payload.get("source_paths") or {},
        "counts": payload.get("counts") or {},
        "signals": payload.get("signals") or [],
    }
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/brain/operator-story-signals/sync",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw_body = response.read().decode("utf-8")
    parsed = json.loads(raw_body or "{}")
    return parsed if isinstance(parsed, dict) else {"raw_response": raw_body}


def main() -> int:
    args = parse_args()
    memory_root = Path(args.memory_root).expanduser()
    reports_dir = Path(args.reports_dir).expanduser()
    payload = build_operator_story_signals_payload(workspace_key=args.workspace_key, memory_root=memory_root)
    markdown = render_operator_story_signals_markdown(payload)

    if args.dry_run:
        print(json.dumps({"success": True, "dry_run": True, "payload": payload, "markdown": markdown}, indent=2))
        return 0

    json_path = reports_dir / "operator_story_signals_latest.json"
    markdown_path = reports_dir / "operator_story_signals_latest.md"
    _write_json(json_path, payload)
    _write_markdown(markdown_path, markdown)

    result: dict[str, Any] = {
        "success": True,
        "workspace_key": args.workspace_key,
        "json_report": str(json_path),
        "markdown_report": str(markdown_path),
        "signal_count": (payload.get("counts") or {}).get("total", 0),
        "counts": payload.get("counts") or {},
    }
    if args.no_sync:
        print(json.dumps(result, indent=2))
        return 0

    try:
        sync_result = _sync_payload(args.api_url, payload, args.source)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(
            json.dumps(
                {
                    "success": False,
                    "json_report": str(json_path),
                    "markdown_report": str(markdown_path),
                    "status": exc.code,
                    "error": detail,
                },
                indent=2,
            )
        )
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "json_report": str(json_path),
                    "markdown_report": str(markdown_path),
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 1

    result["sync"] = sync_result
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
