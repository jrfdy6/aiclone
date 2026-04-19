from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .pm_board import PMCard


class StandupEntry(BaseModel):
    id: str
    owner: str
    workspace_key: str = "shared_ops"
    status: Optional[str] = None
    blockers: List[str] = Field(default_factory=list)
    commitments: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    conversation_path: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class StandupCreate(BaseModel):
    owner: str
    workspace_key: str = "shared_ops"
    status: Optional[str] = None
    blockers: List[str] = Field(default_factory=list)
    commitments: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    conversation_path: Optional[str] = None
    payload: dict = Field(default_factory=dict)


class StandupUpdate(BaseModel):
    workspace_key: Optional[str] = None
    status: Optional[str] = None
    blockers: Optional[List[str]] = None
    commitments: Optional[List[str]] = None
    needs: Optional[List[str]] = None
    source: Optional[str] = None
    conversation_path: Optional[str] = None
    payload: Optional[dict] = None


class StandupPromotionPMUpdate(BaseModel):
    workspace_key: str = "shared_ops"
    scope: str = "shared_ops"
    owner_agent: str = "jean-claude"
    title: str
    status: str = "todo"
    reason: str
    payload: dict = Field(default_factory=dict)


class StandupPromotionRequest(BaseModel):
    standup_kind: str = "executive_ops"
    owner: str = "Jean-Claude"
    workspace_key: str = "shared_ops"
    summary: str
    agenda: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    commitments: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    audience_response: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    owners: List[str] = Field(default_factory=list)
    artifact_deltas: List[str] = Field(default_factory=list)
    standup_sections: dict = Field(default_factory=dict)
    source: Optional[str] = "standup_prep"
    conversation_path: Optional[str] = None
    source_paths: List[str] = Field(default_factory=list)
    memory_promotions: List[str] = Field(default_factory=list)
    pm_snapshot: dict = Field(default_factory=dict)
    participants: List[str] = Field(default_factory=list)
    discussion_rounds: List[dict] = Field(default_factory=list)
    jean_claude_note: Optional[str] = None
    neo_note: Optional[str] = None
    yoda_note: Optional[str] = None
    prep_id: Optional[str] = None
    recommendation_path: Optional[str] = None
    pm_updates: List[StandupPromotionPMUpdate] = Field(default_factory=list)


class StandupPromotionResult(BaseModel):
    standup: StandupEntry
    created_cards: List[PMCard] = Field(default_factory=list)
    existing_cards: List[PMCard] = Field(default_factory=list)
