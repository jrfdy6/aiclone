from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from app.services import capture_service
from app.services import open_brain_repository as repo


def delete_expired_vectors() -> int:
    return repo.delete_expired_vectors()


def refresh_recent_captures(hours: int = 24, limit: int = 50) -> Dict[str, int]:
    threshold = datetime.utcnow() - timedelta(hours=hours)
    captures = repo.fetch_captures_updated_since(threshold, limit)

    refreshed = 0
    chunk_total = 0

    for capture in captures:
        capture_id = capture["id"]
        repo.delete_vectors_for_capture(capture_id)
        records, _ = capture_service.build_chunk_records(
            capture_id=capture_id,
            text=capture["raw_text"],
            importance=capture["importance"],
        )
        repo.insert_vector_chunks(records)
        refreshed += 1
        chunk_total += len(records)

    return {"captures": refreshed, "chunks": chunk_total}
