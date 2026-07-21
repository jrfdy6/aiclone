from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class RefreshSocialFeedRequest(BaseModel):
    skip_fetch: bool = False
    sources: Literal["safe", "all"] = "safe"


class IngestSignalRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    title: str | None = None
    priority_lane: str = "custom"
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_content(self) -> "IngestSignalRequest":
        if not (self.url or self.text):
            raise ValueError("Provide url or text.")
        return self
