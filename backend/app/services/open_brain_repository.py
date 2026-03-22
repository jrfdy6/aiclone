from __future__ import annotations

import json
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.services.open_brain_db import detect_memory_vector_storage, get_pool


def _vector_literal(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


def _json_embedding(values: Iterable[float]) -> Json:
    return Json([float(value) for value in values])


def _coerce_embedding(raw: Any) -> Optional[List[float]]:
    if raw is None:
        return None
    values = raw
    if isinstance(raw, str):
        try:
            values = json.loads(raw)
        except json.JSONDecodeError:
            return None

    if isinstance(values, tuple):
        values = list(values)

    if not isinstance(values, list):
        return None

    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        return None


def _cosine_similarity(left: List[float], right: List[float]) -> Optional[float]:
    if not left or not right or len(left) != len(right):
        return None

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return None
    return dot / (left_norm * right_norm)


def _hit_from_row(row: Dict[str, Any], similarity_score: float) -> Dict[str, Any]:
    return {
        "chunk_id": str(row["chunk_id"]),
        "capture_id": str(row["capture_id"]),
        "chunk_index": int(row.get("chunk_index") or 0),
        "chunk": row.get("chunk") or "",
        "similarity_score": float(similarity_score),
        "source": row.get("source"),
        "topics": row.get("topic") or [],
        "importance": int(row.get("importance") or 0),
        "markdown_path": row.get("markdown_path"),
        "created_at": row.get("created_at"),
        "metadata": row.get("metadata") or {},
    }


def _is_integer_type(udt_name: Optional[str]) -> bool:
    return udt_name in {"int2", "int4", "int8"}


def _coerce_identifier(value: Any, udt_name: Optional[str]) -> Any:
    if _is_integer_type(udt_name):
        return int(value)
    return str(value)


def _vector_join_column(storage: Dict[str, Any]) -> str:
    join_column = storage.get("join_column")
    if join_column not in {"capture_id", "related_id"}:
        raise RuntimeError("memory_vectors has no compatible capture join column")
    return join_column


def _vector_join_condition(storage: Dict[str, Any]) -> str:
    join_column = _vector_join_column(storage)
    return f"kc.id = mv.{join_column}"


def _resolved_capture_key(metadata: Optional[dict]) -> Optional[str]:
    if not metadata:
        return None
    value = metadata.get("resolved_capture_id")
    return str(value).strip() if value else None


def _capture_title(source: str, metadata: Optional[dict]) -> str:
    return str((metadata or {}).get("title") or source)


def _find_matching_captures(
    conn,
    *,
    markdown_path: Optional[str],
    resolved_capture_id: Optional[str],
) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if markdown_path:
        clauses.append("markdown_path = %s")
        params.append(markdown_path)
    if resolved_capture_id:
        clauses.append("metadata ->> 'resolved_capture_id' = %s")
        params.append(resolved_capture_id)
    if not clauses:
        return []

    query = f"""
        SELECT id, created_at, updated_at
        FROM knowledge_capture
        WHERE {" OR ".join(clauses)}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        return cur.fetchall() or []


def _update_capture_row(
    conn,
    storage: Dict[str, Any],
    *,
    capture_id: str,
    source: str,
    topics: List[str],
    importance: int,
    raw_text: str,
    markdown_path: Optional[str],
    metadata: Optional[dict],
) -> None:
    capture_columns = storage.get("capture_table_columns") or {}
    capture_id_type = storage.get("capture_id_type")
    assignments: List[str] = []
    values: List[Any] = []

    def assign(column: str, value: Any) -> None:
        if column in capture_columns:
            assignments.append(f"{column} = %s")
            values.append(value)

    assign("source", source)
    assign("topic", topics or [])
    assign("importance", importance)
    assign("raw_text", raw_text)
    assign("markdown_path", markdown_path)
    assign("metadata", Json(metadata or {}))
    assign("title", _capture_title(source, metadata))
    assign("content", raw_text)
    assignments.append("updated_at = NOW()")

    values.append(_coerce_identifier(capture_id, capture_id_type))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE knowledge_capture
            SET {", ".join(assignments)}
            WHERE id = %s
            """,
            tuple(values),
        )


def _insert_capture_row(
    conn,
    storage: Dict[str, Any],
    *,
    source: str,
    topics: List[str],
    importance: int,
    raw_text: str,
    markdown_path: Optional[str],
    metadata: Optional[dict],
) -> str:
    capture_columns = storage.get("capture_table_columns") or {}
    capture_id_type = storage.get("capture_id_type")
    title = _capture_title(source, metadata)
    with conn.cursor() as cur:
        if _is_integer_type(capture_id_type):
            columns = ["source", "importance", "raw_text", "markdown_path", "metadata", "created_at", "updated_at"]
            values: List[Any] = [source, importance, raw_text, markdown_path, Json(metadata or {})]
            placeholders = ["%s", "%s", "%s", "%s", "%s", "NOW()", "NOW()"]
            if "topic" in capture_columns:
                columns.insert(1, "topic")
                values.insert(1, topics or [])
                placeholders.insert(1, "%s")
            if "content" in capture_columns:
                columns.insert(3, "content")
                values.insert(3, raw_text)
                placeholders.insert(3, "%s")
            if "title" in capture_columns:
                columns.insert(1, "title")
                values.insert(1, title)
                placeholders.insert(1, "%s")

            cur.execute(
                f"""
                INSERT INTO knowledge_capture ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
                RETURNING id
                """,
                tuple(values),
            )
        else:
            capture_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO knowledge_capture (
                    id, source, topic, importance, raw_text, markdown_path, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (
                    capture_id,
                    source,
                    topics or [],
                    importance,
                    raw_text,
                    markdown_path,
                    Json(metadata or {}),
                ),
            )
        return str(cur.fetchone()[0])


def _delete_capture_rows(conn, storage: Dict[str, Any], capture_ids: List[str]) -> None:
    if not capture_ids:
        return
    join_column = _vector_join_column(storage)
    join_value_type = (storage.get("vector_table_columns") or {}).get(join_column, {}).get("udt_name")
    capture_id_type = storage.get("capture_id_type")
    with conn.cursor() as cur:
        for capture_id in capture_ids:
            cur.execute(
                f"DELETE FROM memory_vectors WHERE {join_column} = %s",
                (_coerce_identifier(capture_id, join_value_type),),
            )
            cur.execute(
                "DELETE FROM knowledge_capture WHERE id = %s",
                (_coerce_identifier(capture_id, capture_id_type),),
            )


def upsert_capture(
    *,
    source: str,
    topics: List[str],
    importance: int,
    raw_text: str,
    markdown_path: Optional[str],
    metadata: Optional[dict],
) -> tuple[str, bool]:
    pool = get_pool()
    with pool.connection() as conn:
        storage = detect_memory_vector_storage(conn)
        matches = _find_matching_captures(
            conn,
            markdown_path=markdown_path,
            resolved_capture_id=_resolved_capture_key(metadata),
        )
        if matches:
            capture_id = str(matches[0]["id"])
            duplicate_ids = [str(row["id"]) for row in matches[1:] if str(row["id"]) != capture_id]
            _update_capture_row(
                conn,
                storage,
                capture_id=capture_id,
                source=source,
                topics=topics,
                importance=importance,
                raw_text=raw_text,
                markdown_path=markdown_path,
                metadata=metadata,
            )
            _delete_capture_rows(conn, storage, duplicate_ids)
            conn.commit()
            return capture_id, True

        capture_id = _insert_capture_row(
            conn,
            storage,
            source=source,
            topics=topics,
            importance=importance,
            raw_text=raw_text,
            markdown_path=markdown_path,
            metadata=metadata,
        )
        conn.commit()
    return capture_id, False


def insert_vector_chunks(chunks: Iterable[dict]) -> List[str]:
    chunk_ids: List[str] = []
    pool = get_pool()
    with pool.connection() as conn:
        storage = detect_memory_vector_storage(conn)
        join_column = _vector_join_column(storage)
        join_value_type = (storage.get("vector_table_columns") or {}).get(join_column, {}).get("udt_name")
        vector_id_type = storage.get("vector_id_type")
        with conn.cursor() as cur:
            for item in chunks:
                capture_value = _coerce_identifier(item["capture_id"], join_value_type)
                if storage["storage_backend"] == "pgvector":
                    if _is_integer_type(vector_id_type):
                        cur.execute(
                            f"""
                            INSERT INTO memory_vectors ({join_column}, embedding, chunk, chunk_index, last_refreshed_at, expires_at)
                            VALUES (%s, %s::vector, %s, %s, NOW(), %s)
                            RETURNING id
                            """,
                            (
                                capture_value,
                                _vector_literal(item["embedding"]),
                                item["chunk"],
                                item["chunk_index"],
                                item.get("expires_at"),
                            ),
                        )
                    else:
                        chunk_id = item.get("id") or str(uuid.uuid4())
                        cur.execute(
                            f"""
                            INSERT INTO memory_vectors (id, {join_column}, embedding, chunk, chunk_index, last_refreshed_at, expires_at)
                            VALUES (%s, %s, %s::vector, %s, %s, NOW(), %s)
                            RETURNING id
                            """,
                            (
                                chunk_id,
                                capture_value,
                                _vector_literal(item["embedding"]),
                                item["chunk"],
                                item["chunk_index"],
                                item.get("expires_at"),
                            ),
                        )
                else:
                    if _is_integer_type(vector_id_type):
                        cur.execute(
                            f"""
                            INSERT INTO memory_vectors ({join_column}, embedding_json, chunk, chunk_index, last_refreshed_at, expires_at)
                            VALUES (%s, %s, %s, %s, NOW(), %s)
                            RETURNING id
                            """,
                            (
                                capture_value,
                                _json_embedding(item["embedding"]),
                                item["chunk"],
                                item["chunk_index"],
                                item.get("expires_at"),
                            ),
                        )
                    else:
                        chunk_id = item.get("id") or str(uuid.uuid4())
                        cur.execute(
                            f"""
                            INSERT INTO memory_vectors (id, {join_column}, embedding_json, chunk, chunk_index, last_refreshed_at, expires_at)
                            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                            RETURNING id
                            """,
                            (
                                chunk_id,
                                capture_value,
                                _json_embedding(item["embedding"]),
                                item["chunk"],
                                item["chunk_index"],
                                item.get("expires_at"),
                            ),
                        )
                chunk_ids.append(str(cur.fetchone()[0]))
        conn.commit()
    return chunk_ids


def delete_vectors_for_capture(capture_id: str) -> int:
    pool = get_pool()
    with pool.connection() as conn:
        storage = detect_memory_vector_storage(conn)
        join_column = _vector_join_column(storage)
        join_value_type = (storage.get("vector_table_columns") or {}).get(join_column, {}).get("udt_name")
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM memory_vectors WHERE {join_column} = %s",
                (_coerce_identifier(capture_id, join_value_type),),
            )
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


def search_vector_chunks(
    query_embedding: List[float],
    *,
    limit: int = 5,
    source: Optional[str] = None,
    topic: Optional[str] = None,
    min_importance: Optional[int] = None,
) -> List[Dict[str, Any]]:
    where_clauses = ["(mv.expires_at IS NULL OR mv.expires_at > NOW())"]
    params: List[Any] = []

    if source:
        where_clauses.append("kc.source = %s")
        params.append(source)
    if topic:
        where_clauses.append("%s = ANY(kc.topic)")
        params.append(topic)
    if min_importance is not None:
        where_clauses.append("kc.importance >= %s")
        params.append(min_importance)

    pool = get_pool()
    with pool.connection() as conn:
        storage = detect_memory_vector_storage(conn)
        join_condition = _vector_join_condition(storage)
        with conn.cursor(row_factory=dict_row) as cur:
            if storage["storage_backend"] == "pgvector":
                vector = _vector_literal(query_embedding)
                query = f"""
                    SELECT
                        mv.id AS chunk_id,
                        kc.id AS capture_id,
                        mv.chunk_index,
                        mv.chunk,
                        kc.source,
                        kc.topic,
                        kc.importance,
                        kc.markdown_path,
                        kc.metadata,
                        kc.created_at,
                        1 - (mv.embedding <=> %s::vector) AS similarity_score
                    FROM memory_vectors mv
                    JOIN knowledge_capture kc ON {join_condition}
                    WHERE {" AND ".join(where_clauses)}
                    ORDER BY mv.embedding <=> %s::vector, kc.created_at DESC
                    LIMIT %s
                """
                cur.execute(query, (vector, *params, vector, limit))
                rows = cur.fetchall() or []
                return [_hit_from_row(row, float(row.get("similarity_score") or 0.0)) for row in rows]

            scan_limit = max(limit, int(os.getenv("OPEN_BRAIN_SEARCH_SCAN_LIMIT", "5000")))
            query = f"""
                SELECT
                    mv.id AS chunk_id,
                    kc.id AS capture_id,
                    mv.chunk_index,
                    mv.chunk,
                    mv.embedding_json,
                    kc.source,
                    kc.topic,
                    kc.importance,
                    kc.markdown_path,
                    kc.metadata,
                    kc.created_at
                FROM memory_vectors mv
                JOIN knowledge_capture kc ON {join_condition}
                WHERE {" AND ".join(where_clauses)}
                  AND mv.embedding_json IS NOT NULL
                ORDER BY kc.created_at DESC
                LIMIT %s
            """
            cur.execute(query, (*params, scan_limit))
            rows = cur.fetchall() or []

    scored_rows: List[tuple[float, float, Dict[str, Any]]] = []
    for row in rows:
        embedding = _coerce_embedding(row.get("embedding_json"))
        similarity = _cosine_similarity(query_embedding, embedding or [])
        if similarity is None:
            continue
        created_at = row.get("created_at")
        recency = created_at.timestamp() if created_at else 0.0
        scored_rows.append((similarity, recency, _hit_from_row(row, similarity)))

    scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored_rows[:limit]]


def fetch_vector_health() -> Dict[str, Any]:
    pool = get_pool()
    summary: Dict[str, Any] = {
        "database_connected": False,
        "vector_extension": False,
        "embedding_type": None,
        "configured_dimension": None,
        "storage_backend": None,
        "capture_count": 0,
        "vector_count": 0,
        "non_expired_vector_count": 0,
        "sample_hit": None,
    }

    with pool.connection() as conn:
        storage = detect_memory_vector_storage(conn)
        join_condition = _vector_join_condition(storage)
        with conn.cursor(row_factory=dict_row) as cur:
            summary["database_connected"] = True
            summary["vector_extension"] = bool(storage.get("vector_extension"))
            summary["embedding_type"] = storage.get("embedding_type")
            summary["configured_dimension"] = storage.get("configured_dimension")
            summary["storage_backend"] = storage.get("storage_backend")

            cur.execute("SELECT COUNT(*) AS total FROM knowledge_capture")
            row = cur.fetchone() or {}
            summary["capture_count"] = int(row.get("total") or 0)

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE expires_at IS NULL OR expires_at > NOW()) AS non_expired
                FROM memory_vectors
                """
            )
            row = cur.fetchone() or {}
            summary["vector_count"] = int(row.get("total") or 0)
            summary["non_expired_vector_count"] = int(row.get("non_expired") or 0)

            if summary["storage_backend"] == "pgvector" and summary["non_expired_vector_count"] > 0:
                cur.execute(
                    """
                    SELECT embedding::text AS embedding_literal
                    FROM memory_vectors
                    WHERE expires_at IS NULL OR expires_at > NOW()
                    ORDER BY last_refreshed_at DESC NULLS LAST, created_at DESC NULLS LAST
                    LIMIT 1
                    """
                )
                row = cur.fetchone() or {}
                embedding_literal = row.get("embedding_literal")
                if embedding_literal:
                    cur.execute(
                        f"""
                        SELECT
                            mv.id AS chunk_id,
                            kc.id AS capture_id,
                            mv.chunk_index,
                            mv.chunk,
                            kc.source,
                            kc.topic,
                            kc.importance,
                            kc.markdown_path,
                            kc.metadata,
                            kc.created_at,
                            1 - (mv.embedding <=> %s::vector) AS similarity_score
                        FROM memory_vectors mv
                        JOIN knowledge_capture kc ON {join_condition}
                        WHERE mv.expires_at IS NULL OR mv.expires_at > NOW()
                        ORDER BY mv.embedding <=> %s::vector, kc.created_at DESC
                        LIMIT 1
                        """,
                        (embedding_literal, embedding_literal),
                    )
                    row = cur.fetchone() or {}
                    if row:
                        summary["sample_hit"] = {
                            "chunk_id": str(row["chunk_id"]),
                            "capture_id": str(row["capture_id"]),
                            "chunk_index": int(row.get("chunk_index") or 0),
                            "chunk": row.get("chunk") or "",
                            "similarity_score": float(row.get("similarity_score") or 0.0),
                            "source": row.get("source"),
                            "topics": row.get("topic") or [],
                            "importance": int(row.get("importance") or 0),
                            "markdown_path": row.get("markdown_path"),
                            "created_at": row.get("created_at"),
                            "metadata": row.get("metadata") or {},
                        }
            elif summary["storage_backend"] == "jsonb" and summary["non_expired_vector_count"] > 0:
                cur.execute(
                    f"""
                    SELECT
                        mv.id AS chunk_id,
                        kc.id AS capture_id,
                        mv.chunk_index,
                        mv.chunk,
                        mv.embedding_json,
                        kc.source,
                        kc.topic,
                        kc.importance,
                        kc.markdown_path,
                        kc.metadata,
                        kc.created_at
                    FROM memory_vectors mv
                    JOIN knowledge_capture kc ON {join_condition}
                    WHERE (mv.expires_at IS NULL OR mv.expires_at > NOW())
                      AND mv.embedding_json IS NOT NULL
                    ORDER BY mv.last_refreshed_at DESC NULLS LAST, kc.created_at DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone() or {}
                embedding = _coerce_embedding(row.get("embedding_json"))
                if row and embedding:
                    summary["configured_dimension"] = len(embedding)
                    summary["sample_hit"] = _hit_from_row(row, 1.0)

    return summary
