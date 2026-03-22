from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DailyBrief(BaseModel):
    id: str
    brief_date: date
    title: str
    summary: Optional[str] = None
    content_markdown: str
    source: str
    source_ref: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
