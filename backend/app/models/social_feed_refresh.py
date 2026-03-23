from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, root_validator


class RefreshSocialFeedRequest(BaseModel):
    skip_fetch: bool = False
    sources: Literal["safe", "all"] = "safe"


class IngestSignalRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    title: str | None = None
    priority_lane: str = "custom"
    run_refresh: bool = True

    @root_validator
    def ensure_content(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not (values.get("url") or values.get("text")):
            raise ValueError("Provide url or text.")
        return values
