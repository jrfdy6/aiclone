from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonaDelta(BaseModel):
    id: str
    capture_id: Optional[str] = None
    persona_target: str
    trait: str
    notes: Optional[str] = None
    status: str = "draft"
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    committed_at: Optional[datetime] = None


class PersonaDeltaCreate(BaseModel):
    capture_id: Optional[str] = None
    persona_target: str
    trait: str
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class PersonaDeltaUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[dict] = None


class PersonaDeltaResolve(BaseModel):
    resolution_capture_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    status: str = "resolved"
