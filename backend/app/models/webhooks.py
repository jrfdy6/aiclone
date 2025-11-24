"""
Webhook Models
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WebhookEventType(str, Enum):
    PROSPECT_ADDED = "prospect_added"
    RESEARCH_COMPLETED = "research_completed"
    OUTREACH_SENT = "outreach_sent"
    CONTENT_PUBLISHED = "content_published"
    TASK_COMPLETED = "task_completed"
    AUTOMATION_TRIGGERED = "automation_triggered"


class WebhookStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class Webhook(BaseModel):
    id: str
    user_id: str
    url: str
    event_types: List[WebhookEventType]
    secret: Optional[str] = None
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: datetime
    last_triggered: Optional[datetime] = None
    failure_count: int = 0


class WebhookCreate(BaseModel):
    user_id: str
    url: HttpUrl
    event_types: List[WebhookEventType]
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    event_types: Optional[List[WebhookEventType]] = None
    status: Optional[WebhookStatus] = None
    secret: Optional[str] = None


class WebhookDelivery(BaseModel):
    id: str
    webhook_id: str
    event_type: WebhookEventType
    payload: Dict[str, Any]
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


class WebhookResponse(BaseModel):
    success: bool
    webhook: Optional[Webhook] = None
    message: Optional[str] = None


class WebhookListResponse(BaseModel):
    success: bool
    webhooks: List[Webhook]
    total: int

