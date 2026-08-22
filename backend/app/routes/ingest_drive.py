from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status

from app.models import IngestJob, IngestRequest, KnowledgeDoc
from app.services import firestore_client
from app.services.drive_client import DriveConfigurationError, DriveFile, get_drive_client

router = APIRouter(tags=["Ingestion"])
logger = logging.getLogger(__name__)

FIRESTORE_STATE_HEADER = "X-AI-Clone-Firestore-State"
DATA_AUTHORITY_HEADER = "X-AI-Clone-Data-Authority"
DRIVE_STATE_HEADER = "X-AI-Clone-Drive-State"


def _compact_summary(text: str, *, limit: int = 1_000) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _knowledge_projection(file: DriveFile, text: str, tags: list[str]) -> KnowledgeDoc:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    mime_tag = str(file.mime_type or "unknown").replace("/", ":")
    return KnowledgeDoc(
        id=f"drive-{file.id}",
        title=file.name,
        summary=_compact_summary(text),
        tags=list(dict.fromkeys([*tags, "google_drive", mime_tag])),
        source_path=f"https://drive.google.com/open?id={file.id}",
        origin="google_drive",
        external_id=file.id,
        content_hash=content_hash,
        updated_at=datetime.now(timezone.utc),
    )


@router.post("/ingest/drive", response_model=IngestJob)
async def ingest_drive(request: IngestRequest, response: Response):
    job = IngestJob(id=str(uuid.uuid4()), folder_id=request.folder_id, target_collection=request.target_collection)

    try:
        drive = get_drive_client()
        files = drive.list_files(request.folder_id, page_size=request.max_files)[: request.max_files]
    except DriveConfigurationError as exc:
        logger.warning("Drive ingestion is not configured [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["drive_unavailable"],
                "message": "Drive ingestion is unavailable because its read-only connector is not configured.",
            },
        ) from exc
    except Exception as exc:
        logger.warning("Drive folder listing failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["drive_read_failed"],
                "message": "The Drive folder could not be read.",
            },
        ) from exc

    if request.dry_run:
        job.processed = len(files)
        job.status = "dry_run"
        response.headers[FIRESTORE_STATE_HEADER] = "not_written"
        response.headers[DRIVE_STATE_HEADER] = "ready"
        response.headers[DATA_AUTHORITY_HEADER] = "firestore:knowledge_docs"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return job

    client = firestore_client.get_firestore_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["firestore_unavailable"],
                "message": "Drive ingestion is unavailable because its canonical store is not ready.",
            },
        )

    docs: list[KnowledgeDoc] = []
    for index, file in enumerate(files):
        try:
            text = drive.extract_text(file)
        except Exception as exc:
            logger.warning("Drive file extraction failed index=%s [%s]", index, type(exc).__name__)
            job.errors.append(f"extract_failed:{index}")
            continue
        if not str(text or "").strip():
            job.errors.append(f"unsupported_or_empty:{index}")
            continue
        docs.append(_knowledge_projection(file, text, request.tags))

    try:
        batch = client.batch()
        for doc in docs:
            # target_collection is a Literal allowlist and cannot create a new
            # collection authority from request-controlled input.
            ref = client.collection("knowledge_docs").document(doc.id)
            batch.set(ref, doc.model_dump())
        batch.commit()
    except Exception as exc:
        logger.warning("Drive ingestion Firestore commit failed [%s]", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["firestore_write_failed"],
                "message": "Drive ingestion could not commit to its canonical store.",
            },
        ) from exc

    job.processed = len(docs)
    if job.errors and docs:
        job.status = "completed_with_errors"
        firestore_state = "degraded"
    elif job.errors:
        job.status = "no_change"
        firestore_state = "degraded"
    elif not docs:
        job.status = "no_change"
        firestore_state = "ready"
    else:
        job.status = "completed"
        firestore_state = "ready"
    job.completed_at = datetime.now(timezone.utc)
    response.headers[FIRESTORE_STATE_HEADER] = firestore_state
    response.headers[DRIVE_STATE_HEADER] = "ready"
    response.headers[DATA_AUTHORITY_HEADER] = "firestore:knowledge_docs"
    if job.errors:
        response.headers["X-AI-Clone-Degraded-Reasons"] = "drive_file_extraction_incomplete"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return job
