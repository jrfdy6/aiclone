"""
Prospect Models - Pydantic models for prospects
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class CachedInsights(BaseModel):
    """Cached research insights on prospect"""
    industry_trends: List[str] = Field(default_factory=list)
    trending_pains: List[str] = Field(default_factory=list)
    signal_keywords: List[str] = Field(default_factory=list)
    referral_patterns: List[str] = Field(default_factory=list)
    last_updated: Optional[datetime] = None


class ProspectScoring(BaseModel):
    """Prospect scoring data"""
    fit_score: int = Field(0, ge=0, le=100, description="Fit score 0-100")
    referral_capacity: int = Field(0, ge=0, le=100, description="Referral capacity score")
    signal_strength: int = Field(0, ge=0, le=100, description="Signal strength 0-100")
    best_outreach_angle: Optional[str] = None
    scoring_reasoning: Optional[str] = None
    scored_at: Optional[datetime] = None


class Prospect(BaseModel):
    """Prospect document structure"""
    prospect_id: Optional[str] = None
    user_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: str
    company: str
    website: Optional[str] = None
    linkedin: Optional[str] = None
    discovery_source: str = Field(default="SearchAPI + Firecrawl")
    approval_status: str = Field(default="pending", description="pending|approved|rejected")
    linked_research_ids: List[str] = Field(default_factory=list)
    cached_insights: Optional[CachedInsights] = None
    
    # Scoring fields
    fit_score: Optional[int] = Field(None, ge=0, le=100)
    referral_capacity: Optional[int] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = Field(None, ge=0, le=100)
    best_outreach_angle: Optional[str] = None
    scoring_reasoning: Optional[str] = None
    
    # Outreach tracking
    drafts_generated: int = Field(default=0)
    emails_sent: int = Field(default=0)
    meetings_booked: int = Field(default=0)
    last_contacted: Optional[datetime] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProspectDiscoveryRequest(BaseModel):
    """Request for prospect discovery"""
    user_id: str = Field(..., description="User identifier")
    company_name: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    job_titles: Optional[List[str]] = Field(None, description="Target job titles")
    max_results: int = Field(50, ge=1, le=100)


class ProspectDiscoveryResponse(BaseModel):
    """Response from prospect discovery"""
    success: bool
    discovered_count: int
    prospects: List[Prospect]


class ProspectApproveRequest(BaseModel):
    """Request to approve/reject prospects"""
    user_id: str
    prospect_ids: List[str]
    approval_status: str = Field(..., description="approved|rejected")


class ProspectScoreRequest(BaseModel):
    """Request to score prospects"""
    user_id: str
    prospect_ids: List[str]
    audience_profile: Optional[Dict[str, Any]] = None


class ProspectScoreResponse(BaseModel):
    """Response from prospect scoring"""
    success: bool
    scored_count: int
    prospects: List[Prospect]



