from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeDoc(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source_path: str
    updated_at: Optional[datetime] = None


class Playbook(BaseModel):
    id: str
    name: str
    category: str
    steps: List[str] = Field(default_factory=list)
    sop_path: str
    linked_docs: List[str] = Field(default_factory=list)
    last_run: Optional[datetime] = None


class ProspectContact(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class Prospect(BaseModel):
    id: str
    name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    contact: ProspectContact = Field(default_factory=ProspectContact)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogEntry(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = "INFO"
    component: str
    message: str
    context: Optional[dict] = None


class IngestJob(BaseModel):
    id: str
    folder_id: Optional[str] = None
    target_collection: str = "knowledge"
    tags: List[str] = Field(default_factory=list)
    status: str = "queued"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    processed: int = 0
    errors: List[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    folder_id: Optional[str] = None
    target_collection: str = "knowledge"
    tags: List[str] = Field(default_factory=list)
    dry_run: bool = False


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    source: str = "google"
    attendees: List[str] = Field(default_factory=list)
    status: str = "confirmed"


class NotificationRequest(BaseModel):
    channel: str = "discord"
    template: str
    payload: dict = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    status: str
    detail: str


class CaptureRequest(BaseModel):
    text: str
    source: str = "manual"
    topics: List[str] = Field(default_factory=list)
    importance: int = Field(default=2, ge=1, le=3)
    markdown_path: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    expires_in_hours: Optional[int] = None


class CaptureResponse(BaseModel):
    capture_id: str
    chunk_ids: List[str]
    chunk_count: int
    expires_at: Optional[datetime] = None
