from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


OWNER_DAY_STATUSES = (
    "Open / Not reviewed", "In progress", "Needs decision", "Waiting on someone else",
    "Blocked", "Completed", "Deferred until date", "Deferred until trigger",
    "Deferred indefinitely", "Reopened", "Closed / not pursuing",
)


class OwnerDaySessionUpsert(BaseModel):
    owner_calendar_date: str
    overview: dict[str, Any] = Field(default_factory=dict)


class OwnerDayBriefing(BaseModel):
    plain_language_title: str
    what_it_means: str
    why_now: str
    workspace_goal: str
    recommended_next_action: str
    classification: Literal[
        "standup recommendation",
        "reference-only context",
        "bounded preparation",
        "owner decision",
        "verified evidence",
    ]
    current_evidence: list[str] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    decision_options: list[str] = Field(default_factory=list)

    @field_validator(
        "plain_language_title",
        "what_it_means",
        "why_now",
        "workspace_goal",
        "recommended_next_action",
    )
    @classmethod
    def require_explanatory_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if len(text) < 12:
            raise ValueError("owner-day briefing fields must explain the item in plain language")
        return text


class OwnerDayActionCreate(BaseModel):
    session_id: str
    action_id: str
    workspace_key: str
    title: str
    description: str
    source: dict[str, Any]
    briefing: OwnerDayBriefing
    next_step: str | None = None


class OwnerDayBriefingUpdate(BaseModel):
    briefing: OwnerDayBriefing


class OwnerDayActionUpdate(BaseModel):
    status: str
    next_step: str | None = None
    outcome: dict[str, Any] | None = None
    idempotency_key: str
