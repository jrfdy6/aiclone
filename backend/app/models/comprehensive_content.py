"""
Comprehensive Content Generation Models

Supports 100+ variations across 20+ content types:
- LinkedIn posts (multiple formats)
- Reels/Shorts/TikTok scripts
- Email newsletters
- Outreach messages
- Follow-up sequences
- Content calendars
- Hashtag sets
- Engagement hooks
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import time


class ContentType(str, Enum):
    """Content types that can be generated."""
    # LinkedIn Content
    LINKEDIN_POST = "linkedin_post"
    LINKEDIN_STORY_POST = "linkedin_story_post"
    LINKEDIN_DATA_POST = "linkedin_data_post"
    LINKEDIN_CAROUSEL_SCRIPT = "linkedin_carousel_script"
    LINKEDIN_LESSONS_LEARNED = "linkedin_lessons_learned"
    LINKEDIN_LEADERSHIP_INSIGHT = "linkedin_leadership_insight"
    LINKEDIN_AI_EDTECH = "linkedin_ai_edtech"
    LINKEDIN_REFERRAL_PARTNER = "linkedin_referral_partner"
    LINKEDIN_STEALTH_FOUNDER = "linkedin_stealth_founder"
    
    # Video Scripts
    REELS_7SEC_HOOK = "reels_7sec_hook"
    REELS_30SEC_VALUE = "reels_30sec_value"
    REELS_3THINGS = "reels_3things"
    SHORTS_SCRIPT = "shorts_script"
    TIKTOK_SCRIPT = "tiktok_script"
    
    # Email
    EMAIL_NEWSLETTER_WEEKLY = "email_newsletter_weekly"
    EMAIL_PRIVATE_SCHOOL_VALUE = "email_private_school_value"
    EMAIL_PARTNER_OUTREACH = "email_partner_outreach"
    EMAIL_ENROLLMENT_BEST_PRACTICES = "email_enrollment_best_practices"
    EMAIL_AI_OPERATIONS = "email_ai_operations"
    
    # Outreach
    OUTREACH_CONNECTION_REQUEST = "outreach_connection_request"
    OUTREACH_FIRST_DM = "outreach_first_dm"
    OUTREACH_FOLLOWUP_SEQUENCE = "outreach_followup_sequence"
    OUTREACH_PARTNERSHIP_PITCH = "outreach_partnership_pitch"
    OUTREACH_REFERRAL_WARMER = "outreach_referral_warmer"
    
    # Follow-up Sequences
    FOLLOWUP_3STEP = "followup_3step"
    FOLLOWUP_5STEP = "followup_5step"
    FOLLOWUP_7STEP = "followup_7step"
    FOLLOWUP_SOFT_NUDGE = "followup_soft_nudge"
    FOLLOWUP_DIRECT_CTA = "followup_direct_cta"
    
    # Calendars & Sets
    WEEKLY_CONTENT_CALENDAR = "weekly_content_calendar"
    HASHTAG_SET = "hashtag_set"
    ENGAGEMENT_HOOK = "engagement_hook"


class ContentFormat(str, Enum):
    """Output format options."""
    HUMAN_READY = "human_ready"  # Ready to copy/paste
    JSON_PAYLOAD = "json_payload"  # For backend ingestion
    BOTH = "both"  # Human content + JSON


class HookType(str, Enum):
    """Engagement hook types."""
    CURIOSITY = "curiosity"
    CONTRARIAN = "contrarian"
    DATA = "data"
    FOUNDER_LESSONS = "founder_lessons"
    OPERATIONAL_INSIGHTS = "operational_insights"


class HashtagCategory(str, Enum):
    """Hashtag set categories."""
    INDUSTRY = "industry"
    AI_LEADERSHIP = "ai_leadership"
    REFERRAL_PARTNER = "referral_partner"
    NEURODIVERSITY_SUPPORT = "neurodiversity_support"
    TRENDING = "trending"


class ComprehensiveContentRequest(BaseModel):
    """Request to generate comprehensive content."""
    user_id: str = Field(..., description="User ID")
    content_type: ContentType = Field(..., description="Type of content to generate")
    format: ContentFormat = Field(ContentFormat.BOTH, description="Output format (default: both - human-ready + JSON)")
    
    # Content parameters
    num_variations: int = Field(1, ge=1, le=100, description="Number of variations to generate (max 100)")
    pillar: Optional[str] = Field(None, description="Content pillar (referral, thought_leadership, stealth_founder)")
    topic: Optional[str] = Field(None, description="Specific topic or theme")
    
    # Specific type parameters
    hook_type: Optional[HookType] = Field(None, description="Type of engagement hook (for hook generation)")
    hashtag_category: Optional[HashtagCategory] = Field(None, description="Hashtag category (for hashtag sets)")
    calendar_num_posts: int = Field(5, ge=3, le=10, description="Posts per week (for calendar generation)")
    sequence_steps: Optional[int] = Field(None, description="Number of steps for sequences (for follow-up sequences)")
    
    # Context
    use_cached_research: bool = Field(True, description="Use cached research insights")
    linked_research_ids: List[str] = Field(default_factory=list, description="Link to research insights for context (Step F integration)")
    include_stealth_founder: bool = Field(False, description="Include stealth founder angle when applicable")
    tone: Optional[str] = Field("expert, direct, inspiring", description="Desired tone")
    
    # Options
    generate_hashtags: bool = Field(True, description="Include hashtag suggestions")
    generate_hooks: bool = Field(True, description="Include engagement hooks")
    best_posting_times: bool = Field(False, description="Include best posting times (for calendars)")


class ContentVariation(BaseModel):
    """A single content variation."""
    variation_number: int
    content: str
    suggested_hashtags: List[str] = Field(default_factory=list)
    engagement_hook: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComprehensiveContentResponse(BaseModel):
    """Response from comprehensive content generation."""
    success: bool
    content_type: str
    format: str
    variations_generated: int
    variations: List[ContentVariation] = Field(default_factory=list)
    
    # Human-ready format
    human_readable_content: Optional[str] = None
    
    # JSON payloads (for backend ingestion)
    json_payloads: Optional[List[Dict[str, Any]]] = None
    
    # Metadata
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)


class WeeklyCalendarRequest(BaseModel):
    """Request to generate weekly content calendar."""
    user_id: str = Field(..., description="User ID")
    num_posts: int = Field(5, ge=3, le=10, description="Number of posts per week")
    include_posting_times: bool = Field(True, description="Include optimal posting times")
    include_hashtags: bool = Field(True, description="Include hashtag suggestions")
    include_keywords: bool = Field(True, description="Include keyword targeting")
    pillar_distribution: Optional[Dict[str, int]] = Field(None, description="Custom pillar distribution (40% referral, 50% thought leadership, 10% stealth)")


class WeeklyCalendarPost(BaseModel):
    """A single post in the weekly calendar."""
    day: str  # Monday, Tuesday, etc.
    time: str  # 9:00 AM EST
    pillar: str
    topic: str
    content_preview: str  # First 100 chars
    suggested_hashtags: List[str]
    keywords: List[str] = Field(default_factory=list)
    draft_id: Optional[str] = None  # If already generated


class WeeklyCalendarResponse(BaseModel):
    """Response with weekly content calendar."""
    success: bool
    week_start_date: str
    week_end_date: str
    total_posts: int
    posts: List[WeeklyCalendarPost]
    pillar_distribution: Dict[str, int]
    best_posting_times: Dict[str, List[str]] = Field(default_factory=dict)  # Day -> [times]


class HashtagSetRequest(BaseModel):
    """Request to generate hashtag sets."""
    user_id: str = Field(..., description="User ID")
    categories: List[HashtagCategory] = Field(..., description="Hashtag categories to generate")
    num_per_category: int = Field(10, ge=5, le=30, description="Number of hashtags per category")


class HashtagSetResponse(BaseModel):
    """Response with hashtag sets."""
    success: bool
    sets: Dict[str, List[str]]  # Category -> [hashtags]


class EngagementHookRequest(BaseModel):
    """Request to generate engagement hooks."""
    user_id: str = Field(..., description="User ID")
    hook_types: List[HookType] = Field(..., description="Types of hooks to generate")
    num_per_type: int = Field(5, ge=1, le=20, description="Number of hooks per type")
    pillar: Optional[str] = Field(None, description="Content pillar context")
    topic: Optional[str] = Field(None, description="Topic context")


class EngagementHookResponse(BaseModel):
    """Response with engagement hooks."""
    success: bool
    hooks: Dict[str, List[str]]  # Hook type -> [hooks]

