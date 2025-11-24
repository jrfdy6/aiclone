"""
Knowledge Vault Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class VaultTopicCategory(str, Enum):
    """Vault topic categories"""
    EDUCATION_TECHNOLOGY = "education_technology"
    MARKET_TRENDS = "market_trends"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    INDUSTRY_INSIGHTS = "industry_insights"


class VaultItem(BaseModel):
    """Knowledge vault item model"""
    id: str
    user_id: str
    title: str
    summary: str
    category: VaultTopicCategory
    tags: List[str] = Field(default_factory=list)
    sources: List[Dict[str, str]] = Field(default_factory=list)
    created_at: str
    updated_at: str
    linked_outreach_ids: List[str] = Field(default_factory=list)
    linked_content_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VaultItemCreate(BaseModel):
    """Request to create vault item"""
    user_id: str = Field(..., description="User identifier")
    title: str = Field(..., description="Vault item title")
    summary: str = Field(..., description="Summary/insight text")
    category: VaultTopicCategory = Field(..., description="Topic category")
    tags: List[str] = Field(default_factory=list, description="Tags")
    sources: List[Dict[str, str]] = Field(default_factory=list, description="Source URLs and titles")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class VaultItemUpdate(BaseModel):
    """Request to update vault item"""
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[VaultTopicCategory] = None
    tags: Optional[List[str]] = None
    sources: Optional[List[Dict[str, str]]] = None
    metadata: Optional[Dict[str, Any]] = None


class VaultListResponse(BaseModel):
    """Response for listing vault items"""
    success: bool
    items: List[VaultItem]
    total: int


class VaultItemResponse(BaseModel):
    """Response for single vault item"""
    success: bool
    item: VaultItem


class TopicCluster(BaseModel):
    """Topic cluster model"""
    topic: str
    item_count: int
    items: List[VaultItem]


class TopicClustersResponse(BaseModel):
    """Response for topic clusters"""
    success: bool
    clusters: List[TopicCluster]


class Trendline(BaseModel):
    """Trendline data point"""
    date: str
    item_count: int
    categories: Dict[str, int]


class TrendlinesResponse(BaseModel):
    """Response for trendlines"""
    success: bool
    trendlines: List[Trendline]
    period: str

