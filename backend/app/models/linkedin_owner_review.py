from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LinkedinOwnerReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "revise", "park"]
    notes: str | None = None
