"""
Content Library Models
Repository, version control, approval workflows
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ContentFormat(str, Enum):
    LINKEDIN_POST = "linkedin_post"
    BLOG_POST = "blog_post"
    EMAIL = "email"
    VIDEO_SCRIPT = "video_script"
    WHITE_PAPER = "white_paper"
    CASE_STUDY = "case_study"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    OTHER = "other"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentVersion(BaseModel):
    version_number: int
    content: str
    created_at: datetime
    created_by: str
    changes: Optional[str] = None


class ContentItem(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    format: ContentFormat
    status: ContentStatus = ContentStatus.DRAFT
    pillar: Optional[str] = None  # referral, thought_leadership, etc.
    tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    versions: List[ContentVersion] = Field(default_factory=list)
    current_version: int = 1
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    published_platforms: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ContentCreate(BaseModel):
    user_id: str
    title: str
    content: str
    format: ContentFormat
    pillar: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    format: Optional[ContentFormat] = None
    pillar: Optional[str] = None
    tags: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    status: Optional[ContentStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class ContentResponse(BaseModel):
    success: bool
    content: ContentItem


class ContentListResponse(BaseModel):
    success: bool
    content_items: List[ContentItem]
    total: int


class ApprovalRequest(BaseModel):
    content_id: str
    approver_id: str
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    success: bool
    approved: bool
    comments: Optional[str] = None

