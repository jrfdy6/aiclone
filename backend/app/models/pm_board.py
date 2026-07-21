from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


PMExecutionResultText = Annotated[str, Field(min_length=1, max_length=4_000)]
PMExecutionArtifactPath = Annotated[str, Field(min_length=1, max_length=4_096)]


class PMExecutionResultCommitRequest(BaseModel):
    """Narrow, idempotent result operation accepted from a claimed local runner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_execution_result_commit/v1"] = "pm_execution_result_commit/v1"
    card_id: UUID
    claim_id: UUID
    worker_id: str = Field(min_length=1, max_length=200)
    result_id: UUID
    runner_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    author_agent: str = Field(min_length=1, max_length=120)
    created_at: datetime
    workspace_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=300)
    status: Literal["review", "done", "blocked"]
    summary: str = Field(min_length=1, max_length=6_000)
    decisions: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    blockers: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    learnings: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    outcomes: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    follow_ups: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    host_actions: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    host_action_proof: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    project_updates: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    memory_promotions: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    persistent_state_updates: list[PMExecutionResultText] = Field(default_factory=list, max_length=64)
    artifacts: list[PMExecutionArtifactPath] = Field(default_factory=list, max_length=100)
    result_path: PMExecutionArtifactPath
    memo_path: PMExecutionArtifactPath
    work_order_path: PMExecutionArtifactPath
    workspace_result_path: PMExecutionArtifactPath | None = None

    @model_validator(mode="after")
    def validate_commit(self) -> "PMExecutionResultCommitRequest":
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware.")
        if len(self.model_dump_json().encode("utf-8")) > 768 * 1024:
            raise ValueError("Execution result commit exceeds the 768 KB limit.")
        return self


class PMExecutionClaimRequest(BaseModel):
    """Exact execution identity a local runner must atomically claim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_execution_claim/v1"] = "pm_execution_claim/v1"
    claim_id: UUID
    worker_id: str = Field(min_length=1, max_length=200)
    runner_id: Literal["codex-workspace-execution"] = "codex-workspace-execution"
    workspace_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    execution_mode: str = Field(min_length=1, max_length=120)
    target_agent: str = Field(min_length=1, max_length=200)
    execution_packet_path: PMExecutionArtifactPath


class PMExecutionClaimResult(BaseModel):
    card: PMCard
    disposition: Literal["claimed", "already_claimed"]


class PMExecutionResultCommitResult(BaseModel):
    card: PMCard
    disposition: Literal["committed", "already_committed"]
    auto_progressed: bool = False


class PMStaleExecutionClaimRecoveryRequest(BaseModel):
    """Server-age-gated recovery request for claims owned by one local worker."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_stale_execution_claim_recovery/v1"] = "pm_stale_execution_claim_recovery/v1"
    worker_id: str = Field(min_length=1, max_length=200)
    stale_after_seconds: int = Field(default=1_800, ge=300, le=86_400)
    limit: int = Field(default=50, ge=1, le=250)


class PMStaleExecutionClaimRecoveryItem(BaseModel):
    card_id: str
    claim_id: str
    disposition: Literal[
        "requeued_brain_action",
        "surfaced_manual_review",
        "quarantined_invalid_signature",
        "cas_miss",
    ]
    action: str | None = None
    reason: str


class PMStaleExecutionClaimRecoveryResult(BaseModel):
    schema_version: Literal["pm_stale_execution_claim_recovery_result/v1"] = (
        "pm_stale_execution_claim_recovery_result/v1"
    )
    worker_id: str
    stale_after_seconds: int
    cutoff_at: datetime
    examined_count: int = 0
    requeued_count: int = 0
    surfaced_count: int = 0
    quarantined_count: int = 0
    cas_miss_count: int = 0
    items: list[PMStaleExecutionClaimRecoveryItem] = Field(default_factory=list)


class ExecutionQueueEntry(BaseModel):
    card_id: str
    title: str
    workspace_key: str = "shared_ops"
    pm_status: str = "todo"
    execution_state: str = "ready"
    manager_agent: str = "Jean-Claude"
    target_agent: str = "Jean-Claude"
    workspace_agent: Optional[str] = None
    execution_mode: str = "direct"
    requested_by: Optional[str] = None
    assigned_runner: Optional[str] = None
    lane: str = "codex"
    reason: Optional[str] = None
    source: Optional[str] = None
    link_type: Optional[str] = None
    front_door_agent: Optional[str] = None
    trigger_key: Optional[str] = None
    manager_attention_required: bool = False
    executor_status: Optional[str] = None
    executor_worker_id: Optional[str] = None
    execution_packet_path: Optional[str] = None
    sop_path: Optional[str] = None
    briefing_path: Optional[str] = None
    latest_result_status: Optional[str] = None
    latest_result_summary: Optional[str] = None
    latest_result_artifacts: list[str] = Field(default_factory=list)
    execution_gate_decision: Literal["AUTO_EXECUTE", "REQUIRE_APPROVAL"] = "REQUIRE_APPROVAL"
    execution_gate_reason: Optional[str] = None
    execution_gate_risk_class: str = "unknown"
    execution_gate_risk_factors: list[str] = Field(default_factory=list)
    execution_gate_approval_state: Literal["not_required", "missing", "stale", "approved"] = "missing"
    execution_gate_intent_hash: Optional[str] = None
    execution_gate_authorization_current: bool = False
    queued_at: Optional[datetime] = None
    last_transition_at: Optional[datetime] = None


class PMCardDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_agent: Optional[str] = None
    lane: str = "codex"
    requested_by: str = "Jean-Claude"
    execution_state: str = "queued"
    approval_confirmed: bool = False
    approval_reason: Optional[str] = Field(default=None, max_length=2_000)


class PMCardDispatchResult(BaseModel):
    card: PMCard
    queue_entry: ExecutionQueueEntry


class PMExecutionGateBackfillRequest(BaseModel):
    """Preview or persist the current execution policy on active historical cards."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["pm_execution_gate_backfill/v1"] = "pm_execution_gate_backfill/v1"
    mode: Literal["preview", "apply"] = "preview"
    confirmed: Literal[True] | None = None
    workspace_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    after_card_id: UUID | None = None
    limit: int = Field(default=100, ge=1, le=250)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "PMExecutionGateBackfillRequest":
        if self.mode == "apply" and self.confirmed is not True:
            raise ValueError("Apply mode requires confirmed=true.")
        if self.mode == "preview" and self.confirmed is not None:
            raise ValueError("Preview mode must not include confirmation.")
        return self


class PMExecutionGateBackfillItem(BaseModel):
    card_id: str
    title: str
    workspace_key: str
    status: str
    action: Literal[
        "would_update",
        "updated",
        "unchanged",
        "skipped_active_claim",
        "skipped_manual_reapproval",
        "cas_miss",
    ]
    decision: Literal["AUTO_EXECUTE", "REQUIRE_APPROVAL"]
    approval_state: Literal["not_required", "missing", "stale", "approved"]
    risk_factors: list[str] = Field(default_factory=list)
    reason: str | None = None
    intent_hash: str
    would_become_runnable: bool = False


class PMExecutionGateBackfillResult(BaseModel):
    schema_version: Literal["pm_execution_gate_backfill_result/v1"] = "pm_execution_gate_backfill_result/v1"
    mode: Literal["preview", "apply"]
    policy_version: int
    workspace_key: str | None = None
    scanned_count: int = 0
    candidate_count: int = 0
    classified_auto_execute_count: int = 0
    classified_require_approval_count: int = 0
    would_become_runnable_count: int = 0
    updated_count: int = 0
    already_current_count: int = 0
    active_claim_skipped_count: int = 0
    manual_reapproval_count: int = 0
    cas_miss_count: int = 0
    has_more: bool = False
    next_after_card_id: UUID | None = None
    items: list[PMExecutionGateBackfillItem] = Field(default_factory=list)


class PMWorkRequestCreate(BaseModel):
    """A deliberately approved request from the authenticated executive surface."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    workspace_key: str = "shared_ops"
    outcome: str = Field(min_length=3, max_length=4000)
    context: Optional[str] = Field(default=None, max_length=6000)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=6)
    artifacts_expected: list[str] = Field(default_factory=list, max_length=6)
    approved_for_queue: Literal[True]


class PMWorkRequestRouting(BaseModel):
    workspace_key: str
    manager_agent: str
    target_agent: str
    workspace_agent: Optional[str] = None
    execution_mode: str


class PMWorkRequestResult(BaseModel):
    card: PMCard
    queue_entry: ExecutionQueueEntry
    routing: PMWorkRequestRouting
    disposition: Literal["queued", "already_active", "approval_required"] = "queued"


PMCardActionType = Literal["approve", "return", "blocked"]
PMCardResolutionMode = Literal["close_only", "close_and_spawn_next"]


class PMHostActionProofValue(BaseModel):
    kind: Optional[str] = None
    label: Optional[str] = None
    requirement: Optional[str] = None
    value: Optional[str] = None


class PMCardActionRequest(BaseModel):
    action: PMCardActionType
    requested_by: str = "Neo"
    reason: Optional[str] = None
    resolution_mode: Optional[PMCardResolutionMode] = None
    next_title: Optional[str] = None
    next_reason: Optional[str] = None
    proof_items: list[str] = Field(default_factory=list)
    proof_field_values: list[PMHostActionProofValue] = Field(default_factory=list)


class PMCardActionResult(BaseModel):
    card: PMCard
    queue_entry: Optional[ExecutionQueueEntry] = None
    successor_card: Optional[PMCard] = None


class PMHostActionRunRequest(BaseModel):
    requested_by: str = "Neo"
    reason: Optional[str] = None
    proof_items: list[str] = Field(default_factory=list)
    proof_field_values: list[PMHostActionProofValue] = Field(default_factory=list)
    scheduled_at: Optional[str] = None
    asset_decision: Optional[str] = None
    confirmation_path: Optional[str] = None
    queue_id: Optional[str] = None
