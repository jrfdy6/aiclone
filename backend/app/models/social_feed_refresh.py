from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RefreshSocialFeedRequest(BaseModel):
    skip_fetch: bool = False
    sources: Literal["safe", "all"] = "safe"
