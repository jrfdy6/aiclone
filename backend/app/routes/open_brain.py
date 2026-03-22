from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import OpenBrainHealth, OpenBrainSearchRequest, OpenBrainSearchResponse
from app.services import open_brain_service

router = APIRouter(tags=["Open Brain"], prefix="/api/open-brain")


@router.post("/search", response_model=OpenBrainSearchResponse)
async def search_open_brain(payload: OpenBrainSearchRequest):
    try:
        return open_brain_service.search_memory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health", response_model=OpenBrainHealth)
async def open_brain_health():
    return open_brain_service.fetch_health()
