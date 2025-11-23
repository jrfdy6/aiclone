"""
Research Models - Pydantic models for research insights
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ResearchSource(BaseModel):
    """Source URL from research"""
    url: str
    title: Optional[str] = None


class ResearchInsight(BaseModel):
    """Research insight stored in Firestore"""
    research_id: Optional[str] = None
    title: str = Field(..., description="Research topic title")
    industry: str = Field(..., description="Industry focus")
    summary: str = Field(..., description="Lightweight summary of trends, pains, keywords")
    keywords: List[str] = Field(default_factory=list, description="Signals for prospect fit")
    job_titles: List[str] = Field(default_factory=list, description="High-value roles")
    linked_research_ids: List[str] = Field(default_factory=list, description="Related prospect IDs")
    sources: List[ResearchSource] = Field(default_factory=list, description="Source URLs")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResearchTriggerRequest(BaseModel):
    """Request to trigger research"""
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Research topic (e.g., 'SaaS companies serving SMBs')")
    industry: Optional[str] = Field(None, description="Industry focus")


class ResearchTriggerResponse(BaseModel):
    """Response from research trigger"""
    success: bool
    research_id: str
    status: str = "success"
    summary: ResearchInsight


