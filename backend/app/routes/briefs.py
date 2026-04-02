from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Response

from app.models import DailyBrief, DailyBriefSyncRequest
from app.services import daily_brief_service

router = APIRouter(tags=["Daily Briefs"], prefix="/api/briefs")


@router.get("", response_model=List[DailyBrief], include_in_schema=False)
@router.get("/", response_model=List[DailyBrief])
async def list_daily_briefs(response: Response, limit: int = 50):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return daily_brief_service.list_daily_briefs(limit=limit)


@router.post("/sync")
async def sync_daily_briefs(payload: DailyBriefSyncRequest):
    try:
        synced = daily_brief_service.sync_daily_briefs_from_markdown(
            payload.raw_markdown,
            source=payload.source,
            source_ref=payload.source_ref,
            metadata=payload.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Daily briefs synced.",
        "count": len(synced),
        "latest_brief_date": synced[0].brief_date.isoformat() if synced else None,
    }
