import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.firestore_client import db


def save_chunk(
    user_id: str,
    text: str,
    embedding: List[float],
    metadata: Dict[str, Any],
    tags: Optional[List[str]] = None,
) -> str:
    collection = db.collection("users").document(user_id).collection("memory_chunks")
    chunk_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    document = {
        "text": text,
        "embedding": embedding,
        "source": metadata.get("source"),
        "source_type": metadata.get("source_type"),
        "source_id": metadata.get("source_id"),
        "chunk_index": metadata.get("chunk_index"),
        "language": metadata.get("language", "en"),
        "created_at": metadata.get("upload_timestamp", now),
        "ingest_job_id": metadata.get("ingest_job_id"),
        "confidence": metadata.get("confidence", 1.0),
        "tags": tags or [],
        "metadata": metadata,
    }
    collection.document(chunk_id).set(document)
    return chunk_id


def log_ingest_job(
    user_id: str,
    job_id: str,
    status: str,
    filename: str,
    chunk_count: Optional[int] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    collection = db.collection("users").document(user_id).collection("ingest_jobs")
    payload: Dict[str, Any] = {
        "status": status,
        "filename": filename,
        "notes": notes,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    if chunk_count is not None:
        payload["chunk_count"] = chunk_count
    if metadata:
        payload["metadata"] = metadata

    collection.document(job_id).set(payload, merge=True)
