"""
LinkedIn Models

Pydantic models for LinkedIn post search and analysis.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class LinkedInPost(BaseModel):
    """Model representing a LinkedIn post."""
    
    post_id: str = Field(..., description="Unique identifier for the post")
    post_url: str = Field(..., description="URL of the LinkedIn post")
    author_name: Optional[str] = Field(None, description="Name of the post author")
    author_profile_url: Optional[str] = Field(None, description="URL to author's LinkedIn profile")
    author_title: Optional[str] = Field(None, description="Job title of the author")
    author_company: Optional[str] = Field(None, description="Company of the author")
    content: str = Field(..., description="Full text content of the post")
    engagement_metrics: Optional[Dict[str, Any]] = Field(None, description="Engagement metrics (likes, comments, shares)")
    engagement_score: Optional[float] = Field(None, description="Calculated engagement score")
    post_date: Optional[str] = Field(None, description="Date the post was published")
    is_connection: Optional[bool] = Field(None, description="Whether the author is a connection")
    hashtags: Optional[List[str]] = Field(None, description="List of hashtags in the post")
    mentions: Optional[List[str]] = Field(None, description="List of mentioned users/companies")
    media_urls: Optional[List[str]] = Field(None, description="URLs of media (images, videos) in the post")
    scraped_at: str = Field(..., description="ISO timestamp when the post was scraped")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata about the post")


class LinkedInSearchRequest(BaseModel):
    """Request model for LinkedIn post search."""
    
    query: str = Field(..., description="Search query for LinkedIn posts")
    industry: Optional[str] = Field(None, description="Target industry for filtering posts")
    include_connections: bool = Field(True, description="Include posts from connections")
    include_non_connections: bool = Field(True, description="Include posts from non-connections")
    max_results: int = Field(20, ge=1, le=100, description="Maximum number of results to return")
    min_engagement_score: Optional[float] = Field(None, ge=0, description="Minimum engagement score threshold")
    sort_by: str = Field("engagement", description="Sort order: 'engagement' or 'recent'")
    filter_by_company: bool = Field(False, description="Filter posts by company relevance")
    topics: Optional[List[str]] = Field(None, description="Additional topics/keywords to search for")


class LinkedInSearchResponse(BaseModel):
    """Response model for LinkedIn post search."""
    
    success: bool = Field(..., description="Whether the search was successful")
    query: str = Field(..., description="The search query that was executed")
    total_results: int = Field(..., description="Total number of posts found")
    posts: List[LinkedInPost] = Field(..., description="List of LinkedIn posts")
    search_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata about the search")
