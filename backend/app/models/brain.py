from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class BrainLongFormIngestRequest(BaseModel):
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    notes: str | None = None
    transcript_text: str | None = None
    source_type: str | None = None
    author: str | None = None
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_source(self) -> "BrainLongFormIngestRequest":
        if not ((self.url or "").strip() or (self.transcript_text or "").strip() or (self.notes or "").strip()):
            raise ValueError("Provide a url, transcript_text, or notes.")
        return self


class BrainYouTubeWatchlistIngestRequest(BaseModel):
    url: str
    title: str | None = None
    summary: str | None = None
    author: str | None = None
    channel_name: str | None = None
    priority_lane: str | None = None
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_url(self) -> "BrainYouTubeWatchlistIngestRequest":
        if not (self.url or "").strip():
            raise ValueError("Provide url.")
        return self


class PromotionItemPayload(BaseModel):
    id: str
    kind: Literal["talking_point", "framework", "anecdote", "phrase_candidate", "stat"]
    label: str
    content: str
    evidence: str | None = None
    targetFile: str | None = None
    artifactSummary: str | None = None
    artifactKind: str | None = None
    artifactRef: str | None = None
    deltaSummary: str | None = None
    reviewInterpretation: str | None = None
    capabilitySignal: str | None = None
    positioningSignal: str | None = None
    leverageSignal: str | None = None
    proofSignal: str | None = None
    proofStrength: Literal["none", "weak", "strong"] = "none"
    gateDecision: Literal["pending", "allow", "hold", "block"] = "pending"
    gateReason: str | None = None


class BrainPersonaReviewRequest(BaseModel):
    mode: Literal["reviewed", "approved"] = "reviewed"
    response_kind: Literal["agree", "disagree", "nuance", "story", "language"] = "nuance"
    reflection_excerpt: str
    resolution_capture_id: str | None = None
    selected_promotion_items: list[PromotionItemPayload] = []

    @model_validator(mode="after")
    def ensure_reflection_and_selection(self) -> "BrainPersonaReviewRequest":
        if not (self.reflection_excerpt or "").strip():
            raise ValueError("Provide reflection_excerpt.")
        if self.mode == "approved" and not self.selected_promotion_items:
            raise ValueError("Select at least one promotion item before approving.")
        return self


class BrainPersonaRerouteRequest(BaseModel):
    target_file: str

    @model_validator(mode="after")
    def ensure_target_file(self) -> "BrainPersonaRerouteRequest":
        if not (self.target_file or "").strip():
            raise ValueError("Provide target_file.")
        return self


class BrainSystemRouteRequest(BaseModel):
    reflection_excerpt: str | None = None
    selected_promotion_items: list[PromotionItemPayload] = []
    workspace_key: str | None = "shared_ops"
    workspace_keys: list[str] = []
    canonical_memory_targets: list[Literal["persistent_state", "learnings", "chronicle"]] = []
    route_to_standup: bool = False
    standup_kind: Literal["auto", "executive_ops", "operations", "weekly_review", "saturday_vision", "workspace_sync"] = "auto"
    route_to_pm: bool = False
    pm_title: str | None = None

    @model_validator(mode="after")
    def ensure_route_target(self) -> "BrainSystemRouteRequest":
        if not self.canonical_memory_targets and not self.route_to_standup and not self.route_to_pm:
            raise ValueError("Select at least one route target.")
        normalized_workspace_keys = [value.strip() for value in self.workspace_keys if (value or "").strip()]
        if not normalized_workspace_keys and not (self.workspace_key or "").strip():
            raise ValueError("Provide at least one workspace target.")
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
