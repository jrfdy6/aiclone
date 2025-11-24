"""
Automations Engine Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class AutomationTrigger(str, Enum):
    """Automation trigger types"""
    NEW_PROSPECT_ADDED = "new_prospect_added"
    RESEARCH_TASK_COMPLETED = "research_task_completed"
    FOLLOW_UP_EVENT_DUE = "follow_up_event_due"
    HIGH_FIT_PROSPECT_DETECTED = "high_fit_prospect_detected"
    NEW_FILE_INGESTED = "new_file_ingested"


class AutomationAction(str, Enum):
    """Automation action types"""
    GENERATE_OUTREACH = "generate_outreach"
    ADD_CALENDAR_EVENT = "add_calendar_event"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_PROSPECT_STATUS = "update_prospect_status"
    RUN_FIRECRAWL = "run_firecrawl"
    RUN_PERPLEXITY = "run_perplexity"
    STORE_INSIGHT = "store_insight"


class AutomationStatus(str, Enum):
    """Automation status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Automation(BaseModel):
    """Automation model"""
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    trigger: AutomationTrigger
    actions: List[AutomationAction] = Field(..., description="List of actions to execute")
    status: AutomationStatus
    created_at: str
    updated_at: str
    execution_count: int = 0
    last_executed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationCreate(BaseModel):
    """Request to create automation"""
    user_id: str = Field(..., description="User identifier")
    name: str = Field(..., description="Automation name")
    description: Optional[str] = Field(None, description="Automation description")
    trigger: AutomationTrigger = Field(..., description="Trigger type")
    actions: List[AutomationAction] = Field(..., description="Actions to execute")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AutomationUpdate(BaseModel):
    """Request to update automation"""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[AutomationTrigger] = None
    actions: Optional[List[AutomationAction]] = None
    status: Optional[AutomationStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class AutomationListResponse(BaseModel):
    """Response for listing automations"""
    success: bool
    automations: List[Automation]
    total: int


class AutomationResponse(BaseModel):
    """Response for single automation"""
    success: bool
    automation: Automation


class ExecutionRecord(BaseModel):
    """Automation execution record"""
    id: str
    automation_id: str
    user_id: str
    status: ExecutionStatus
    triggered_by: str  # What triggered this execution
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    results: Dict[str, Any] = Field(default_factory=dict)


class ExecutionListResponse(BaseModel):
    """Response for listing executions"""
    success: bool
    executions: List[ExecutionRecord]
    total: int

