from __future__ import annotations

import uuid
import json
from datetime import datetime
from typing import Iterable, List, Optional

from psycopg.rows import dict_row

from app.services.open_brain_db import get_pool


def insert_capture(
    *,
    source: str,
    topics: List[str],
    importance: int,
    raw_text: str,
    markdown_path: Optional[str],
    metadata: Optional[dict],
) -> str:
    capture_id = str(uuid.uuid4())
    query = (
        """
        INSERT INTO knowledge_capture (id, source, topic, importance, raw_text, markdown_path, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
    )
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    capture_id,
                    source,
                    topics or [],
                    importance,
                    raw_text,
                    markdown_path,
                    json.dumps(metadata or {}),
                ),
            )
        conn.commit()
    return capture_id


def insert_vector_chunks(chunks: Iterable[dict]) -> List[str]:
    chunk_ids: List[str] = []
    query = (
        """
        INSERT INTO memory_vectors (id, capture_id, embedding, chunk, chunk_index, last_refreshed_at, expires_at)
        VALUES (%s, %s, %s, %s, %s, NOW(), %s)
        """
    )
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for item in chunks:
                chunk_id = item.get("id") or str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                cur.execute(
                    query,
                    (
                        chunk_id,
                        item["capture_id"],
                        item["embedding"],
                        item["chunk"],
                        item["chunk_index"],
                        item.get("expires_at"),
                    ),
                )
        conn.commit()
    return chunk_ids


def delete_vectors_for_capture(capture_id: str) -> int:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memory_vectors WHERE capture_id = %s", (capture_id,))
            deleted = cur.rowcount or 0
        conn.commit()
    return deleted


def fetch_captures_updated_since(threshold: datetime, limit: int) -> List[dict]:
    query = """
        SELECT id, raw_text, importance
        FROM knowledge_capture
        WHERE updated_at >= %s
        ORDER BY updated_at DESC
        LIMIT %s
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (threshold, limit))
            return cur.fetchall() or []


def delete_expired_vectors() -> int:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memory_vectors WHERE expires_at IS NOT NULL AND expires_at < NOW()")
            deleted = cur.rowcount or 0
        conn.commit()
    return deleted
