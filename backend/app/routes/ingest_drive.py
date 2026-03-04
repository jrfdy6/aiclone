from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.models import IngestJob, IngestRequest
from app.services import firestore_client
from app.services.local_store import load_local_knowledge

router = APIRouter(tags=["Ingestion"])


@router.post("/ingest/drive", response_model=IngestJob)
async def ingest_drive(request: IngestRequest):
    job = IngestJob(id=str(uuid.uuid4()), folder_id=request.folder_id, target_collection=request.target_collection)

    docs = load_local_knowledge()
    job.processed = len(docs)
    job.status = "completed" if not request.dry_run else "dry_run"

    client = firestore_client.get_firestore_client()
    if client is not None and not request.dry_run:
        batch = client.batch()
        for doc in docs:
            ref = client.collection(job.target_collection).document(doc.id)
            batch.set(ref, doc.model_dump())
        batch.commit()

    return job
