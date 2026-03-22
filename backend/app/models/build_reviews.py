from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BuildReview(BaseModel):
    id: str
    title: str
    status: str = "pending"
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    ingestion_path: Optional[str] = None
    summary: Optional[str] = None
    why_showing: Optional[str] = None
    decision: Optional[str] = None
    response_notes: Optional[str] = None
    resolution_capture_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class BuildReviewUpsert(BaseModel):
    id: Optional[str] = None
    title: str
    status: str = "pending"
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    ingestion_path: Optional[str] = None
    summary: Optional[str] = None
    why_showing: Optional[str] = None
    decision: Optional[str] = None
    response_notes: Optional[str] = None
    resolution_capture_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)


class BuildReviewUpdate(BaseModel):
    status: Optional[str] = None
    decision: Optional[str] = None
    response_notes: Optional[str] = None
    resolution_capture_id: Optional[str] = None
    payload: Optional[dict] = None
