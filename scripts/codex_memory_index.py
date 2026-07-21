#!/usr/bin/env python3
"""API-free durable memory search for the Codex-native AI Clone runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from runtime_paths import MEMORY_INDEX_PATH, PROJECT_ROOT, ensure_runtime_dirs


SCHEMA_VERSION = "codex_memory_index/v1"
INDEX_ROOTS = ("memory", "knowledge", "docs", "SOPs", "workspaces", "agents")
ROOT_FILES = (
    "SOURCE_OF_TRUTH.md",
    "CODEX_STARTUP.md",
    "AGENTS.md",
    "MEMORY.md",
    "CHARTER.md",
    "SOUL.md",
    "USER.md",
)
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml"}
EXCLUDED_PARTS = {
    ".git",
    ".next",
    "node_modules",
    "__pycache__",
    "backups",
    "downloads",
    "media",
    "tmp",
    "logs",
    ".railway-stage",
    "dispatch",
    "agent-ledgers",
    "standups",
    "analytics",
    "archive",
    "archived",
}
MAX_FILE_BYTES = 5 * 1024 * 1024
EXCLUDED_PREFIXES = (
    "memory/standup-prep/",
    "memory/runner-memos/",
    "memory/runner-results/",
    "memory/runner-inputs/",
    "memory/runner-ledgers/",
    "memory/media_jobs/",
    "knowledge/ingestions/",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect_writable(index_path: Path = MEMORY_INDEX_PATH) -> sqlite3.Connection:
    ensure_runtime_dirs()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(index_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS memory_documents (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            path UNINDEXED,
            title,
            content,
            tokenize='porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS memory_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    return conn


def _connect_readonly(index_path: Path = MEMORY_INDEX_PATH) -> sqlite3.Connection:
    """Open an existing index without creating files or changing SQLite state."""

    uri = f"{index_path.expanduser().resolve().as_uri()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _candidate_paths(project_root: Path = PROJECT_ROOT) -> Iterable[Path]:
    for name in ROOT_FILES:
        path = project_root / name
        if path.is_file():
            yield path
    for rel_root in INDEX_ROOTS:
        root = project_root / rel_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel_parts = path.relative_to(project_root).parts
            rel = path.relative_to(project_root).as_posix()
            if any(part in EXCLUDED_PARTS for part in rel_parts):
                continue
            if rel.startswith(EXCLUDED_PREFIXES):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _title(text: str, path: Path) -> str:
    for line in text.splitlines()[:80]:
        stripped = line.strip()
        if stripped.startswith("#"):
            value = stripped.lstrip("#").strip()
            if value:
                return value[:240]
    return path.stem.replace("_", " ").replace("-", " ")[:240]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "")


def sync_index(
    *,
    project_root: Path = PROJECT_ROOT,
    index_path: Path = MEMORY_INDEX_PATH,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    conn = _connect_writable(index_path)
    existing = {
        str(row["path"]): (int(row["mtime_ns"]), int(row["size_bytes"]), str(row["sha256"]))
        for row in conn.execute("SELECT path, mtime_ns, size_bytes, sha256 FROM memory_documents")
    }
    observed: set[str] = set()
    added = updated = unchanged = skipped = 0

    processed = 0
    for path in sorted(set(_candidate_paths(project_root))):
        try:
            stat = path.stat()
            rel = path.relative_to(project_root).as_posix()
            observed.add(rel)
            prior = existing.get(rel)
            if prior and prior[0] == stat.st_mtime_ns and prior[1] == stat.st_size:
                unchanged += 1
                continue
            content = _read_text(path)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if prior and prior[2] == digest:
                conn.execute(
                    "UPDATE memory_documents SET mtime_ns=?, size_bytes=?, indexed_at=? WHERE path=?",
                    (stat.st_mtime_ns, stat.st_size, _utcnow(), rel),
                )
                unchanged += 1
                continue
            title = _title(content, path)
            conn.execute("DELETE FROM memory_fts WHERE path=?", (rel,))
            conn.execute(
                "INSERT INTO memory_fts(path, title, content) VALUES (?, ?, ?)",
                (rel, title, content),
            )
            conn.execute(
                """
                INSERT INTO memory_documents(path, title, mtime_ns, size_bytes, sha256, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title=excluded.title,
                    mtime_ns=excluded.mtime_ns,
                    size_bytes=excluded.size_bytes,
                    sha256=excluded.sha256,
                    indexed_at=excluded.indexed_at
                """,
                (rel, title, stat.st_mtime_ns, stat.st_size, digest, _utcnow()),
            )
            if prior:
                updated += 1
            else:
                added += 1
        except (OSError, sqlite3.Error):
            skipped += 1
        processed += 1
        if processed % 10 == 0:
            conn.commit()
        if progress is not None and processed % 50 == 0:
            progress(processed)

    removed_paths = sorted(set(existing) - observed)
    for rel in removed_paths:
        conn.execute("DELETE FROM memory_fts WHERE path=?", (rel,))
        conn.execute("DELETE FROM memory_documents WHERE path=?", (rel,))

    finished_at = _utcnow()
    conn.execute(
        "INSERT INTO memory_metadata(key, value) VALUES ('last_sync_at', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (finished_at,),
    )
    conn.execute(
        "INSERT INTO memory_metadata(key, value) VALUES ('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (SCHEMA_VERSION,),
    )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    total = int(conn.execute("SELECT COUNT(*) FROM memory_documents").fetchone()[0])
    conn.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "project_root": str(project_root),
        "index_path": str(index_path),
        "last_sync_at": finished_at,
        "files": total,
        "added": added,
        "updated": updated,
        "removed": len(removed_paths),
        "unchanged": unchanged,
        "skipped": skipped,
    }


def _fts_query(value: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", value)
    if not tokens:
        return '"__no_match__"'
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:12])


def search_index(
    query: str,
    *,
    limit: int = 8,
    project_root: Path = PROJECT_ROOT,
    index_path: Path = MEMORY_INDEX_PATH,
    sync_if_missing: bool = True,
) -> list[dict[str, Any]]:
    if sync_if_missing and not index_path.exists():
        sync_index(project_root=project_root, index_path=index_path)
    conn = _connect_readonly(index_path)
    rows = conn.execute(
        """
        SELECT path, title,
               snippet(memory_fts, 2, '[', ']', ' ... ', 28) AS excerpt,
               bm25(memory_fts, 8.0, 4.0, 1.0) AS rank
        FROM memory_fts
        WHERE memory_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (_fts_query(query), max(1, min(50, limit))),
    ).fetchall()
    conn.close()
    return [
        {
            "path": str(row["path"]),
            "title": str(row["title"]),
            "excerpt": " ".join(str(row["excerpt"] or "").split()),
            "score": round(float(row["rank"]), 6),
            "source": "codex_memory_index",
            "absolute_path": str(project_root / str(row["path"])),
        }
        for row in rows
    ]


def index_status(index_path: Path = MEMORY_INDEX_PATH) -> dict[str, Any]:
    if not index_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "missing",
            "index_path": str(index_path),
            "files": 0,
            "last_sync_at": None,
        }
    conn = _connect_readonly(index_path)
    files = int(conn.execute("SELECT COUNT(*) FROM memory_documents").fetchone()[0])
    row = conn.execute("SELECT value FROM memory_metadata WHERE key='last_sync_at'").fetchone()
    conn.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if files else "empty",
        "index_path": str(index_path),
        "files": files,
        "last_sync_at": str(row[0]) if row else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync")
    subparsers.add_parser("status")
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    if args.command == "sync":
        payload: Any = sync_index(progress=lambda count: print(f"indexed={count}", flush=True))
    elif args.command == "status":
        payload = index_status()
    else:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "query": args.query,
            "results": search_index(args.query, limit=args.limit),
        }
    print(json.dumps(payload, indent=2))
    return 0 if not isinstance(payload, dict) or payload.get("status") not in {"missing", "empty"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
