#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PersonaDelta
from app.services.persona_bundle_writer import write_promotion_items_to_bundle
from app.services.persona_promotion_extractor import extract_canonical_promotion_items
from app.services.persona_promotion_utils import normalize_selected_promotion_items


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
LOCAL_SYNC_HOST = socket.gethostname()


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, headers=headers, method=method.upper())
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return None
    return json.loads(raw)


def list_committed_deltas(api_url: str, limit: int = 200) -> list[PersonaDelta]:
    query = parse.urlencode({"status": "committed", "limit": limit})
    payload = _json_request("GET", f"{api_url.rstrip('/')}/api/persona/deltas?{query}")
    if not isinstance(payload, list):
        return []
    deltas: list[PersonaDelta] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        try:
            deltas.append(PersonaDelta.model_validate(entry))
        except Exception:
            continue
    return deltas


def update_local_sync_state(
    api_url: str,
    delta_id: str,
    *,
    state: str,
    bundle_write: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    synced_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "metadata": {
            "local_bundle_sync": {
                "state": state,
                "host": LOCAL_SYNC_HOST,
                "updated_at": synced_at,
                "synced_at": synced_at if state == "synced" else None,
                "written_files": (bundle_write or {}).get("written_files") or [],
                "file_results": (bundle_write or {}).get("file_results") or {},
                "error": error_message,
            }
        }
    }
    return _json_request("PATCH", f"{api_url.rstrip('/')}/api/persona/deltas/{delta_id}", payload=payload)


def _sync_state(delta: PersonaDelta) -> str:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    sync = metadata.get("local_bundle_sync")
    if isinstance(sync, dict):
        return str(sync.get("state") or "").strip().lower()
    return ""


def needs_local_sync(delta: PersonaDelta) -> bool:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    if not metadata.get("selected_promotion_items"):
        return False
    return _sync_state(delta) != "synced"


def sync_delta(delta: PersonaDelta, *, api_url: str, dry_run: bool = False) -> dict[str, Any]:
    extracted_items = extract_canonical_promotion_items(normalize_selected_promotion_items(delta))
    if not extracted_items:
        return {
            "delta_id": delta.id,
            "trait": delta.trait,
            "state": "skipped",
            "reason": "no_selected_promotion_items",
        }

    if dry_run:
        return {
            "delta_id": delta.id,
            "trait": delta.trait,
            "state": "pending",
            "item_count": len(extracted_items),
            "target_files": sorted({item["target_file"] for item in extracted_items}),
        }

    try:
        bundle_write = write_promotion_items_to_bundle(extracted_items)
        update_local_sync_state(api_url, delta.id, state="synced", bundle_write=bundle_write)
        return {
            "delta_id": delta.id,
            "trait": delta.trait,
            "state": "synced",
            "item_count": len(extracted_items),
            "written_files": bundle_write.get("written_files") or [],
            "file_results": bundle_write.get("file_results") or {},
        }
    except Exception as exc:
        try:
            update_local_sync_state(api_url, delta.id, state="failed", error_message=str(exc))
        except Exception:
            pass
        return {
            "delta_id": delta.id,
            "trait": delta.trait,
            "state": "failed",
            "error": str(exc),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync committed persona promotions into the local canonical bundle.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Base URL for the backend persona API.")
    parser.add_argument("--limit", type=int, default=200, help="Max committed deltas to inspect.")
    parser.add_argument("--delta-id", default="", help="Optional specific delta id to sync.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would sync without writing or patching remote metadata.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        deltas = list_committed_deltas(args.api_url, limit=args.limit)
    except error.HTTPError as exc:
        print(json.dumps({"ok": False, "error": f"HTTP {exc.code} while listing persona deltas"}))
        return 1
    except error.URLError as exc:
        print(json.dumps({"ok": False, "error": f"Unable to reach persona API: {exc.reason}"}))
        return 1

    if args.delta_id:
        deltas = [delta for delta in deltas if delta.id == args.delta_id]

    pending = [delta for delta in deltas if needs_local_sync(delta)]
    results = [sync_delta(delta, api_url=args.api_url, dry_run=args.dry_run) for delta in pending]
    summary = {
        "ok": True,
        "api_url": args.api_url,
        "dry_run": args.dry_run,
        "scanned": len(deltas),
        "pending": len(pending),
        "synced": sum(1 for item in results if item.get("state") == "synced"),
        "failed": sum(1 for item in results if item.get("state") == "failed"),
        "skipped": sum(1 for item in results if item.get("state") == "skipped"),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
