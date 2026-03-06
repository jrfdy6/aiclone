from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

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
    last_status: str = "success"
    metrics: Dict[str, str] = Field(default_factory=dict)
    instructions: List[AutomationInstruction] = Field(default_factory=list)
    notes: Optional[str] = None
