"""
Metrics Models - Pydantic models for metrics tracking
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class TopPerformer(BaseModel):
    """Top performer entry"""
    value: str  # industry name, job title, or outreach angle
    count: int
    meetings: Optional[int] = 0
    response_rate: Optional[float] = None


class Metrics(BaseModel):
    """Metrics document structure"""
    metric_id: Optional[str] = None
    user_id: str
    week_start: Optional[datetime] = None
    month: Optional[str] = None
    prospects_analyzed: int = Field(default=0)
    emails_sent: int = Field(default=0)
    meetings_booked: int = Field(default=0)
    top_industries: List[TopPerformer] = Field(default_factory=list)
    top_job_titles: List[TopPerformer] = Field(default_factory=list)
    top_outreach_angles: List[TopPerformer] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class UpdateMetricsRequest(BaseModel):
    """Request to update metrics"""
    user_id: str
    prospect_id: Optional[str] = None
    action: str = Field(..., description="prospects_analyzed|emails_sent|meetings_booked")
    engagement_data: Optional[Dict[str, Any]] = None


class MetricsResponse(BaseModel):
    """Response with metrics"""
    success: bool
    metrics: Metrics




