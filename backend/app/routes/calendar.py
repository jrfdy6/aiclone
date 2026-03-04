from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter

from app.models import CalendarEvent

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/upcoming", response_model=List[CalendarEvent])
async def list_upcoming(window_hours: int = 48):
    now = datetime.utcnow()
    events = [
        CalendarEvent(
            id="daily-briefing",
            title="Daily Briefing Review",
            start=now + timedelta(hours=2),
            end=now + timedelta(hours=3),
            attendees=["feeze"],
        ),
        CalendarEvent(
            id="prospect-check-in",
            title="Prospect Pipeline Sync",
            start=now + timedelta(hours=6),
            end=now + timedelta(hours=6, minutes=30),
            attendees=["feeze", "neo"],
        ),
    ]
    upper = now + timedelta(hours=window_hours)
    return [event for event in events if event.start <= upper]
