from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PMCard(BaseModel):
    id: str
    title: str
    owner: Optional[str] = None
    status: str = "todo"
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PMCardCreate(BaseModel):
    title: str
    owner: Optional[str] = None
    status: str = "todo"
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: dict = Field(default_factory=dict)


class PMCardUpdate(BaseModel):
    title: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    link_type: Optional[str] = None
    link_id: Optional[str] = None
    due_at: Optional[datetime] = None
    payload: Optional[dict] = None
