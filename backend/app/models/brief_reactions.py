from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .persona import PersonaDelta


class BriefReactionPersonaContext(BaseModel):
    delta_id: str
    trait: str
    response_kind: Optional[str] = None
    excerpt: Optional[str] = None
    target_file: Optional[str] = None
    review_source: Optional[str] = None
    created_at: Optional[datetime] = None


class BriefReaction(BaseModel):
    id: str
    brief_id: str
    item_key: str
    item_title: str
    reaction_kind: Literal["agree", "disagree", "nuance", "story"]
    text: str
    source_kind: Optional[str] = None
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    linked_delta_id: Optional[str] = None
    linked_capture_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class BriefReactionCreate(BaseModel):
    brief_id: str
    item_key: str
    item_title: str
    item_summary: Optional[str] = None
    item_hook: Optional[str] = None
    source_kind: Optional[str] = None
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    priority_lane: Optional[str] = None
    route_reason: Optional[str] = None
    target_file: Optional[str] = None
    reaction_kind: Literal["agree", "disagree", "nuance", "story"]
    text: str
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_required_fields(self) -> "BriefReactionCreate":
        if not (self.brief_id or "").strip():
            raise ValueError("Provide brief_id.")
        if not (self.item_key or "").strip():
            raise ValueError("Provide item_key.")
        if not (self.item_title or "").strip():
            raise ValueError("Provide item_title.")
        if not (self.text or "").strip():
            raise ValueError("Provide text.")
        return self


class BriefReactionCreateResponse(BaseModel):
    reaction: BriefReaction
    delta: PersonaDelta
    capture_id: Optional[str] = None
