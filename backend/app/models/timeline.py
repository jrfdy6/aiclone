from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    id: str
    type: str
    title: str
    occurred_at: datetime
    source: str
    payload: dict = Field(default_factory=dict)
