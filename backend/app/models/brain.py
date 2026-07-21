from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.persona_promotion_targets import validate_persona_promotion_target


def _validate_generated_at(value: str) -> datetime:
    text = str(value or "").strip()
    if "T" not in text:
        raise ValueError("Provide generated_at as a timezone-aware ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Provide generated_at as a timezone-aware ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Provide generated_at as a timezone-aware ISO-8601 timestamp.")
    return parsed


class BrainLongFormIngestRequest(BaseModel):
    url: str | None = Field(default=None, max_length=2_048)
    title: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=8_000)
    notes: str | None = Field(default=None, max_length=20_000)
    transcript_text: str | None = Field(default=None, max_length=200_000)
    source_type: str | None = Field(default=None, max_length=120)
    author: str | None = Field(default=None, max_length=300)
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_source(self) -> "BrainLongFormIngestRequest":
        if not ((self.url or "").strip() or (self.transcript_text or "").strip() or (self.notes or "").strip()):
            raise ValueError("Provide a url, transcript_text, or notes.")
        return self


class BrainYouTubeWatchlistIngestRequest(BaseModel):
    url: str = Field(max_length=2_048)
    title: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=8_000)
    author: str | None = Field(default=None, max_length=300)
    channel_name: str | None = Field(default=None, max_length=300)
    priority_lane: str | None = Field(default=None, max_length=120)
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_url(self) -> "BrainYouTubeWatchlistIngestRequest":
        if not (self.url or "").strip():
            raise ValueError("Provide url.")
        return self


class BrainYouTubeWatchlistSnapshotRequest(BaseModel):
    schema_version: Literal["youtube_watchlist/v1"] = "youtube_watchlist/v1"
    generated_at: str
    workspace: Literal["linkedin-content-os"] = "linkedin-content-os"
    data_mode: Literal["local_runner_refresh", "live_refresh"] = "local_runner_refresh"
    runtime: dict[str, Any] = Field(default_factory=dict)
    auto_ingest: dict[str, Any] = Field(default_factory=dict)
    channels: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    counts: dict[str, Any] = Field(default_factory=dict)
    pending_transcript_backfill: list[dict[str, Any]] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "BrainYouTubeWatchlistSnapshotRequest":
        if not (self.generated_at or "").strip():
            raise ValueError("Provide generated_at.")
        _validate_generated_at(self.generated_at)
        video_count = sum(
            len(channel.get("videos") or [])
            for channel in self.channels
            if isinstance(channel, dict) and isinstance(channel.get("videos"), list)
        )
        if video_count > 1_000:
            raise ValueError("YouTube watchlist snapshot exceeds the 1000-video limit.")
        return self


class BrainWorkspaceSnapshotSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brain_workspace_snapshots/v1"] = "brain_workspace_snapshots/v1"
    generated_at: str
    workspace: Literal["linkedin-content-os"] = "linkedin-content-os"
    source: Literal["codex_local_runner"] = "codex_local_runner"
    source_assets: dict[str, Any] | None = None
    content_reservoir: dict[str, Any] | None = None
    long_form_routes: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_sync(self) -> "BrainWorkspaceSnapshotSyncRequest":
        _validate_generated_at(self.generated_at)
        if not any(
            value is not None
            for value in (
                self.source_assets,
                self.content_reservoir,
                self.long_form_routes,
            )
        ):
            raise ValueError("Provide at least one allowlisted Brain workspace snapshot.")
        return self


BrainSignalReviewStatus = Literal["new", "in_review", "reviewed", "routed", "ignored"]
BrainSignalRouteTarget = Literal["source_only", "canonical_memory", "persona_canon", "standup", "pm", "workspace_local", "ignore"]


class BrainSignal(BaseModel):
    id: str
    source_kind: str
    source_ref: str | None = None
    source_workspace_key: str = "shared_ops"
    raw_summary: str
    digest: str | None = None
    signal_types: list[str] = Field(default_factory=list)
    durability: str = "unknown"
    confidence: str = "unknown"
    actionability: str = "unknown"
    identity_relevance: str = "unknown"
    workspace_candidates: list[str] = Field(default_factory=list)
    executive_interpretation: dict[str, str] = Field(default_factory=dict)
    route_decision: dict[str, Any] = Field(default_factory=dict)
    review_status: BrainSignalReviewStatus = "new"
    created_at: datetime
    updated_at: datetime


class BrainSignalSnapshotRequest(BaseModel):
    schema_version: Literal["brain_signals/v1"] = "brain_signals/v1"
    generated_at: str
    source: Literal["codex_local_runner"] = "codex_local_runner"
    count: int = Field(ge=0, le=5_000)
    signals: list[BrainSignal] = Field(default_factory=list, max_length=5_000)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "BrainSignalSnapshotRequest":
        _validate_generated_at(self.generated_at)
        if self.count != len(self.signals):
            raise ValueError("Brain signal snapshot count must match signals length.")
        return self


class BrainSignalSnapshotChunkRequest(BaseModel):
    schema_version: Literal["brain_signals_chunk/v1"] = "brain_signals_chunk/v1"
    snapshot_id: str = Field(min_length=1, max_length=64)
    generated_at: str
    source: Literal["codex_local_runner"] = "codex_local_runner"
    chunk_index: int = Field(ge=0, lt=100)
    chunk_count: int = Field(ge=1, le=100)
    total_count: int = Field(ge=0, le=5_000)
    signals: list[BrainSignal] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_chunk(self) -> "BrainSignalSnapshotChunkRequest":
        try:
            UUID(self.snapshot_id)
        except ValueError as exc:
            raise ValueError("Provide snapshot_id as a UUID.") from exc
        _validate_generated_at(self.generated_at)
        if self.chunk_index >= self.chunk_count:
            raise ValueError("Brain signal chunk_index must be below chunk_count.")
        if self.total_count == 0 and self.signals:
            raise ValueError("An empty Brain signal snapshot cannot contain chunk signals.")
        return self


class BrainSignalSnapshotCommitRequest(BaseModel):
    schema_version: Literal["brain_signals_manifest/v1"] = "brain_signals_manifest/v1"
    snapshot_id: str = Field(min_length=1, max_length=64)
    generated_at: str
    source: Literal["codex_local_runner"] = "codex_local_runner"
    chunk_count: int = Field(ge=1, le=100)
    total_count: int = Field(ge=0, le=5_000)

    @model_validator(mode="after")
    def validate_manifest(self) -> "BrainSignalSnapshotCommitRequest":
        try:
            UUID(self.snapshot_id)
        except ValueError as exc:
            raise ValueError("Provide snapshot_id as a UUID.") from exc
        _validate_generated_at(self.generated_at)
        return self


class BrainSignalCreateRequest(BaseModel):
    source_kind: str
    source_ref: str | None = None
    source_workspace_key: str = "shared_ops"
    raw_summary: str
    digest: str | None = None
    signal_types: list[str] = Field(default_factory=list)
    durability: str = "unknown"
    confidence: str = "unknown"
    actionability: str = "unknown"
    identity_relevance: str = "unknown"
    workspace_candidates: list[str] = Field(default_factory=list)
    executive_interpretation: dict[str, str] = Field(default_factory=dict)
    route_decision: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_signal_content(self) -> "BrainSignalCreateRequest":
        if not (self.source_kind or "").strip():
            raise ValueError("Provide source_kind.")
        if not (self.raw_summary or "").strip() and not (self.digest or "").strip():
            raise ValueError("Provide raw_summary or digest.")
        return self


class BrainSignalReviewRequest(BaseModel):
    digest: str | None = None
    signal_types: list[str] | None = None
    durability: str | None = None
    confidence: str | None = None
    actionability: str | None = None
    identity_relevance: str | None = None
    workspace_candidates: list[str] | None = None
    executive_interpretation: dict[str, str] | None = None
    route_decision: dict[str, Any] | None = None
    review_status: BrainSignalReviewStatus | None = None

    @model_validator(mode="after")
    def ensure_review_update(self) -> "BrainSignalReviewRequest":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Provide at least one review update.")
        return self


class BrainSignalRouteRequest(BaseModel):
    route: BrainSignalRouteTarget
    workspace_key: str = Field(default="shared_ops", min_length=1, max_length=64)
    summary: str | None = Field(default=None, max_length=2_000)
    route_reason: str | None = Field(default=None, max_length=2_000)
    canonical_memory_targets: list[Literal["persistent_state", "learnings", "chronicle"]] = Field(
        default_factory=list,
        max_length=3,
    )
    standup_kind: str = Field(default="auto", max_length=80)
    pm_title: str | None = Field(default=None, max_length=200)
    executive_interpretation: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_route_content(self) -> "BrainSignalRouteRequest":
        if self.route != "ignore" and not (self.summary or self.route_reason or "").strip():
            raise ValueError("Provide summary or route_reason.")
        if self.route == "pm" and not (self.pm_title or "").strip():
            raise ValueError("Provide pm_title for PM routes.")
        if self.route == "canonical_memory" and not self.canonical_memory_targets:
            raise ValueError("Select at least one canonical memory target.")
        if self.route != "canonical_memory" and self.canonical_memory_targets:
            raise ValueError("canonical_memory_targets are only valid for canonical_memory routes.")
        if len(self.executive_interpretation) > 12 or any(
            len(str(key)) > 120 or len(str(value)) > 2_000
            for key, value in self.executive_interpretation.items()
        ):
            raise ValueError("executive_interpretation exceeds the bounded route limit.")
        return self


class BrainSignalRouteEffectRequest(BaseModel):
    card_id: str = Field(min_length=1, max_length=64)
    signal: BrainSignal
    route: BrainSignalRouteRequest


class PromotionItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    kind: Literal["talking_point", "framework", "anecdote", "phrase_candidate", "stat"]
    label: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20_000)
    evidence: str | None = Field(default=None, max_length=8_000)
    targetFile: str | None = Field(default=None, max_length=500)
    artifactSummary: str | None = Field(default=None, max_length=4_000)
    artifactKind: str | None = Field(default=None, max_length=120)
    artifactRef: str | None = Field(default=None, max_length=1_000)
    deltaSummary: str | None = Field(default=None, max_length=4_000)
    reviewInterpretation: str | None = Field(default=None, max_length=4_000)
    capabilitySignal: str | None = Field(default=None, max_length=2_000)
    positioningSignal: str | None = Field(default=None, max_length=2_000)
    leverageSignal: str | None = Field(default=None, max_length=2_000)
    proofSignal: str | None = Field(default=None, max_length=2_000)
    proofStrength: Literal["none", "weak", "strong"] = "none"
    gateDecision: Literal["pending", "allow", "hold", "block"] = "pending"
    gateReason: str | None = Field(default=None, max_length=2_000)

    @field_validator("targetFile")
    @classmethod
    def validate_target_file(cls, value: str | None) -> str | None:
        return validate_persona_promotion_target(value, allow_none=True)


class BrainPersonaReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["reviewed", "approved"] = "reviewed"
    response_kind: Literal["agree", "disagree", "nuance", "story", "language"] = "nuance"
    reflection_excerpt: str = Field(min_length=1, max_length=20_000)
    resolution_capture_id: str | None = Field(default=None, max_length=128)
    selected_promotion_items: list[PromotionItemPayload] = Field(default_factory=list, max_length=25)

    @model_validator(mode="after")
    def ensure_reflection_and_selection(self) -> "BrainPersonaReviewRequest":
        if not (self.reflection_excerpt or "").strip():
            raise ValueError("Provide reflection_excerpt.")
        if self.mode == "approved" and not self.selected_promotion_items:
            raise ValueError("Select at least one promotion item before approving.")
        return self


class BrainPersonaRerouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_file: str = Field(min_length=1, max_length=500)

    @field_validator("target_file")
    @classmethod
    def ensure_target_file(cls, value: str) -> str:
        target_file = validate_persona_promotion_target(value)
        if target_file is None:  # pragma: no cover - required targets never return None
            raise ValueError("Provide target_file.")
        return target_file


class BrainSystemRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reflection_excerpt: str | None = Field(default=None, max_length=20_000)
    selected_promotion_items: list[PromotionItemPayload] = Field(default_factory=list, max_length=25)
    workspace_key: str | None = Field(default="shared_ops", max_length=64)
    workspace_keys: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(default_factory=list, max_length=12)
    canonical_memory_targets: list[Literal["persistent_state", "learnings", "chronicle"]] = Field(
        default_factory=list,
        max_length=3,
    )
    route_to_standup: bool = False
    standup_kind: Literal["auto", "executive_ops", "operations", "weekly_review", "saturday_vision", "workspace_sync"] = "auto"
    route_to_pm: bool = False
    pm_title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def ensure_route_target(self) -> "BrainSystemRouteRequest":
        if not self.canonical_memory_targets and not self.route_to_standup and not self.route_to_pm:
            raise ValueError("Select at least one route target.")
        normalized_workspace_keys = [value.strip() for value in self.workspace_keys if (value or "").strip()]
        if not normalized_workspace_keys and not (self.workspace_key or "").strip():
            raise ValueError("Provide at least one workspace target.")
        if not self.route_to_pm and (self.pm_title or "").strip():
            raise ValueError("pm_title is only valid when route_to_pm is enabled.")
        if not self.route_to_standup and self.standup_kind != "auto":
            raise ValueError("standup_kind is only valid when route_to_standup is enabled.")
        self.workspace_keys = normalized_workspace_keys
        return self


class BrainCanonicalMemorySyncStatusRequest(BaseModel):
    generated_at: str | None = None
    source: str = "brain_canonical_memory_sync"
    sync_live: bool = True
    queued_route_count: int = 0
    processed_count: int = 0
    artifact_paths: list[str] = []
    processed_items: list[dict[str, Any]] = []


class BrainOperatorStorySignalsSyncRequest(BaseModel):
    generated_at: str | None = None
    source: str = "operator_story_signal_distiller"
    workspace_key: str = "linkedin-content-os"
    signal_count: int = 0
    source_paths: dict[str, str] = {}
    counts: dict[str, Any] = {}
    signals: list[dict[str, Any]] = []


class BrainContentSafeOperatorLessonsSyncRequest(BaseModel):
    generated_at: str | None = None
    source: str = "content_safe_operator_lesson_distiller"
    workspace_key: str = "linkedin-content-os"
    lesson_count: int = 0
    source_snapshot_type: str = "operator_story_signals"
    source_generated_at: str | None = None
    counts: dict[str, Any] = {}
    lessons: list[dict[str, Any]] = []
