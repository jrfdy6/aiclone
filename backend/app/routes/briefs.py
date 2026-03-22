from __future__ import annotations

from typing import List

from fastapi import APIRouter

from app.models import DailyBrief
from app.services import daily_brief_service

router = APIRouter(tags=["Daily Briefs"], prefix="/api/briefs")


@router.get("", response_model=List[DailyBrief], include_in_schema=False)
@router.get("/", response_model=List[DailyBrief])
async def list_daily_briefs(limit: int = 50):
    return daily_brief_service.list_daily_briefs(limit=limit)
