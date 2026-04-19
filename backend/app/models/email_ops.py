from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


EmailDirection = Literal["inbound", "outbound"]
EmailThreadStatus = Literal["new", "triaged", "routed", "drafted", "human_review", "sent", "waiting", "closed"]
EmailDataMode = Literal["sample_only", "provider_sync"]
EmailDraftType = Literal["acknowledge", "qualify", "schedule", "decline_or_redirect"]


class EmailMessage(BaseModel):
    id: str
    direction: EmailDirection = "inbound"
    from_address: str
    from_name: Optional[str] = None
    to_addresses: list[str] = Field(default_factory=list)
    cc_addresses: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    received_at: datetime


class EmailThread(BaseModel):
    id: str
    provider: str = "sample"
    provider_thread_id: Optional[str] = None
    provider_labels: list[str] = Field(default_factory=list)
    workspace_key: str = "shared_ops"
    lane: str = "manual_review"
    status: EmailThreadStatus = "new"
    subject: str
    from_address: str
    from_name: Optional[str] = None
    organization: Optional[str] = None
    to_addresses: list[str] = Field(default_factory=list)
    alias_hint: Optional[str] = None
    confidence_score: float = 0.0
    needs_human: bool = False
    high_value: bool = False
    high_risk: bool = False
    sla_at_risk: bool = False
    linked_opportunity_id: Optional[str] = None
    summary: Optional[str] = None
    excerpt: Optional[str] = None
    routing_reasons: list[str] = Field(default_factory=list)
    messages: list[EmailMessage] = Field(default_factory=list)
    draft_subject: Optional[str] = None
    draft_body: Optional[str] = None
    draft_type: Optional[EmailDraftType] = None
    draft_generated_at: Optional[datetime] = None
    last_message_at: datetime
    manual_workspace_key: Optional[str] = None
    manual_lane: Optional[str] = None
    manual_notes: Optional[str] = None
    last_route_source: Literal["auto", "manual"] = "auto"
    pm_card_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmailThreadListResponse(BaseModel):
    items: list[EmailThread] = Field(default_factory=list)
    total: int = 0
    needs_human_count: int = 0
    high_value_count: int = 0
    high_risk_count: int = 0
    workspace_counts: dict[str, int] = Field(default_factory=dict)
    agc_lane_counts: dict[str, int] = Field(default_factory=dict)
    data_mode: EmailDataMode = "sample_only"
    last_synced_at: Optional[datetime] = None


class EmailSyncResponse(BaseModel):
    status: str
    thread_count: int
    data_mode: EmailDataMode = "sample_only"
    seeded_samples: bool = False
    last_synced_at: Optional[datetime] = None


class EmailThreadRouteRequest(BaseModel):
    workspace_key: Optional[str] = None
    lane: Optional[str] = None
    needs_human: Optional[bool] = None
    high_value: Optional[bool] = None
    notes: Optional[str] = None


class EmailThreadDraftRequest(BaseModel):
    draft_type: Optional[EmailDraftType] = None


class EmailThreadDraftResponse(BaseModel):
    thread: EmailThread
    draft_subject: str
    draft_body: str
    draft_type: EmailDraftType


class EmailThreadEscalateRequest(BaseModel):
    reason: Optional[str] = None
    create_pm_card: bool = True


class EmailThreadEscalateResponse(BaseModel):
    thread: EmailThread
    pm_card_id: Optional[str] = None
    message: str


class EmailProviderStatusResponse(BaseModel):
    configured: bool = False
    connected: bool = False
    dependencies_ready: bool = False
    account_email: Optional[str] = None
    client_file: Optional[str] = None
    token_file: Optional[str] = None
    token_present: bool = False
    refreshable: bool = False
    sync_query: Optional[str] = None
    max_results: int = 0
    scopes: list[str] = Field(default_factory=list)
    error: Optional[str] = None
