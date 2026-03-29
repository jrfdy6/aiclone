from __future__ import annotations

from typing import Literal

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
