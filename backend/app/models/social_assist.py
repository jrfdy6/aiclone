from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SocialEngagementOpportunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(..., min_length=1, max_length=32)
    source_url: str = Field(..., min_length=1, max_length=2_048)
    visible_text: str = Field(..., min_length=1, max_length=20_000)
    draft_text: str = Field(..., min_length=1, max_length=10_000)
    engagement_type: str = Field(..., min_length=1, max_length=32)
    title: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=300)
    idempotency_key: str | None = Field(default=None, max_length=200)


class SocialEngagementActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., min_length=1, max_length=64)
    request_id: str | None = Field(default=None, max_length=200)
