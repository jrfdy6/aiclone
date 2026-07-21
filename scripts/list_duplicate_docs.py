#!/usr/bin/env python3
"""List duplicate files between the workspace root and downloads/aiclone."""
import os
from pathlib import Path

def main() -> int:
    workspace = Path(__file__).resolve().parents[1]
    downloads = workspace / "downloads" / "aiclone"
    if not downloads.exists():
        print("No downloads/aiclone directory found.")
        return 1
    duplicates = []
    for entry in workspace.iterdir():
        if entry.is_file() and entry.name not in {"DUPLICATE_INVENTORY.md", "scripts", "media", "downloads", "notes", "memory", "workspace"}:
            for match in downloads.rglob(entry.name):
                duplicates.append((entry.relative_to(workspace), match.relative_to(workspace)))
    if not duplicates:
        print("No duplicates found between root and downloads/aiclone.")
        return 0
    print("Duplicates between workspace root and downloads/aiclone:")
    for root_path, download_path in sorted(duplicates):
        print(f"- {root_path} ↔ downloads/aiclone/{download_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
