#!/usr/bin/env python3
"""Validate the Codex-native SQLite memory index and a real recall probe."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from codex_memory_index import INDEX_ROOTS, index_status, search_index, sync_index


STALE_THRESHOLD_HOURS = 24
PROBE_QUERY = "Codex handoff Railway PM board"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_report(*, sync: bool = False) -> dict[str, Any]:
    sync_report = sync_index() if sync else None
    status = index_status()
    last_update = _parse_timestamp(status.get("last_sync_at"))
    hours = None
    if last_update is not None:
        hours = (datetime.now(timezone.utc) - last_update).total_seconds() / 3600
    results = search_index(PROBE_QUERY, limit=3, sync_if_missing=sync)
    stale = hours is None or hours > STALE_THRESHOLD_HOURS
    ready = status.get("status") == "ok" and int(status.get("files") or 0) > 0 and bool(results)
    return {
        "schema_version": "codex_memory_freshness/v1",
        "status": "ok" if ready and not stale else "action_required",
        "backend": "sqlite_fts5",
        "index_path": status.get("index_path"),
        "files": int(status.get("files") or 0),
        "collections": list(INDEX_ROOTS),
        "last_update": status.get("last_sync_at"),
        "hours_since_update": round(hours, 2) if hours is not None else None,
        "stale": stale,
        "probe_query": PROBE_QUERY,
        "probe_result_count": len(results),
        "ready": ready,
        "sync": sync_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Refresh the index before checking it")
    args = parser.parse_args()
    report = build_report(sync=args.sync)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 4


if __name__ == "__main__":
    raise SystemExit(main())
