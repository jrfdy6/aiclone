from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from app.services.brain_docs_service import list_brain_docs, read_brain_doc
from app.services.brain_response_privacy_service import sanitize_brain_payload


router = APIRouter(tags=["Brain Docs"], prefix="/api/brain/docs")


@router.get("")
async def get_brain_docs(response: Response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        payload = await run_in_threadpool(list_brain_docs)
        return sanitize_brain_payload(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain document index is temporarily unavailable.") from exc


@router.get("/content")
async def get_brain_doc_content(response: Response, path: str = Query(..., min_length=1)):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        doc = await run_in_threadpool(read_brain_doc, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Brain document content is temporarily unavailable.") from exc
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return sanitize_brain_payload(doc)
