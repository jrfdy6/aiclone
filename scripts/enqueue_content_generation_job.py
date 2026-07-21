#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from thin_trigger_client import DEFAULT_API_URL, ThinTriggerError, request_json


ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.trigger_identity_service import build_content_job_idempotency_key  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue a thin content-generation job through the backend contract.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--user-id", default="johnnie_fields")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--context", default="")
    parser.add_argument("--content-type", default="linkedin_post")
    parser.add_argument("--category", default="value")
    parser.add_argument("--tone", default="expert_direct")
    parser.add_argument("--audience", default="tech_ai")
    parser.add_argument("--source-mode", default="persona_only")
    parser.add_argument("--workspace-slug", default="linkedin-content-os")
    parser.add_argument("--wait", action="store_true", help="Poll the job until it reaches a terminal state.")
    parser.add_argument("--poll-seconds", type=float, default=4.0)
    parser.add_argument("--timeout-seconds", type=int, default=420)
    parser.add_argument("--include-artifacts", action="store_true", help="Fetch artifact metadata when waiting.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_request_payload(args: argparse.Namespace | SimpleNamespace) -> dict[str, str]:
    payload = {
        "user_id": str(args.user_id),
        "topic": str(args.topic),
        "context": str(args.context),
        "content_type": str(args.content_type),
        "category": str(args.category),
        "tone": str(args.tone),
        "audience": str(args.audience),
        "source_mode": str(args.source_mode),
        "workspace_slug": str(args.workspace_slug),
    }
    payload["idempotency_key"] = build_content_job_idempotency_key(payload)
    return payload


def _fetch_status(api_url: str, job_id: str) -> dict[str, object]:
    payload = request_json(api_url, f"/api/content-generation/codex-jobs/{job_id}")
    return payload if isinstance(payload, dict) else {}


def _fetch_artifacts(api_url: str, job_id: str) -> list[dict[str, object]]:
    payload = request_json(api_url, f"/api/content-generation/codex-jobs/{job_id}/artifacts")
    if not isinstance(payload, dict):
        return []
    items = payload.get("artifacts")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def main() -> int:
    args = parse_args()
    payload = build_request_payload(args)
    if args.dry_run:
        print(json.dumps({"success": True, "dry_run": True, "api_url": args.api_url, "payload": payload}, indent=2))
        return 0
    try:
        created = request_json(args.api_url, "/api/content-generation/codex-jobs", method="POST", payload=payload)
        if not isinstance(created, dict):
            raise ThinTriggerError("Content trigger returned a non-object create response.")
        job_id = str(created.get("job_id") or "").strip()
        if not job_id:
            raise ThinTriggerError("Content trigger did not return a job id.", detail=created)

        if not args.wait:
            print(json.dumps({"success": True, "create": created}, indent=2))
            return 0

        deadline = time.monotonic() + max(1, int(args.timeout_seconds))
        last_status = _fetch_status(args.api_url, job_id)
        while str(last_status.get("status") or "").lower() not in {"completed", "failed", "canceled"}:
            if time.monotonic() >= deadline:
                print(
                    json.dumps(
                        {
                            "success": False,
                            "timeout": True,
                            "create": created,
                            "status": last_status,
                        },
                        indent=2,
                    )
                )
                return 2
            time.sleep(max(0.5, float(args.poll_seconds)))
            last_status = _fetch_status(args.api_url, job_id)

        result: dict[str, object] = {
            "success": str(last_status.get("status") or "").lower() == "completed",
            "create": created,
            "status": last_status,
        }
        if args.include_artifacts:
            result["artifacts"] = _fetch_artifacts(args.api_url, job_id)
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    except ThinTriggerError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
