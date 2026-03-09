from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Query

from app.models import CaptureRequest, CaptureResponse
from app.services import capture_service, refresh_service

router = APIRouter(tags=["Capture"])


@router.post("/", response_model=CaptureResponse)
async def ingest_capture(payload: CaptureRequest):
    try:
        result = capture_service.create_capture(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/refresh")
async def refresh_captures(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    x_cron_token: str | None = Header(default=None, convert_underscores=False),
):
    expected = os.getenv("CRON_ACCESS_TOKEN")
    if expected and x_cron_token != expected:
        raise HTTPException(status_code=401, detail="Invalid cron token")

    deleted = refresh_service.delete_expired_vectors()
    refreshed = refresh_service.refresh_recent_captures(hours=hours, limit=limit)
    return {"deleted_chunks": deleted, **refreshed}
