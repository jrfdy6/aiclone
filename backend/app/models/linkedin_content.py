"""
LinkedIn Content Models

Models for LinkedIn content drafting, scheduling, and engagement tracking.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ContentPillar(str, Enum):
    """Content pillar types for PACER strategy."""
    REFERRAL = "referral"  # Private school admins, mental health pros
    THOUGHT_LEADERSHIP = "thought_leadership"  # EdTech business leaders
    STEALTH_FOUNDER = "stealth_founder"  # Early adopters, investors
    MIXED = "mixed"  # Cross-pillar content


class ContentStatus(str, Enum):
    """Content draft status."""
    DRAFT = "draft"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentDraft(BaseModel):
    """Model for a LinkedIn content draft."""
    draft_id: str = Field(..., description="Unique identifier for the draft")
    user_id: str = Field(..., description="User who created the draft")
    title: Optional[str] = Field(None, description="Draft title/headline")
    content: str = Field(..., description="Post content/text")
    pillar: ContentPillar = Field(..., description="Content pillar this belongs to")
    topic: Optional[str] = Field(None, description="Topic/subject of the post")
    suggested_hashtags: List[str] = Field(default_factory=list, description="Suggested hashtags")
    engagement_hook: Optional[str] = Field(None, description="Engagement hook/question")
    stealth_founder_mention: bool = Field(False, description="Whether this includes stealth founder angle")
    linked_research_ids: List[str] = Field(default_factory=list, description="Linked research insight IDs")
    linked_post_ids: List[str] = Field(default_factory=list, description="LinkedIn post IDs used as inspiration")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    status: ContentStatus = Field(ContentStatus.DRAFT, description="Current status")
    created_at: float = Field(..., description="Timestamp when draft was created")
    updated_at: float = Field(..., description="Timestamp when draft was last updated")
    scheduled_date: Optional[float] = Field(None, description="Scheduled publish timestamp")


class ContentCalendarEntry(BaseModel):
    """Model for a calendar entry (scheduled post)."""
    calendar_id: str = Field(..., description="Unique identifier for calendar entry")
    user_id: str = Field(..., description="User ID")
    draft_id: str = Field(..., description="Linked content draft ID")
    scheduled_date: float = Field(..., description="Scheduled publish timestamp")
    pillar: ContentPillar = Field(..., description="Content pillar")
    status: str = Field("scheduled", description="Status: scheduled, published, cancelled")
    notes: Optional[str] = Field(None, description="Notes about this posting")
    created_at: float = Field(..., description="Timestamp when entry was created")


class EngagementMetrics(BaseModel):
    """Model for LinkedIn post engagement metrics."""
    post_url: Optional[str] = Field(None, description="URL of the published post")
    draft_id: str = Field(..., description="Linked content draft ID")
    likes: int = Field(0, description="Number of likes")
    comments: int = Field(0, description="Number of comments")
    shares: int = Field(0, description="Number of shares")
    reactions: Dict[str, int] = Field(default_factory=dict, description="Breakdown of reaction types")
    profile_views: Optional[int] = Field(None, description="Profile views from this post")
    impressions: Optional[int] = Field(None, description="Post impressions")
    engagement_rate: Optional[float] = Field(None, description="Calculated engagement rate")
    recorded_at: float = Field(..., description="Timestamp when metrics were recorded")
    updated_at: float = Field(..., description="Timestamp when metrics were last updated")


class ContentDraftRequest(BaseModel):
    """Request to generate a content draft."""
    user_id: str = Field(..., description="User ID")
    pillar: ContentPillar = Field(..., description="Content pillar")
    topic: Optional[str] = Field(None, description="Specific topic to write about")
    include_stealth_founder: bool = Field(False, description="Include stealth founder angle (5-10% of posts)")
    linked_research_ids: List[str] = Field(default_factory=list, description="Research insight IDs to use")
    num_drafts: int = Field(3, ge=1, le=5, description="Number of draft variants to generate")
    tone: Optional[str] = Field("authentic and insightful", description="Desired tone")


class ContentDraftResponse(BaseModel):
    """Response containing generated drafts."""
    success: bool
    drafts: List[ContentDraft]
    insights_used: List[str] = Field(default_factory=list, description="Research/post insights referenced")


class ContentCalendarRequest(BaseModel):
    """Request to schedule content."""
    user_id: str = Field(..., description="User ID")
    draft_id: str = Field(..., description="Content draft ID")
    scheduled_date: float = Field(..., description="Unix timestamp for scheduled publish time")
    notes: Optional[str] = Field(None, description="Optional notes")


class EngagementMetricsUpdate(BaseModel):
    """Request to update engagement metrics."""
    user_id: str = Field(..., description="User ID")
    draft_id: str = Field(..., description="Content draft ID")
    post_url: Optional[str] = Field(None, description="URL of published post")
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    reactions: Dict[str, int] = Field(default_factory=dict)
    profile_views: Optional[int] = Field(None, ge=0)
    impressions: Optional[int] = Field(None, ge=0)


class OutreachRequest(BaseModel):
    """Request to generate outreach (DMs, connection requests)."""
    user_id: str = Field(..., description="User ID")
    prospect_id: str = Field(..., description="Prospect ID")
    outreach_type: str = Field("dm", description="Type: 'connection_request', 'dm', 'follow_up'")
    use_research_insights: bool = Field(True, description="Use linked research insights")
    tone: Optional[str] = Field("professional and authentic", description="Desired tone")


class OutreachResponse(BaseModel):
    """Response containing generated outreach."""
    success: bool
    prospect_id: str
    outreach_type: str
    variants: List[Dict[str, str]] = Field(default_factory=list, description="Multiple outreach variants")
    suggested_timing: Optional[str] = Field(None, description="Suggested send timing")
    personalization_notes: Optional[str] = Field(None, description="Notes on personalization used")


class StoreDraftRequest(BaseModel):
    """Request to store manually generated drafts."""
    user_id: str = Field(..., description="User ID")
    drafts: List[Dict[str, Any]] = Field(..., description="List of draft objects with title, content, pillar, etc.")


class StoreDraftResponse(BaseModel):
    """Response from storing drafts."""
    success: bool
    stored_count: int
    drafts: List[ContentDraft]

