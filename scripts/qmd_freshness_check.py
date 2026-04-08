#!/usr/bin/env python3
"""Report QMD index freshness and required collection availability."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_PATH = Path.home() / ".openclaw" / "agents" / "main" / "qmd" / "xdg-cache" / "qmd" / "index.sqlite"
QMD_CONFIG_HOME = Path.home() / ".openclaw" / "agents" / "main" / "qmd" / "xdg-config"
QMD_CACHE_HOME = Path.home() / ".openclaw" / "agents" / "main" / "qmd" / "xdg-cache"
STALE_THRESHOLD_HOURS = 24
REQUIRED_COLLECTIONS = ("memory-main", "memory-dir-main", "knowledge-main")
ALIAS_PROBE_QUERY = "Codex handoff"

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

def qmd_env() -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(QMD_CONFIG_HOME)
    env["XDG_CACHE_HOME"] = str(QMD_CACHE_HOME)
    return env

def run_qmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["qmd", *args],
        capture_output=True,
        text=True,
        env=qmd_env(),
    )

def parse_collection_list(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        if " (qmd://" not in line:
            continue
        names.add(line.split(" (qmd://", 1)[0].strip())
    return names

def validate_collections() -> dict[str, object]:
    list_result = run_qmd("collection", "list")
    if list_result.returncode != 0:
        return {
            "available": False,
            "error": (list_result.stderr or list_result.stdout or "qmd collection list failed").strip(),
        }

    listed = parse_collection_list(list_result.stdout)
    missing = [name for name in REQUIRED_COLLECTIONS if name not in listed]

    search_result = run_qmd("search", ALIAS_PROBE_QUERY, "-c", "memory-dir-main", "-n", "1")
    alias_search_ok = search_result.returncode == 0

    validation: dict[str, object] = {
        "available": True,
        "listed": sorted(listed),
        "missing_required": missing,
        "memory_dir_main_search_ok": alias_search_ok,
    }
    if not alias_search_ok:
        validation["memory_dir_main_search_error"] = (
            search_result.stderr or search_result.stdout or "qmd search probe failed"
        ).strip()
    return validation

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

    validation = validate_collections()
    alias_ready = bool(
        validation.get("available")
        and not validation.get("missing_required")
        and validation.get("memory_dir_main_search_ok")
    )

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
        "required_collections": validation,
        "alias_ready": alias_ready,
    }

    print(json.dumps(summary, indent=2))
    if stale or not alias_ready:
        sys.exit(4)

if __name__ == "__main__":
    main()
