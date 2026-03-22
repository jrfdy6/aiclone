from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionTotals(BaseModel):
    total_tokens: int = 0
    active_agents: int = 0
    models_deployed: int = 0
    errors_24h: int = 0


class ModelDistributionBucket(BaseModel):
    model: str
    tokens: int = 0


class SessionRow(BaseModel):
    id: str
    agent_name: str
    model: Optional[str] = None
    status: str = "active"
    total_tokens: int = 0
    last_message_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class SessionMetrics(BaseModel):
    totals: SessionTotals = Field(default_factory=SessionTotals)
    model_distribution: List[ModelDistributionBucket] = Field(default_factory=list)
    top_sessions: List[SessionRow] = Field(default_factory=list)
    sessions: List[SessionRow] = Field(default_factory=list)
