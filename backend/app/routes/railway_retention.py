from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool

from app.services.railway_retention_status_service import (
    build_retention_status,
    degraded_retention_status,
    retention_status_is_sanitized,
)


router = APIRouter(prefix="/api/system", tags=["System Health"])


@router.get("/railway-retention")
async def railway_retention_status(response: Response) -> dict:
    receipt = await run_in_threadpool(build_retention_status)
    if not retention_status_is_sanitized(receipt):  # pragma: no cover - defensive projection guard.
        receipt = degraded_retention_status("retention_projection_failed")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-AI-Clone-Retention-State"] = str(receipt["state"])
    return receipt
