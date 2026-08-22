from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool

from app.services.firestore_readiness_service import (
    check_firestore_readiness,
    degraded_readiness_receipt,
    receipt_is_sanitized,
)


router = APIRouter(prefix="/api/system", tags=["System Health"])


@router.get("/firestore-readiness")
async def firestore_readiness(response: Response) -> dict:
    receipt = await run_in_threadpool(check_firestore_readiness)
    if not receipt_is_sanitized(receipt):  # pragma: no cover - defensive projection guard.
        receipt = degraded_readiness_receipt("firestore_readiness_projection_rejected")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-AI-Clone-Firestore-State"] = str(receipt["state"])
    return receipt
