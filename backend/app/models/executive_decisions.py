from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ExecutiveDecisionSourceType = Literal[
    "pm",
    "workspace_review",
    "brain_signal",
    "persona",
    "email",
    "standup",
    "system_exception",
]
ExecutiveDecisionPriority = Literal["critical", "high", "medium", "low"]
ExecutiveDecisionFreshness = Literal["today", "recent", "aging", "stale", "unknown"]
ExecutiveDecisionSourceState = Literal["ok", "degraded", "error"]
ExecutiveDecisionActionKind = Literal["open_context", "delegate"]


class ExecutiveDecisionAction(BaseModel):
    id: str
    label: str
    kind: ExecutiveDecisionActionKind
    method: Literal["GET", "POST"]
    href: str
    source_href: str | None = None
    requires_confirmation: bool = False
    requires_note: bool = False


class ExecutiveDecision(BaseModel):
    id: str
    dedupe_key: str
    source_type: ExecutiveDecisionSourceType
    source_id: str
    workspace_key: str = "shared_ops"
    title: str
    what_changed: str
    why_it_matters: str
    recommendation: str
    priority: ExecutiveDecisionPriority
    priority_score: int = Field(ge=0, le=100)
    freshness: ExecutiveDecisionFreshness
    updated_at: datetime | None = None
    evidence: list[str] = Field(default_factory=list)
    context_href: str
    actions: list[ExecutiveDecisionAction] = Field(default_factory=list)


class ExecutiveDecisionSourceError(BaseModel):
    source_type: ExecutiveDecisionSourceType
    message: str


class ExecutiveDecisionSummary(BaseModel):
    total_pending: int = 0
    today_count: int = 0
    today_candidate_count: int = 0
    priority_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    verification_status: Literal["verified", "partial"] = "verified"
    verified_clear: bool = False


class ExecutiveDecisionQueue(BaseModel):
    generated_at: datetime
    summary: ExecutiveDecisionSummary
    source_status: dict[str, ExecutiveDecisionSourceState] = Field(default_factory=dict)
    source_errors: list[ExecutiveDecisionSourceError] = Field(default_factory=list)
    today: list[ExecutiveDecision] = Field(default_factory=list)
    all_pending: list[ExecutiveDecision] = Field(default_factory=list)


class ExecutiveDecisionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: Literal[True]
    notes: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=4000)


class ExecutiveDecisionActionResult(BaseModel):
    status: Literal["completed", "open_context"]
    decision_id: str
    action_id: str
    source_type: ExecutiveDecisionSourceType
    source_id: str
    message: str
    result: dict[str, Any] = Field(default_factory=dict)
