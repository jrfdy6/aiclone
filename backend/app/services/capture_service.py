from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Tuple

from app.models.core import CaptureRequest, CaptureResponse
from app.services import embedders
from app.services import open_brain_repository as repo
from app.utils.ai_clone_clock import as_utc, utc_now

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


def _chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    chunks: List[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks or [normalized]


def _compute_expiry(
    importance: int,
    expires_in_hours: int | None,
    *,
    observed_at: datetime,
) -> datetime | None:
    observation = as_utc(observed_at)
    if expires_in_hours:
        return observation + timedelta(hours=expires_in_hours)
    if importance <= 1:
        return observation + timedelta(days=1)
    if importance == 2:
        return observation + timedelta(days=7)
    return None


def build_chunk_records(
    *,
    capture_id: str,
    text: str,
    importance: int,
    expires_in_hours: int | None = None,
    observed_at: datetime | None = None,
    canonical_expires_at: datetime | None = None,
    preserve_canonical_expiry: bool = False,
) -> Tuple[List[dict], datetime | None]:
    observation = as_utc(observed_at) if observed_at is not None else utc_now()
    chunks = _chunk_text(text)
    embeddings = embedders.embed_texts(chunks)
    if preserve_canonical_expiry:
        expires_at = (
            as_utc(canonical_expires_at)
            if canonical_expires_at is not None
            else None
        )
    else:
        expires_at = _compute_expiry(
            importance,
            expires_in_hours,
            observed_at=observation,
        )

    records = []
    for index, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        records.append(
            {
                "capture_id": capture_id,
                "chunk": chunk_text,
                "chunk_index": index,
                "embedding": embedding,
                "expires_at": expires_at,
            }
        )
    return records, expires_at


def create_capture(
    payload: CaptureRequest,
    *,
    observed_at: datetime | None = None,
) -> CaptureResponse:
    if not payload.text or not payload.text.strip():
        raise ValueError("Capture text is required")

    observation = as_utc(observed_at) if observed_at is not None else utc_now()

    capture_id, reused_capture = repo.upsert_capture(
        source=payload.source,
        topics=payload.topics,
        importance=payload.importance,
        raw_text=payload.text.strip(),
        markdown_path=payload.markdown_path,
        metadata=payload.metadata,
    )

    if reused_capture:
        repo.delete_vectors_for_capture(capture_id)

    chunk_records, expires_at = build_chunk_records(
        capture_id=capture_id,
        text=payload.text,
        importance=payload.importance,
        expires_in_hours=payload.expires_in_hours,
        observed_at=observation,
    )

    chunk_ids = repo.insert_vector_chunks(chunk_records)

    return CaptureResponse(
        capture_id=capture_id,
        chunk_ids=chunk_ids,
        chunk_count=len(chunk_ids),
        expires_at=expires_at,
    )
