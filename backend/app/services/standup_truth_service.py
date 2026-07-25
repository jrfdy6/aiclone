from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import StandupEntry
from app.services.workspace_registry_service import canonicalize_workspace_key


STANDUP_FRESHNESS_HOURS = {
    "shared_ops": 12,
    "feezie-os": 36,
}
DEFAULT_STANDUP_FRESHNESS_HOURS = 72


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def classify_standup(standup: StandupEntry, *, now: datetime | None = None) -> dict[str, Any]:
    """Describe whether a standup is fresh and whether it produced decisions."""

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    created_at = getattr(standup, "created_at", current_time)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)
    workspace_key = canonicalize_workspace_key(getattr(standup, "workspace_key", None), default="shared_ops")
    payload = dict(getattr(standup, "payload", {}) or {})
    commitments = _items(getattr(standup, "commitments", []))
    blockers = _items(getattr(standup, "blockers", []))
    needs = _items(getattr(standup, "needs", []))
    decisions = _items(payload.get("decisions"))
    pm_updates = _items(payload.get("pm_updates"))
    pm_recommendations = _items(payload.get("pm_recommendations"))
    summary = _text(payload.get("summary"))

    age_hours = max(0.0, (current_time - created_at).total_seconds() / 3600)
    freshness_limit = STANDUP_FRESHNESS_HOURS.get(workspace_key, DEFAULT_STANDUP_FRESHNESS_HOURS)
    freshness = "current" if age_hours <= freshness_limit else "stale"
    decision_yield = len(decisions) + len(pm_updates) + len(pm_recommendations)

    if not summary and not commitments and not blockers and not needs:
        quality = "empty"
        quality_reason = "The standup contains no summary, commitment, blocker, or owner need."
    elif len(commitments) >= 4 and decision_yield == 0:
        quality = "ceremonial"
        quality_reason = "The standup repeats several commitments without recording a decision or PM handoff."
    elif blockers and decision_yield == 0:
        quality = "unrouted_blocker"
        quality_reason = "The standup names a blocker without a recorded decision or PM handoff."
    else:
        quality = "actionable"
        quality_reason = "The standup produced a bounded update, decision, or execution handoff."

    return {
        "workspace_key": workspace_key,
        "freshness": freshness,
        "freshness_limit_hours": freshness_limit,
        "age_hours": round(age_hours, 1),
        "quality": quality,
        "quality_reason": quality_reason,
        "decision_yield": decision_yield,
        "commitment_count": len(commitments),
        "blocker_count": len(blockers),
        "owner_need_count": len(needs),
        "has_decision_output": decision_yield > 0,
    }
