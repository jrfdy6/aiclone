from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OpenBrainSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    source: Optional[str] = None
    topic: Optional[str] = None
    min_importance: Optional[int] = Field(default=None, ge=1, le=3)


class OpenBrainSearchHit(BaseModel):
    chunk_id: str
    capture_id: str
    chunk_index: int
    chunk: str
    similarity_score: float
    source: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    importance: int = 0
    markdown_path: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class OpenBrainSearchResponse(BaseModel):
    query: str
    results: List[OpenBrainSearchHit] = Field(default_factory=list)


class OpenBrainHealth(BaseModel):
    database_connected: bool = False
    vector_extension: bool = False
    embedding_type: Optional[str] = None
    configured_dimension: Optional[int] = None
    storage_backend: Optional[str] = None
    embedder_dimension: int = 0
    dimension_match: bool = False
    capture_count: int = 0
    vector_count: int = 0
    non_expired_vector_count: int = 0
    search_ready: bool = False
    sample_hit: Optional[OpenBrainSearchHit] = None
