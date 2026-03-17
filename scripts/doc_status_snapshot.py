#!/usr/bin/env python3
"""Emit size + mtime metadata for docs that Rolling Docs monitors."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FILES = {
    "README.md": Path("/Users/neo/.openclaw/workspace/README.md"),
    "memory/LEARNINGS.md": Path("/Users/neo/.openclaw/workspace/memory/LEARNINGS.md"),
    "HEARTBEAT.md": Path("/Users/neo/.openclaw/workspace/HEARTBEAT.md"),
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
