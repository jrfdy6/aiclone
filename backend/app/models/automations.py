from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AutomationInstruction(BaseModel):
    """Instructional step for a given automation."""

    title: str
    detail: str


class Automation(BaseModel):
    """Automation/cron job definition."""

    id: str
    name: str
    description: str
    type: str = "scheduled"
    status: str = "active"
    schedule: str
    cron: str
    channel: str = "system"
    isolation: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_status: str = "unknown"
    source: str = "codex_launchd_registry"
    runtime: Optional[str] = None
    delivery_channel: Optional[str] = None
    delivery_target: Optional[str] = None
    last_delivered: Optional[bool] = None
    last_error: Optional[str] = None
    session_target: Optional[str] = None
    owner_agent: Optional[str] = None
    scope: str = "shared_ops"
    workspace_key: Optional[str] = None
    metrics: Dict[str, str] = Field(default_factory=dict)
    instructions: List[AutomationInstruction] = Field(default_factory=list)
    notes: Optional[str] = None


class AutomationRun(BaseModel):
    """Observed local Codex/launchd automation run."""

    id: str
    automation_id: str
    automation_name: str
    source: str = "local_launchd_registry"
    runtime: Optional[str] = None
    status: str = "unknown"
    delivered: Optional[bool] = None
    delivery_channel: Optional[str] = None
    delivery_target: Optional[str] = None
    run_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    owner_agent: Optional[str] = None
    session_target: Optional[str] = None
    scope: str = "shared_ops"
    workspace_key: Optional[str] = None
    action_required: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationRunMirrorRequest(BaseModel):
    runs: List[AutomationRun] = Field(default_factory=list)


class AutomationRunMirrorResponse(BaseModel):
    success: bool = True
    count: int = 0
    source_of_truth: str = "codex_launchd_registry+codex_run_ledger"


class AutomationMismatch(BaseModel):
    """Represents drift between the Codex registry, run ledger, and local launchd state."""

    kind: str
    severity: str = "warn"
    automation_id: Optional[str] = None
    automation_name: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationMismatchReport(BaseModel):
    """Summary report for automation mismatches and action-needed state."""

    source_of_truth: str
    registry_count: int = 0
    registered_launchd_count: int = 0
    run_count: int = 0
    mismatch_count: int = 0
    action_required_count: int = 0
    mismatches: List[AutomationMismatch] = Field(default_factory=list)
