"""
Enhanced Metrics & Learning Models

Complete metrics tracking for:
- Content Metrics (LinkedIn posts, reels, emails, DMs)
- Prospect & Outreach Metrics (connection requests, DMs, meetings)
- Learning Patterns (performance analysis)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ====================
# Content Metrics
# ====================

class ContentPillar(str, Enum):
    """Content pillar types."""
    REFERRAL = "referral"
    THOUGHT_LEADERSHIP = "thought_leadership"
    STEALTH_FOUNDER = "stealth_founder"


class Platform(str, Enum):
    """Platform types."""
    LINKEDIN = "LinkedIn"
    INSTAGRAM = "Instagram"
    EMAIL = "Email"


class PostType(str, Enum):
    """Post/content types."""
    POST = "post"
    REEL = "reel"
    EMAIL = "email"
    DM = "dm"


class Reactions(BaseModel):
    """Reaction counts."""
    like: int = Field(0, ge=0)
    love: int = Field(0, ge=0)
    celebrate: int = Field(0, ge=0)
    insightful: int = Field(0, ge=0)
    curious: int = Field(0, ge=0)


class ContentMetricsData(BaseModel):
    """Content metrics data structure."""
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    reactions: Reactions = Field(default_factory=Reactions)
    impressions: int = Field(0, ge=0)
    profile_views: int = Field(0, ge=0)
    clicks: int = Field(0, ge=0)


class ContentMetricsUpdateRequest(BaseModel):
    """Request to update content metrics."""
    user_id: str
    content_id: str
    pillar: ContentPillar
    platform: Platform
    post_type: PostType
    post_url: Optional[str] = None
    publish_date: Optional[datetime] = None
    metrics: ContentMetricsData
    top_hashtags: List[str] = Field(default_factory=list)
    top_mentions: List[str] = Field(default_factory=list)
    audience_segment: List[str] = Field(default_factory=list)
    notes: Optional[str] = ""


class ContentMetricsResponse(BaseModel):
    """Response from content metrics update."""
    success: bool
    metrics_id: str
    engagement_rate: float


class ContentMetricsDocument(BaseModel):
    """Full content metrics document structure."""
    metrics_id: str
    user_id: str
    content_id: str
    pillar: str
    platform: str
    post_type: str
    post_url: Optional[str] = None
    publish_date: Optional[datetime] = None
    metrics: Dict[str, Any]
    engagement_rate: float
    top_hashtags: List[str]
    top_mentions: List[str]
    audience_segment: List[str]
    notes: str
    created_at: datetime
    updated_at: datetime


# ====================
# Prospect Metrics
# ====================

class ResponseType(str, Enum):
    """DM response types."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    NO_RESPONSE = "no_response"


class DMEntry(BaseModel):
    """DM entry structure."""
    message_id: str
    sent_at: datetime
    response_received_at: Optional[datetime] = None
    response_text: Optional[str] = None
    response_type: Optional[ResponseType] = None


class MeetingEntry(BaseModel):
    """Meeting entry structure."""
    meeting_id: str
    scheduled_at: datetime
    attended: bool
    notes: Optional[str] = ""


class ScoreUpdates(BaseModel):
    """Score update structure."""
    fit_score: Optional[int] = Field(None, ge=0, le=100)
    referral_capacity: Optional[int] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = Field(None, ge=0, le=100)


class ProspectMetricsUpdateRequest(BaseModel):
    """Request to update prospect metrics."""
    user_id: str
    prospect_id: str
    sequence_id: Optional[str] = None
    connection_request_sent: Optional[datetime] = None
    connection_accepted: Optional[datetime] = None
    dm_sent: List[DMEntry] = Field(default_factory=list)
    meetings_booked: List[MeetingEntry] = Field(default_factory=list)
    score_updates: Optional[ScoreUpdates] = None


class ProspectMetricsResponse(BaseModel):
    """Response from prospect metrics update."""
    success: bool
    prospect_metric_id: str
    reply_rate: Optional[float] = None
    meeting_rate: Optional[float] = None


class ProspectMetricsDocument(BaseModel):
    """Full prospect metrics document structure."""
    prospect_metric_id: str
    user_id: str
    prospect_id: str
    sequence_id: Optional[str] = None
    connection_request_sent: Optional[datetime] = None
    connection_accepted: Optional[datetime] = None
    dm_sent: List[Dict[str, Any]]
    meetings_booked: List[Dict[str, Any]]
    score_updates: Optional[Dict[str, int]] = None
    created_at: datetime
    updated_at: datetime


# ====================
# Learning Patterns
# ====================

class PatternType(str, Enum):
    """Learning pattern types."""
    CONTENT_PILLAR = "content_pillar"
    HASHTAG = "hashtag"
    TOPIC = "topic"
    OUTREACH_SEQUENCE = "outreach_sequence"
    AUDIENCE_SEGMENT = "audience_segment"


class SuccessMetric(str, Enum):
    """Success metrics for learning patterns."""
    LIKES = "likes"
    COMMENTS = "comments"
    SHARES = "shares"
    REPLY_RATE = "reply_rate"
    MEETING_RATE = "meeting_rate"
    ENGAGEMENT_RATE = "engagement_rate"


class LearningPattern(BaseModel):
    """Learning pattern structure."""
    pattern_id: str
    user_id: str
    pattern_type: PatternType
    pattern_key: str
    success_metric: SuccessMetric
    average_performance: float
    best_performance_variant: Optional[str] = None
    last_updated: datetime
    trend_notes: Optional[str] = ""
    # Additional tracking
    sample_size: int = Field(1, ge=1)
    performance_history: List[float] = Field(default_factory=list)


class UpdateLearningPatternsRequest(BaseModel):
    """Request to update learning patterns."""
    user_id: str
    pattern_type: Optional[PatternType] = None  # If None, analyzes all types
    date_range_days: int = Field(30, ge=1, le=365)


class UpdateLearningPatternsResponse(BaseModel):
    """Response from learning patterns update."""
    success: bool
    patterns_updated: int
    patterns: List[LearningPattern]


# ====================
# Weekly Reports
# ====================

class OutreachSummary(BaseModel):
    """Outreach summary for weekly report."""
    connection_accept_rate: float
    dm_reply_rate: float
    meetings_booked: int
    total_connection_requests: int
    total_dms_sent: int


class WeeklyReportRequest(BaseModel):
    """Request for weekly report."""
    user_id: str
    week_start: Optional[datetime] = None  # If None, uses current week
    week_end: Optional[datetime] = None


class WeeklyReportResponse(BaseModel):
    """Weekly report response."""
    success: bool
    week_start: datetime
    week_end: datetime
    total_posts: int
    avg_engagement_rate: float
    best_pillar: Optional[str] = None
    top_hashtags: List[str] = Field(default_factory=list)
    top_audience_segments: List[str] = Field(default_factory=list)
    outreach_summary: Optional[OutreachSummary] = None
    recommendations: List[str] = Field(default_factory=list)

