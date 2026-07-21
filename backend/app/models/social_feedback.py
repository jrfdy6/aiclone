from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class SocialFeedbackCreate(BaseModel):
    feed_item_id: str
    title: str
    platform: str
    decision: Literal["like", "dislike", "copy", "approve", "reject"]
    lens: Optional[str] = None
    notes: Optional[str] = None
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    stance: Optional[str] = None
    belief_used: Optional[str] = None
    experience_anchor: Optional[str] = None
    techniques: list[str] = []
    evaluation_overall: Optional[float] = None
    source_expression_quality: Optional[float] = None
    output_expression_quality: Optional[float] = None
    expression_delta: Optional[float] = None
    why_this_angle: Optional[str] = None
