from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.models import PMCard
from app.services.workspace_registry_service import canonicalize_workspace_key


CLOSED_STATUSES = {"done", "completed", "closed", "cancelled", "canceled", "archived"}
ACTIVE_STATUSES = {"todo", "queued", "running", "in_progress", "review", "blocked", "failed"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _text(value)
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    # A timestamp without an offset has no evidenced relationship to the
    # canonical ai_clone_utc clock.  Never reinterpret host-local wall time as
    # UTC merely to make a card look fresh.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _has_timestamp_value(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    return bool(_text(value))


def _evidence_at(card: PMCard) -> tuple[datetime | None, str | None]:
    payload = _dict(card.payload)
    execution = _dict(payload.get("execution"))
    latest_result = _dict(payload.get("latest_execution_result"))
    candidates = (
        ("execution.last_transition_at", execution.get("last_transition_at")),
        ("latest_execution_result.created_at", latest_result.get("created_at")),
        ("latest_execution_result.completed_at", latest_result.get("completed_at")),
        ("source_created_at", payload.get("source_created_at")),
        ("captured_at", payload.get("captured_at")),
        ("scheduled_for", payload.get("scheduled_for")),
        ("created_at", getattr(card, "created_at", None)),
    )
    for field, candidate in candidates:
        if not _has_timestamp_value(candidate):
            continue
        parsed = _parse_datetime(candidate)
        if parsed is None:
            return None, f"invalid_semantic_timestamp:{field}"
        return parsed, None
    updated_at = getattr(card, "updated_at", None)
    if _has_timestamp_value(updated_at):
        parsed = _parse_datetime(updated_at)
        if parsed is None:
            return None, "invalid_semantic_timestamp:updated_at"
        return parsed, None
    return None, "missing_semantic_timestamp"


def _first_semantic_timestamp(
    candidates: tuple[tuple[str, Any], ...],
) -> tuple[datetime | None, str | None]:
    for field, candidate in candidates:
        if not _has_timestamp_value(candidate):
            continue
        parsed = _parse_datetime(candidate)
        if parsed is None:
            return None, f"invalid_semantic_timestamp:{field}"
        return parsed, None
    return None, None


def classify_pm_card(card: PMCard, *, now: datetime | None = None) -> dict[str, Any]:
    """Build a non-mutating operator truth view for one PM card."""

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("PM truth observation must include a timezone offset.")
    current_time = current_time.astimezone(timezone.utc)
    payload = _dict(card.payload)
    policy = _dict(payload.get("pm_review_policy"))
    execution = _dict(payload.get("execution"))
    latest_result = _dict(payload.get("latest_execution_result"))
    activation = _dict(payload.get("host_action_activation")) or _dict(policy.get("host_action_activation"))
    status = _text(card.status).lower() or "todo"
    workspace_key = canonicalize_workspace_key(
        payload.get("workspace_key") or payload.get("workspace") or payload.get("belongs_to_workspace"),
        default="shared_ops",
    )

    attention = _text(policy.get("attention_class")).lower() or "informational"
    if attention == "fyi":
        attention = "informational"
    attention_reason = _text(policy.get("attention_reason"))
    source = _text(getattr(card, "source", "")).lower()
    link_type = _text(getattr(card, "link_type", "")).lower()
    owner_review = _dict(payload.get("owner_review"))
    if attention == "informational" and (
        link_type == "owner_review"
        or "owner-review" in source
        or _text(owner_review.get("sync_state")).lower() == "pending_owner_review"
    ):
        attention = "needs_owner"
        attention_reason = attention_reason or "This is an explicit owner-review gate."
    elif attention == "informational" and (
        source == "pm_host_action_required" or bool(_dict(payload.get("host_action_required")))
    ):
        attention = "needs_host"
        attention_reason = attention_reason or "This step must be completed outside the runtime."

    execution_state = _text(execution.get("state") or execution.get("executor_status")).lower()
    result_status = _text(latest_result.get("status")).lower()
    activation_state = _text(activation.get("state")).lower()
    if attention == "needs_host":
        execution_class = "host_action"
    elif activation_state in {"waiting_on_prerequisite", "not_due_yet"}:
        execution_class = "waiting"
    elif execution_state in {"failed", "error"} or result_status == "failed":
        execution_class = "failed"
    elif execution_state in {"running", "in_progress", "claimed"} or status in {"running", "in_progress"}:
        execution_class = "running"
    elif execution_state in {"queued", "pending"} or status == "queued":
        execution_class = "queued"
    elif status == "blocked":
        execution_class = "blocked"
    elif status == "review" or result_status == "review":
        execution_class = "review"
    elif status in CLOSED_STATUSES or result_status in {"done", "completed"}:
        execution_class = "completed"
    else:
        execution_class = "unverified"

    if status in CLOSED_STATUSES:
        resolution = "closed"
    elif payload.get("duplicate_resolution") or payload.get("superseded_by"):
        resolution = "superseded"
    else:
        resolution = "active"

    host_action = _dict(payload.get("host_action_required"))
    host_follow_up = _dict(payload.get("host_action_followup"))
    due_at, due_error = _first_semantic_timestamp(
        (
            ("due_at", getattr(card, "due_at", None)),
            ("scheduled_for", payload.get("scheduled_for")),
            ("host_action_required.scheduled_for", host_action.get("scheduled_for")),
            ("host_action_required.due_at", host_action.get("due_at")),
            ("host_action_followup.due_at", host_follow_up.get("due_at")),
        )
    )
    evidence_at, evidence_error = _evidence_at(card)
    timestamp_error = due_error or evidence_error
    age_hours = (
        max(0.0, (current_time - evidence_at).total_seconds() / 3600)
        if evidence_at is not None
        else None
    )
    if timestamp_error:
        # Invalid/missing semantic time stays visible to Dream/portfolio
        # consumers as an integrity problem.  It is never silently promoted to
        # current or demoted to harmless historical recovery.
        freshness = "invalid"
    elif resolution != "active":
        freshness = "historical"
    elif activation_state == "waiting_on_prerequisite":
        freshness = "waiting"
    elif due_at is not None and due_at < current_time:
        freshness = "expired"
    elif due_at is not None and (due_at - current_time).total_seconds() <= 86_400:
        freshness = "due"
    elif age_hours is not None and age_hours <= 72:
        freshness = "current"
    elif age_hours is not None and age_hours <= 336:
        freshness = "aging"
    else:
        freshness = "stale"

    mismatch = status in {"running", "in_progress"} and execution_class == "failed"
    searchable = f"{_text(getattr(card, 'title', ''))} {json.dumps(payload, default=str)}".lower()
    legacy_instruction = any(
        marker in searchable
        for marker in (
            "/.openclaw/",
            "\\.openclaw\\",
            "/users/",
            "workspaces/linkedin-content-os/dispatch/",
        )
    )
    return {
        "workspace_key": workspace_key,
        "attention_class": attention,
        "attention_reason": attention_reason,
        "execution_class": execution_class,
        "execution_state": execution_state or None,
        "result_status": result_status or None,
        "freshness": freshness,
        "evidence_at": evidence_at.isoformat().replace("+00:00", "Z") if evidence_at else None,
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "freshness_error": timestamp_error,
        "resolution": resolution,
        "state_mismatch": mismatch,
        "legacy_instruction": legacy_instruction,
        "is_active": status in ACTIVE_STATUSES and resolution == "active",
        "needs_operator": attention in {"needs_owner", "needs_host"} and resolution == "active",
    }
