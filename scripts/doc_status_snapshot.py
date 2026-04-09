#!/usr/bin/env python3
"""Emit size + mtime metadata for docs that Rolling Docs monitors."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_snapshot_fallback_path

FILES = {
    "README.md": WORKSPACE_ROOT / "README.md",
    "memory/LEARNINGS.md": resolve_snapshot_fallback_path(WORKSPACE_ROOT, "memory/LEARNINGS.md"),
    "HEARTBEAT.md": WORKSPACE_ROOT / "HEARTBEAT.md",
}

rows = []
for name, path in FILES.items():
    if path.exists():
        stat = path.stat()
        rows.append(
            {
                "name": name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    else:
        rows.append({"name": name, "path": str(path), "missing": True})

print(json.dumps({"docs": rows}, indent=2))
