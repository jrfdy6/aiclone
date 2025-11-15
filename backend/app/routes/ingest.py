import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.embedders import embed_texts
from app.services.memory_service import log_ingest_job, save_chunk
from app.services.parsers import pdf_parser, pptx_parser
from app.utils.chunker import chunk_text


router = APIRouter()


SUPPORTED_TEXT_TYPES = {"text/plain", "application/json"}


def _load_metadata(metadata_raw: Optional[str]) -> Dict[str, Any]:
    if not metadata_raw:
        return {}
    try:
        return json.loads(metadata_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc


def _extract_text(
    temp_path: Path,
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str],
    source_type: str,
) -> str:
    suffix = Path(filename).suffix.lower()

    if source_type == "pdf" or suffix == ".pdf" or content_type == "application/pdf":
        return pdf_parser.extract_text_from_pdf(temp_path)
    if source_type in {"pptx", "slides"} or suffix in {".ppt", ".pptx"}:
        return pptx_parser.extract_text_from_pptx(temp_path)
    if content_type in SUPPORTED_TEXT_TYPES:
        return file_bytes.decode("utf-8", errors="ignore")

    # Fallback: attempt utf-8 decode
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Unsupported file type for ingestion.")


def _build_base_metadata(
    user_id: str,
    filename: str,
    source_type: str,
    extra_metadata: Dict[str, Any],
    ingest_job_id: str,
    file_id: str,
) -> Dict[str, Any]:
    timestamp = datetime.utcnow().isoformat() + "Z"
    metadata = {
        "source": filename,
        "source_type": source_type,
        "source_id": file_id,
        "file_name": filename,
        "file_type": source_type,
        "upload_timestamp": timestamp,
        "ingest_job_id": ingest_job_id,
        **extra_metadata,
    }
    metadata.setdefault("extra_tags", extra_metadata.get("extra_tags", []))
    metadata.setdefault("topic", extra_metadata.get("topic"))
    metadata.setdefault("user_id", user_id)
    return metadata


@router.post("/upload")
async def upload_file(
    user_id: str = Form(...),
    source_type: str = Form("unknown"),
    metadata: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extra_metadata = _load_metadata(metadata)

    fd, tmp_path_str = tempfile.mkstemp(suffix=Path(file.filename or "").suffix)
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(file_bytes)

        text = _extract_text(
            tmp_path,
            file_bytes,
            file.filename or "upload",
            file.content_type,
            source_type,
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No textual content could be extracted from the file.")

    embeddings = embed_texts(chunks)
    ingest_job_id = f"ingest_{uuid.uuid4().hex}"
    file_id = f"file_{uuid.uuid4().hex}"

    base_metadata = _build_base_metadata(
        user_id=user_id,
        filename=file.filename or "upload",
        source_type=source_type,
        extra_metadata=extra_metadata,
        ingest_job_id=ingest_job_id,
        file_id=file_id,
    )

    saved_chunk_ids: List[str] = []
    for idx, (chunk_text_value, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_metadata = {
            **base_metadata,
            "chunk_index": idx,
        }
        chunk_id = save_chunk(
            user_id=user_id,
            text=chunk_text_value,
            embedding=embedding,
            metadata=chunk_metadata,
            tags=chunk_metadata.get("extra_tags"),
        )
        saved_chunk_ids.append(chunk_id)

    log_ingest_job(
        user_id=user_id,
        job_id=ingest_job_id,
        status="completed",
        filename=file.filename or "upload",
        chunk_count=len(saved_chunk_ids),
        metadata={"file_id": file_id, "source_type": source_type},
    )

    return {
        "success": True,
        "file_id": file_id,
        "chunks_created": len(saved_chunk_ids),
        "ingest_job_id": ingest_job_id,
        "message": "File successfully ingested and embedded.",
    }
