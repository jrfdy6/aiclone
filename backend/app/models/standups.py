from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StandupEntry(BaseModel):
    id: str
    owner: str
    status: Optional[str] = None
    blockers: List[str] = Field(default_factory=list)
    commitments: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    conversation_path: Optional[str] = None
    created_at: datetime


class StandupCreate(BaseModel):
    owner: str
    status: Optional[str] = None
    blockers: List[str] = Field(default_factory=list)
    commitments: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    conversation_path: Optional[str] = None


class StandupUpdate(BaseModel):
    status: Optional[str] = None
    blockers: Optional[List[str]] = None
    commitments: Optional[List[str]] = None
    needs: Optional[List[str]] = None
    source: Optional[str] = None
    conversation_path: Optional[str] = None
