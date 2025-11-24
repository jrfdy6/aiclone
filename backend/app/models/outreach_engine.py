"""
Outreach Engine Models

Complete outreach system with:
- Prospect segmentation (50% referral, 50% thought leadership, 5% stealth founder)
- Outreach sequences (connection requests, DMs, follow-ups)
- Scoring & prioritization
- Engagement tracking
- Calendar & cadence management
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import time


class ProspectSegment(str, Enum):
    """Prospect audience segments."""
    REFERRAL_NETWORK = "referral_network"  # 50% - Private school admins, mental health, referral network
    THOUGHT_LEADERSHIP = "thought_leadership"  # 50% - EdTech / AI-savvy leaders
    STEALTH_FOUNDER = "stealth_founder"  # 5% - Stealth founder / early adopters


class OutreachType(str, Enum):
    """Types of outreach."""
    CONNECTION_REQUEST = "connection_request"
    INITIAL_DM = "initial_dm"
    FOLLOWUP_1 = "followup_1"
    FOLLOWUP_2 = "followup_2"
    FOLLOWUP_3 = "followup_3"
    CHECKIN = "checkin"  # Quarterly re-engagement


class EngagementStatus(str, Enum):
    """Engagement status."""
    NOT_SENT = "not_sent"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    MEETING_BOOKED = "meeting_booked"
    NOT_INTERESTED = "not_interested"
    NO_RESPONSE = "no_response"


class ProspectSegmentTag(BaseModel):
    """Prospect segmentation tags."""
    segment: ProspectSegment
    industry: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    engagement_potential: float = Field(0.5, ge=0.0, le=1.0)
    pacer_relevance: List[str] = Field(default_factory=list)  # ["referral", "thought_leadership", etc.]
    prospect_id: str


class SegmentProspectsRequest(BaseModel):
    """Request to segment prospects."""
    user_id: str
    prospect_ids: Optional[List[str]] = None  # If None, segments all prospects
    target_distribution: Optional[Dict[str, float]] = Field(None, description="Custom distribution (default: 50% referral, 50% thought leadership, 5% stealth founder)")


class SegmentProspectsResponse(BaseModel):
    """Response from prospect segmentation."""
    success: bool
    total_prospects: int
    segments: Dict[str, int]  # segment -> count
    tagged_prospects: List[ProspectSegmentTag]


class OutreachSequence(BaseModel):
    """Complete outreach sequence for a prospect."""
    prospect_id: str
    segment: ProspectSegment
    sequence_type: str = Field(..., description="3-step, 5-step, 7-step")
    
    # Sequence steps
    connection_request: Optional[Dict[str, Any]] = None
    initial_dm: Optional[Dict[str, Any]] = None
    followup_1: Optional[Dict[str, Any]] = None
    followup_2: Optional[Dict[str, Any]] = None
    followup_3: Optional[Dict[str, Any]] = None
    
    # Timing
    send_dates: Dict[str, float] = Field(default_factory=dict)  # step -> timestamp
    current_step: int = Field(0, ge=0)
    
    # Status
    status: EngagementStatus = EngagementStatus.NOT_SENT
    engagement_data: Dict[str, Any] = Field(default_factory=dict)


class GenerateSequenceRequest(BaseModel):
    """Request to generate outreach sequence."""
    user_id: str
    prospect_id: str
    sequence_type: str = Field("3-step", description="3-step, 5-step, 7-step, soft_nudge, direct_cta")
    num_variants: int = Field(2, ge=1, le=5, description="Number of variants per step")


class GenerateSequenceResponse(BaseModel):
    """Response with generated outreach sequence."""
    success: bool
    prospect_id: str
    segment: str
    sequence_type: str
    sequence: OutreachSequence
    variants: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)  # step -> [variants]


class PrioritizeProspectsRequest(BaseModel):
    """Request to prioritize prospects."""
    user_id: str
    min_fit_score: int = Field(70, ge=0, le=100)
    min_referral_capacity: int = Field(60, ge=0, le=100)
    min_signal_strength: int = Field(50, ge=0, le=100)
    segment: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)


class PrioritizeProspectsResponse(BaseModel):
    """Response with prioritized prospects."""
    success: bool
    total_scored: int
    top_tier_count: int
    prospects: List[Dict[str, Any]]  # Prioritized prospect list


class TrackEngagementRequest(BaseModel):
    """Request to track outreach engagement."""
    user_id: str
    prospect_id: str
    outreach_type: OutreachType
    engagement_status: EngagementStatus
    engagement_data: Dict[str, Any] = Field(default_factory=dict)  # replies, meetings, etc.


class WeeklyCadenceRequest(BaseModel):
    """Request to generate weekly outreach cadence."""
    user_id: str
    week_start_date: Optional[float] = None  # Unix timestamp
    target_connection_requests: int = Field(40, ge=10, le=100)
    target_followups: int = Field(30, ge=5, le=100)


class WeeklyCadenceEntry(BaseModel):
    """Single entry in weekly outreach cadence."""
    day: str  # Monday, Tuesday, etc.
    date: str  # YYYY-MM-DD
    time: str  # 9:00 AM EST
    prospect_id: str
    prospect_name: str
    segment: str
    outreach_type: OutreachType
    sequence_step: int
    message_variant: int
    priority_score: float


class WeeklyCadenceResponse(BaseModel):
    """Response with weekly outreach cadence."""
    success: bool
    week_start: str
    week_end: str
    total_outreach: int
    entries: List[WeeklyCadenceEntry]
    distribution: Dict[str, int]  # segment -> count


class OutreachMetricsRequest(BaseModel):
    """Request to get outreach metrics."""
    user_id: str
    date_range_days: int = Field(30, ge=1, le=365)


class OutreachMetricsResponse(BaseModel):
    """Response with outreach metrics."""
    success: bool
    date_range_days: int
    total_outreach: int
    connection_requests_sent: int
    dms_sent: int
    followups_sent: int
    replies_received: int
    meetings_booked: int
    reply_rate: float
    meeting_rate: float
    segment_performance: Dict[str, Dict[str, Any]]  # segment -> metrics
    top_performing_sequences: List[Dict[str, Any]]

