from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException, Response

from app.models import DailyBrief, DailyBriefSyncRequest
from app.services import daily_brief_service

router = APIRouter(tags=["Daily Briefs"], prefix="/api/briefs")
LOGGER = logging.getLogger(__name__)


def _read_timeout_setting() -> float:
    try:
        value = float(os.getenv("BRAIN_BRIEFS_READ_TIMEOUT_SECONDS", "5.0"))
    except (TypeError, ValueError):
        value = 5.0
    return max(0.1, min(10.0, value))


BRAIN_BRIEFS_READ_TIMEOUT_SECONDS = _read_timeout_setting()


@router.get("", response_model=List[DailyBrief], include_in_schema=False)
@router.get("/", response_model=List[DailyBrief])
async def list_daily_briefs(response: Response, limit: int = 50):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    bounded_limit = max(1, min(int(limit or 50), 100))
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(daily_brief_service.list_daily_briefs, limit=bounded_limit),
            timeout=BRAIN_BRIEFS_READ_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Daily brief read timed out.") from exc


@router.post("/sync")
def sync_daily_briefs(payload: DailyBriefSyncRequest):
    try:
        synced = daily_brief_service.sync_daily_briefs_from_markdown(
            payload.raw_markdown,
            source=payload.source,
            source_ref=payload.source_ref,
            metadata=payload.metadata,
            expected_latest_brief_date=payload.expected_latest_brief_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.exception("Daily brief sync failed")
        raise HTTPException(status_code=500, detail="Daily brief sync failed.") from exc

    return {
        "message": "Daily briefs synced.",
        "count": len(synced),
        "latest_brief_date": synced[0].brief_date.isoformat() if synced else None,
    }
