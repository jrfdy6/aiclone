from __future__ import annotations

import hashlib
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from urllib.parse import quote

from pydantic import BaseModel

from app.models import (
    ExecutiveDecision,
    ExecutiveDecisionAction,
    ExecutiveDecisionActionRequest,
    ExecutiveDecisionActionResult,
    ExecutiveDecisionQueue,
    ExecutiveDecisionSourceError,
    ExecutiveDecisionSummary,
    PMCardActionRequest,
)
from app.services import (
    automation_mismatch_service,
    automation_run_service,
    email_ops_service,
    persona_delta_service,
    pm_card_service,
    standup_service,
)
from app.services.automation_service import list_automations
from app.services.brain_signal_service import list_signals
from app.services.linkedin_owner_review_service import list_owner_review_items, record_owner_decision
from app.services.persona_review_queue_service import prepare_for_brain_queue
from app.services.standup_truth_service import is_verified_meeting_record
from app.services.workspace_registry_service import canonicalize_workspace_key, workspace_registry_entries
from app.utils.ai_clone_clock import resolve_payload_observation


SOURCE_TYPES = (
    "pm",
    "workspace_review",
    "brain_signal",
    "persona",
    "email",
    "standup",
    "system_exception",
)
_SOURCE_LABELS = {
    "pm": "PM",
    "workspace_review": "Workspace review",
    "brain_signal": "Brain signals",
    "persona": "Persona",
    "email": "Email",
    "standup": "Standup",
    "system_exception": "System exceptions",
}
TODAY_LIMIT = 5
SOURCE_READ_LIMIT = 500
DEFAULT_SOURCE_TIMEOUT_SECONDS = 8.0
DEFAULT_OVERALL_TIMEOUT_SECONDS = 12.0
MAX_SOURCE_TIMEOUT_SECONDS = 12.0
MAX_OVERALL_TIMEOUT_SECONDS = 14.0
_CLOSED_PM_STATUSES = {"done", "closed", "cancelled"}
_CLOSED_EMAIL_STATUSES = {"sent", "closed"}
_OWNER_NEED_WORDS = ("owner", "approve", "approval", "decision", "input", "review", "host action")
_SOURCE_PREFERENCE = {
    "workspace_review": 30,
    "email": 30,
    "persona": 20,
    "brain_signal": 20,
    "standup": 20,
    "system_exception": 20,
    "pm": 10,
}


class ExecutiveDecisionNotFoundError(LookupError):
    pass


class ExecutiveDecisionActionError(ValueError):
    pass


@dataclass
class _CollectionResult:
    items: list[ExecutiveDecision] = field(default_factory=list)
    status: str = "ok"
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _InFlightCollection:
    future: Future[_CollectionResult]
    started_at: float


_SOURCE_EXECUTORS = {
    source_type: ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"executive-{source_type}")
    for source_type in SOURCE_TYPES
}
_SOURCE_INFLIGHT: dict[str, _InFlightCollection] = {}
_SOURCE_INFLIGHT_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    cleaned = " ".join(str(value or "").replace("\xa0", " ").split()).strip()
    if limit is not None and len(cleaned) > limit:
        return cleaned[: max(0, limit - 3)].rstrip() + "..."
    return cleaned


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _freshness(updated_at: datetime | None, *, now: datetime) -> str:
    timestamp = _aware_utc(updated_at)
    current = _aware_utc(now) or now
    if timestamp is None:
        return "unknown"
    age = current - timestamp
    if age <= timedelta(hours=24):
        return "today"
    if age <= timedelta(days=3):
        return "recent"
    if age <= timedelta(days=14):
        return "aging"
    return "stale"


def _freshness_adjustment(freshness: str) -> int:
    return {
        "today": 8,
        "recent": 5,
        "aging": -5,
        "stale": -25,
        "unknown": -15,
    }.get(freshness, 0)


def _priority(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _score(base_score: int, updated_at: datetime | None, *, now: datetime) -> tuple[int, str, str]:
    freshness = _freshness(updated_at, now=now)
    score = max(0, min(100, int(base_score) + _freshness_adjustment(freshness)))
    return score, _priority(score), freshness


def _dedupe_strings(values: Iterable[Any], *, limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value, limit=500)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _decision_id(source_type: str, source_id: str) -> str:
    return f"{source_type}:{source_id}"


def _action_endpoint(decision_id: str, action_id: str) -> str:
    return (
        f"/api/executive/decisions/{quote(decision_id, safe='')}/actions/"
        f"{quote(action_id, safe='')}"
    )


def _open_context_action(context_href: str) -> ExecutiveDecisionAction:
    return ExecutiveDecisionAction(
        id="open_context",
        label="Review context",
        kind="open_context",
        method="GET",
        href=context_href,
        source_href=context_href,
        requires_confirmation=False,
    )


def _delegate_action(
    *,
    decision_id: str,
    action_id: str,
    label: str,
    source_href: str,
    requires_confirmation: bool = True,
    requires_note: bool = False,
) -> ExecutiveDecisionAction:
    return ExecutiveDecisionAction(
        id=action_id,
        label=label,
        kind="delegate",
        method="POST",
        href=_action_endpoint(decision_id, action_id),
        source_href=source_href,
        requires_confirmation=requires_confirmation,
        requires_note=requires_note,
    )


def _build_decision(
    *,
    source_type: str,
    source_id: str,
    dedupe_key: str,
    workspace_key: str,
    title: str,
    what_changed: str,
    why_it_matters: str,
    recommendation: str,
    base_score: int,
    updated_at: datetime | None,
    evidence: Iterable[Any],
    context_href: str,
    actions: Callable[[str], list[ExecutiveDecisionAction]],
    now: datetime,
) -> ExecutiveDecision:
    decision_id = _decision_id(source_type, source_id)
    priority_score, priority, freshness = _score(base_score, updated_at, now=now)
    return ExecutiveDecision(
        id=decision_id,
        dedupe_key=dedupe_key,
        source_type=source_type,
        source_id=source_id,
        workspace_key=canonicalize_workspace_key(workspace_key, default="shared_ops"),
        title=_clean_text(title, limit=300) or "Untitled decision",
        what_changed=_clean_text(what_changed, limit=700) or "This item entered an owner decision state.",
        why_it_matters=_clean_text(why_it_matters, limit=700) or "It remains open until the authoritative source is resolved.",
        recommendation=_clean_text(recommendation, limit=700) or "Review the source context before deciding.",
        priority=priority,
        priority_score=priority_score,
        freshness=freshness,
        updated_at=updated_at,
        evidence=_dedupe_strings(evidence),
        context_href=context_href,
        actions=actions(decision_id),
    )


def _payload_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _workspace_key_from_pm(card: Any) -> str:
    payload = _payload_dict(getattr(card, "payload", None))
    return canonicalize_workspace_key(
        payload.get("workspace_key") or payload.get("workspace") or payload.get("belongs_to_workspace"),
        default="shared_ops",
    )


def _owner_review_payload(card: Any) -> dict[str, Any] | None:
    payload = _payload_dict(getattr(card, "payload", None))
    owner_review = payload.get("owner_review")
    if not isinstance(owner_review, dict):
        owner_review = {}
    queue_id = _clean_text(owner_review.get("queue_id"))
    source = _clean_text(getattr(card, "source", "")).lower()
    link_type = _clean_text(getattr(card, "link_type", "")).lower()
    looks_like_owner_review = bool(
        queue_id
        or link_type == "owner_review"
        or "workspace-owner-review" in source
        or _clean_text(payload.get("trigger_origin")).lower() == "owner_review"
    )
    if not looks_like_owner_review:
        return None
    if _clean_text(owner_review.get("decision")):
        return None
    if not queue_id:
        return None
    return owner_review


def _owner_review_actions(decision_id: str, queue_id: str, context_href: str) -> list[ExecutiveDecisionAction]:
    source_href = f"/api/workspace/linkedin-os-owner-review/{quote(queue_id, safe='')}"
    return [
        _delegate_action(
            decision_id=decision_id,
            action_id="approve",
            label="Approve",
            source_href=source_href,
        ),
        _delegate_action(
            decision_id=decision_id,
            action_id="revise",
            label="Request revision",
            source_href=source_href,
            requires_note=True,
        ),
        _delegate_action(
            decision_id=decision_id,
            action_id="park",
            label="Park",
            source_href=source_href,
        ),
        _open_context_action(context_href),
    ]


def _owner_review_identity(payload: dict[str, Any], queue_id: str) -> str:
    return _clean_text(payload.get("identity_key")) or queue_id


def _owner_review_from_pm(card: Any, owner_review: dict[str, Any], *, now: datetime) -> ExecutiveDecision:
    queue_id = _clean_text(owner_review.get("queue_id"))
    identity_key = _owner_review_identity(owner_review, queue_id)
    context_href = f"/ops?focus=workspace&owner_review={quote(queue_id, safe='')}"
    updated_at = _parse_datetime(getattr(card, "updated_at", None))
    assessment = _payload_dict(owner_review.get("system_assessment"))
    scaffold = _payload_dict(owner_review.get("decision_scaffold"))
    evidence = [
        f"PM card: {getattr(card, 'id', '')}",
        f"Queue item: {queue_id}",
        f"Draft: {_clean_text(owner_review.get('draft_path'))}" if owner_review.get("draft_path") else "",
        f"Core angle: {_clean_text(owner_review.get('core_angle'))}" if owner_review.get("core_angle") else "",
        *[f"Proof: {_clean_text(item)}" for item in owner_review.get("proof_anchors") or []],
    ]
    return _build_decision(
        source_type="workspace_review",
        source_id=queue_id,
        dedupe_key=f"workspace_review:{identity_key.lower()}",
        workspace_key="feezie-os",
        title=_clean_text(owner_review.get("title")) or _clean_text(getattr(card, "title", "")),
        what_changed=(
            _clean_text(assessment.get("summary"))
            or _clean_text(owner_review.get("first_pass_draft"), limit=600)
            or "A FEEZIE draft reached owner review through the PM mirror."
        ),
        why_it_matters=(
            _clean_text(owner_review.get("why_now"))
            or _clean_text(owner_review.get("core_angle"))
            or "Public content cannot advance until the owner chooses approve, revise, or park."
        ),
        recommendation=(
            _clean_text(scaffold.get("neo_answer_contract"))
            or _clean_text(assessment.get("fallback_action"))
            or "Read the draft once, then approve, request one concrete revision, or park it."
        ),
        base_score=69,
        updated_at=updated_at,
        evidence=evidence,
        context_href=context_href,
        actions=lambda decision_id: _owner_review_actions(decision_id, queue_id, context_href),
        now=now,
    )


def _collect_pm_decisions(now: datetime) -> _CollectionResult:
    raw_cards = pm_card_service.list_cards(limit=SOURCE_READ_LIMIT)
    cards = pm_card_service.decorate_cards_for_client(raw_cards)
    decisions: list[ExecutiveDecision] = []
    for card in cards:
        status = _clean_text(getattr(card, "status", "todo")).lower() or "todo"
        if status in _CLOSED_PM_STATUSES:
            continue
        owner_review = _owner_review_payload(card)
        if owner_review is not None:
            decisions.append(_owner_review_from_pm(card, owner_review, now=now))
            continue

        payload = _payload_dict(getattr(card, "payload", None))
        policy = _payload_dict(payload.get("pm_review_policy"))
        attention_class = _clean_text(policy.get("attention_class")).lower()
        if attention_class not in {"needs_owner", "needs_host"}:
            continue

        source_id = _clean_text(getattr(card, "id", ""))
        if not source_id:
            continue
        workspace_key = _workspace_key_from_pm(card)
        context_href = f"/ops?focus=pm&card_id={quote(source_id, safe='')}"
        updated_at = _parse_datetime(getattr(card, "updated_at", None))
        due_at = _parse_datetime(getattr(card, "due_at", None))
        execution = _payload_dict(payload.get("execution"))
        latest_result = _payload_dict(payload.get("latest_execution_result"))
        host_action = _payload_dict(payload.get("host_action_required"))
        base_score = 58
        if attention_class == "needs_host":
            base_score += 14
        if status == "blocked":
            base_score += 17
        elif status == "failed":
            base_score += 22
        elif status == "review":
            base_score += 8
        if due_at is not None:
            current = _aware_utc(now) or now
            due = _aware_utc(due_at) or due_at
            if due < current:
                base_score += 10
            elif due <= current + timedelta(hours=24):
                base_score += 5

        evidence = [
            f"Status: {status}",
            f"Owner: {_clean_text(getattr(card, 'owner', ''))}" if getattr(card, "owner", None) else "",
            f"Due: {due_at.isoformat()}" if due_at else "",
            f"Execution state: {_clean_text(execution.get('state'))}" if execution.get("state") else "",
            *[f"Artifact: {_clean_text(item)}" for item in latest_result.get("artifacts") or []],
            *[f"Proof required: {_clean_text(item)}" for item in host_action.get("proof_required") or []],
        ]
        source_href = f"/api/pm/cards/{quote(source_id, safe='')}/actions"
        email_thread_id = _clean_text(payload.get("email_thread_id"))

        def actions(decision_id: str, *, attention_class: str = attention_class) -> list[ExecutiveDecisionAction]:
            result: list[ExecutiveDecisionAction] = []
            if attention_class == "needs_owner":
                result.extend(
                    [
                        _delegate_action(
                            decision_id=decision_id,
                            action_id="approve",
                            label="Approve & close",
                            source_href=source_href,
                        ),
                        _delegate_action(
                            decision_id=decision_id,
                            action_id="return",
                            label="Return to system",
                            source_href=source_href,
                            requires_note=True,
                        ),
                        _delegate_action(
                            decision_id=decision_id,
                            action_id="blocked",
                            label="Mark blocked",
                            source_href=source_href,
                            requires_note=True,
                        ),
                    ]
                )
            result.append(_open_context_action(context_href))
            return result

        decisions.append(
            _build_decision(
                source_type="pm",
                source_id=source_id,
                dedupe_key=f"email:{email_thread_id}" if email_thread_id else f"pm:{source_id}",
                workspace_key=workspace_key,
                title=_clean_text(getattr(card, "title", "")),
                what_changed=(
                    _clean_text(latest_result.get("summary"))
                    or _clean_text(execution.get("last_error"))
                    or f"This PM card is {status} and classified as {attention_class.replace('_', ' ')}."
                ),
                why_it_matters=(
                    _clean_text(policy.get("attention_reason"))
                    or _clean_text(payload.get("reason"))
                    or "The PM loop is waiting for a human decision before it can close or continue."
                ),
                recommendation=(
                    "Complete the required host step and attach the requested proof."
                    if attention_class == "needs_host"
                    else _clean_text(policy.get("suggested_next_reason"))
                    or "Approve and close it, return it with a concrete reason, or mark the blocker explicitly."
                ),
                base_score=base_score,
                updated_at=updated_at,
                evidence=evidence,
                context_href=context_href,
                actions=actions,
                now=now,
            )
        )
    truncated = len(raw_cards) >= SOURCE_READ_LIMIT
    return _CollectionResult(
        items=decisions,
        status="degraded" if truncated else "ok",
        errors=(
            [f"PM reached its {SOURCE_READ_LIMIT}-item read cap; older decisions were not verified."]
            if truncated
            else []
        ),
    )


def _collect_workspace_review_decisions(now: datetime) -> _CollectionResult:
    payload = list_owner_review_items(include_resolved=False)
    decisions: list[ExecutiveDecision] = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict) or _clean_text(item.get("current_decision")):
            continue
        queue_id = _clean_text(item.get("queue_id"))
        if not queue_id:
            continue
        context_href = f"/ops?focus=workspace&owner_review={quote(queue_id, safe='')}"
        updated_at = (
            _parse_datetime(item.get("reviewed_at"))
            or _parse_datetime(item.get("updated_at"))
            or _parse_datetime(item.get("created_at"))
        )
        assessment = _payload_dict(item.get("system_assessment"))
        scaffold = _payload_dict(item.get("decision_scaffold"))
        identity_key = _owner_review_identity(item, queue_id)
        suggested = _clean_text(assessment.get("suggested_decision")).lower()
        confidence = _clean_text(assessment.get("confidence")).lower()
        base_score = 78 if suggested in {"approve", "revise"} else 68
        if confidence == "high":
            base_score += 4
        evidence = [
            f"Queue item: {queue_id}",
            f"Lane: {_clean_text(item.get('lane'))}" if item.get("lane") else "",
            f"Draft: {_clean_text(item.get('draft_path'))}" if item.get("draft_path") else "",
            f"Source: {_clean_text(item.get('source_url') or item.get('source_path'))}"
            if item.get("source_url") or item.get("source_path")
            else "",
            *[f"Proof: {_clean_text(proof)}" for proof in item.get("proof_anchors") or []],
            *[f"Missing: {_clean_text(gap)}" for gap in assessment.get("missing_items") or []],
        ]

        def actions(
            decision_id: str,
            queue_id: str = queue_id,
            context_href: str = context_href,
        ) -> list[ExecutiveDecisionAction]:
            return _owner_review_actions(decision_id, queue_id, context_href)

        decisions.append(
            _build_decision(
                source_type="workspace_review",
                source_id=queue_id,
                dedupe_key=f"workspace_review:{identity_key.lower()}",
                workspace_key="feezie-os",
                title=_clean_text(item.get("title")) or queue_id,
                what_changed=(
                    _clean_text(assessment.get("summary"))
                    or _clean_text(item.get("first_pass_draft"), limit=600)
                    or "A FEEZIE draft reached owner review."
                ),
                why_it_matters=(
                    _clean_text(item.get("why_now"))
                    or _clean_text(item.get("core_angle"))
                    or "This draft cannot enter scheduling or another revision pass without an explicit owner call."
                ),
                recommendation=(
                    _clean_text(scaffold.get("neo_answer_contract"))
                    or _clean_text(assessment.get("fallback_action"))
                    or "Read the draft once, then approve, request one concrete revision, or park it."
                ),
                base_score=base_score,
                updated_at=updated_at,
                evidence=evidence,
                context_href=context_href,
                actions=actions,
                now=now,
            )
        )
    return _CollectionResult(items=decisions)


def _metadata_updated_at(metadata: dict[str, Any], fallback: datetime | None) -> datetime | None:
    for key in (
        "last_reviewed_at",
        "owner_response_updated_at",
        "source_updated_at",
        "sync_updated_at",
        "updated_at",
    ):
        parsed = _parse_datetime(metadata.get(key))
        if parsed is not None:
            return parsed
    return fallback


def _collect_persona_decisions(now: datetime) -> _CollectionResult:
    raw_deltas = persona_delta_service.list_deltas(limit=SOURCE_READ_LIMIT)
    deltas = prepare_for_brain_queue(raw_deltas)
    decisions: list[ExecutiveDecision] = []
    for delta in deltas:
        metadata = _payload_dict(delta.metadata)
        stage = _clean_text(metadata.get("queue_stage")).lower()
        if stage not in {"brain_pending_review", "pending_promotion"}:
            continue
        if bool(metadata.get("queue_muted")):
            continue
        source_id = _clean_text(delta.id)
        stable_identity = (
            _clean_text(metadata.get("review_key"))
            or _clean_text(getattr(delta, "capture_id", None))
            or source_id
        )
        context_href = f"/brain?delta_id={quote(source_id, safe='')}#brain-section-persona"
        updated_at = _metadata_updated_at(metadata, _parse_datetime(delta.created_at))
        queue_score = int(metadata.get("queue_priority_score") or 0)
        base_score = (79 if stage == "pending_promotion" else 55) + min(20, max(0, queue_score // 2))
        target_file = _clean_text(metadata.get("queue_target_file") or metadata.get("target_file"))
        review_source = _clean_text(metadata.get("queue_review_source") or metadata.get("review_source"))
        signal_count = int(metadata.get("queue_promotion_signal_count") or 0)

        decisions.append(
            _build_decision(
                source_type="persona",
                source_id=source_id,
                dedupe_key=f"persona:{stable_identity.lower()}",
                workspace_key=(metadata.get("source_workspace_key") or metadata.get("workspace_key") or "shared_ops"),
                title=_clean_text(delta.trait) or "Persona review",
                what_changed=(
                    "Selected persona evidence is ready for canonical promotion."
                    if stage == "pending_promotion"
                    else _clean_text(delta.notes)
                    or "New persona evidence is waiting for interpretation."
                ),
                why_it_matters=(
                    f"This may change {target_file}." if target_file else "This may change how the system understands or writes in your voice."
                ),
                recommendation=(
                    "Review the selected fragments and commit only the canon-safe targets."
                    if stage == "pending_promotion"
                    else "Agree, disagree, add nuance or lived context, then choose whether anything should be promoted."
                ),
                base_score=base_score,
                updated_at=updated_at,
                evidence=[
                    f"Stage: {stage}",
                    f"Target: {target_file}" if target_file else "",
                    f"Review source: {review_source}" if review_source else "",
                    f"Promotion signals: {signal_count}" if signal_count else "",
                    f"Source: {_clean_text(metadata.get('source_url') or metadata.get('source_path'))}"
                    if metadata.get("source_url") or metadata.get("source_path")
                    else "",
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )
    truncated = len(raw_deltas) >= SOURCE_READ_LIMIT
    return _CollectionResult(
        items=decisions,
        status="degraded" if truncated else "ok",
        errors=(
            [f"Persona reached its {SOURCE_READ_LIMIT}-item read cap; older decisions were not verified."]
            if truncated
            else []
        ),
    )


def _brain_signal_is_actionable(signal: Any) -> bool:
    source_kind = _clean_text(getattr(signal, "source_kind", "")).lower()
    actionability = _clean_text(getattr(signal, "actionability", "")).lower()
    if source_kind == "source_intelligence":
        # Raw ingestion belongs in briefs/persona curation. Surfacing it here
        # recreates the noisy firehose this executive queue is meant to avoid.
        return False
    return actionability in {"medium", "high"} or source_kind in {"automation_output", "workspace_attention"}


def _collect_brain_signal_decisions(now: datetime) -> _CollectionResult:
    decisions: list[ExecutiveDecision] = []
    signals = list_signals(limit=SOURCE_READ_LIMIT)
    for signal in signals:
        review_status = _clean_text(getattr(signal, "review_status", "new")).lower()
        if review_status not in {"new", "in_review"} or not _brain_signal_is_actionable(signal):
            continue
        source_id = _clean_text(signal.id)
        source_kind = _clean_text(signal.source_kind).lower()
        actionability = _clean_text(signal.actionability).lower()
        confidence = _clean_text(signal.confidence).lower()
        identity_relevance = _clean_text(signal.identity_relevance).lower()
        updated_at = _parse_datetime(signal.updated_at)
        base_score = 45
        if source_kind in {"automation_output", "workspace_attention"}:
            base_score += 23
        if actionability == "high":
            base_score += 12
        elif actionability == "medium":
            base_score += 6
        if confidence == "high":
            base_score += 5
        if identity_relevance == "high":
            base_score += 5
        source_ref = _clean_text(signal.source_ref)
        stable_identity = f"{source_kind}:{source_ref.lower()}" if source_ref else source_id
        context_href = f"/brain?signal_id={quote(source_id, safe='')}#brain-section-dashboard"
        interpretation = _payload_dict(signal.executive_interpretation)

        decisions.append(
            _build_decision(
                source_type="brain_signal",
                source_id=source_id,
                dedupe_key=f"brain_signal:{stable_identity}",
                workspace_key=signal.source_workspace_key,
                title=_clean_text(signal.digest) or _clean_text(signal.raw_summary, limit=180),
                what_changed=_clean_text(signal.raw_summary),
                why_it_matters=(
                    _clean_text(interpretation.get("neo_system_impact"))
                    or _clean_text(interpretation.get("yoda_meaning"))
                    or "This signal was classified as actionable and has not been routed or dismissed."
                ),
                recommendation=(
                    _clean_text(interpretation.get("jean_claude_operational_translation"))
                    or "Review the source, then route it to the existing Brain destination or dismiss it."
                ),
                base_score=base_score,
                updated_at=updated_at,
                evidence=[
                    f"Source kind: {source_kind}",
                    f"Source ref: {source_ref}" if source_ref else "",
                    f"Actionability: {actionability}",
                    f"Confidence: {confidence}",
                    *[f"Signal: {_clean_text(value)}" for value in signal.signal_types],
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )
    truncated = len(signals) >= SOURCE_READ_LIMIT
    return _CollectionResult(
        items=decisions,
        status="degraded" if truncated else "ok",
        errors=(
            [f"Brain signals reached the {SOURCE_READ_LIMIT}-item read cap; older decisions were not verified."]
            if truncated
            else []
        ),
    )


def _collect_email_decisions(now: datetime) -> _CollectionResult:
    response = email_ops_service.list_persisted_threads(limit=250)
    if response.data_mode == "sample_only":
        return _CollectionResult(
            status="degraded",
            errors=["Email is in sample-only mode; sample threads were excluded from executive decisions."],
        )
    decisions: list[ExecutiveDecision] = []
    for thread in response.items:
        if thread.provider == "sample" or _clean_text(thread.status).lower() in _CLOSED_EMAIL_STATUSES:
            continue
        if not (thread.needs_human or thread.high_value or thread.high_risk or thread.sla_at_risk):
            continue
        source_id = _clean_text(thread.id)
        context_href = f"/inbox/{quote(source_id, safe='')}"
        updated_at = _parse_datetime(thread.last_message_at) or _parse_datetime(thread.updated_at)
        base_score = 54
        if thread.high_risk:
            base_score += 22
        if thread.sla_at_risk:
            base_score += 16
        if thread.high_value:
            base_score += 10
        if thread.draft_body:
            base_score += 5
        decisions.append(
            _build_decision(
                source_type="email",
                source_id=source_id,
                dedupe_key=f"email:{thread.provider_thread_id or source_id}",
                workspace_key=thread.workspace_key,
                title=thread.subject,
                what_changed=thread.summary or thread.excerpt or "An email thread was classified for human review.",
                why_it_matters=(
                    "This thread is high risk or time-sensitive and should not be handled automatically."
                    if thread.high_risk or thread.sla_at_risk
                    else "This thread is high value, ambiguous, or requires your judgment before a reply advances."
                ),
                recommendation=(
                    "Review the prepared draft and decide whether to save, revise, or clear it."
                    if thread.draft_body
                    else "Open the thread, confirm its workspace and lane, then draft or escalate from the existing inbox controls."
                ),
                base_score=base_score,
                updated_at=updated_at,
                evidence=[
                    f"From: {_clean_text(thread.from_name or thread.from_address)}",
                    f"Lane: {_clean_text(thread.lane)}",
                    "High risk" if thread.high_risk else "",
                    "SLA at risk" if thread.sla_at_risk else "",
                    "High value" if thread.high_value else "",
                    *[f"Routing: {_clean_text(reason)}" for reason in thread.routing_reasons],
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )
    truncated = response.total > len(response.items) or len(response.items) >= 250
    return _CollectionResult(
        items=decisions,
        status="degraded" if truncated else "ok",
        errors=(
            ["Email has more threads than the 250-item read window; older decisions were not verified."]
            if truncated
            else []
        ),
    )


def _needs_owner_decision(needs: Iterable[Any]) -> bool:
    return any(any(word in _clean_text(item).lower() for word in _OWNER_NEED_WORDS) for item in needs)


def _collect_standup_decisions(now: datetime) -> _CollectionResult:
    standups = standup_service.list_standups(limit=SOURCE_READ_LIMIT)
    display_names = {
        canonicalize_workspace_key(entry.get("key") or entry.get("workspace_key"), default="shared_ops"): _clean_text(
            entry.get("display_name") or entry.get("name")
        )
        for entry in workspace_registry_entries()
        if isinstance(entry, dict)
    }
    candidates_by_workspace: dict[str, list[Any]] = {}
    for standup in standups:
        workspace_key = canonicalize_workspace_key(getattr(standup, "workspace_key", None), default="shared_ops")
        payload = _payload_dict(getattr(standup, "payload", None))
        evidence = payload.get("meeting_evidence")
        # Daily workspace evaluations, synthetic role lenses, and async plans
        # share the historical standups table, but they are not meetings and
        # cannot create an owner-facing "standup exception".  Keep this cheap
        # structural gate ahead of signed-report verification.
        if not (
            payload.get("record_kind") == "standup"
            and payload.get("meeting_held") is True
            and payload.get("evaluation_only") is False
            and isinstance(evidence, dict)
        ):
            continue
        candidates_by_workspace.setdefault(workspace_key, []).append(standup)

    def semantic_order(standup: Any) -> tuple[int, datetime, datetime]:
        payload = _payload_dict(getattr(standup, "payload", None))
        observed_at, source = resolve_payload_observation(
            payload,
            created_at=getattr(standup, "created_at", None),
        )
        priority = (
            2
            if source in {"semantic_observed_at", "semantic_cycle_observation"}
            else 1
            if source == "legacy_created_at_fallback"
            else 0
        )
        floor = datetime.min.replace(tzinfo=timezone.utc)
        persisted_at = _aware_utc(_parse_datetime(getattr(standup, "created_at", None))) or floor
        return priority, observed_at or floor, persisted_at

    latest_by_workspace: dict[str, tuple[Any, datetime | None, str]] = {}
    for workspace_key, candidates in candidates_by_workspace.items():
        for candidate in sorted(candidates, key=semantic_order, reverse=True):
            payload = _payload_dict(getattr(candidate, "payload", None))
            if not is_verified_meeting_record(
                payload,
                source=getattr(candidate, "source", None),
                workspace_key=workspace_key,
            ):
                continue
            observed_at, source = resolve_payload_observation(
                payload,
                created_at=getattr(candidate, "created_at", None),
            )
            latest_by_workspace[workspace_key] = (candidate, observed_at, source)
            break

    decisions: list[ExecutiveDecision] = []
    degraded_clock_workspaces: list[str] = []
    for workspace_key, (latest, meeting_observed_at, observation_source) in latest_by_workspace.items():
        blockers = [_clean_text(item) for item in getattr(latest, "blockers", []) or [] if _clean_text(item)]
        needs = [_clean_text(item) for item in getattr(latest, "needs", []) or [] if _clean_text(item)]
        if not blockers and not _needs_owner_decision(needs):
            continue
        source_id = _clean_text(getattr(latest, "id", ""))
        if not source_id:
            continue
        context_href = f"/ops?focus=standups&standup_id={quote(source_id, safe='')}"
        payload = _payload_dict(getattr(latest, "payload", None))
        semantic_timestamp = (
            meeting_observed_at
            if observation_source in {"semantic_observed_at", "semantic_cycle_observation"}
            else None
        )
        if semantic_timestamp is None:
            degraded_clock_workspaces.append(workspace_key)
        base_score = 73 if blockers else 58
        base_score += min(8, max(0, len(blockers) - 1) * 2)
        decisions.append(
            _build_decision(
                source_type="standup",
                source_id=source_id,
                dedupe_key=f"standup:{source_id}",
                workspace_key=workspace_key,
                title=f"{display_names.get(workspace_key) or workspace_key} standup exception",
                what_changed=(
                    _clean_text(payload.get("summary"))
                    or (f"Blocker: {blockers[0]}" if blockers else f"Owner need: {needs[0]}")
                ),
                why_it_matters=(
                    "; ".join(_dedupe_strings(blockers or needs, limit=3))
                    or "The latest standup cannot close its decision loop without human attention."
                ),
                recommendation=(
                    "Resolve or route the blocker from the standup context; use the PM card if one already represents the same work."
                    if blockers
                    else "Answer the named owner need in the standup context."
                ),
                base_score=base_score,
                # Persistence created_at is only storage metadata.  A legacy
                # row may remain reviewable, but it must never look newly
                # observed because it was replayed late.
                updated_at=semantic_timestamp,
                evidence=[
                    *[f"Blocker: {item}" for item in blockers],
                    *[f"Need: {item}" for item in needs],
                    f"Source: {_clean_text(getattr(latest, 'conversation_path', ''))}"
                    if getattr(latest, "conversation_path", None)
                    else "",
                    *[f"Source: {_clean_text(path)}" for path in payload.get("source_paths") or []],
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )
    truncated = len(standups) >= SOURCE_READ_LIMIT
    errors: list[str] = []
    if truncated:
        errors.append(
            f"Standups reached the {SOURCE_READ_LIMIT}-item read cap; older workspaces were not verified."
        )
    if degraded_clock_workspaces:
        errors.append(
            "Verified meeting exceptions without a valid semantic ai_clone_utc observation were retained with unknown freshness: "
            + ", ".join(sorted(set(degraded_clock_workspaces)))
            + "."
        )
    return _CollectionResult(
        items=decisions,
        status="degraded" if errors else "ok",
        errors=errors,
    )


def _run_timestamp(run: Any) -> datetime | None:
    return _parse_datetime(getattr(run, "finished_at", None)) or _parse_datetime(getattr(run, "run_at", None))


def _stable_exception_source_id(*values: Any) -> str:
    raw = "|".join(_clean_text(value) for value in values)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _collect_system_exception_decisions(now: datetime) -> _CollectionResult:
    runs = automation_run_service.list_runs(limit=SOURCE_READ_LIMIT)
    automations = list_automations(runs=runs)
    report = automation_mismatch_service.build_mismatch_report(automations=automations, runs=runs)
    latest_by_automation: dict[str, Any] = {}
    for run in runs:
        automation_id = _clean_text(getattr(run, "automation_id", ""))
        if not automation_id:
            continue
        current = latest_by_automation.get(automation_id)
        if current is None or (_aware_utc(_run_timestamp(run)) or datetime.min.replace(tzinfo=timezone.utc)) > (
            _aware_utc(_run_timestamp(current)) or datetime.min.replace(tzinfo=timezone.utc)
        ):
            latest_by_automation[automation_id] = run

    decisions: list[ExecutiveDecision] = []
    for mismatch in report.mismatches:
        severity = _clean_text(mismatch.severity).lower()
        if severity not in {"warn", "warning", "error", "critical"}:
            continue
        automation_id = _clean_text(mismatch.automation_id)
        source_id = automation_id or _stable_exception_source_id(mismatch.kind, mismatch.automation_name, mismatch.message)
        run = latest_by_automation.get(automation_id)
        updated_at = _run_timestamp(run) if run is not None else _parse_datetime((mismatch.metadata or {}).get("updated_at"))
        context_href = (
            f"/brain?automation_id={quote(automation_id, safe='')}#brain-section-automations"
            if automation_id
            else "/brain#brain-section-automations"
        )
        decisions.append(
            _build_decision(
                source_type="system_exception",
                source_id=f"{source_id}:{_clean_text(mismatch.kind).lower() or 'mismatch'}",
                dedupe_key=f"system_exception:{source_id}:{_clean_text(mismatch.kind).lower() or 'mismatch'}",
                workspace_key=_clean_text(getattr(run, "workspace_key", "")) or "shared_ops",
                title=_clean_text(mismatch.automation_name) or _clean_text(mismatch.kind).replace("_", " ").title(),
                what_changed=mismatch.message,
                why_it_matters="A scheduled system lane is failing, drifting, or not delivering its expected result.",
                recommendation="Inspect the automation evidence and repair or explicitly retire the affected lane.",
                base_score=91 if severity in {"error", "critical"} else 73,
                updated_at=updated_at,
                evidence=[
                    f"Exception: {_clean_text(mismatch.kind)}",
                    f"Severity: {severity}",
                    f"Latest status: {_clean_text(getattr(run, 'status', ''))}" if run is not None else "",
                    f"Error: {_clean_text(getattr(run, 'error', ''))}" if run is not None and getattr(run, "error", None) else "",
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )

    mismatch_automation_ids = {
        _clean_text(mismatch.automation_id)
        for mismatch in report.mismatches
        if _clean_text(mismatch.automation_id)
        and _clean_text(mismatch.severity).lower() in {"warn", "warning", "error", "critical"}
    }
    for run in latest_by_automation.values():
        if not bool(getattr(run, "action_required", False)):
            continue
        automation_id = _clean_text(getattr(run, "automation_id", ""))
        if not automation_id or automation_id in mismatch_automation_ids:
            continue
        source_id = f"{automation_id}:action_required"
        context_href = f"/brain?automation_id={quote(automation_id, safe='')}#brain-section-automations"
        decisions.append(
            _build_decision(
                source_type="system_exception",
                source_id=source_id,
                dedupe_key=f"system_exception:{source_id}",
                workspace_key=_clean_text(getattr(run, "workspace_key", "")) or "shared_ops",
                title=_clean_text(getattr(run, "automation_name", "")) or automation_id,
                what_changed="The latest automation run explicitly marked owner action as required.",
                why_it_matters="The automation cannot close its loop autonomously until the requested action is handled.",
                recommendation="Open the automation evidence and complete or route the requested action.",
                base_score=82,
                updated_at=_run_timestamp(run),
                evidence=[
                    f"Automation: {automation_id}",
                    f"Status: {_clean_text(getattr(run, 'status', ''))}",
                    f"Error: {_clean_text(getattr(run, 'error', ''))}" if getattr(run, "error", None) else "",
                ],
                context_href=context_href,
                actions=lambda decision_id: [_open_context_action(context_href)],
                now=now,
            )
        )
    truncated = len(runs) >= SOURCE_READ_LIMIT
    return _CollectionResult(
        items=decisions,
        status="degraded" if truncated else "ok",
        errors=(
            [f"Automation runs reached the {SOURCE_READ_LIMIT}-item read cap; older exceptions were not verified."]
            if truncated
            else []
        ),
    )


def _decision_sort_key(decision: ExecutiveDecision) -> tuple[int, float, str]:
    updated = _aware_utc(decision.updated_at)
    timestamp = updated.timestamp() if updated is not None else 0.0
    return (-decision.priority_score, -timestamp, decision.id)


def _decision_timestamp(decision: ExecutiveDecision) -> float:
    updated = _aware_utc(decision.updated_at)
    return updated.timestamp() if updated is not None else 0.0


def _is_owner_review_pm_mirror(decision: ExecutiveDecision) -> bool:
    return decision.source_type == "workspace_review" and any(
        evidence.startswith("PM card:") for evidence in decision.evidence
    )


def _display_preference(decision: ExecutiveDecision) -> tuple[int, int, float, int, str]:
    return (
        0 if _is_owner_review_pm_mirror(decision) else 1,
        _SOURCE_PREFERENCE.get(decision.source_type, 0),
        _decision_timestamp(decision),
        len(decision.evidence),
        decision.id,
    )


def _merge_duplicate_decisions(
    primary: ExecutiveDecision,
    secondary: ExecutiveDecision,
    *,
    dedupe_key: str,
) -> ExecutiveDecision:
    priority_score = max(primary.priority_score, secondary.priority_score)
    freshness_rank = {"unknown": 0, "stale": 1, "aging": 2, "recent": 3, "today": 4}
    freshness = max(
        (primary.freshness, secondary.freshness),
        key=lambda value: freshness_rank.get(value, 0),
    )
    updated_at = (
        secondary.updated_at
        if _decision_timestamp(secondary) > _decision_timestamp(primary)
        else primary.updated_at
    )
    return primary.model_copy(
        update={
            "dedupe_key": dedupe_key,
            "priority_score": priority_score,
            "priority": _priority(priority_score),
            "freshness": freshness,
            "updated_at": updated_at,
            "evidence": _dedupe_strings([*primary.evidence, *secondary.evidence]),
        }
    )


def _dedupe_decisions(decisions: Iterable[ExecutiveDecision]) -> list[ExecutiveDecision]:
    materialized = list(decisions)
    # Escalation PM cards store the AI Clone email id, while the inbox item is
    # canonically keyed by its provider thread. Resolve that local alias only
    # when the matching inbox item is present, so either source can still stand
    # alone when the other collector is unavailable.
    email_keys_by_source_id = {
        decision.source_id: decision.dedupe_key
        for decision in materialized
        if decision.source_type == "email"
    }
    deduped: dict[str, ExecutiveDecision] = {}
    for decision in materialized:
        dedupe_key = decision.dedupe_key
        if decision.source_type == "pm" and dedupe_key.startswith("email:"):
            local_thread_id = dedupe_key.removeprefix("email:")
            dedupe_key = email_keys_by_source_id.get(local_thread_id, dedupe_key)
        current = deduped.get(dedupe_key)
        if current is None:
            deduped[dedupe_key] = decision.model_copy(update={"dedupe_key": dedupe_key})
            continue
        primary, secondary = (
            (decision, current)
            if _display_preference(decision) > _display_preference(current)
            else (current, decision)
        )
        deduped[dedupe_key] = _merge_duplicate_decisions(
            primary,
            secondary,
            dedupe_key=dedupe_key,
        )
    return sorted(deduped.values(), key=_decision_sort_key)


def _select_today(candidates: list[ExecutiveDecision], *, limit: int = TODAY_LIMIT) -> list[ExecutiveDecision]:
    selected: list[ExecutiveDecision] = []
    selected_ids: set[str] = set()
    used_sources: set[str] = set()
    used_workspaces: set[str] = set()
    source_counts: dict[str, int] = {}

    def can_add(decision: ExecutiveDecision) -> bool:
        return source_counts.get(decision.source_type, 0) < 3

    def add(decision: ExecutiveDecision) -> None:
        selected.append(decision)
        selected_ids.add(decision.id)
        used_sources.add(decision.source_type)
        used_workspaces.add(decision.workspace_key)
        source_counts[decision.source_type] = source_counts.get(decision.source_type, 0) + 1

    # First preserve both source and workspace diversity. The second pass
    # relaxes one dimension, then the final pass returns to global rank.
    for decision in candidates:
        if len(selected) >= limit:
            break
        if (
            can_add(decision)
            and decision.source_type not in used_sources
            and decision.workspace_key not in used_workspaces
        ):
            add(decision)
    for decision in candidates:
        if len(selected) >= limit:
            break
        if decision.id in selected_ids:
            continue
        if can_add(decision) and (
            decision.source_type not in used_sources or decision.workspace_key not in used_workspaces
        ):
            add(decision)
    for decision in candidates:
        if len(selected) >= limit:
            break
        if decision.id not in selected_ids and can_add(decision):
            add(decision)
    # Diversity controls membership, not the displayed rank. Once selected,
    # return the set in deterministic priority/freshness order.
    return sorted(selected, key=_decision_sort_key)


def _is_today_candidate(decision: ExecutiveDecision) -> bool:
    """Keep Today current; the full unresolved backlog remains in all_pending."""

    if decision.freshness in {"stale", "unknown"}:
        return False
    if decision.freshness == "aging":
        return (
            decision.source_type in {"pm", "workspace_review", "system_exception"}
            and decision.priority_score >= 75
        )
    return decision.priority == "critical" or decision.priority_score >= 55


def _safe_collect(
    source_type: str,
    collector: Callable[[datetime], _CollectionResult],
    *,
    now: datetime,
) -> _CollectionResult:
    try:
        result = collector(now)
        if result.status not in {"ok", "degraded"}:
            result.status = "degraded"
        return result
    except Exception as exc:
        print(f"Executive decision source `{source_type}` failed: {type(exc).__name__}", flush=True)
        return _CollectionResult(
            status="error",
            errors=[f"{_SOURCE_LABELS.get(source_type, source_type)} could not be verified; its decisions were not ranked."],
        )


def _bounded_timeout_setting(name: str, default: float, maximum: float) -> float:
    raw = _clean_text(os.getenv(name))
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    return max(0.05, min(maximum, value))


def _acquire_collection_future(
    source_type: str,
    collector: Callable[[datetime], _CollectionResult],
    *,
    now: datetime,
) -> _InFlightCollection:
    with _SOURCE_INFLIGHT_LOCK:
        current = _SOURCE_INFLIGHT.get(source_type)
        if current is not None and not current.future.done():
            return current
        entry = _InFlightCollection(
            future=_SOURCE_EXECUTORS[source_type].submit(_safe_collect, source_type, collector, now=now),
            started_at=time.monotonic(),
        )
        _SOURCE_INFLIGHT[source_type] = entry
        return entry


def _release_collection_future(source_type: str, entry: _InFlightCollection) -> None:
    with _SOURCE_INFLIGHT_LOCK:
        current = _SOURCE_INFLIGHT.get(source_type)
        if current is entry:
            _SOURCE_INFLIGHT.pop(source_type, None)


def _timeout_collection(source_type: str) -> _CollectionResult:
    return _CollectionResult(
        status="degraded",
        errors=[
            f"{_SOURCE_LABELS.get(source_type, source_type)} did not finish within the executive queue deadline; "
            "its decisions were not ranked."
        ],
    )


def _collect_sources_with_deadlines(
    collectors: tuple[tuple[str, Callable[[datetime], _CollectionResult]], ...],
    *,
    now: datetime,
    source_timeout_seconds: float,
    overall_timeout_seconds: float,
) -> dict[str, _CollectionResult]:
    overall_deadline = time.monotonic() + overall_timeout_seconds
    pending = {
        source_type: _acquire_collection_future(source_type, collector, now=now)
        for source_type, collector in collectors
    }
    results: dict[str, _CollectionResult] = {}

    while pending:
        current_time = time.monotonic()
        expired = [
            source_type
            for source_type, entry in pending.items()
            if current_time >= overall_deadline
            or current_time - entry.started_at >= source_timeout_seconds
        ]
        for source_type in expired:
            entry = pending[source_type]
            duration_ms = int(max(0.0, current_time - entry.started_at) * 1000)
            print(
                f"Executive decision source `{source_type}` timed out duration_ms={duration_ms}",
                flush=True,
            )
            results[source_type] = _timeout_collection(source_type)
            pending.pop(source_type, None)
        if not pending:
            break

        next_deadline = min(
            overall_deadline,
            *(entry.started_at + source_timeout_seconds for entry in pending.values()),
        )
        wait_seconds = max(0.0, next_deadline - time.monotonic())
        done, _ = wait(
            [entry.future for entry in pending.values()],
            timeout=wait_seconds,
            return_when=FIRST_COMPLETED,
        )
        if not done:
            continue
        for source_type, entry in list(pending.items()):
            if entry.future not in done:
                continue
            try:
                results[source_type] = entry.future.result()
                duration_ms = int(max(0.0, time.monotonic() - entry.started_at) * 1000)
                print(
                    f"Executive decision source `{source_type}` completed "
                    f"status={results[source_type].status} items={len(results[source_type].items)} "
                    f"duration_ms={duration_ms}",
                    flush=True,
                )
            except Exception as exc:
                duration_ms = int(max(0.0, time.monotonic() - entry.started_at) * 1000)
                print(
                    f"Executive decision source `{source_type}` future failed: {type(exc).__name__} "
                    f"duration_ms={duration_ms}",
                    flush=True,
                )
                results[source_type] = _CollectionResult(
                    status="error",
                    errors=[
                        f"{_SOURCE_LABELS.get(source_type, source_type)} could not be verified; "
                        "its decisions were not ranked."
                    ],
                )
            finally:
                pending.pop(source_type, None)
                _release_collection_future(source_type, entry)
    return results


def build_executive_decision_queue(
    *,
    now: datetime | None = None,
    source_timeout_seconds: float | None = None,
    overall_timeout_seconds: float | None = None,
) -> ExecutiveDecisionQueue:
    build_started_at = time.monotonic()
    build_id = f"{threading.get_ident()}-{int(build_started_at * 1000) % 1_000_000}"
    generated_at = now or _utcnow()
    collectors: tuple[tuple[str, Callable[[datetime], _CollectionResult]], ...] = (
        ("workspace_review", _collect_workspace_review_decisions),
        ("pm", _collect_pm_decisions),
        ("persona", _collect_persona_decisions),
        ("brain_signal", _collect_brain_signal_decisions),
        ("email", _collect_email_decisions),
        ("standup", _collect_standup_decisions),
        ("system_exception", _collect_system_exception_decisions),
    )
    source_status = {source_type: "error" for source_type in SOURCE_TYPES}
    source_errors: list[ExecutiveDecisionSourceError] = []
    collected: list[ExecutiveDecision] = []
    source_timeout = (
        source_timeout_seconds
        if source_timeout_seconds is not None
        else _bounded_timeout_setting(
            "EXECUTIVE_DECISION_SOURCE_TIMEOUT_SECONDS",
            DEFAULT_SOURCE_TIMEOUT_SECONDS,
            MAX_SOURCE_TIMEOUT_SECONDS,
        )
    )
    overall_timeout = (
        overall_timeout_seconds
        if overall_timeout_seconds is not None
        else _bounded_timeout_setting(
            "EXECUTIVE_DECISION_OVERALL_TIMEOUT_SECONDS",
            DEFAULT_OVERALL_TIMEOUT_SECONDS,
            MAX_OVERALL_TIMEOUT_SECONDS,
        )
    )
    source_timeout = max(0.01, min(MAX_SOURCE_TIMEOUT_SECONDS, source_timeout))
    overall_timeout = max(0.01, min(MAX_OVERALL_TIMEOUT_SECONDS, overall_timeout))
    source_timeout = min(source_timeout, overall_timeout)
    collection_results = _collect_sources_with_deadlines(
        collectors,
        now=generated_at,
        source_timeout_seconds=source_timeout,
        overall_timeout_seconds=overall_timeout,
    )
    print(
        f"Executive decision build `{build_id}` phase=collect_complete "
        f"duration_ms={int((time.monotonic() - build_started_at) * 1000)}",
        flush=True,
    )
    for source_type, collector in collectors:
        result = collection_results.get(source_type) or _timeout_collection(source_type)
        source_status[source_type] = result.status
        collected.extend(result.items)
        print(
            f"Executive decision build `{build_id}` source={source_type} "
            f"status={result.status} items={len(result.items)}",
            flush=True,
        )
        source_errors.extend(
            ExecutiveDecisionSourceError(source_type=source_type, message=message)
            for message in result.errors
            if _clean_text(message)
        )

    dedupe_started_at = time.monotonic()
    print(
        f"Executive decision build `{build_id}` phase=dedupe_start collected={len(collected)}",
        flush=True,
    )
    all_pending = _dedupe_decisions(collected)
    print(
        f"Executive decision build `{build_id}` phase=dedupe_complete pending={len(all_pending)} "
        f"duration_ms={int((time.monotonic() - dedupe_started_at) * 1000)}",
        flush=True,
    )
    rank_started_at = time.monotonic()
    today_candidates = [
        decision
        for decision in all_pending
        if _is_today_candidate(decision)
    ]
    today = _select_today(today_candidates)
    priority_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for decision in all_pending:
        priority_counts[decision.priority] = priority_counts.get(decision.priority, 0) + 1
        source_counts[decision.source_type] = source_counts.get(decision.source_type, 0) + 1
    verification_status = "partial" if any(status != "ok" for status in source_status.values()) else "verified"
    print(
        f"Executive decision build `{build_id}` phase=rank_complete candidates={len(today_candidates)} "
        f"today={len(today)} duration_ms={int((time.monotonic() - rank_started_at) * 1000)}",
        flush=True,
    )
    response = ExecutiveDecisionQueue(
        generated_at=generated_at,
        summary=ExecutiveDecisionSummary(
            total_pending=len(all_pending),
            today_count=len(today),
            today_candidate_count=len(today_candidates),
            priority_counts=priority_counts,
            source_counts=source_counts,
            verification_status=verification_status,
            verified_clear=not all_pending and verification_status == "verified",
        ),
        source_status=source_status,
        source_errors=source_errors,
        today=today,
        all_pending=all_pending,
    )
    print(
        f"Executive decision build `{build_id}` phase=return_ready total_pending={len(all_pending)} "
        f"total_duration_ms={int((time.monotonic() - build_started_at) * 1000)}",
        flush=True,
    )
    return response


def _model_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": _clean_text(value)}


def _find_decision_and_action(decision_id: str, action_id: str) -> tuple[ExecutiveDecision, ExecutiveDecisionAction]:
    source_type, separator, _source_id = decision_id.partition(":")
    collectors: dict[str, Callable[[datetime], _CollectionResult]] = {
        "workspace_review": _collect_workspace_review_decisions,
        "pm": _collect_pm_decisions,
        "persona": _collect_persona_decisions,
        "brain_signal": _collect_brain_signal_decisions,
        "email": _collect_email_decisions,
        "standup": _collect_standup_decisions,
        "system_exception": _collect_system_exception_decisions,
    }
    collector = collectors.get(source_type) if separator else None
    if collector is None:
        raise ExecutiveDecisionNotFoundError("Executive decision is no longer pending or its source is unavailable.")
    # Action validation deliberately bypasses the GET aggregation futures. A
    # mutation must re-read only its authoritative source so a concurrent or
    # recently completed action cannot be authorized from a stale shared read.
    current = _safe_collect(source_type, collector, now=_utcnow())
    decision = next((item for item in current.items if item.id == decision_id), None)
    if decision is None:
        raise ExecutiveDecisionNotFoundError("Executive decision is no longer pending or its source is unavailable.")
    action = next((item for item in decision.actions if item.id == action_id), None)
    if action is None:
        raise ExecutiveDecisionActionError("This action is not available for the current decision state.")
    return decision, action


def execute_executive_decision_action(
    decision_id: str,
    action_id: str,
    payload: ExecutiveDecisionActionRequest,
    *,
    legacy_compatibility: bool = False,
) -> ExecutiveDecisionActionResult:
    decision, action = _find_decision_and_action(decision_id, action_id)
    if action.kind == "open_context":
        return ExecutiveDecisionActionResult(
            status="open_context",
            decision_id=decision.id,
            action_id=action.id,
            source_type=decision.source_type,
            source_id=decision.source_id,
            message="Open the source context to continue.",
            result={"href": decision.context_href},
        )

    result: Any
    if decision.source_type == "pm" and action_id in {"approve", "return", "blocked"}:
        if action_id in {"return", "blocked"} and not _clean_text(payload.reason or payload.notes):
            raise ExecutiveDecisionActionError(f"A reason is required before marking this PM decision `{action_id}`.")
        result = pm_card_service.act_on_card(
            decision.source_id,
            PMCardActionRequest(
                action=action_id,
                requested_by="Neo",
                reason=payload.reason or payload.notes,
                resolution_mode="close_only" if action_id == "approve" else None,
            ),
        )
        if result is None:
            raise ExecutiveDecisionNotFoundError("PM card was not found.")
        message = f"PM decision `{action_id}` was delegated to the existing PM action contract."
    elif decision.source_type == "workspace_review" and action_id in {"approve", "revise", "park"}:
        if legacy_compatibility is not True:
            raise ExecutiveDecisionActionError(
                "The historical workspace owner-review decision writer is disabled by default; "
                "use the canonical integrated-content lifecycle or explicitly enable the "
                "rollback-only compatibility path."
            )
        if action_id == "revise" and not _clean_text(payload.notes or payload.reason):
            raise ExecutiveDecisionActionError("Revision notes are required before returning a draft.")
        result = record_owner_decision(
            decision.source_id,
            action_id,
            payload.notes or payload.reason,
            legacy_compatibility=True,
        )
        message = f"Owner review `{action_id}` was delegated to the existing FEEZIE review contract."
    else:
        raise ExecutiveDecisionActionError("This action is not a supported fixed executive mutation.")

    return ExecutiveDecisionActionResult(
        status="completed",
        decision_id=decision.id,
        action_id=action.id,
        source_type=decision.source_type,
        source_id=decision.source_id,
        message=message,
        result=_model_payload(result),
    )
