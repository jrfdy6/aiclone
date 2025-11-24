"""
Template Management Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TemplateCategory(str, Enum):
    """Template categories"""
    LINKEDIN_POST = "linkedin_post"
    EMAIL = "email"
    LINKEDIN_DM = "linkedin_dm"
    FOLLOW_UP = "follow_up"
    VIDEO = "video"
    TWITTER = "twitter"
    BLOG = "blog"


class Template(BaseModel):
    """Template model"""
    id: str
    user_id: str
    name: str
    category: TemplateCategory
    content: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_favorite: bool = False
    created_at: str
    updated_at: str
    usage_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TemplateCreate(BaseModel):
    """Request to create template"""
    user_id: str = Field(..., description="User identifier")
    name: str = Field(..., description="Template name")
    category: TemplateCategory = Field(..., description="Template category")
    content: str = Field(..., description="Template content")
    description: Optional[str] = Field(None, description="Template description")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TemplateUpdate(BaseModel):
    """Request to update template"""
    name: Optional[str] = None
    category: Optional[TemplateCategory] = None
    content: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TemplateListResponse(BaseModel):
    """Response for listing templates"""
    success: bool
    templates: List[Template]
    total: int


class TemplateResponse(BaseModel):
    """Response for single template"""
    success: bool
    template: Template


class TemplateUseRequest(BaseModel):
    """Request to use template"""
    user_id: str = Field(..., description="User identifier")
    variables: Dict[str, str] = Field(default_factory=dict, description="Variables to replace in template")


class TemplateUseResponse(BaseModel):
    """Response from using template"""
    success: bool
    generated_content: str
    template_id: str
    template_name: str

