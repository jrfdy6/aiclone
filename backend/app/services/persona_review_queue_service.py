from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from app.models import PersonaDelta


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_bool(metadata: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(metadata, dict):
        return False
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _metadata_array(metadata: dict[str, Any] | None, key: str) -> list[Any]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    return value if isinstance(value, list) else []


def has_selectable_promotion_metadata(metadata: dict[str, Any] | None) -> bool:
    return any(
        _metadata_array(metadata, key)
        for key in ("talking_points", "frameworks", "anecdotes", "phrase_candidates", "stats")
    )


def promotion_signal_count(metadata: dict[str, Any] | None) -> int:
    return sum(
        len(_metadata_array(metadata, key))
        for key in ("talking_points", "frameworks", "anecdotes", "phrase_candidates", "stats")
    )


def is_workspace_approved(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    review_source = _metadata_text(metadata, "review_source")
    approval_state = _metadata_text(metadata, "approval_state")
    return normalized == "approved" and (
        review_source == "linkedin_workspace.feed_quote" or approval_state == "approved_from_workspace"
    )


def is_brain_pending_review(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    if normalized in {"draft", "pending", "in_review"}:
        return True
    return normalized == "reviewed" and has_selectable_promotion_metadata(metadata) and not _metadata_bool(
        metadata, "pending_promotion"
    )


def persona_delta_stage(status: str, metadata: dict[str, Any] | None) -> str:
    normalized = (status or "draft").strip().lower()
    if normalized == "committed":
        return "committed"
    if _metadata_bool(metadata, "pending_promotion"):
        return "pending_promotion"
    if is_workspace_approved(normalized, metadata):
        return "workspace_saved"
    if is_brain_pending_review(normalized, metadata):
        return "brain_pending_review"
    if normalized == "approved":
        return "approved_unpromoted"
    return normalized or "draft"


def is_promotion_ready(status: str, metadata: dict[str, Any] | None) -> bool:
    normalized = (status or "draft").strip().lower()
    return normalized in {"in_review", "reviewed"} and has_selectable_promotion_metadata(metadata)


def _target_priority(target_file: str | None) -> int:
    if not target_file:
        return 1
    if "identity/claims" in target_file:
        return 5
    if "identity/VOICE_PATTERNS" in target_file:
        return 5
    if "identity/philosophy" in target_file:
        return 4
    if "identity/decision_principles" in target_file:
        return 4
    if "prompts/content_pillars" in target_file:
        return 4
    if "history/story_bank" in target_file:
        return 3
    if "history/wins" in target_file:
        return 3
    if "history/initiatives" in target_file:
        return 2
    if "history/resume" in target_file:
        return 1
    return 1


def _recency_priority(delta: PersonaDelta) -> int:
    if not delta.created_at:
        return 0
    if delta.created_at.tzinfo is not None and delta.created_at.utcoffset() is not None:
        now = datetime.now(delta.created_at.tzinfo)
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    age = now - delta.created_at
    if age.days <= 1:
        return 4
    if age.days <= 3:
        return 3
    if age.days <= 7:
        return 2
    if age.days <= 30:
        return 1
    return 0


def _review_state_priority(status: str, metadata: dict[str, Any] | None) -> int:
    normalized = (status or "draft").strip().lower()
    if is_promotion_ready(normalized, metadata):
        return 6
    if normalized == "in_review":
        return 5
    if normalized == "reviewed":
        return 4
    if normalized == "pending":
        return 3
    if normalized == "draft":
        return 2
    return 0


def _review_source_priority(review_source: str | None) -> int:
    if review_source == "brain.persona.ui":
        return 3
    if review_source == "linkedin_workspace.feed_quote":
        return 2
    if review_source == "long_form_media.segment":
        return 1
    return 0


def _looks_weak_long_form_text(text: str) -> bool:
    normalized = text.lower()
    return any(
        pattern in normalized
        for pattern in (
            "# clean transcript",
            "**open questions:**",
            "machine learning is a subset of ai",
            "that element in green",
            "my team and i thought",
            "i'm super proud",
            "alive in spirit",
            "not very well done",
            "why does it have to be that way",
            "questions when my team is sleeping",
            "chief product officer was presenting",
            "showed me his ai dashboard",
            "showed me her ai dashboard",
            "showed me their ai dashboard",
            "ai magic takes over",
        )
    )


def should_mute_active_delta(delta: PersonaDelta) -> bool:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    review_source = _metadata_text(metadata, "review_source")
    if review_source != "long_form_media.segment":
        return False
    if _metadata_text(metadata, "sync_state") == "stale_segment":
        return True
    if _looks_weak_long_form_text(delta.trait) or _looks_weak_long_form_text(delta.notes or ""):
        return True
    signal_count = promotion_signal_count(metadata)
    if signal_count == 0:
        return True
    has_strong_signal = (
        len(_metadata_array(metadata, "frameworks")) > 0
        or len(_metadata_array(metadata, "anecdotes")) > 0
        or len(_metadata_array(metadata, "phrase_candidates")) > 0
    )
    return not has_strong_signal and signal_count < 3


def queue_priority_score(delta: PersonaDelta) -> int:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    target_file = _metadata_text(metadata, "target_file")
    review_source = _metadata_text(metadata, "review_source")
    signal_count = promotion_signal_count(metadata)
    muted = should_mute_active_delta(delta)
    score = 0
    score += _target_priority(target_file) * 4
    score += signal_count * 2
    score += _recency_priority(delta)
    score += _review_state_priority(delta.status, metadata)
    score += _review_source_priority(review_source)
    if _metadata_bool(metadata, "pending_promotion"):
        score += 4
    if muted:
        score -= 8
    return score


def queue_metadata(delta: PersonaDelta) -> dict[str, Any]:
    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    stage = persona_delta_stage(delta.status, metadata)
    muted = should_mute_active_delta(delta)
    return {
        "queue_stage": stage,
        "queue_review_source": _metadata_text(metadata, "review_source") or "unknown",
        "queue_target_file": _metadata_text(metadata, "target_file"),
        "queue_promotion_signal_count": promotion_signal_count(metadata),
        "queue_promotion_ready": is_promotion_ready(delta.status, metadata),
        "queue_muted": muted,
        "queue_priority_score": queue_priority_score(delta),
    }


def annotate_for_brain_queue(delta: PersonaDelta) -> PersonaDelta:
    metadata = dict(delta.metadata or {})
    metadata.update(queue_metadata(delta))
    return delta.model_copy(update={"metadata": metadata})


def _stage_order(stage: str) -> int:
    order = {
        "brain_pending_review": 0,
        "workspace_saved": 1,
        "pending_promotion": 2,
        "committed": 3,
        "approved_unpromoted": 4,
        "resolved": 5,
        "reviewed": 5,
        "approved": 5,
    }
    return order.get(stage, 6)


def prepare_for_brain_queue(deltas: Iterable[PersonaDelta]) -> list[PersonaDelta]:
    annotated = [annotate_for_brain_queue(delta) for delta in deltas]

    def sort_key(delta: PersonaDelta) -> tuple[int, int, int, float]:
        metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
        stage = _metadata_text(metadata, "queue_stage") or "draft"
        muted = _metadata_bool(metadata, "queue_muted")
        score = int(metadata.get("queue_priority_score") or 0)
        created = delta.created_at.timestamp() if delta.created_at else 0.0
        return (_stage_order(stage), 1 if muted else 0, -score, -created)

    return sorted(annotated, key=sort_key)
