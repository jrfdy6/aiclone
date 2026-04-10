#!/usr/bin/env python3
"""Autonomous PM review-resolution worker."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
RUNNER_ID = "pm-review-resolution"
AUTOMATION_ID = "pm_review_resolution"
AUTOMATION_NAME = "PM Review Resolution"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _optional_backend_imports(mode: str) -> dict[str, Any]:
    if mode != "service":
        return {"mode": "api"}
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    try:
        from app.services.pm_card_service import auto_progress_review_cards  # type: ignore

        return {
            "mode": "service",
            "auto_progress_review_cards": auto_progress_review_cards,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "mode": "api",
            "error": str(exc),
        }


def _run_progress(imports: dict[str, Any], api_url: str, *, limit: int) -> tuple[str, dict[str, Any]]:
    if imports.get("mode") == "service":
        payload = imports["auto_progress_review_cards"](limit=limit)
        return "service", payload if isinstance(payload, dict) else {}
    query = urllib.parse.urlencode({"limit": limit})
    payload = _fetch_json(f"{api_url}/api/pm/review-hygiene/auto-progress?{query}", method="POST")
    return "api", payload if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--mode", choices=["api", "service"], default="api")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--skip-mirror", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = _now()
    imports = _optional_backend_imports(args.mode)
    run_id = f"{AUTOMATION_ID}::{uuid.uuid4()}"

    try:
        mode_used, payload = _run_progress(imports, args.api_url, limit=args.limit)
        finished_at = _now()
        if not args.skip_mirror:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=run_id,
                        automation_id=AUTOMATION_ID,
                        automation_name=AUTOMATION_NAME,
                        status="ok",
                        delivered=True,
                        delivery_channel="ops",
                        delivery_target="pm/review-resolution",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=max(1, int((finished_at - started_at).total_seconds() * 1000)),
                        owner_agent="Codex Review Worker",
                        session_target="local_launchd",
                        scope="shared_ops",
                        action_required=False,
                        metadata={
                            "runner_id": RUNNER_ID,
                            "mode": mode_used,
                            "processed_count": int(payload.get("processed_count") or 0),
                            "closed_count": int(payload.get("closed_count") or 0),
                            "continued_count": int(payload.get("continued_count") or 0),
                            "service_import_error": imports.get("error"),
                        },
                    )
                ],
            )
        print(json.dumps(payload, indent=2, default=_json_default))
        return 0
    except Exception as exc:
        finished_at = _now()
        error_text = str(exc)
        if not args.skip_mirror:
            mirror_runs(
                args.api_url,
                [
                    build_run_payload(
                        run_id=run_id,
                        automation_id=AUTOMATION_ID,
                        automation_name=AUTOMATION_NAME,
                        status="error",
                        delivered=False,
                        delivery_channel="ops",
                        delivery_target="pm/review-resolution",
                        run_at=started_at,
                        finished_at=finished_at,
                        duration_ms=max(1, int((finished_at - started_at).total_seconds() * 1000)),
                        error=error_text[:4000],
                        owner_agent="Codex Review Worker",
                        session_target="local_launchd",
                        scope="shared_ops",
                        action_required=True,
                        metadata={
                            "runner_id": RUNNER_ID,
                            "mode": imports.get("mode"),
                            "service_import_error": imports.get("error"),
                        },
                    )
                ],
            )
        raise SystemExit(error_text) from exc


if __name__ == "__main__":
    raise SystemExit(main())
