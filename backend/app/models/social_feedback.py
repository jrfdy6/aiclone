from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class SocialFeedbackCreate(BaseModel):
    feed_item_id: str
    title: str
    platform: str
    decision: Literal["like", "dislike"]
    lens: Optional[str] = None
    notes: Optional[str] = None
