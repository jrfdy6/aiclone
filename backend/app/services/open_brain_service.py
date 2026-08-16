from __future__ import annotations

import re

from app.models import OpenBrainHealth, OpenBrainSearchHit, OpenBrainSearchRequest, OpenBrainSearchResponse
from app.services.embedders import VECTOR_DIM, embed_text
from app.services.open_brain_repository import fetch_vector_health, search_vector_chunks


def search_memory(payload: OpenBrainSearchRequest) -> OpenBrainSearchResponse:
    query = payload.query.strip()
    if not query:
        raise ValueError("Query cannot be empty")

    query_embedding = embed_text(query)
    rows = search_vector_chunks(
        query_embedding,
        limit=payload.top_k,
        source=payload.source,
        topic=payload.topic,
        min_importance=payload.min_importance,
    )
    return OpenBrainSearchResponse(
        query=query,
        results=[OpenBrainSearchHit(**row) for row in rows],
    )


def fetch_health() -> OpenBrainHealth:
    try:
        payload = fetch_vector_health()
    except Exception:
        return OpenBrainHealth(embedder_dimension=VECTOR_DIM)

    embedding_type = payload.get("embedding_type")
    configured_dimension = payload.get("configured_dimension")
    if configured_dimension is None:
        configured_dimension = _parse_vector_dimension(embedding_type)
    sample_hit = payload.get("sample_hit")

    return OpenBrainHealth(
        database_connected=bool(payload.get("database_connected")),
        vector_extension=bool(payload.get("vector_extension")),
        embedding_type=embedding_type,
        configured_dimension=configured_dimension,
        storage_backend=payload.get("storage_backend"),
        embedder_dimension=VECTOR_DIM,
        dimension_match=configured_dimension == VECTOR_DIM,
        capture_count=int(payload.get("capture_count") or 0),
        vector_count=int(payload.get("vector_count") or 0),
        non_expired_vector_count=int(payload.get("non_expired_vector_count") or 0),
        search_ready=bool(sample_hit),
        sample_hit=OpenBrainSearchHit(**sample_hit) if sample_hit else None,
    )


def _parse_vector_dimension(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"vector\((\d+)\)", value)
    if not match:
        return None
    return int(match.group(1))
