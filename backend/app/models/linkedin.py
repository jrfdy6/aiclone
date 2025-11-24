"""
LinkedIn Post Models

Data models for LinkedIn posts and search results.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class LinkedInPost(BaseModel):
    """Model for a LinkedIn post."""
    post_id: str = Field(..., description="Unique identifier for the post")
    post_url: str = Field(..., description="URL to the LinkedIn post")
    author_name: Optional[str] = Field(None, description="Name of the post author")
    author_profile_url: Optional[str] = Field(None, description="URL to author's LinkedIn profile")
    author_title: Optional[str] = Field(None, description="Author's job title")
    author_company: Optional[str] = Field(None, description="Author's company")
    content: str = Field(..., description="Post content/text")
    engagement_metrics: Optional[Dict[str, int]] = Field(
        None,
        description="Engagement metrics (likes, comments, shares, reactions)"
    )
    engagement_score: Optional[float] = Field(
        None,
        description="Calculated engagement score based on metrics"
    )
    post_date: Optional[str] = Field(None, description="Date when post was published")
    is_connection: Optional[bool] = Field(
        None,
        description="Whether the author is a connection/following"
    )
    hashtags: Optional[List[str]] = Field(None, description="Hashtags in the post")
    mentions: Optional[List[str]] = Field(None, description="Mentioned users/companies")
    media_urls: Optional[List[str]] = Field(None, description="URLs to media in the post")
    scraped_at: str = Field(..., description="Timestamp when post was scraped")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class LinkedInSearchRequest(BaseModel):
    """Request model for LinkedIn post search."""
    query: str = Field(..., description="Search query (e.g., 'AI tools for developers', 'SaaS marketing')")
    industry: Optional[str] = Field(
        None,
        description="Target industry (e.g., 'SaaS', 'FinTech', 'Healthcare', 'E-commerce', 'AI/ML', 'Marketing', 'Real Estate', 'Education')"
    )
    include_connections: bool = Field(
        True,
        description="Include posts from people you're connected with/following"
    )
    include_non_connections: bool = Field(
        True,
        description="Include posts from people you're not connected with"
    )
    min_engagement_score: Optional[float] = Field(
        None,
        ge=0,
        description="Minimum engagement score to filter posts"
    )
    max_results: int = Field(20, ge=1, le=100, description="Maximum number of posts to return")
    sort_by: str = Field(
        "engagement",
        description="Sort order: 'engagement', 'recent', 'relevance'"
    )
    topics: Optional[List[str]] = Field(
        None,
        description="Filter by topics/keywords (e.g., ['AI', 'marketing', 'SaaS'])"
    )
    filter_by_company: Optional[bool] = Field(
        False,
        description="Filter results to only include posts from companies in the target industry"
    )


class LinkedInSearchResponse(BaseModel):
    """Response model for LinkedIn post search."""
    success: bool
    query: str
    total_results: int
    posts: List[LinkedInPost]
    search_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata about the search (e.g., search time, sources)"
    )

