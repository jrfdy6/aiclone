#!/usr/bin/env python3
"""Repair the agent-local QMD `memory-dir-main` compatibility alias.

OpenClaw still issues searches against `memory-dir-main`, but the live agent
QMD store can drift to only having `memory-main`. This script restores the
alias, backfills existing documents, and installs mirroring triggers so future
`memory-main` updates stay visible through `memory-dir-main`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_DIR = WORKSPACE_ROOT / "memory"
MEMORY_ALIAS_LINK = WORKSPACE_ROOT / ".memory-dir-link"
QMD_CONFIG_ROOT = Path("/Users/neo/.openclaw/agents/main/qmd/xdg-config")
QMD_CONFIG_FILES = (
    QMD_CONFIG_ROOT / "index.yml",
    QMD_CONFIG_ROOT / "qmd" / "index.yml",
)
QMD_DB = Path("/Users/neo/.openclaw/agents/main/qmd/xdg-cache/qmd/index.sqlite")

ALIAS_NAME = "memory-dir-main"
SOURCE_NAME = "memory-main"
ALIAS_PATTERN = "**/*.md"


def ensure_alias_link() -> None:
    if MEMORY_ALIAS_LINK.is_symlink():
        if MEMORY_ALIAS_LINK.resolve() == MEMORY_DIR.resolve():
            return
        MEMORY_ALIAS_LINK.unlink()
    elif MEMORY_ALIAS_LINK.exists():
        raise RuntimeError(f"{MEMORY_ALIAS_LINK} exists but is not the expected symlink.")
    MEMORY_ALIAS_LINK.symlink_to(MEMORY_DIR, target_is_directory=True)


def ensure_config_alias() -> None:
    expected_block = (
        f"  {ALIAS_NAME}:\n"
        f"    path: {MEMORY_ALIAS_LINK}\n"
        f'    pattern: "{ALIAS_PATTERN}"\n'
    )
    anchor = (
        f"  {SOURCE_NAME}:\n"
        f"    path: {MEMORY_DIR}\n"
        f'    pattern: "{ALIAS_PATTERN}"\n'
    )

    for config_path in QMD_CONFIG_FILES:
        if not config_path.exists():
            raise FileNotFoundError(f"Missing QMD config: {config_path}")
        content = config_path.read_text()
        if f"  {ALIAS_NAME}:\n" in content:
            continue
        if anchor not in content:
            raise RuntimeError(f"Could not find anchor block in {config_path}")
        config_path.write_text(content.replace(anchor, anchor + expected_block, 1))


def repair_alias(conn: sqlite3.Connection) -> dict[str, int]:
    alias_path = str(MEMORY_ALIAS_LINK)
    source_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE collection = ?",
        (SOURCE_NAME,),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO store_collections(name, path, pattern, ignore_patterns, include_by_default, update_command, context)
        VALUES (?, ?, ?, NULL, 1, NULL, NULL)
        ON CONFLICT(name) DO UPDATE SET path = excluded.path, pattern = excluded.pattern
        """,
        (ALIAS_NAME, alias_path, ALIAS_PATTERN),
    )

    conn.execute(
        """
        INSERT INTO documents(collection, path, title, hash, created_at, modified_at, active)
        SELECT ?, path, title, hash, created_at, modified_at, active
        FROM documents
        WHERE collection = ?
          AND NOT EXISTS (
            SELECT 1
            FROM documents existing
            WHERE existing.collection = ?
              AND existing.path = documents.path
          )
        """,
        (ALIAS_NAME, SOURCE_NAME, ALIAS_NAME),
    )

    conn.executescript(
        f"""
        DROP TRIGGER IF EXISTS documents_ai_{ALIAS_NAME.replace('-', '_')};
        CREATE TRIGGER documents_ai_{ALIAS_NAME.replace('-', '_')}
        AFTER INSERT ON documents
        WHEN NEW.collection = '{SOURCE_NAME}'
        BEGIN
          INSERT OR REPLACE INTO documents(collection, path, title, hash, created_at, modified_at, active)
          VALUES ('{ALIAS_NAME}', NEW.path, NEW.title, NEW.hash, NEW.created_at, NEW.modified_at, NEW.active);
        END;

        DROP TRIGGER IF EXISTS documents_au_{ALIAS_NAME.replace('-', '_')};
        CREATE TRIGGER documents_au_{ALIAS_NAME.replace('-', '_')}
        AFTER UPDATE ON documents
        WHEN OLD.collection = '{SOURCE_NAME}'
        BEGIN
          DELETE FROM documents
          WHERE collection = '{ALIAS_NAME}' AND path = OLD.path;

          INSERT INTO documents(collection, path, title, hash, created_at, modified_at, active)
          VALUES ('{ALIAS_NAME}', NEW.path, NEW.title, NEW.hash, NEW.created_at, NEW.modified_at, NEW.active);
        END;

        DROP TRIGGER IF EXISTS documents_ad_{ALIAS_NAME.replace('-', '_')};
        CREATE TRIGGER documents_ad_{ALIAS_NAME.replace('-', '_')}
        AFTER DELETE ON documents
        WHEN OLD.collection = '{SOURCE_NAME}'
        BEGIN
          DELETE FROM documents
          WHERE collection = '{ALIAS_NAME}' AND path = OLD.path;
        END;
        """
    )

    alias_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE collection = ?",
        (ALIAS_NAME,),
    ).fetchone()[0]
    return {
        "source_documents": int(source_count),
        "alias_documents": int(alias_count),
    }


def main() -> int:
    if not QMD_DB.exists():
        raise FileNotFoundError(f"Missing QMD index: {QMD_DB}")

    ensure_alias_link()
    ensure_config_alias()
    with sqlite3.connect(QMD_DB) as conn:
        stats = repair_alias(conn)
        conn.commit()

    print(f"Repaired {ALIAS_NAME} -> {MEMORY_ALIAS_LINK}")
    print(f"Source documents: {stats['source_documents']}")
    print(f"Alias documents: {stats['alias_documents']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
