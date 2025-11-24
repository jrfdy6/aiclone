"""
Enhanced Playbooks Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Playbook(BaseModel):
    """Playbook model"""
    id: str
    name: str
    description: str
    category: str
    prompts: List[Dict[str, str]] = Field(default_factory=list)
    is_favorite: bool = False
    usage_count: int = 0
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaybookExecution(BaseModel):
    """Playbook execution record"""
    id: str
    playbook_id: str
    user_id: str
    input: str
    output: str
    executed_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaybookListResponse(BaseModel):
    """Response for listing playbooks"""
    success: bool
    playbooks: List[Playbook]
    total: int


class PlaybookResponse(BaseModel):
    """Response for single playbook"""
    success: bool
    playbook: Playbook


class PlaybookRunRequest(BaseModel):
    """Request to run a playbook"""
    user_id: str = Field(..., description="User identifier")
    input: str = Field(..., description="Input text for the playbook")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PlaybookRunResponse(BaseModel):
    """Response from running a playbook"""
    success: bool
    execution_id: str
    output: str
    playbook_id: str
    playbook_name: str


class ExecutionListResponse(BaseModel):
    """Response for listing executions"""
    success: bool
    executions: List[PlaybookExecution]
    total: int

