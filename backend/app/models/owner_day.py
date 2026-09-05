from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


OWNER_DAY_STATUSES = (
    "Open / Not reviewed", "In progress", "Needs decision", "Waiting on someone else",
    "Blocked", "Completed", "Deferred until date", "Deferred until trigger",
    "Deferred indefinitely", "Reopened", "Closed / not pursuing",
)


class OwnerDaySessionUpsert(BaseModel):
    owner_calendar_date: str
    overview: dict[str, Any] = Field(default_factory=dict)


class OwnerDayActionCreate(BaseModel):
    session_id: str
    action_id: str
    workspace_key: str
    title: str
    description: str
    source: dict[str, Any]
    next_step: str | None = None


class OwnerDayActionUpdate(BaseModel):
    status: str
    next_step: str | None = None
    outcome: dict[str, Any] | None = None
    idempotency_key: str
