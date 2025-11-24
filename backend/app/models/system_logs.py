"""
System Logs Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class LogLevel(str, Enum):
    """Log levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class LogCategory(str, Enum):
    """Log categories"""
    API = "api"
    RESEARCH = "research"
    AUTOMATION = "automation"
    CONTENT = "content"
    OUTREACH = "outreach"
    PROSPECT = "prospect"
    SYSTEM = "system"


class SystemLog(BaseModel):
    """System log model"""
    id: str
    user_id: str
    level: LogLevel
    category: LogCategory
    message: str
    details: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    related_id: Optional[str] = None  # ID of related resource (prospect, task, etc.)
    can_rerun: bool = False


class LogCreate(BaseModel):
    """Request to create log entry"""
    user_id: str = Field(..., description="User identifier")
    level: LogLevel = Field(..., description="Log level")
    category: LogCategory = Field(..., description="Log category")
    message: str = Field(..., description="Log message")
    details: Optional[str] = Field(None, description="Detailed error/context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    related_id: Optional[str] = Field(None, description="Related resource ID")
    can_rerun: bool = Field(False, description="Whether task can be re-run")


class LogListResponse(BaseModel):
    """Response for listing logs"""
    success: bool
    logs: List[SystemLog]
    total: int


class LogResponse(BaseModel):
    """Response for single log"""
    success: bool
    log: SystemLog


class LogStatsResponse(BaseModel):
    """Response for log statistics"""
    success: bool
    total_logs: int
    by_level: Dict[str, int]
    by_category: Dict[str, int]
    recent_errors: int

