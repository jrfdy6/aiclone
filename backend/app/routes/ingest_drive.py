import traceback
import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.drive_client import DriveConfigurationError, DriveFile, get_drive_client
from app.services.embedders import embed_texts
from app.services.memory_service import log_ingest_job, save_chunk
from app.utils.chunker import chunk_text


router = APIRouter()


drive_client = None


class DriveIngestRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    folder_id: str = Field(..., description="Google Drive folder ID to ingest")
    max_files: int | None = Field(
        default=None,
        ge=1,
        description="Optional cap on number of files to ingest from the folder",
    )


def _get_drive_client():
    global drive_client
    if drive_client is None:
        drive_client = get_drive_client()
    return drive_client


def _base_metadata(user_id: str, folder_id: str, file: DriveFile) -> Dict:
    return {
        "source": file.name,
        "source_type": file.mime_type,
        "source_id": file.id,
        "file_name": file.name,
        "file_type": file.mime_type,
        "upload_timestamp": None,
        "folder_id": folder_id,
        "user_id": user_id,
    }


@router.post("/ingest_drive")
async def ingest_drive_folder(req: DriveIngestRequest):
    try:
        client = _get_drive_client()
        files = client.list_files(req.folder_id)
    except DriveConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        if not files:
            return {
                "success": True,
                "files_ingested": 0,
                "message": "No files found in the specified folder.",
            }

        if req.max_files is not None:
            files = files[: req.max_files]

        ingest_job_id = f"gdrive_{uuid.uuid4().hex}"
        total_chunks = 0
        processed_files: List[Dict] = []

        for drive_file in files:
            try:
                text_content = client.extract_text(drive_file)
            except RuntimeError as exc:
                print(f"Failed to extract text for file {drive_file.id}: {exc}", flush=True)
                traceback.print_exc()
                continue

            if not text_content or not text_content.strip():
                continue

            chunks = chunk_text(text_content)
            if not chunks:
                continue

            embeddings = embed_texts(chunks)
            base_metadata = _base_metadata(req.user_id, req.folder_id, drive_file)

            for idx, (chunk_text_value, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": idx,
                }
                save_chunk(
                    user_id=req.user_id,
                    text=chunk_text_value,
                    embedding=embedding,
                    metadata=chunk_metadata,
                    tags=chunk_metadata.get("extra_tags"),
                )
                total_chunks += 1

            processed_files.append({"file_id": drive_file.id, "file_name": drive_file.name})

        log_ingest_job(
            user_id=req.user_id,
            job_id=ingest_job_id,
            status="completed",
            filename=f"Drive folder {req.folder_id}",
            chunk_count=total_chunks,
            metadata={"folder_id": req.folder_id, "files": processed_files},
        )

        return {
            "success": True,
            "files_ingested": len(processed_files),
            "chunks_created": total_chunks,
            "ingest_job_id": ingest_job_id,
            "message": "Drive folder ingested successfully.",
        }
    except Exception as exc:
        print("Unexpected Drive ingestion error:", exc, flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Drive ingestion failed.") from exc
