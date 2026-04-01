from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PMCard(BaseModel):
    id: str
    title: str
    owner: Optional[str] = None
    status: str = "todo"
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PMCardCreate(BaseModel):
    title: str
    owner: Optional[str] = None
    status: str = "todo"
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: dict = Field(default_factory=dict)


class PMCardUpdate(BaseModel):
    title: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: Optional[dict] = None


class ExecutionQueueEntry(BaseModel):
    card_id: str
    title: str
    workspace_key: str = "shared_ops"
    pm_status: str = "todo"
    execution_state: str = "ready"
    manager_agent: str = "Jean-Claude"
    target_agent: str = "Jean-Claude"
    workspace_agent: Optional[str] = None
    execution_mode: str = "direct"
    requested_by: Optional[str] = None
    assigned_runner: Optional[str] = None
    lane: str = "codex"
    reason: Optional[str] = None
    source: Optional[str] = None
    link_type: Optional[str] = None
    queued_at: Optional[datetime] = None
    last_transition_at: Optional[datetime] = None


class PMCardDispatchRequest(BaseModel):
    target_agent: Optional[str] = None
    lane: str = "codex"
    requested_by: str = "Jean-Claude"
    execution_state: str = "queued"


class PMCardDispatchResult(BaseModel):
    card: PMCard
    queue_entry: ExecutionQueueEntry
