from __future__ import annotations

import os
import re
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_DB_KEYS = [
    "OPEN_BRAIN_DATABASE_URL",
    "BRAIN_VECTOR_DATABASE_URL",
    "DATABASE_URL",
    "DATABASE_PUBLIC_URL",
]
DEFAULT_VECTOR_DIM = 1024

_UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"

_pool: Optional[ConnectionPool] = None


def _get_conninfo() -> Optional[str]:
    for key in _DB_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


def _ensure_connect_timeout(conninfo: str, timeout_seconds: int = 3) -> str:
    normalized = (conninfo or "").strip()
    if not normalized or "connect_timeout=" in normalized:
        return normalized
    if "://" in normalized:
        parts = urlsplit(normalized)
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        query_pairs.append(("connect_timeout", str(timeout_seconds)))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment))
    return f"{normalized} connect_timeout={timeout_seconds}"


_BASE_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS knowledge_capture (
        id UUID PRIMARY KEY,
        source TEXT,
        topic TEXT[],
        importance INT DEFAULT 2,
        raw_text TEXT,
        markdown_path TEXT,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS source TEXT",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS topic TEXT[]",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS importance INT DEFAULT 2",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS raw_text TEXT",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS markdown_path TEXT",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb",
    "ALTER TABLE knowledge_capture ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS knowledge_capture_markdown_path_idx ON knowledge_capture(markdown_path)",
    "CREATE INDEX IF NOT EXISTS knowledge_capture_resolved_capture_idx ON knowledge_capture((metadata->>'resolved_capture_id'))",
    """
    CREATE TABLE IF NOT EXISTS memory_vectors (
        id UUID PRIMARY KEY,
        capture_id UUID REFERENCES knowledge_capture(id) ON DELETE CASCADE,
        embedding_json JSONB,
        chunk TEXT,
        chunk_index INT,
        last_refreshed_at TIMESTAMPTZ DEFAULT NOW(),
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS capture_id UUID",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS embedding_json JSONB",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS chunk TEXT",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS chunk_index INT",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS last_refreshed_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
    "ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS memory_vectors_capture_idx ON memory_vectors(capture_id)",
    "CREATE INDEX IF NOT EXISTS memory_vectors_expires_idx ON memory_vectors(expires_at)",
    """
    CREATE TABLE IF NOT EXISTS session_metrics (
        id UUID PRIMARY KEY,
        agent_name TEXT NOT NULL,
        model TEXT,
        status TEXT DEFAULT 'active',
        total_tokens BIGINT DEFAULT 0,
        last_message_at TIMESTAMPTZ,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS session_metrics_last_message_idx ON session_metrics(last_message_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS persona_deltas (
        id UUID PRIMARY KEY,
        capture_id UUID REFERENCES knowledge_capture(id) ON DELETE SET NULL,
        persona_target TEXT NOT NULL,
        trait TEXT NOT NULL,
        notes TEXT,
        status TEXT DEFAULT 'draft',
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        committed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS persona_deltas_status_idx ON persona_deltas(status)",
    """
    CREATE TABLE IF NOT EXISTS pm_cards (
        id UUID PRIMARY KEY,
        title TEXT NOT NULL,
        owner TEXT,
        status TEXT DEFAULT 'todo',
        source TEXT,
        link_type TEXT,
        link_id UUID,
        due_at TIMESTAMPTZ,
        payload JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS pm_cards_status_idx ON pm_cards(status)",
    """
    CREATE TABLE IF NOT EXISTS build_reviews (
        id UUID PRIMARY KEY,
        title TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        source_type TEXT,
        source_url TEXT,
        ingestion_path TEXT,
        summary TEXT,
        why_showing TEXT,
        decision TEXT,
        response_notes TEXT,
        resolution_capture_id TEXT,
        payload JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        resolved_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS build_reviews_status_idx ON build_reviews(status)",
    "CREATE INDEX IF NOT EXISTS build_reviews_ingestion_idx ON build_reviews(ingestion_path)",
    """
    CREATE TABLE IF NOT EXISTS standups (
        id UUID PRIMARY KEY,
        owner TEXT NOT NULL,
        workspace_key TEXT DEFAULT 'shared_ops',
        status TEXT,
        blockers TEXT[] DEFAULT '{}',
        commitments TEXT[] DEFAULT '{}',
        needs TEXT[] DEFAULT '{}',
        source TEXT,
        conversation_path TEXT,
        payload JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS standups_owner_idx ON standups(owner)",
    "ALTER TABLE standups ADD COLUMN IF NOT EXISTS workspace_key TEXT DEFAULT 'shared_ops'",
    "ALTER TABLE standups ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb",
    "CREATE INDEX IF NOT EXISTS standups_workspace_idx ON standups(workspace_key, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS daily_briefs (
        id UUID PRIMARY KEY,
        brief_date DATE NOT NULL UNIQUE,
        title TEXT NOT NULL,
        summary TEXT,
        content_markdown TEXT NOT NULL,
        source TEXT NOT NULL,
        source_ref TEXT,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS daily_briefs_date_idx ON daily_briefs(brief_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS brief_reactions (
        id UUID PRIMARY KEY,
        brief_id TEXT NOT NULL,
        item_key TEXT NOT NULL,
        item_title TEXT NOT NULL,
        reaction_kind TEXT NOT NULL,
        text TEXT NOT NULL,
        source_kind TEXT,
        source_url TEXT,
        source_path TEXT,
        linked_delta_id TEXT,
        linked_capture_id TEXT,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS brief_reactions_brief_idx ON brief_reactions(brief_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS brief_reactions_item_idx ON brief_reactions(item_key, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS workspace_snapshots (
        id UUID PRIMARY KEY,
        workspace_key TEXT NOT NULL,
        snapshot_type TEXT NOT NULL,
        payload JSONB DEFAULT '{}'::jsonb,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (workspace_key, snapshot_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS workspace_snapshots_workspace_idx ON workspace_snapshots(workspace_key, snapshot_type)",
    """
    CREATE TABLE IF NOT EXISTS automation_runs (
        id TEXT PRIMARY KEY,
        automation_id TEXT NOT NULL,
        automation_name TEXT NOT NULL,
        source TEXT DEFAULT 'static_registry',
        runtime TEXT,
        status TEXT DEFAULT 'unknown',
        delivered BOOLEAN,
        delivery_channel TEXT,
        delivery_target TEXT,
        run_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        duration_ms INT,
        error TEXT,
        owner_agent TEXT,
        session_target TEXT,
        scope TEXT DEFAULT 'shared_ops',
        workspace_key TEXT,
        action_required BOOLEAN DEFAULT FALSE,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS automation_runs_automation_idx ON automation_runs(automation_id, run_at DESC)",
    "CREATE INDEX IF NOT EXISTS automation_runs_status_idx ON automation_runs(status, action_required, run_at DESC)",
)


def _parse_vector_dimension(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"vector\((\d+)\)", value)
    if not match:
        return None
    return int(match.group(1))


def _table_columns(conn: Connection[Any], table_name: str) -> dict[str, dict[str, str]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            (table_name,),
        )
        rows = cur.fetchall() or []
    return {row["column_name"]: row for row in rows}


def _fetch_embedding_type(conn: Connection[Any]) -> Optional[str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod) AS embedding_type
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'memory_vectors'
              AND a.attname = 'embedding'
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY n.nspname = current_schema() DESC
            LIMIT 1
            """
        )
        row = cur.fetchone() or {}
    return row.get("embedding_type")


def detect_memory_vector_storage(conn: Connection[Any]) -> dict[str, Any]:
    capture_columns = _table_columns(conn, "knowledge_capture")
    vector_columns = _table_columns(conn, "memory_vectors")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector') AS available")
        vector_available = bool((cur.fetchone() or {}).get("available"))

        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') AS enabled")
        vector_enabled = bool((cur.fetchone() or {}).get("enabled"))

    embedding_type = _fetch_embedding_type(conn) if "embedding" in vector_columns else None
    configured_dimension = _parse_vector_dimension(embedding_type)

    if vector_enabled and configured_dimension:
        storage_backend = "pgvector"
    elif "embedding_json" in vector_columns:
        storage_backend = "jsonb"
    else:
        storage_backend = "legacy"

    capture_id_type = capture_columns.get("id", {}).get("udt_name")
    vector_id_type = vector_columns.get("id", {}).get("udt_name")
    if vector_columns.get("related_id", {}).get("udt_name") == capture_id_type:
        join_column = "related_id"
    elif vector_columns.get("capture_id", {}).get("udt_name") == capture_id_type:
        join_column = "capture_id"
    else:
        join_column = None

    return {
        "storage_backend": storage_backend,
        "vector_available": vector_available,
        "vector_extension": vector_enabled,
        "embedding_type": embedding_type or ("jsonb" if "embedding_json" in vector_columns else None),
        "configured_dimension": configured_dimension,
        "capture_id_type": capture_id_type,
        "vector_id_type": vector_id_type,
        "join_column": join_column,
        "capture_table_columns": capture_columns,
        "vector_table_columns": vector_columns,
    }


def _maybe_enable_vector_extension(conn: Connection[Any]) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'vector') AS available")
        row = cur.fetchone() or {}

    if not row.get("available"):
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def _backfill_legacy_columns(conn: Connection[Any]) -> None:
    vector_columns = _table_columns(conn, "memory_vectors")
    if not vector_columns:
        return

    with conn.cursor() as cur:
        related_id_column = vector_columns.get("related_id")
        capture_id_column = vector_columns.get("capture_id")
        if related_id_column and capture_id_column:
            if related_id_column["udt_name"] == "uuid" and capture_id_column["udt_name"] == "uuid":
                cur.execute(
                    """
                    UPDATE memory_vectors
                    SET capture_id = related_id
                    WHERE capture_id IS NULL
                      AND related_id IS NOT NULL
                    """
                )
            elif related_id_column["data_type"] in {"text", "character varying"} and capture_id_column["udt_name"] == "uuid":
                cur.execute(
                    """
                    UPDATE memory_vectors
                    SET capture_id = related_id::uuid
                    WHERE capture_id IS NULL
                      AND related_id IS NOT NULL
                      AND related_id ~* %s
                    """,
                    (_UUID_PATTERN,),
                )

        legacy_vector = vector_columns.get("vector")
        if legacy_vector and "embedding_json" in vector_columns:
            if legacy_vector["data_type"] in {"json", "jsonb"}:
                cur.execute(
                    """
                    UPDATE memory_vectors
                    SET embedding_json = COALESCE(embedding_json, vector::jsonb)
                    WHERE vector IS NOT NULL
                    """
                )
            elif legacy_vector["data_type"] == "ARRAY" and legacy_vector["udt_name"] in {"_float4", "_float8", "_numeric"}:
                cur.execute(
                    """
                    UPDATE memory_vectors
                    SET embedding_json = COALESCE(embedding_json, to_jsonb(vector))
                    WHERE vector IS NOT NULL
                    """
                )
    conn.commit()


def initialize_schema_on_connection(conn: Connection[Any]) -> None:
    vector_enabled = _maybe_enable_vector_extension(conn)

    with conn.cursor() as cur:
        for statement in _BASE_SCHEMA_STATEMENTS:
            cur.execute(statement)
    conn.commit()

    if vector_enabled:
        try:
            vector_dim = DEFAULT_VECTOR_DIM
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE memory_vectors ADD COLUMN IF NOT EXISTS embedding vector({vector_dim})")
            conn.commit()
        except Exception:
            conn.rollback()

    _backfill_legacy_columns(conn)


def initialize_schema(pool: ConnectionPool) -> None:
    with pool.connection() as conn:
        initialize_schema_on_connection(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        conninfo = _get_conninfo()
        if not conninfo:
            raise RuntimeError("Open brain database url is not configured")
        conninfo = _ensure_connect_timeout(conninfo)

        min_size = int(os.getenv("OPEN_BRAIN_POOL_MIN", "1"))
        max_size = int(os.getenv("OPEN_BRAIN_POOL_MAX", "5"))

        _pool = ConnectionPool(conninfo=conninfo, min_size=min_size, max_size=max_size)

        initialize_schema(_pool)

    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
