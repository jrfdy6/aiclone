from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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
    front_door_agent: Optional[str] = None
    trigger_key: Optional[str] = None
    manager_attention_required: bool = False
    executor_status: Optional[str] = None
    executor_worker_id: Optional[str] = None
    execution_packet_path: Optional[str] = None
    sop_path: Optional[str] = None
    briefing_path: Optional[str] = None
    latest_result_status: Optional[str] = None
    latest_result_summary: Optional[str] = None
    latest_result_artifacts: list[str] = Field(default_factory=list)
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


PMCardActionType = Literal["approve", "return", "blocked"]
PMCardResolutionMode = Literal["close_only", "close_and_spawn_next"]


class PMCardActionRequest(BaseModel):
    action: PMCardActionType
    requested_by: str = "Neo"
    reason: Optional[str] = None
    resolution_mode: Optional[PMCardResolutionMode] = None
    next_title: Optional[str] = None
    next_reason: Optional[str] = None
    proof_items: list[str] = Field(default_factory=list)


class PMCardActionResult(BaseModel):
    card: PMCard
    queue_entry: Optional[ExecutionQueueEntry] = None
    successor_card: Optional[PMCard] = None


class PMHostActionRunRequest(BaseModel):
    requested_by: str = "Neo"
    reason: Optional[str] = None
    proof_items: list[str] = Field(default_factory=list)
    scheduled_at: Optional[str] = None
    asset_decision: Optional[str] = None
    confirmation_path: Optional[str] = None
    queue_id: Optional[str] = None
