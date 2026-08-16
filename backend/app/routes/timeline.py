from __future__ import annotations

from typing import List

from fastapi import APIRouter

from app.models import TimelineEvent
from app.services import timeline_service

router = APIRouter(tags=["Timeline"], prefix="/api/timeline")


@router.get("/", response_model=List[TimelineEvent])
async def list_timeline(limit: int = 50):
    return timeline_service.list_events(limit=limit)
