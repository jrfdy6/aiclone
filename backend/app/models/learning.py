"""
Learning Models - Pydantic models for learning patterns
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class LearningPattern(BaseModel):
    """Learning pattern stored in Firestore"""
    pattern_id: Optional[str] = None
    user_id: str
    industry: Optional[str] = None
    job_title: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    outreach_angle: Optional[str] = None
    performance_score: int = Field(0, ge=0, le=100, description="How well this pattern converts")
    engagement_count: int = Field(default=0)
    updated_at: Optional[datetime] = None


class UpdatePatternsRequest(BaseModel):
    """Request to update learning patterns"""
    user_id: str
    prospect_id: str
    engagement_data: dict = Field(..., description="Engagement data (email_sent, email_opened, etc.)")


class UpdatePatternsResponse(BaseModel):
    """Response from pattern update"""
    success: bool
    updated_patterns: List[LearningPattern]


class GetPatternsRequest(BaseModel):
    """Request to get learning patterns"""
    user_id: str
    pattern_type: Optional[str] = Field(None, description="industry|job_title|keyword|outreach_angle")
    limit: int = Field(10, ge=1, le=50)


class GetPatternsResponse(BaseModel):
    """Response with learning patterns"""
    success: bool
    patterns: List[LearningPattern]




