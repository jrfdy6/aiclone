#!/usr/bin/env python3
"""Report QMD index freshness using `openclaw memory status --json`."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

INDEX_PATH = Path.home() / ".openclaw" / "agents" / "main" / "qmd" / "xdg-cache" / "qmd" / "index.sqlite"
STALE_THRESHOLD_HOURS = 24

def run_status() -> dict:
    try:
        result = subprocess.run(
            ["openclaw", "memory", "status", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or exc.stdout or "Failed to run openclaw memory status\n")
        sys.exit(exc.returncode or 1)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid JSON from openclaw memory status: {exc}\n")
        sys.exit(2)
    if not data:
        sys.stderr.write("No status entries returned.\n")
        sys.exit(3)
    return data[0]

def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def main() -> None:
    entry = run_status()
    status = entry.get("status", {})
    scan = entry.get("scan", {})

    files = status.get("files")
    chunks = status.get("chunks")
    vector = status.get("vector", {})
    custom_qmd = status.get("custom", {}).get("qmd", {})
    collections = custom_qmd.get("collections")
    last_update = parse_timestamp(custom_qmd.get("lastUpdateAt"))

    if last_update is None and INDEX_PATH.exists():
        last_update = datetime.fromtimestamp(INDEX_PATH.stat().st_mtime, tz=timezone.utc)

    now = datetime.now(timezone.utc)
    freshness = None
    stale = False
    if last_update:
        freshness = (now - last_update).total_seconds() / 3600
        stale = freshness > STALE_THRESHOLD_HOURS

    summary = {
        "files": files,
        "chunks": chunks,
        "collections": collections,
        "vector_enabled": vector.get("enabled"),
        "vector_available": vector.get("available"),
        "scan_files": scan.get("totalFiles"),
        "last_update": last_update.isoformat() if last_update else None,
        "hours_since_update": round(freshness, 2) if freshness is not None else None,
        "stale": stale,
    }

    print(json.dumps(summary, indent=2))
    if stale:
        sys.exit(4)

if __name__ == "__main__":
    main()
