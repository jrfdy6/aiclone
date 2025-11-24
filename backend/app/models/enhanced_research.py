"""
Enhanced Research & Knowledge Management Models

Multi-source research pipeline with prospect extraction, normalization,
and integration with content generation and outreach systems.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import time


class SourceType(str, Enum):
    """Research source types."""
    PERPLEXITY = "perplexity"
    FIRECRAWL = "firecrawl"
    GOOGLE_CUSTOM_SEARCH = "google_custom_search"
    INTERNAL = "internal"  # From user's knowledge base


class InsightStatus(str, Enum):
    """Status of insight object."""
    COLLECTING = "collecting"
    PROCESSING = "processing"
    READY_FOR_CONTENT_GENERATION = "ready_for_content_generation"
    READY_FOR_OUTREACH = "ready_for_outreach"
    ARCHIVED = "archived"


class ResearchSourceDetail(BaseModel):
    """Detailed source information."""
    type: SourceType
    source_name: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    source_url: str
    date_collected: str  # ISO 8601 format


class ProspectTarget(BaseModel):
    """Prospect target extracted from research."""
    name: str
    role: str
    organization: str
    contact_url: Optional[str] = None
    pillar_relevance: List[str] = Field(default_factory=list)  # ["referral", "thought_leadership", etc.]
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class EngagementSignals(BaseModel):
    """Engagement signals for the insight."""
    relevance_score: float = Field(0.5, ge=0.0, le=1.0)
    trend_score: float = Field(0.5, ge=0.0, le=1.0)
    urgency_score: Optional[float] = Field(None, ge=0.0, le=1.0)




class AudienceType(str, Enum):
    """Target audience types for insights."""
    PRIVATE_SCHOOL_ADMINS = "private_school_admins"
    MENTAL_HEALTH_PROFESSIONALS = "mental_health_professionals"
    TREATMENT_CENTERS = "treatment_centers"
    EDTECH_BUSINESS_LEADERS = "edtech_business_leaders"
    AI_SAVVY_EXECUTIVES = "ai_savvy_executives"
    EARLY_ADOPTERS = "early_adopters"
    INVESTORS = "investors"
    STEALTH_FOUNDERS = "stealth_founders"
    EDUCATORS = "educators"
    SCHOOL_COUNSELORS = "school_counselors"


class EnhancedResearchInsight(BaseModel):
    """Enhanced research insight object (Firestore-ready)."""
    user_id: str
    insight_id: Optional[str] = None
    topic: str
    pillar: Optional[str] = Field(None, description="Content pillar: referral, thought_leadership, stealth_founder")
    audiences: List[str] = Field(default_factory=list, description="Target audiences (auto-assigned from pillar)")
    sources: List[ResearchSourceDetail] = Field(default_factory=list)
    prospect_targets: List[ProspectTarget] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    engagement_signals: EngagementSignals = Field(default_factory=EngagementSignals)
    date_collected: str  # ISO 8601 format
    status: InsightStatus = InsightStatus.COLLECTING
    linked_research_ids: List[str] = Field(default_factory=list)
    
    # Normalized fields
    normalized_key_points: List[str] = Field(default_factory=list)
    normalized_tags: List[str] = Field(default_factory=list)
    deduplication_hash: Optional[str] = None


class TopicTriggerRequest(BaseModel):
    """Request to trigger topic research."""
    user_id: str
    topic: str
    industry: Optional[str] = None
    pillar: Optional[str] = None  # Auto-assign if not provided
    use_cached: bool = Field(True, description="Use cached insights if available")
    include_prospect_extraction: bool = Field(True, description="Extract prospect targets")


class TopicTriggerResponse(BaseModel):
    """Response from topic trigger."""
    success: bool
    topic_id: str
    insight_id: str
    status: str
    pillar_assigned: Optional[str] = None
    estimated_completion_time: Optional[int] = None  # seconds


class MultiSourceResearchRequest(BaseModel):
    """Request to run multi-source research."""
    user_id: str
    insight_id: str
    topic: str
    use_perplexity: bool = Field(True)
    use_firecrawl: bool = Field(True)
    use_google_search: bool = Field(True)
    max_sources_per_type: int = Field(5, ge=1, le=10)
    batch_mode: bool = Field(True, description="Batch queries for free-tier optimization")


class MultiSourceResearchResponse(BaseModel):
    """Response from multi-source research."""
    success: bool
    insight_id: str
    sources_collected: int
    sources_by_type: Dict[str, int]
    prospect_targets_extracted: int
    status: str


class NormalizeInsightRequest(BaseModel):
    """Request to normalize and deduplicate insight."""
    user_id: str
    insight_id: str


class NormalizeInsightResponse(BaseModel):
    """Response from normalization."""
    success: bool
    insight_id: str
    deduplicated_key_points: int
    normalized_tags: int
    merged_sources: int


class ProspectExtractionRequest(BaseModel):
    """Request to extract prospect targets from insight."""
    user_id: str
    insight_id: str
    min_relevance_score: float = Field(0.7, ge=0.0, le=1.0)


class ProspectExtractionResponse(BaseModel):
    """Response from prospect extraction."""
    success: bool
    insight_id: str
    prospects_extracted: int
    prospects: List[ProspectTarget]

