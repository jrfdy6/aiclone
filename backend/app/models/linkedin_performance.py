from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


LinkedinPerformanceEventType = Literal[
    "owner_reviewed",
    "publication_confirmed",
    "metrics_24h_recorded",
    "metrics_7d_recorded",
    "owner_assessment_recorded",
]


class LinkedinMetricSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impressions: Optional[int] = Field(default=None, ge=0)
    members_reached: Optional[int] = Field(default=None, ge=0)
    reactions: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    reposts: Optional[int] = Field(default=None, ge=0)
    saves: Optional[int] = Field(default=None, ge=0)
    sends: Optional[int] = Field(default=None, ge=0)
    profile_views: Optional[int] = Field(default=None, ge=0)
    new_followers: Optional[int] = Field(default=None, ge=0)
    meaningful_comments: Optional[int] = Field(default=None, ge=0)
    target_audience_comments: Optional[int] = Field(default=None, ge=0)

class LinkedinOutcomeCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dm: Optional[int] = Field(default=None, ge=0)
    referral: Optional[int] = Field(default=None, ge=0)
    speaking: Optional[int] = Field(default=None, ge=0)
    recruiting: Optional[int] = Field(default=None, ge=0)
    partnership: Optional[int] = Field(default=None, ge=0)
    career_signal: Optional[int] = Field(default=None, ge=0)
    technology_conversation: Optional[int] = Field(default=None, ge=0)
    education_community: Optional[int] = Field(default=None, ge=0)

class LinkedinPerformanceEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: LinkedinPerformanceEventType
    idempotency_key: str = Field(min_length=3, max_length=200)
    content_id: str = Field(min_length=1, max_length=160)
    content_version_sha256: Optional[str] = Field(default=None, max_length=80)
    copy_text: Optional[str] = Field(default=None, max_length=20000)
    occurred_at: datetime
    supersedes_event_id: Optional[str] = Field(default=None, max_length=96)

    owner_decision: Optional[Literal["approve", "revise", "park", "reject"]] = None
    approval_ref: Optional[str] = Field(default=None, max_length=300)
    owner_edit_minutes: Optional[float] = Field(default=None, ge=0, le=1440)
    owner_edit_ratio: Optional[float] = Field(default=None, ge=0, le=1)

    confirmed: Optional[bool] = None
    publication_url: Optional[str] = Field(default=None, max_length=1000)
    published_at: Optional[datetime] = None
    confirmation_method: Optional[
        Literal["manual_url", "opened_post", "screenshot", "authorized_export"]
    ] = None
    evidence_ref: Optional[str] = Field(default=None, max_length=300)
    pillar_id: Optional[str] = Field(default=None, max_length=80)
    intent: Optional[str] = Field(default=None, max_length=40)
    treatment: Optional[str] = Field(default=None, max_length=120)
    career_signal: Optional[str] = Field(default=None, max_length=80)
    employer_safety: Optional[str] = Field(default=None, max_length=80)
    proof_posture: Optional[str] = Field(default=None, max_length=80)
    hook_family: Optional[str] = Field(default=None, max_length=120)
    format: Optional[str] = Field(default=None, max_length=80)
    audience: list[str] = Field(default_factory=list, max_length=12)
    experiment_id: Optional[str] = Field(default=None, max_length=120)

    metrics: Optional[LinkedinMetricSnapshot] = None
    unavailable_metrics: list[str] = Field(default_factory=list, max_length=30)
    metric_source: Optional[Literal["manual_linkedin_analytics", "authorized_export"]] = None

    meaningful_target_conversations: Optional[int] = Field(default=None, ge=0)
    outcome_counts: Optional[LinkedinOutcomeCounts] = None
    sounded_like_me: Optional[Literal["yes", "mixed", "no"]] = None
    quality_flags: list[
        Literal["too_generic", "too_safe", "too_exposed", "wrong_audience"]
    ] = Field(default_factory=list)
    follow_up: Optional[Literal["reuse", "iterate", "retire", "none"]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class LinkedinPerformanceLocalActionRequest(LinkedinPerformanceEventCreate):
    """Privacy-minimized event accepted by the Railway-to-local action queue.

    Raw copy and private notes must never become durable PM-card payloads on
    Railway. The browser computes the exact copy digest before submission; the
    local runner then applies the same canonical ledger validation as the CLI.
    """

    content_version_sha256: str = Field(
        min_length=64,
        max_length=71,
        pattern=r"^(?:sha256:)?[A-Fa-f0-9]{64}$",
    )
    copy_text: None = None
    notes: None = None

    @model_validator(mode="after")
    def validate_queue_ready_event(self):
        if self.event_type == "owner_reviewed":
            if self.owner_decision is None:
                raise ValueError("owner_reviewed requires owner_decision.")
        elif self.event_type == "publication_confirmed":
            required = {
                "confirmed": self.confirmed is True,
                "publication_url": bool(self.publication_url),
                "published_at": self.published_at is not None,
                "confirmation_method": self.confirmation_method is not None,
                "pillar_id": bool(self.pillar_id),
                "intent": self.intent in {"value", "invitation", "personal"},
                "treatment": bool(self.treatment),
                "career_signal": self.career_signal in {"education_anchor", "bridge", "tech_proof"},
                "employer_safety": self.employer_safety in {"pass", "owner_review_required"},
                "proof_posture": self.proof_posture
                in {"verified_public", "verified_private_anonymize", "owner_confirmation_required", "principle_only"},
                "audience": bool(self.audience),
            }
            missing = [name for name, present in required.items() if not present]
            if missing:
                raise ValueError(
                    "publication_confirmed is not queue-ready; missing or unsafe fields: " + ", ".join(missing) + "."
                )
            if self.published_at and self.published_at > self.occurred_at:
                raise ValueError("published_at cannot be later than occurred_at.")
        elif self.event_type in {"metrics_24h_recorded", "metrics_7d_recorded"}:
            metric_values = self.metrics.model_dump().values() if self.metrics is not None else ()
            if not any(value is not None for value in metric_values) and not self.unavailable_metrics:
                raise ValueError("Metrics require at least one value or unavailable_metrics.")
            if self.metric_source is None:
                raise ValueError("Metrics require metric_source.")
        else:
            has_assessment = any(
                (
                    self.meaningful_target_conversations is not None,
                    self.outcome_counts is not None,
                    self.sounded_like_me is not None,
                    bool(self.quality_flags),
                    self.follow_up is not None,
                )
            )
            if not has_assessment:
                raise ValueError("owner_assessment_recorded requires at least one qualitative or outcome field.")
        return self
