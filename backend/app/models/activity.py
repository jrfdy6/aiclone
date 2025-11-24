"""
Activity Logging Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ActivityType(str, Enum):
    """Activity event types"""
    PROSPECT = "prospect"
    OUTREACH = "outreach"
    RESEARCH = "research"
    INSIGHT = "insight"
    CONTENT = "content"
    AUTOMATION = "automation"
    ERROR = "error"


class ActivityEvent(BaseModel):
    """Activity event model"""
    id: str
    user_id: str
    type: ActivityType
    title: str
    message: str
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    link: Optional[str] = None


class ActivityListResponse(BaseModel):
    """Response for listing activities"""
    success: bool
    activities: List[ActivityEvent]
    total: int


class ActivityCreate(BaseModel):
    """Request to create activity log"""
    user_id: str = Field(..., description="User identifier")
    type: ActivityType = Field(..., description="Activity type")
    title: str = Field(..., description="Activity title")
    message: str = Field(..., description="Activity message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    link: Optional[str] = Field(None, description="Optional link to related resource")


class ActivityResponse(BaseModel):
    """Response for single activity"""
    success: bool
    activity: ActivityEvent

