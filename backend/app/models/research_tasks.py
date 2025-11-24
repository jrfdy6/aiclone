"""
Research Task Management Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ResearchEngine(str, Enum):
    """Research engine types"""
    PERPLEXITY = "perplexity"
    FIRECRAWL = "firecrawl"
    GOOGLE_SEARCH = "google_search"


class ResearchTaskStatus(str, Enum):
    """Research task status"""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Task priority levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceType(str, Enum):
    """Input source types"""
    KEYWORDS = "keywords"
    URLS = "urls"
    PROFILE = "profile"


class ResearchTaskCreate(BaseModel):
    """Request to create a research task"""
    user_id: str = Field(..., description="User identifier")
    title: str = Field(..., description="Task title")
    input_source: str = Field(..., description="Keywords, URLs, or profile info")
    source_type: SourceType = Field(..., description="Type of input source")
    research_engine: ResearchEngine = Field(..., description="Research engine to use")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Task priority")


class ResearchTask(BaseModel):
    """Research task model"""
    id: str
    user_id: str
    title: str
    input_source: str
    source_type: SourceType
    research_engine: ResearchEngine
    status: ResearchTaskStatus
    priority: TaskPriority
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    outputs_available: bool = False
    result_id: Optional[str] = None  # ID of research insight in Firestore


class ResearchInsight(BaseModel):
    """Research insights from completed task"""
    summary: str
    pain_points: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    suggested_outreach: List[str] = Field(default_factory=list)
    content_angles: List[str] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class ResearchTaskListResponse(BaseModel):
    """Response for listing research tasks"""
    success: bool
    tasks: List[ResearchTask]
    total: int


class ResearchTaskResponse(BaseModel):
    """Response for single research task"""
    success: bool
    task: ResearchTask


class ResearchInsightsResponse(BaseModel):
    """Response for research insights"""
    success: bool
    task_id: str
    task_title: str
    insights: ResearchInsight

