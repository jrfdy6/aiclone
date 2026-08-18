from __future__ import annotations

import re
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


_PRIVATE_PROJECTION_KEYS = {
    "content",
    "copy_text",
    "notes",
    "private_notes",
    "comment_text",
    "dm_text",
    "audience_identities",
    "local_path",
    "absolute_path",
    "publication_url",
    "recent_publications",
    "publication_lifecycle_index",
    "raw_metrics",
    "metrics",
    "unavailable_metrics",
    "outcome_counts",
    "audience",
    "publication_id",
    "content_id",
    "content_version_sha256",
    "raw_copy",
}


def _validate_performance_projection_privacy(value: Any, *, path: str = "projection") -> None:
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key or "").strip().lower()
            if key in _PRIVATE_PROJECTION_KEYS:
                raise ValueError(f"{path} contains the private field {key!r}.")
            _validate_performance_projection_privacy(item, path=f"{path}.{key or 'field'}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_performance_projection_privacy(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.startswith(("/Users/", "file://", "~/")):
            raise ValueError(f"{path} contains an absolute private filesystem reference.")


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
    generated_at: str = Field(min_length=1, max_length=64)
    workspace: Literal["linkedin-content-os"] = "linkedin-content-os"
    source: Literal["codex_local_runner"] = "codex_local_runner"
    source_assets: dict[str, Any] | None = None
    content_reservoir: dict[str, Any] | None = None
    long_form_routes: dict[str, Any] | None = None
    publication_performance_summary: dict[str, Any] | None = None
    publication_performance_status: dict[str, Any] | None = None
    publication_performance_lifecycle: dict[str, Any] | None = None
    feezie_runtime_context: dict[str, Any] | None = None
    weekly_plan: dict[str, Any] | None = None
    persona_review_refresh: Literal["recompute_db_owned"] | None = None

    @model_validator(mode="after")
    def validate_sync(self) -> "BrainWorkspaceSnapshotSyncRequest":
        _validate_generated_at(self.generated_at)
        snapshot_values = (
            self.source_assets,
            self.content_reservoir,
            self.long_form_routes,
            self.publication_performance_summary,
            self.publication_performance_status,
            self.publication_performance_lifecycle,
            self.feezie_runtime_context,
            self.weekly_plan,
        )
        if self.persona_review_refresh is not None:
            if any(value is not None for value in snapshot_values):
                raise ValueError(
                    "persona_review_refresh is capability-exclusive and cannot be mixed with snapshots."
                )
            return self
        if not any(value is not None for value in snapshot_values):
            raise ValueError("Provide at least one allowlisted Brain workspace snapshot.")
        if self.weekly_plan is not None:
            from app.services.workspace_snapshot_service import (
                compact_and_validate_weekly_plan_projection,
            )

            try:
                self.weekly_plan = compact_and_validate_weekly_plan_projection(
                    self.weekly_plan,
                    envelope_generated_at=self.generated_at,
                )
            except ValueError as exc:
                raise ValueError("weekly_plan does not match the public-safe projection contract.") from exc
        if self.publication_performance_summary is not None:
            summary = self.publication_performance_summary
            allowed_summary_keys = {
                "schema_version",
                "generated_at",
                "workspace_key",
                "strategy_contract",
                "counts",
                "feedback_completeness",
                "rolling_topic_mix",
                "rolling_intent_mix",
                "initial_pilot",
                "primary_kpi",
                "learning_gate",
                "learning_aggregates",
                "actionable_gaps",
                "data_policy",
            }
            if (
                summary.get("schema_version") != "linkedin_publication_summary/v1"
                or summary.get("workspace_key") != "feezie-os"
                or not isinstance(summary.get("counts"), dict)
                or bool(set(summary) - allowed_summary_keys)
            ):
                raise ValueError("publication_performance_summary does not match the canonical safe summary contract.")
            _validate_performance_projection_privacy(summary, path="publication_performance_summary")
        if self.publication_performance_status is not None:
            status = self.publication_performance_status
            allowed_status_keys = {
                "schema_version",
                "generated_at",
                "workspace_key",
                "checked_at",
                "state",
                "availability",
                "projection_generated_at",
                "projection_age_hours",
                "stale_after_hours",
                "evidence",
                "source",
                "error_type",
                "data_policy",
            }
            if (
                status.get("schema_version") != "linkedin_publication_status/v1"
                or status.get("workspace_key") != "feezie-os"
                or status.get("state") not in {"fresh", "stale", "missing", "degraded", "corrupt"}
                or bool(set(status) - allowed_status_keys)
            ):
                raise ValueError("publication_performance_status does not match the canonical status contract.")
            _validate_performance_projection_privacy(status, path="publication_performance_status")
        if self.publication_performance_lifecycle is not None:
            lifecycle = self.publication_performance_lifecycle
            allowed_keys = {
                "schema_version",
                "generated_at",
                "workspace_key",
                "identity_token",
                "approval_completed",
                "publication_confirmed",
                "published_at",
                "data_policy",
            }
            if set(lifecycle) - allowed_keys:
                raise ValueError("publication_performance_lifecycle contains unsupported fields.")
            identity_token = str(lifecycle.get("identity_token") or "").strip().lower()
            if (
                lifecycle.get("schema_version") != "linkedin_publication_lifecycle_projection/v1"
                or lifecycle.get("workspace_key") != "feezie-os"
                or re.fullmatch(r"[a-f0-9]{64}", identity_token) is None
                or not isinstance(lifecycle.get("approval_completed"), bool)
                or not isinstance(lifecycle.get("publication_confirmed"), bool)
            ):
                raise ValueError("publication_performance_lifecycle does not match the exact-identity contract.")
            published_at = lifecycle.get("published_at")
            if lifecycle.get("publication_confirmed") is True:
                if lifecycle.get("approval_completed") is not True or not isinstance(published_at, str):
                    raise ValueError("Confirmed publication lifecycle requires approval and published_at.")
                _validate_generated_at(published_at)
            elif published_at is not None:
                raise ValueError("Unconfirmed publication lifecycle must not include published_at.")
            _validate_performance_projection_privacy(
                lifecycle,
                path="publication_performance_lifecycle",
            )
        if self.feezie_runtime_context is not None:
            from app.services.feezie_runtime_context_service import (
                FeezieRuntimeContextError,
                require_current_feezie_runtime_context_bundle,
            )

            try:
                validated_runtime_context = require_current_feezie_runtime_context_bundle(
                    self.feezie_runtime_context
                )
            except FeezieRuntimeContextError as exc:
                raise ValueError("feezie_runtime_context does not match the private runtime contract.") from exc
            if validated_runtime_context.get("generated_at") != self.generated_at:
                raise ValueError("feezie_runtime_context generated_at must match the sync envelope.")
            self.feezie_runtime_context = validated_runtime_context
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
