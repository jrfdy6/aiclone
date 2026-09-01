from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import (
    ExecutionQueueEntry,
    PMCard,
    PMCardActionRequest,
    PMCardActionResult,
    PMCardCreate,
    PMCardDispatchRequest,
    PMCardDispatchResult,
    PMExecutionGateBackfillItem,
    PMExecutionGateBackfillRequest,
    PMExecutionGateBackfillResult,
    PMExecutionClaimFailureRequest,
    PMExecutionClaimRequest,
    PMExecutionResultCommitRequest,
    PMStaleExecutionClaimRecoveryRequest,
    PMStaleExecutionClaimRecoveryResult,
    PMCardUpdate,
)
from app.services.open_brain_db import get_pool
from app.services.execution_gate_service import (
    AUTO_EXECUTE,
    BOUNDED_PROJECT_CAPABILITY,
    POLICY_VERSION,
    REQUIRE_APPROVAL,
    apply_execution_gate,
    evaluate_execution_gate,
    execution_gate_allows_run,
    execution_gate_matches_current,
    grant_execution_approval,
    require_current_execution_gate,
)
from app.services.execution_artifact_reference_service import (
    contains_private_filesystem_reference,
    validate_remote_execution_artifact_reference,
)
from app.services.brain_response_privacy_service import sanitize_brain_text
from app.services.canonical_decision_service import PM_OWNER_DECISION_CHOICES
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.pm_review_hygiene_audit_service import list_review_hygiene_audit, record_review_hygiene_audit
from app.services.trigger_identity_service import build_pm_trigger_key
from app.services.workspace_registry_service import (
    canonicalize_workspace_key,
    workspace_registry_entries,
    workspace_root_slug,
    workspace_storage_aliases,
)
from app.services.workspace_runtime_contract_service import (
    execution_defaults_for_workspace as runtime_execution_defaults_for_workspace,
    pm_review_policy_for_workspace as runtime_pm_review_policy_for_workspace,
)
from app.security.execution_authorization import (
    AUTH_FIELD,
    execution_signing_configured,
    sign_execution_payload,
    verify_execution_payload,
)
from app.utils.ai_clone_clock import as_utc, utc_now

AUTO_RESOLVE_REQUESTED_BY = "PM Auto Resolve Policy"
AUTO_PROGRESS_REQUESTED_BY = "Codex PM Review Worker"
AUTO_CONTRACT_RETRY_LIMIT = 2
FAILED_EXECUTION_RECOVERY_SCHEMA_VERSION = "pm_failed_execution_recovery/v1"
HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_WRITEBACK = "fallback_watchdog_writeback"
HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULED_WRITEBACK = "linkedin_scheduled_writeback"
HOST_ACTION_AUTOMATION_STANDUP_PREP_WRITEBACK = "standup_prep_writeback"
HOST_ACTION_AUTOMATION_EXECUTION_RESULT_WRITEBACK_PROOF = "execution_result_writeback_proof"
HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_MARKERS = (
    "fallback_watchdog_latest.json",
    "memory/reports/fallback_watchdog_latest.json",
)
HOST_ACTION_AUTOMATION_STANDUP_PREP_MARKERS = (
    "memory/standup-prep",
    "standup-prep",
    "standup prep",
    "decision_loop",
)
HOST_ACTION_STANDUP_DECISION_LOOP_TARGETS = (
    "canonical_memory",
    "standup_interpretation",
    "pm_execution",
    "workspace_handoff",
    "no_action",
)
HOST_ACTION_AUTOMATION_WRITEBACK_PATTERNS = (
    re.compile(r"\bwrite[_-]?execution[_-]?result\b", re.IGNORECASE),
    re.compile(r"\bexecution[-\s]?result\s+writer\b", re.IGNORECASE),
    re.compile(r"\bexecution[-\s]?result\s*/?\s*write[-\s]?back\b", re.IGNORECASE),
    re.compile(r"\bresult\s*/?\s*write[-\s]?back\b", re.IGNORECASE),
    re.compile(r"\bwrite[-\s]?back\b", re.IGNORECASE),
    re.compile(r"\bwriteback\b", re.IGNORECASE),
)
PM_CARD_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
FEEZIE_QUEUE_ID_PATTERN = re.compile(r"\bFEEZIE-\d{3}\b", re.IGNORECASE)
HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULER_PATTERNS = (
    re.compile(r"\blinkedin\b", re.IGNORECASE),
    re.compile(r"\bnative\s+scheduler\b", re.IGNORECASE),
    re.compile(r"\bschedule(?:d|r|ing)?\b", re.IGNORECASE),
    re.compile(r"\bqueue\b", re.IGNORECASE),
)
HOST_ACTION_PREFIX = re.compile(r"^\s*(?:[-*]\s*)?(?:\d+\.\s*)?(?:host(?:\s+action)?)\s*:\s*(.+?)\s*$", re.IGNORECASE)
HOST_ACTION_DELAYED_PATTERNS = (
    re.compile(r"\bwithin\s+\d+\s*(?:hours?|hrs?|h)\b", re.IGNORECASE),
    re.compile(r"\bfirst[-\s]24h\b", re.IGNORECASE),
    re.compile(r"\bfirst[-\s]24[-\s]hour\b", re.IGNORECASE),
    re.compile(r"\bafter\s+publish\b", re.IGNORECASE),
    re.compile(r"\bonce\s+the\s+post\s+(?:is\s+)?live\b", re.IGNORECASE),
    re.compile(r"\bafter\s+slot\s*0\b", re.IGNORECASE),
    re.compile(r"\bafter\s+the\s+real\s+slot\s*0\b", re.IGNORECASE),
)
HOST_ACTION_PUBLISH_PATTERNS = (
    re.compile(r"\bpublish\b", re.IGNORECASE),
    re.compile(r"\bafter\s+publish\b", re.IGNORECASE),
    re.compile(r"\bpublished?\b", re.IGNORECASE),
    re.compile(r"\bpost\s+(?:is\s+)?live\b", re.IGNORECASE),
    re.compile(r"\bgo[-\s]?live\b", re.IGNORECASE),
)
HOST_ACTION_SCHEDULE_PATTERNS = (
    re.compile(r"\bschedule(?:d|r|ing)?\b", re.IGNORECASE),
    re.compile(r"\bnative\s+scheduler\b", re.IGNORECASE),
    re.compile(r"\bslot\s*0\b", re.IGNORECASE),
)
HOST_ACTION_TIMESTAMP_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*(?:ET|EST|EDT|UTC)?\b", re.IGNORECASE),
)
NEW_YORK_TZ = ZoneInfo("America/New_York")


class PMExecutionResultCommitConflict(ValueError):
    """Raised when a result does not match the card's active execution claim."""


class PMExecutionClaimConflict(ValueError):
    """Raised when a local runner cannot atomically acquire a PM execution claim."""


class PMExecutionClaimFailureConflict(ValueError):
    """Raised when a runner failure no longer matches the live signed claim."""


class PMOwnerDecisionReconciliationConflict(ValueError):
    """Raised when a canonical owner choice no longer matches its signed PM intent."""


class PMCardMutationConflict(ValueError):
    """Raised when a best-effort PM mutation cannot survive its bounded CAS retry."""


class PMRecommendationIdentityConflict(ValueError):
    """Raised when one coordination recommendation cannot resolve to one PM card."""


PM_OWNER_DECISION_RESOLUTION_SCHEMA = "pm_owner_decision_resolution/v1"
PM_RETAINED_TRIGGER_EVIDENCE_SCHEMA = "pm_retained_trigger_evidence/v1"
PM_EXECUTION_RESULT_COMMIT_SCHEMA = "pm_execution_result_commit/v1"
PM_EXECUTION_RESULT_TIMESTAMP_SEMANTICS = (
    "executor_finished_at_is_request_created_at/v1"
)
PM_RECOMMENDATION_IDENTITY_SCHEMA = "pm_recommendation_identity/v1"
PM_RECOMMENDATION_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PM_OWNER_DECISION_APPROVABLE_RISK_FACTORS = frozenset(
    {"OWNER_JUDGMENT_REQUIRED", "OWNER_REVIEW_REQUIRED"}
)
PM_OWNER_DECISION_APPROVABLE_REASON_CODES = frozenset(
    {
        "BOUNDED_INTERNAL_PROJECT_WORK",
        "OWNER_REVIEW_DECISION_REQUIRES_APPROVAL",
        "OWNER_REVIEW_GATE_PRESENT",
    }
)


STALE_CLAIM_AUTO_RECOVERABLE_BRAIN_ACTIONS = frozenset(
    {
        "signal_create",
        "signal_review",
        "signal_route",
        "signal_intake",
        "linkedin_performance_record",
        "social_engagement_capture",
        "social_engagement_action",
        "refresh_feezie_workspace",
        "refresh_persona_review",
        "integrated_content_variant",
        "integrated_owner_post",
        "integrated_content_manual_edit",
        "integrated_content_learning",
        "integrated_persona_reversal",
        "canonical_decision_create",
        "canonical_decision_transition",
    }
)


def list_cards(
    limit: int = 100,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    workspace_key: Optional[str] = None,
) -> List[PMCard]:
    pool = get_pool()
    clauses = []
    params = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if workspace_key:
        clauses.append(
            "LOWER(COALESCE(payload->>'workspace_key', payload->>'workspace', "
            "payload->>'belongs_to_workspace', 'shared_ops')) = ANY(%s)"
        )
        params.append(list(workspace_storage_aliases(workspace_key)))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    query = f"""
        SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
        FROM pm_cards
        {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_card(row) for row in rows]


def backfill_execution_gates(
    request: PMExecutionGateBackfillRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> PMExecutionGateBackfillResult:
    """Persist current fail-closed gates on active historical execution cards.

    This migration deliberately classifies the payload exactly as stored. It
    never synthesizes a completion contract and never grants approval.
    """

    if request.mode == "apply" and not execution_signing_configured():
        raise RuntimeError("Execution signing is not configured; no gate backfill was applied.")

    cards, has_more = _list_execution_gate_backfill_cards(request)
    items: list[PMExecutionGateBackfillItem] = []
    candidate_count = 0
    auto_count = 0
    approval_count = 0
    updated_count = 0
    already_current_count = 0
    active_claim_skipped_count = 0
    manual_reapproval_count = 0
    cas_miss_count = 0

    for card in cards:
        if (
            _is_workspace_owner_review_card(card)
            and legacy_owner_review_compatibility is not True
            and (card.payload or {}).get("legacy_owner_review_compatibility") is not True
        ):
            continue
        if not _is_execution_gate_backfill_candidate(card):
            continue
        candidate_count += 1
        raw_payload = dict(card.payload or {})
        workspace_key = _workspace_key_from_card(card)
        next_payload = apply_execution_gate(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=workspace_key,
            payload=raw_payload,
        )
        gate = dict(next_payload.get("execution_gate") or {})
        decision = str(gate.get("decision") or REQUIRE_APPROVAL)
        if decision == AUTO_EXECUTE:
            auto_count += 1
        else:
            approval_count += 1

        gate_current = execution_gate_matches_current(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=workspace_key,
            payload=raw_payload,
        )
        signature_current = verify_execution_payload(card.id, raw_payload)
        action = "would_update"
        would_become_runnable = False

        if gate_current and signature_current:
            action = "unchanged"
            already_current_count += 1
        elif _has_active_execution_claim(raw_payload):
            action = "skipped_active_claim"
            active_claim_skipped_count += 1
        elif decision == REQUIRE_APPROVAL and str(gate.get("approval_state") or "") == "approved":
            # A migration must never reactivate consequential work from
            # approval evidence that was not already part of a current,
            # signed gate. The normal exact-intent approval path must be used.
            action = "skipped_manual_reapproval"
            manual_reapproval_count += 1
        elif request.mode == "apply":
            updated = _persist_execution_gate_backfill(card, next_payload)
            if updated is None:
                action = "cas_miss"
                cas_miss_count += 1
            else:
                action = "updated"
                updated_count += 1
                would_become_runnable = decision == AUTO_EXECUTE
        else:
            would_become_runnable = decision == AUTO_EXECUTE

        items.append(
            PMExecutionGateBackfillItem(
                card_id=card.id,
                title=card.title,
                workspace_key=canonicalize_workspace_key(workspace_key),
                status=card.status or "todo",
                action=action,
                decision=decision,
                approval_state=str(gate.get("approval_state") or "missing"),
                risk_factors=[str(item) for item in gate.get("risk_factors") or []],
                reason=_optional_str(gate.get("reason")),
                intent_hash=str(gate.get("intent_hash") or ""),
                would_become_runnable=would_become_runnable,
            )
        )

    next_after_card_id = None
    if has_more and cards:
        next_after_card_id = cards[-1].id

    return PMExecutionGateBackfillResult(
        mode=request.mode,
        policy_version=POLICY_VERSION,
        workspace_key=(canonicalize_workspace_key(request.workspace_key) if request.workspace_key else None),
        scanned_count=len(cards),
        candidate_count=candidate_count,
        classified_auto_execute_count=auto_count,
        classified_require_approval_count=approval_count,
        would_become_runnable_count=sum(1 for item in items if item.would_become_runnable),
        updated_count=updated_count,
        already_current_count=already_current_count,
        active_claim_skipped_count=active_claim_skipped_count,
        manual_reapproval_count=manual_reapproval_count,
        cas_miss_count=cas_miss_count,
        has_more=has_more,
        next_after_card_id=next_after_card_id,
        items=items,
    )


def _list_execution_gate_backfill_cards(
    request: PMExecutionGateBackfillRequest,
) -> tuple[list[PMCard], bool]:
    clauses = ["LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled')"]
    params: list[Any] = []
    if request.workspace_key:
        canonical = canonicalize_workspace_key(request.workspace_key)
        aliases = {canonical.lower()}
        for entry in workspace_registry_entries():
            if str(entry.get("key") or "") != canonical:
                continue
            aliases.update(str(value).strip().lower() for value in entry.get("aliases") or [] if str(value).strip())
        clauses.append(
            "LOWER(COALESCE(payload->>'workspace_key', payload->>'workspace', payload->>'belongs_to_workspace', 'shared_ops')) = ANY(%s)"
        )
        params.append(sorted(aliases))
    if request.after_card_id is not None:
        clauses.append("id > %s")
        params.append(str(request.after_card_id))
    params.append(request.limit + 1)
    query = f"""
        SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
        FROM pm_cards
        WHERE {' AND '.join(clauses)}
        ORDER BY id
        LIMIT %s
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    has_more = len(rows) > request.limit
    return [_row_to_card(row) for row in rows[: request.limit]], has_more


def _is_execution_gate_backfill_candidate(card: PMCard) -> bool:
    payload = dict(card.payload or {})
    return bool(
        isinstance(payload.get("execution"), dict)
        or isinstance(payload.get("completion_contract"), dict)
        or isinstance(payload.get("brain_local_action"), dict)
        or isinstance(payload.get("host_action_automation"), dict)
        or isinstance(payload.get("host_action_required"), dict)
        or _is_owner_decision_gate(card)
        or _execution_contract_source(card) is not None
    )


def _has_active_execution_claim(payload: dict[str, Any]) -> bool:
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return False
    return bool(
        str(execution.get("state") or "").strip().lower() == "running"
        and str(execution.get("executor_status") or "").strip().lower() == "running"
        and str(execution.get("claim_id") or "").strip()
        and str(execution.get("executor_worker_id") or "").strip()
    )


def _persist_execution_gate_backfill(card: PMCard, next_payload: dict[str, Any]) -> PMCard | None:
    signed_payload = sign_execution_payload(card.id, next_payload)
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE pm_cards
                SET payload = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND updated_at = %s
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (Json(signed_payload), card.id, card.updated_at),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_card(row) if row else None


_MISSING_PM_PAYLOAD_VALUE = object()


def _persist_reconciled_card_update(
    snapshot: PMCard,
    *,
    operation: str,
    build_update: Any,
    is_committed: Any,
    update_kwargs: dict[str, Any] | None = None,
) -> PMCard:
    """Persist one card mutation with one bounded, freshly rebuilt CAS retry.

    Callers supply both the mutation builder and the durable-state predicate so a
    CAS miss can never be converted into a synthetic success. The retry is built
    from the newly read row and is bound to that row's ``updated_at`` value.
    """

    current = snapshot
    for _attempt in range(2):
        if is_committed(current):
            return current
        if current.updated_at is None:
            raise PMCardMutationConflict(
                f"{operation} was not persisted because PM card {snapshot.id} has no CAS timestamp."
            )
        mutation = build_update(current)
        if mutation is None:
            raise PMCardMutationConflict(
                f"{operation} was not persisted because PM card {snapshot.id} changed incompatibly."
            )
        governed_kwargs = dict(update_kwargs or {})
        governed_kwargs.pop("_expected_updated_at", None)
        updated = update_card(
            snapshot.id,
            mutation,
            _expected_updated_at=current.updated_at,
            **governed_kwargs,
        )
        if updated is not None:
            if not is_committed(updated):
                raise PMCardMutationConflict(
                    f"{operation} returned without the requested durable PM state for card {snapshot.id}."
                )
            return updated
        current = get_card(snapshot.id)
        if current is None:
            raise PMCardMutationConflict(
                f"{operation} was not persisted because PM card {snapshot.id} no longer exists."
            )

    if is_committed(current):
        return current
    raise PMCardMutationConflict(
        f"{operation} was not persisted because PM card {snapshot.id} changed during both CAS attempts."
    )


def _status_payload_reconciliation(
    snapshot: PMCard,
    *,
    status: str | None,
    payload: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Build safe retry and durable-state checks for status/payload mutations."""

    base_payload = dict(snapshot.payload or {})
    desired_payload = dict(payload) if payload is not None else None
    changed_payload_keys = (
        {
            key
            for key in set(base_payload) | set(desired_payload or {})
            if base_payload.get(key, _MISSING_PM_PAYLOAD_VALUE)
            != (desired_payload or {}).get(key, _MISSING_PM_PAYLOAD_VALUE)
        }
        if desired_payload is not None
        else set()
    )

    def is_committed(current: PMCard) -> bool:
        if status is not None and str(current.status) != str(status):
            return False
        current_payload = dict(current.payload or {})
        return all(
            current_payload.get(key, _MISSING_PM_PAYLOAD_VALUE)
            == (desired_payload or {}).get(key, _MISSING_PM_PAYLOAD_VALUE)
            for key in changed_payload_keys
        )

    def build_update(current: PMCard) -> PMCardUpdate | None:
        if (
            status is not None
            and str(current.status) not in {str(snapshot.status), str(status)}
        ):
            return None
        rebased_payload = dict(current.payload or {})
        if desired_payload is not None:
            for key in changed_payload_keys:
                base_value = base_payload.get(key, _MISSING_PM_PAYLOAD_VALUE)
                desired_value = desired_payload.get(key, _MISSING_PM_PAYLOAD_VALUE)
                current_value = rebased_payload.get(key, _MISSING_PM_PAYLOAD_VALUE)
                if current_value not in (base_value, desired_value):
                    return None
                if desired_value is _MISSING_PM_PAYLOAD_VALUE:
                    rebased_payload.pop(key, None)
                else:
                    rebased_payload[key] = desired_value
        return PMCardUpdate(
            status=status,
            payload=rebased_payload if desired_payload is not None else None,
        )

    return build_update, is_committed


def _persist_status_payload_update(
    snapshot: PMCard,
    *,
    operation: str,
    status: str | None = None,
    payload: dict[str, Any] | None = None,
    update_kwargs: dict[str, Any] | None = None,
) -> PMCard:
    build_update, is_committed = _status_payload_reconciliation(
        snapshot,
        status=status,
        payload=payload,
    )
    return _persist_reconciled_card_update(
        snapshot,
        operation=operation,
        build_update=build_update,
        is_committed=is_committed,
        update_kwargs=update_kwargs,
    )


def _signed_new_card_payload(
    normalized_payload: PMCardCreate,
    *,
    card_id: str,
    payload_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_payload = dict(normalized_payload.payload or {})
    canonical_payload.update(payload_overrides or {})
    execution = (
        dict(canonical_payload.get("execution") or {})
        if isinstance(canonical_payload.get("execution"), dict)
        else {}
    )
    execution_state = str(execution.get("state") or "").strip().lower()
    if execution and execution_state in {"queued", "pending"}:
        queued_at = datetime.now(timezone.utc).isoformat()
        execution.setdefault("queued_at", queued_at)
        execution.setdefault("last_transition_at", queued_at)
        canonical_payload["execution"] = execution
    gated_payload = apply_execution_gate(
        card_id=card_id,
        title=normalized_payload.title,
        source=normalized_payload.source,
        workspace_key=_workspace_key_from_payload(canonical_payload),
        payload=canonical_payload,
    )
    return sign_execution_payload(card_id, gated_payload)


def get_or_create_recommendation_card(
    payload: PMCardCreate,
    *,
    coordination_record_id: str,
    request_sha256: str,
) -> tuple[PMCard, bool]:
    """Atomically bind one exact coordination recommendation to one PM card.

    The partial unique index is the canonical concurrency authority. The card
    and its identity are inserted in one statement and one transaction, so a
    losing concurrent caller can only return the winner; it cannot leave an
    unreferenced second card behind.
    """

    try:
        canonical_coordination_id = str(UUID(str(coordination_record_id).strip()))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("coordination_record_id must be a canonical UUID") from exc
    canonical_request_sha256 = str(request_sha256 or "").strip().lower()
    if PM_RECOMMENDATION_SHA256_PATTERN.fullmatch(canonical_request_sha256) is None:
        raise ValueError("request_sha256 must be exactly 64 lowercase hexadecimal characters")

    normalized_payload = _normalize_card_create_payload(payload)
    raw_card_payload = dict(normalized_payload.payload or {})
    supplied_coordination_id = str(
        raw_card_payload.get("created_from_coordination_record_id") or ""
    ).strip()
    supplied_request_sha256 = str(
        raw_card_payload.get("recommendation_request_sha256") or ""
    ).strip().lower()
    if supplied_coordination_id and supplied_coordination_id != canonical_coordination_id:
        raise PMRecommendationIdentityConflict(
            "PM recommendation payload coordination identity does not match its canonical writer"
        )
    if supplied_request_sha256 and supplied_request_sha256 != canonical_request_sha256:
        raise PMRecommendationIdentityConflict(
            "PM recommendation payload digest does not match its canonical writer"
        )

    card_id = str(
        uuid5(
            NAMESPACE_URL,
            (
                "ai-clone:pm-recommendation:"
                f"{canonical_coordination_id}:{canonical_request_sha256}"
            ),
        )
    )
    signed_payload = _signed_new_card_payload(
        normalized_payload,
        card_id=card_id,
        payload_overrides={
            "recommendation_identity_schema_version": PM_RECOMMENDATION_IDENTITY_SCHEMA,
            "created_from_coordination_record_id": canonical_coordination_id,
            "recommendation_request_sha256": canonical_request_sha256,
        },
    )
    pool = get_pool()
    with pool.connection() as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO pm_cards (
                        id, title, owner, status, source, link_type, link_id,
                        recommendation_coordination_record_id,
                        recommendation_request_sha256,
                        due_at, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id, title, owner, status, source, link_type, link_id,
                              due_at, payload, created_at, updated_at
                    """,
                    (
                        card_id,
                        normalized_payload.title,
                        normalized_payload.owner,
                        normalized_payload.status or "todo",
                        normalized_payload.source,
                        normalized_payload.link_type,
                        normalized_payload.link_id,
                        canonical_coordination_id,
                        canonical_request_sha256,
                        normalized_payload.due_at,
                        Json(signed_payload),
                    ),
                )
                row = cur.fetchone()
                created = row is not None
                if row is None:
                    cur.execute(
                        """
                        SELECT id, title, owner, status, source, link_type, link_id,
                               due_at, payload, created_at, updated_at
                        FROM pm_cards
                        WHERE recommendation_coordination_record_id = %s
                          AND recommendation_request_sha256 = %s
                        """,
                        (canonical_coordination_id, canonical_request_sha256),
                    )
                    row = cur.fetchone()
                if row is None:
                    raise PMRecommendationIdentityConflict(
                        "PM recommendation identity conflicted without a canonical card"
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return _row_to_card(row), created


def create_card(payload: PMCardCreate) -> PMCard:
    normalized_payload = _normalize_card_create_payload(payload)
    trigger_key = _payload_value(normalized_payload.payload, "trigger_key")
    if trigger_key:
        existing = find_active_card_by_trigger_key(trigger_key)
        if existing is not None:
            replay_observed_at = datetime.now(timezone.utc).isoformat()
            replay_origin = _payload_value(normalized_payload.payload, "trigger_origin")
            minimum_replay_count = int((existing.payload or {}).get("trigger_replays") or 0) + 1

            def replay_is_committed(current: PMCard) -> bool:
                current_payload = dict(current.payload or {})
                return bool(
                    current_payload.get("last_triggered_at") == replay_observed_at
                    and current_payload.get("latest_trigger_origin") == replay_origin
                    and int(current_payload.get("trigger_replays") or 0) >= minimum_replay_count
                )

            def build_replay_update(current: PMCard) -> PMCardUpdate:
                current_payload = dict(current.payload or {})
                current_payload["last_triggered_at"] = replay_observed_at
                current_payload["trigger_replays"] = int(current_payload.get("trigger_replays") or 0) + 1
                current_payload["latest_trigger_origin"] = replay_origin
                return PMCardUpdate(payload=current_payload)

            return _persist_reconciled_card_update(
                existing,
                operation=f"PM trigger replay `{trigger_key}`",
                build_update=build_replay_update,
                is_committed=replay_is_committed,
            )

    pool = get_pool()
    card_id = str(uuid4())
    signed_payload = _signed_new_card_payload(normalized_payload, card_id=card_id)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pm_cards (id, title, owner, status, source, link_type, link_id, due_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    card_id,
                    normalized_payload.title,
                    normalized_payload.owner,
                    normalized_payload.status or "todo",
                    normalized_payload.source,
                    normalized_payload.link_type,
                    normalized_payload.link_id,
                    normalized_payload.due_at,
                    Json(signed_payload),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_to_card(row)


def update_card(
    card_id: str,
    payload: PMCardUpdate,
    *,
    _governed_review_transition: bool = False,
    _governed_execution_approval_transition: bool = False,
    _expected_updated_at: datetime | None = None,
) -> Optional[PMCard]:
    pool = get_pool()
    fields = []
    values = []
    current_card = get_card(card_id)
    if current_card is None:
        return None
    if (
        _expected_updated_at is not None
        and current_card.updated_at != _expected_updated_at
    ):
        return None
    write_expected_updated_at = _expected_updated_at or current_card.updated_at
    effective_title = payload.title if payload.title is not None else current_card.title
    effective_source = payload.source if payload.source is not None else current_card.source
    proposed_card_payload = (
        payload.payload if payload.payload is not None else dict(current_card.payload or {})
    )
    _require_update_preserves_owner_decision_resolution(
        current_card,
        proposed_payload=proposed_card_payload,
    )
    _require_update_preserves_execution_approval(
        current_card,
        proposed_payload=proposed_card_payload,
        proposed_title=effective_title,
        proposed_source=effective_source,
        governed_transition=_governed_execution_approval_transition,
    )
    governed_result_transition = bool(
        _governed_review_transition
        and _has_purpose_authorized_execution_result_receipt(current_card)
    )
    if governed_result_transition:
        _require_governed_execution_result_review_transition(
            current_card,
            proposed_payload=proposed_card_payload,
            proposed_status=payload.status,
            proposed_title=effective_title,
            proposed_source=effective_source,
            proposed_owner=payload.owner,
        )
    else:
        _require_generic_update_preserves_execution_authority(
            current_card,
            proposed_payload=proposed_card_payload,
            proposed_status=payload.status,
            proposed_title=effective_title,
            proposed_source=effective_source,
            proposed_owner=payload.owner,
        )
    if payload.title is not None:
        fields.append("title = %s")
        values.append(payload.title)
    if payload.owner is not None:
        fields.append("owner = %s")
        values.append(payload.owner)
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
    if payload.source is not None:
        fields.append("source = %s")
        values.append(payload.source)
    if payload.link_type is not None:
        fields.append("link_type = %s")
        values.append(payload.link_type)
    if payload.link_id is not None:
        fields.append("link_id = %s")
        values.append(payload.link_id)
    if payload.due_at is not None:
        fields.append("due_at = %s")
        values.append(payload.due_at)
    if payload.payload is not None:
        gated_payload = apply_execution_gate(
            card_id=card_id,
            title=effective_title,
            source=effective_source,
            workspace_key=_workspace_key_from_payload(payload.payload),
            payload=payload.payload,
        )
        if not governed_result_transition:
            _require_generic_update_preserves_gate_intent(current_card, gated_payload)
        fields.append("payload = %s")
        values.append(Json(sign_execution_payload(card_id, gated_payload)))
    elif current_card is not None and (payload.title is not None or payload.source is not None):
        effective_title = payload.title if payload.title is not None else current_card.title
        effective_source = payload.source if payload.source is not None else current_card.source
        gated_payload = apply_execution_gate(
            card_id=card_id,
            title=effective_title,
            source=effective_source,
            workspace_key=_workspace_key_from_payload(current_card.payload or {}),
            payload=current_card.payload or {},
        )
        if not governed_result_transition:
            _require_generic_update_preserves_gate_intent(current_card, gated_payload)
        fields.append("payload = %s")
        values.append(Json(sign_execution_payload(card_id, gated_payload)))

    if not fields:
        return get_card(card_id)

    fields.append("updated_at = NOW()")
    values.extend((card_id, write_expected_updated_at))

    query = f"""
        UPDATE pm_cards
        SET {', '.join(fields)}
        WHERE id = %s
          AND updated_at = %s
        RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_card(row) if row else None


def _claim_bound_execution(payload: dict[str, Any]) -> dict[str, Any] | None:
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        return None
    if (
        str(execution.get("state") or "").strip().lower() != "running"
        or str(execution.get("executor_status") or "").strip().lower() != "running"
        or not str(execution.get("claim_id") or "").strip()
        or not str(execution.get("executor_worker_id") or "").strip()
        or not str(execution.get("execution_packet_sha256") or "").strip()
        or not str(execution.get("result_runner_id") or "").strip()
        or not str(execution.get("result_author_agent") or "").strip()
        or not str(execution.get("claimed_execution_gate_intent_hash") or "").strip()
    ):
        return None
    return dict(execution)


def _require_update_preserves_owner_decision_resolution(
    card: PMCard,
    *,
    proposed_payload: dict[str, Any],
) -> None:
    """Reserve canonical owner-decision receipts for the locked reconciler."""

    current_payload = dict(card.payload or {})
    current_has_resolution = "owner_decision_resolution" in current_payload
    proposed_has_resolution = "owner_decision_resolution" in proposed_payload
    if (
        current_has_resolution != proposed_has_resolution
        or (
            current_has_resolution
            and proposed_payload.get("owner_decision_resolution")
            != current_payload.get("owner_decision_resolution")
        )
    ):
        raise ValueError(
            "Generic PM updates cannot create, replace, or remove canonical "
            "owner-decision authority; use the locked canonical decision reconciler."
        )


def _require_update_preserves_execution_approval(
    card: PMCard,
    *,
    proposed_payload: dict[str, Any],
    proposed_title: str,
    proposed_source: str | None,
    governed_transition: bool,
) -> None:
    """Allow execution approval writes only from a validated private PM path."""

    current_payload = dict(card.payload or {})
    current_has_approval = "execution_approval" in current_payload
    proposed_has_approval = "execution_approval" in proposed_payload
    approval_changed = (
        current_has_approval != proposed_has_approval
        or (
            current_has_approval
            and proposed_payload.get("execution_approval")
            != current_payload.get("execution_approval")
        )
    )
    if not approval_changed:
        return
    if governed_transition is not True:
        raise ValueError(
            "Generic PM updates cannot create, replace, or remove execution-approval "
            "authority; use a governed PM approval action."
        )

    approval = proposed_payload.get("execution_approval")
    gate = (
        dict(proposed_payload.get("execution_gate") or {})
        if isinstance(proposed_payload.get("execution_gate"), dict)
        else {}
    )
    current_workspace = canonicalize_workspace_key(_workspace_key_from_card(card))
    proposed_workspace = canonicalize_workspace_key(
        _workspace_key_from_payload(proposed_payload)
    )
    if (
        not isinstance(approval, dict)
        or approval.get("schema_version") != "execution_approval/v1"
        or not str(approval.get("approval_id") or "").strip()
        or not str(approval.get("approved_by") or "").strip()
        or not str(approval.get("approved_at") or "").strip()
        or proposed_workspace != current_workspace
        or gate.get("decision") != REQUIRE_APPROVAL
        or gate.get("approval_state") != "approved"
        or str(approval.get("intent_hash") or "")
        != str(gate.get("intent_hash") or "")
        or not execution_gate_allows_run(proposed_payload)
        or not execution_gate_matches_current(
            card_id=card.id,
            title=proposed_title,
            source=proposed_source,
            workspace_key=current_workspace,
            payload=proposed_payload,
        )
    ):
        raise ValueError(
            "Governed PM approval writes require one current, runnable execution approval "
            "for the card's exact workspace and intent."
        )


def _require_generic_update_preserves_execution_authority(
    card: PMCard,
    *,
    proposed_payload: dict[str, Any],
    proposed_status: str | None,
    proposed_title: str,
    proposed_source: str | None,
    proposed_owner: str | None,
) -> None:
    """Keep generic PM mutation outside claimed and canonical-result authority."""

    current_payload = dict(card.payload or {})
    if (
        proposed_payload.get("scheduler_receipt")
        != current_payload.get("scheduler_receipt")
        and "scheduler_receipt" in proposed_payload
    ):
        raise ValueError(
            "Generic PM updates cannot create or replace scheduler authority."
        )
    claim_execution = _claim_bound_execution(current_payload)
    canonical_result = _has_purpose_authorized_execution_result_receipt(card)
    if claim_execution is None and not canonical_result:
        return
    if not verify_execution_payload(card.id, current_payload):
        raise ValueError("Canonical PM execution authority is missing or invalid.")
    if proposed_title != card.title or proposed_source != card.source:
        raise ValueError(
            "Generic PM updates cannot change title or source while canonical execution authority is active."
        )
    if proposed_owner is not None and proposed_owner != card.owner:
        raise ValueError(
            "Generic PM updates cannot change owner while canonical execution authority is active."
        )
    if proposed_status is not None and str(proposed_status) != str(card.status):
        raise ValueError(
            "Generic PM updates cannot change status while canonical execution authority is active."
        )
    current_workspace = canonicalize_workspace_key(_workspace_key_from_payload(current_payload))
    proposed_workspace = canonicalize_workspace_key(_workspace_key_from_payload(proposed_payload))
    if current_workspace != proposed_workspace:
        raise ValueError(
            "Generic PM updates cannot move canonical execution authority into another workspace."
        )
    if proposed_payload.get("execution") != current_payload.get("execution"):
        raise ValueError(
            "Generic PM updates cannot replace a live claim or canonical execution result."
        )
    for field in ("latest_execution_result", "latest_execution_failure"):
        if proposed_payload.get(field) != current_payload.get(field):
            raise ValueError(
                f"Generic PM updates cannot replace canonical {field.replace('_', ' ')} truth."
            )


def _require_generic_update_preserves_gate_intent(
    card: PMCard,
    proposed_payload: dict[str, Any],
) -> None:
    current_payload = dict(card.payload or {})
    if (
        _claim_bound_execution(current_payload) is None
        and not _has_purpose_authorized_execution_result_receipt(card)
    ):
        return
    current_intent = str(dict(current_payload.get("execution_gate") or {}).get("intent_hash") or "")
    proposed_intent = str(dict(proposed_payload.get("execution_gate") or {}).get("intent_hash") or "")
    if not current_intent or proposed_intent != current_intent:
        raise ValueError(
            "Generic PM updates cannot change the execution intent behind a live claim or canonical result."
        )


def _require_governed_execution_result_review_transition(
    card: PMCard,
    *,
    proposed_payload: dict[str, Any],
    proposed_status: str | None,
    proposed_title: str,
    proposed_source: str | None,
    proposed_owner: str | None,
) -> None:
    """Authorize only the existing review action while retaining its signed result."""

    current_payload = dict(card.payload or {})
    current_result = dict(current_payload.get("latest_execution_result") or {})
    proposed_result = proposed_payload.get("latest_execution_result")
    review = (
        dict(proposed_payload.get("latest_manual_review") or {})
        if isinstance(proposed_payload.get("latest_manual_review"), dict)
        else {}
    )
    action = str(review.get("action") or "").strip().lower()
    expected = {
        "approve": ("done", "done", "manual_approve"),
        "return": ("todo", "queued", "manual_return"),
        "blocked": ("blocked", "queued", "manual_blocked"),
    }.get(action)
    proposed_execution = (
        dict(proposed_payload.get("execution") or {})
        if isinstance(proposed_payload.get("execution"), dict)
        else {}
    )
    history = [item for item in proposed_execution.get("history") or [] if isinstance(item, dict)]
    if (
        not verify_execution_payload(card.id, current_payload)
        or str(card.status or "").strip().lower() != "review"
        or str(current_result.get("status") or "").strip().lower() != "review"
        or expected is None
        or proposed_status != expected[0]
        or str(proposed_execution.get("state") or "").strip().lower() != expected[1]
        or not history
        or str(history[-1].get("event") or "") != expected[2]
        or proposed_result != current_result
        or proposed_title != card.title
        or proposed_source != card.source
        or proposed_owner is not None and proposed_owner != card.owner
        or canonicalize_workspace_key(_workspace_key_from_payload(proposed_payload))
        != canonicalize_workspace_key(_workspace_key_from_payload(current_payload))
        or str(proposed_execution.get("result_id") or "")
        != str(dict(current_payload.get("execution") or {}).get("result_id") or "")
        or str(proposed_execution.get("claim_id") or "")
        != str(dict(current_payload.get("execution") or {}).get("claim_id") or "")
    ):
        raise ValueError(
            "Governed PM review transition must preserve the immutable accepted result and its workspace."
        )


def _normalize_pm_owner_decision_choice(choice: object) -> str:
    normalized = " ".join(str(choice or "").split()).strip()
    if normalized not in PM_OWNER_DECISION_CHOICES:
        raise PMOwnerDecisionReconciliationConflict(
            "Unsupported canonical PM owner decision choice."
        )
    return normalized


def _validate_pm_owner_decision_binding(
    card: PMCard,
    *,
    expected_execution_gate_intent_hash: str,
) -> dict[str, Any]:
    payload = dict(card.payload or {})
    expected_hash = str(expected_execution_gate_intent_hash or "").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_hash):
        raise PMOwnerDecisionReconciliationConflict(
            "The canonical decision is missing its exact signed PM execution intent."
        )
    if not verify_execution_payload(card.id, payload):
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card no longer has valid signed execution authorization."
        )
    gate = _execution_gate_for_card(card)
    if not execution_gate_matches_current(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key=_workspace_key_from_card(card),
        payload=payload,
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card execution gate is stale for its current intent."
        )
    if str(gate.get("intent_hash") or "") != expected_hash:
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card changed after this canonical owner decision was created."
        )
    return gate


def _require_approvable_bounded_internal_pm_intent(
    card: PMCard,
    *,
    gate: dict[str, Any],
) -> None:
    """Allow this owner path to queue internal project work, never external action."""

    payload = dict(card.payload or {})
    completion_contract = (
        dict(payload.get("completion_contract") or {})
        if isinstance(payload.get("completion_contract"), dict)
        else {}
    )
    instructions = payload.get("instructions")
    acceptance_criteria = payload.get("acceptance_criteria")
    done_when = completion_contract.get("done_when")
    if (
        gate.get("capability_id") != BOUNDED_PROJECT_CAPABILITY
        or gate.get("runner_profile") != "codex_workspace"
        or completion_contract.get("source") != "standup_promotion"
        or not isinstance(instructions, list)
        or not any(str(item or "").strip() for item in instructions)
        or not isinstance(acceptance_criteria, list)
        or not any(str(item or "").strip() for item in acceptance_criteria)
        or not isinstance(done_when, list)
        or not any(str(item or "").strip() for item in done_when)
        or not gate.get("allowed_roots")
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "Only a signed, bounded standup-promotion project contract can use this approval choice."
        )
    if isinstance(payload.get("host_action_required"), dict):
        raise PMOwnerDecisionReconciliationConflict(
            "Host or platform actions cannot be approved into the internal PM executor."
        )
    risk_factors = {
        str(item).strip().upper()
        for item in gate.get("risk_factors") or []
        if str(item).strip()
    }
    reason_codes = {
        str(item).strip().upper()
        for item in gate.get("reason_codes") or []
        if str(item).strip()
    }
    if risk_factors - PM_OWNER_DECISION_APPROVABLE_RISK_FACTORS:
        raise PMOwnerDecisionReconciliationConflict(
            "This choice cannot authorize publication, communication, platform, deployment, financial, "
            "destructive, privileged, identity-sensitive, unknown, or otherwise non-internal work."
        )
    if reason_codes - PM_OWNER_DECISION_APPROVABLE_REASON_CODES:
        raise PMOwnerDecisionReconciliationConflict(
            "This PM intent requires a different governed owner-action path and cannot enter internal execution."
        )
    if gate.get("decision") not in {AUTO_EXECUTE, REQUIRE_APPROVAL}:
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card has no recognized execution-gate decision."
        )


def _build_pm_owner_decision_update(
    card: PMCard,
    *,
    decision_id: str,
    choice: str,
    expected_execution_gate_intent_hash: str,
    future_trigger: str,
    decided_by: str,
    decided_at: datetime,
) -> tuple[str, dict[str, Any], str]:
    """Build one signed-authority PM transition from the currently locked card."""

    normalized_choice = _normalize_pm_owner_decision_choice(choice)
    normalized_decision_id = " ".join(str(decision_id or "").split()).strip()
    if not normalized_decision_id or len(normalized_decision_id) > 128:
        raise PMOwnerDecisionReconciliationConflict(
            "A bounded canonical decision identity is required."
        )
    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        raise PMOwnerDecisionReconciliationConflict(
            "The PM owner decision time must be timezone-aware."
        )
    decided_at = decided_at.astimezone(timezone.utc)
    payload = dict(card.payload or {})
    gate = _validate_pm_owner_decision_binding(
        card,
        expected_execution_gate_intent_hash=expected_execution_gate_intent_hash,
    )
    existing_resolution = (
        dict(payload.get("owner_decision_resolution") or {})
        if isinstance(payload.get("owner_decision_resolution"), dict)
        else {}
    )
    if existing_resolution:
        if (
            existing_resolution.get("schema_version")
            == PM_OWNER_DECISION_RESOLUTION_SCHEMA
            and str(existing_resolution.get("decision_id") or "")
            == normalized_decision_id
            and str(existing_resolution.get("choice") or "") == normalized_choice
            and str(existing_resolution.get("bound_execution_gate_intent_hash") or "")
            == str(expected_execution_gate_intent_hash)
        ):
            return str(card.status or "todo"), payload, "already_reconciled"
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card already has a different canonical owner decision receipt."
        )

    status = str(card.status or "todo").strip().lower()
    execution = (
        dict(payload.get("execution") or {})
        if isinstance(payload.get("execution"), dict)
        else {}
    )
    execution_state = str(execution.get("state") or "").strip().lower()
    executor_status = str(execution.get("executor_status") or "").strip().lower()
    latest_result = (
        dict(payload.get("latest_execution_result") or {})
        if isinstance(payload.get("latest_execution_result"), dict)
        else {}
    )
    if (
        _is_closed_pm_status(status)
        or status in {"blocked", "failed", "running", "in_progress"}
        or execution_state in {"running", "in_progress", "claimed", "done", "completed", "failed", "blocked"}
        or executor_status not in {"", "queued", "pending"}
        or str(execution.get("claim_id") or "").strip()
        or str(latest_result.get("result_id") or "").strip()
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card advanced after the owner decision was prepared; no stale state was overwritten."
        )
    if not execution:
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card has no bounded execution lifecycle to reconcile."
        )

    normalized_trigger = " ".join(str(future_trigger or "").split()).strip()[:1000]
    if not normalized_trigger:
        normalized_trigger = (
            "New eligible evidence changes this recommendation or its authorization boundary."
        )
    now_iso = decided_at.isoformat()
    history = list(execution.get("history") or [])
    resolution_state = {
        "approve_bounded_internal_action": "queued",
        "reject_recommendation": "rejected",
        "retain_until_trigger": "retained",
    }[normalized_choice]
    receipt = {
        "schema_version": PM_OWNER_DECISION_RESOLUTION_SCHEMA,
        "decision_id": normalized_decision_id,
        "choice": normalized_choice,
        "state": resolution_state,
        "decided_by": " ".join(str(decided_by or "Neo").split()).strip()[:120] or "Neo",
        "decided_at": now_iso,
        "bound_execution_gate_intent_hash": str(expected_execution_gate_intent_hash),
        "future_trigger": normalized_trigger if normalized_choice == "retain_until_trigger" else None,
    }
    payload["owner_decision_resolution"] = receipt

    if normalized_choice == "approve_bounded_internal_action":
        _require_approvable_bounded_internal_pm_intent(card, gate=gate)
        payload = grant_execution_approval(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=_workspace_key_from_card(card),
            payload=payload,
            approved_by=receipt["decided_by"],
            reason="Owner approved this exact bounded internal PM intent through its canonical decision.",
            surface="canonical_owner_decision",
        )
        execution = dict(payload.get("execution") or execution)
        history.append(
            {
                "event": "canonical_owner_approved_bounded_internal_action",
                "state": "queued",
                "requested_by": receipt["decided_by"],
                "decision_id": normalized_decision_id,
                "at": now_iso,
            }
        )
        execution.update(
            {
                "state": "queued",
                "queued_at": execution.get("queued_at") or now_iso,
                "last_transition_at": now_iso,
                "manager_attention_required": False,
                "executor_status": None,
                "executor_worker_id": None,
                "execution_packet_path": None,
                "claim_id": None,
                "history": history[-16:],
            }
        )
        payload["execution"] = execution
        next_status = "todo"
        disposition = "queued"
    elif normalized_choice == "reject_recommendation":
        payload.pop("execution_approval", None)
        history.append(
            {
                "event": "canonical_owner_rejected_recommendation",
                "state": "cancelled",
                "requested_by": receipt["decided_by"],
                "decision_id": normalized_decision_id,
                "at": now_iso,
            }
        )
        execution.update(
            {
                "state": "cancelled",
                "last_transition_at": now_iso,
                "manager_attention_required": False,
                "executor_status": None,
                "executor_worker_id": None,
                "execution_packet_path": None,
                "claim_id": None,
                "history": history[-16:],
            }
        )
        payload["execution"] = execution
        next_status = "cancelled"
        disposition = "rejected"
    else:
        payload.pop("execution_approval", None)
        history.append(
            {
                "event": "canonical_owner_retained_until_trigger",
                "state": "approval_required",
                "requested_by": receipt["decided_by"],
                "decision_id": normalized_decision_id,
                "future_trigger": normalized_trigger,
                "at": now_iso,
            }
        )
        execution.update(
            {
                "state": "approval_required",
                "last_transition_at": now_iso,
                "manager_attention_required": False,
                "executor_status": None,
                "executor_worker_id": None,
                "execution_packet_path": None,
                "claim_id": None,
                "history": history[-16:],
            }
        )
        payload["execution"] = execution
        next_status = "review"
        disposition = "retained"

    payload = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key=_workspace_key_from_card(card),
        payload=payload,
    )
    return next_status, payload, disposition


def reconcile_pm_owner_decision(
    card_id: str,
    *,
    decision_id: str,
    choice: str,
    expected_execution_gate_intent_hash: str,
    future_trigger: str,
    decided_by: str = "Neo",
) -> tuple[PMCard, str]:
    """Atomically reconcile one resolved canonical decision through PM authority.

    The linked row is locked and revalidated against the exact execution-gate
    intent captured by the decision. Exact replays return the durable receipt;
    different or stale work fails without replacing newer PM truth.
    """

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise PMOwnerDecisionReconciliationConflict(
                    "The canonical decision's linked PM card no longer exists."
                )
            card = _row_to_card(row)
            next_status, next_payload, disposition = _build_pm_owner_decision_update(
                card,
                decision_id=decision_id,
                choice=choice,
                expected_execution_gate_intent_hash=expected_execution_gate_intent_hash,
                future_trigger=future_trigger,
                decided_by=decided_by,
                decided_at=datetime.now(timezone.utc),
            )
            if disposition == "already_reconciled":
                conn.commit()
                return card, disposition
            signed_payload = sign_execution_payload(card.id, next_payload)
            cur.execute(
                """
                UPDATE pm_cards
                SET status = %s,
                    payload = %s,
                    updated_at = clock_timestamp()
                WHERE id = %s
                  AND updated_at = %s
                  AND COALESCE(payload->'execution_gate'->>'intent_hash', '') = %s
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    next_status,
                    Json(signed_payload),
                    card.id,
                    row["updated_at"],
                    str(expected_execution_gate_intent_hash),
                ),
            )
            updated_row = cur.fetchone()
        if updated_row is None:
            conn.rollback()
            raise PMOwnerDecisionReconciliationConflict(
                "The linked PM card changed before its canonical owner decision could be reconciled."
            )
        conn.commit()
    return _row_to_card(updated_row), disposition


def preflight_pm_owner_decision(
    card_id: str,
    *,
    decision_id: str,
    choice: str,
    expected_execution_gate_intent_hash: str,
    future_trigger: str,
    decided_by: str = "Neo",
) -> str:
    """Fail deterministic stale or unsafe choices before the canonical commit.

    The actual PM write still occurs after the canonical transition. This
    read-only check prevents a known-invalid publication or stale-intent choice
    from terminally resolving the local decision, while the locked reconciler
    remains the final authority against races.
    """

    card = get_card(card_id)
    if card is None:
        raise PMOwnerDecisionReconciliationConflict(
            "The canonical decision's linked PM card no longer exists."
        )
    _next_status, _next_payload, disposition = _build_pm_owner_decision_update(
        card,
        decision_id=decision_id,
        choice=choice,
        expected_execution_gate_intent_hash=expected_execution_gate_intent_hash,
        future_trigger=future_trigger,
        decided_by=decided_by,
        decided_at=datetime.now(timezone.utc),
    )
    return disposition


def _build_retained_pm_owner_decision_refresh(
    card: PMCard,
    *,
    expected_decision_id: str,
    expected_execution_gate_intent_hash: str,
    title: str,
    proposed_payload: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    """Build a new signed intent only when an exact Dream delta fires retention."""

    old_gate = _validate_pm_owner_decision_binding(
        card,
        expected_execution_gate_intent_hash=expected_execution_gate_intent_hash,
    )
    current_payload = dict(card.payload or {})
    resolution = (
        dict(current_payload.get("owner_decision_resolution") or {})
        if isinstance(current_payload.get("owner_decision_resolution"), dict)
        else {}
    )
    normalized_decision_id = " ".join(str(expected_decision_id or "").split()).strip()
    retained_trigger = " ".join(
        str(resolution.get("future_trigger") or "").split()
    ).strip()[:1000]
    if (
        resolution.get("schema_version") != PM_OWNER_DECISION_RESOLUTION_SCHEMA
        or resolution.get("choice") != "retain_until_trigger"
        or resolution.get("state") != "retained"
        or str(resolution.get("decision_id") or "") != normalized_decision_id
        or str(resolution.get("bound_execution_gate_intent_hash") or "")
        != str(expected_execution_gate_intent_hash)
        or not retained_trigger
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "The linked PM card does not have the exact retained canonical owner decision to refresh."
        )
    execution = (
        dict(current_payload.get("execution") or {})
        if isinstance(current_payload.get("execution"), dict)
        else {}
    )
    if (
        str(card.status or "").strip().lower() != "review"
        or str(execution.get("state") or "").strip().lower() != "approval_required"
        or str(execution.get("claim_id") or "").strip()
        or str(execution.get("executor_status") or "").strip()
        or isinstance(current_payload.get("latest_execution_result"), dict)
        and str(current_payload["latest_execution_result"].get("result_id") or "").strip()
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "The retained PM lane advanced before its future trigger could refresh the intent."
        )

    next_payload = dict(proposed_payload or {})
    current_workspace_key = canonicalize_workspace_key(_workspace_key_from_card(card))
    proposed_workspace_key = canonicalize_workspace_key(
        _workspace_key_from_payload(next_payload)
    )
    if proposed_workspace_key != current_workspace_key:
        raise PMOwnerDecisionReconciliationConflict(
            "A retained PM lane trigger cannot move work into a different workspace."
        )
    evidence = (
        dict(next_payload.get("retained_trigger_evidence") or {})
        if isinstance(next_payload.get("retained_trigger_evidence"), dict)
        else {}
    )
    dream_lineage = (
        dict(next_payload.get("dream_lineage") or {})
        if isinstance(next_payload.get("dream_lineage"), dict)
        else {}
    )
    source_delta = (
        dict(dream_lineage.get("source_goal_delta") or {})
        if isinstance(dream_lineage.get("source_goal_delta"), dict)
        else {}
    )
    prior_lineage = (
        dict(current_payload.get("dream_lineage") or {})
        if isinstance(current_payload.get("dream_lineage"), dict)
        else {}
    )
    prior_delta = (
        dict(prior_lineage.get("source_goal_delta") or {})
        if isinstance(prior_lineage.get("source_goal_delta"), dict)
        else {}
    )
    source_delta_id = str(source_delta.get("goal_delta_id") or "").strip()
    source_consolidation_id = str(source_delta.get("consolidation_id") or "").strip()
    if (
        evidence.get("schema_version") != PM_RETAINED_TRIGGER_EVIDENCE_SCHEMA
        or str(evidence.get("prior_decision_id") or "") != normalized_decision_id
        or str(evidence.get("prior_execution_gate_intent_hash") or "")
        != str(expected_execution_gate_intent_hash)
        or " ".join(str(evidence.get("prior_future_trigger") or "").split()).strip()
        != retained_trigger
        or source_delta.get("schema_version") != "dream_workspace_goal_delta/v1"
        or source_delta.get("delta_kind") != "unresolved_action_recommendation"
        or canonicalize_workspace_key(
            str(source_delta.get("workspace_key") or "").strip()
        )
        != current_workspace_key
        or not source_delta_id
        or source_delta_id == str(prior_delta.get("goal_delta_id") or "").strip()
        or str(evidence.get("source_goal_delta_id") or "") != source_delta_id
        or not source_consolidation_id
        or str(evidence.get("source_consolidation_id") or "")
        != source_consolidation_id
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "A distinct exact Dream goal delta must evidence the retained PM lane's explicit future trigger."
        )

    normalized_title = " ".join(str(title or "").split()).strip()[:300]
    if not normalized_title:
        raise PMOwnerDecisionReconciliationConflict(
            "A retained PM lane refresh requires one bounded successor title."
        )
    next_execution = (
        dict(next_payload.get("execution") or {})
        if isinstance(next_payload.get("execution"), dict)
        else {}
    )
    if (
        str(next_execution.get("state") or "").strip().lower() != "queued"
        or str(next_execution.get("claim_id") or "").strip()
        or str(next_execution.get("executor_status") or "").strip()
    ):
        raise PMOwnerDecisionReconciliationConflict(
            "The refreshed retained lane must re-enter the existing unclaimed PM queue lifecycle."
        )
    next_payload.pop("owner_decision_resolution", None)
    next_payload.pop("execution_approval", None)
    next_payload.pop("scheduler_receipt", None)
    next_payload = apply_execution_gate(
        card_id=card.id,
        title=normalized_title,
        source=card.source,
        workspace_key=current_workspace_key,
        payload=next_payload,
    )
    next_gate = dict(next_payload.get("execution_gate") or {})
    if str(next_gate.get("intent_hash") or "") == str(old_gate.get("intent_hash") or ""):
        raise PMOwnerDecisionReconciliationConflict(
            "The exact Dream trigger did not produce a distinct PM execution intent."
        )
    return "todo", next_payload, "refreshed"


def refresh_retained_pm_owner_decision_lane(
    card_id: str,
    *,
    expected_card_updated_at: datetime,
    expected_decision_id: str,
    expected_execution_gate_intent_hash: str,
    title: str,
    proposed_payload: dict[str, Any],
) -> tuple[PMCard, str]:
    """CAS-refresh one retained PM row in place from exact Dream evidence."""

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise PMOwnerDecisionReconciliationConflict(
                    "The retained canonical decision's linked PM card no longer exists."
                )
            card = _row_to_card(row)
            current_payload = dict(card.payload or {})
            current_evidence = (
                dict(current_payload.get("retained_trigger_evidence") or {})
                if isinstance(current_payload.get("retained_trigger_evidence"), dict)
                else {}
            )
            proposed_evidence = (
                dict(proposed_payload.get("retained_trigger_evidence") or {})
                if isinstance(proposed_payload.get("retained_trigger_evidence"), dict)
                else {}
            )
            if not isinstance(current_payload.get("owner_decision_resolution"), dict):
                if (
                    current_evidence == proposed_evidence
                    and card.title == " ".join(str(title or "").split()).strip()[:300]
                    and verify_execution_payload(card.id, current_payload)
                    and execution_gate_matches_current(
                        card_id=card.id,
                        title=card.title,
                        source=card.source,
                        workspace_key=_workspace_key_from_card(card),
                        payload=current_payload,
                    )
                    and str(
                        dict(current_payload.get("execution_gate") or {}).get("intent_hash")
                        or ""
                    )
                    != str(expected_execution_gate_intent_hash)
                ):
                    conn.commit()
                    return card, "already_refreshed"
                conn.rollback()
                raise PMOwnerDecisionReconciliationConflict(
                    "The retained PM lane no longer has the exact owner decision targeted by this trigger."
                )
            if row["updated_at"] != expected_card_updated_at:
                conn.rollback()
                raise PMOwnerDecisionReconciliationConflict(
                    "The retained PM lane changed before its exact Dream trigger could refresh it."
                )

            next_status, next_payload, disposition = _build_retained_pm_owner_decision_refresh(
                card,
                expected_decision_id=expected_decision_id,
                expected_execution_gate_intent_hash=expected_execution_gate_intent_hash,
                title=title,
                proposed_payload=proposed_payload,
            )
            signed_payload = sign_execution_payload(card.id, next_payload)
            cur.execute(
                """
                UPDATE pm_cards
                SET title = %s,
                    status = %s,
                    payload = %s,
                    updated_at = clock_timestamp()
                WHERE id = %s
                  AND updated_at = %s
                  AND COALESCE(payload->'execution_gate'->>'intent_hash', '') = %s
                  AND COALESCE(payload->'owner_decision_resolution'->>'decision_id', '') = %s
                  AND COALESCE(payload->'owner_decision_resolution'->>'choice', '') = 'retain_until_trigger'
                  AND COALESCE(payload->'owner_decision_resolution'->>'state', '') = 'retained'
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    " ".join(str(title or "").split()).strip()[:300],
                    next_status,
                    Json(signed_payload),
                    card.id,
                    row["updated_at"],
                    str(expected_execution_gate_intent_hash),
                    str(expected_decision_id),
                ),
            )
            updated_row = cur.fetchone()
        if updated_row is None:
            conn.rollback()
            raise PMOwnerDecisionReconciliationConflict(
                "The retained PM lane changed before its exact Dream trigger refresh committed."
            )
        conn.commit()
    return _row_to_card(updated_row), disposition


def _execution_result_commit_digest(payload: PMExecutionResultCommitRequest) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _execution_result_commit_authorization_id(card_id: str, result_id: str) -> str:
    return f"pm-execution-result-commit:{card_id}:{result_id}"


def _result_runner_id_for_target(target_agent: object) -> str:
    """Use the same stable result-writer identity as the local runner packet."""

    lowered = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(target_agent or "").strip()
    )
    return "-".join(part for part in lowered.split("-") if part) or "codex-executor"


def _authorize_execution_result_commit_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Bind one result receipt to the canonical signing authority and purpose."""

    next_receipt = dict(receipt)
    card_id = str(next_receipt.get("card_id") or "").strip()
    result_id = str(next_receipt.get("result_id") or "").strip()
    authorized = sign_execution_payload(
        _execution_result_commit_authorization_id(card_id, result_id),
        next_receipt,
    )
    authorization = authorized.get(AUTH_FIELD)
    if isinstance(authorization, dict):
        next_receipt["commit_authorization"] = dict(authorization)
    return next_receipt


def _execution_result_timestamp_semantics(result: dict[str, Any]) -> str | None:
    """Classify exact signed legacy or current result timestamp semantics.

    Marker absence is accepted only as compatibility truth for receipts written
    before the current semantic timestamp contract. It does not claim that the
    legacy executor-finished value represented actual executor completion.
    """

    if "timestamp_semantics" not in result:
        return "legacy_pm_commit_time/v1"
    if (
        result.get("timestamp_semantics")
        == PM_EXECUTION_RESULT_TIMESTAMP_SEMANTICS
    ):
        return PM_EXECUTION_RESULT_TIMESTAMP_SEMANTICS
    return None


def _has_purpose_authorized_execution_result_receipt(card: PMCard) -> bool:
    """Verify the immutable accepted receipt independent of later PM lifecycle state."""

    payload = dict(card.payload or {})
    result = (
        dict(payload.get("latest_execution_result") or {})
        if isinstance(payload.get("latest_execution_result"), dict)
        else {}
    )
    authorization = (
        dict(result.get("commit_authorization") or {})
        if isinstance(result.get("commit_authorization"), dict)
        else {}
    )
    if (
        result.get("schema_version") != PM_EXECUTION_RESULT_COMMIT_SCHEMA
        or _execution_result_timestamp_semantics(result) is None
        or str(result.get("status") or "").strip().lower()
        not in {"done", "review", "blocked"}
        or authorization.get("version") != 1
        or authorization.get("algorithm") != "hmac-sha256"
        or not str(authorization.get("signature") or "").strip()
    ):
        return False
    request_payload = {
        key: result.get(key) for key in PMExecutionResultCommitRequest.model_fields
    }
    try:
        request = PMExecutionResultCommitRequest.model_validate(request_payload)
        committed_at = datetime.fromisoformat(
            str(result.get("committed_at") or "").strip().replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return False
    if (
        committed_at.tzinfo is None
        or committed_at.utcoffset() is None
        or request.created_at.astimezone(timezone.utc)
        > committed_at.astimezone(timezone.utc)
        or str(request.card_id) != str(card.id)
        or request.workspace_key != _workspace_key_from_card(card)
        or request.title != card.title
        or str(result.get("commit_digest") or "")
        != _execution_result_commit_digest(request)
    ):
        return False
    unsigned_receipt = dict(result)
    unsigned_receipt.pop("commit_authorization", None)
    return verify_execution_payload(
        _execution_result_commit_authorization_id(
            str(request.card_id),
            str(request.result_id),
        ),
        {**unsigned_receipt, AUTH_FIELD: authorization},
    )


def _has_authorized_execution_result_commit(card: PMCard) -> bool:
    """Return whether `card` carries one exact purpose-authorized result receipt.

    The card-level signature alone is insufficient because generic PM updates
    are also re-signed. The result writer therefore adds a purpose-bound
    authorization over the complete receipt. Every committed status must also
    match the status-specific PM and execution state written by this authority.
    """

    if not _has_purpose_authorized_execution_result_receipt(card):
        return False
    payload = dict(card.payload or {})
    result = (
        dict(payload.get("latest_execution_result") or {})
        if isinstance(payload.get("latest_execution_result"), dict)
        else {}
    )
    execution = (
        dict(payload.get("execution") or {})
        if isinstance(payload.get("execution"), dict)
        else {}
    )
    authorization = (
        dict(result.get("commit_authorization") or {})
        if isinstance(result.get("commit_authorization"), dict)
        else {}
    )
    if (
        result.get("schema_version") != PM_EXECUTION_RESULT_COMMIT_SCHEMA
        or str(result.get("status") or "").strip().lower()
        not in {"done", "review", "blocked"}
        or authorization.get("version") != 1
        or authorization.get("algorithm") != "hmac-sha256"
        or not str(authorization.get("signature") or "").strip()
    ):
        return False

    request_fields = PMExecutionResultCommitRequest.model_fields
    request_payload = {key: result.get(key) for key in request_fields}
    try:
        request = PMExecutionResultCommitRequest.model_validate(request_payload)
    except (TypeError, ValueError):
        return False
    card_id = str(request.card_id)
    result_id = str(request.result_id)
    claim_id = str(request.claim_id)
    result_status = str(request.status)
    expected_execution_state = "queued" if result_status == "blocked" else result_status
    expected_history_event = "blocked_return" if result_status == "blocked" else "result"
    expected_assigned_runner = (
        "jean-claude" if result_status == "blocked" else request.runner_id
    )
    committed_at_raw = str(result.get("committed_at") or "").strip()
    executor_finished_at_raw = str(execution.get("executor_finished_at") or "").strip()
    executor_started_at_raw = str(execution.get("executor_started_at") or "").strip()
    timestamp_semantics = _execution_result_timestamp_semantics(result)
    try:
        committed_at = datetime.fromisoformat(committed_at_raw.replace("Z", "+00:00"))
        executor_finished_at = datetime.fromisoformat(
            executor_finished_at_raw.replace("Z", "+00:00")
        )
        executor_started_at = datetime.fromisoformat(
            executor_started_at_raw.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return False
    if (
        committed_at.tzinfo is None
        or committed_at.utcoffset() is None
        or executor_finished_at.tzinfo is None
        or executor_finished_at.utcoffset() is None
        or executor_started_at.tzinfo is None
        or executor_started_at.utcoffset() is None
    ):
        return False
    if timestamp_semantics == PM_EXECUTION_RESULT_TIMESTAMP_SEMANTICS:
        executor_finished_at_is_authorized = (
            executor_finished_at.astimezone(timezone.utc)
            == request.created_at.astimezone(timezone.utc)
        )
    elif timestamp_semantics == "legacy_pm_commit_time/v1":
        executor_finished_at_is_authorized = (
            executor_finished_at.astimezone(timezone.utc)
            == committed_at.astimezone(timezone.utc)
        )
    else:
        return False
    if (
        not executor_finished_at_is_authorized
        or request.created_at.astimezone(timezone.utc)
        < executor_started_at.astimezone(timezone.utc)
        or request.created_at.astimezone(timezone.utc)
        > committed_at.astimezone(timezone.utc)
        or card_id != str(card.id)
        or request.workspace_key != _workspace_key_from_card(card)
        or request.title != card.title
        or str(card.status or "").strip().lower() != result_status
        or str(result.get("commit_digest") or "")
        != _execution_result_commit_digest(request)
        or str(execution.get("state") or "").strip().lower()
        != expected_execution_state
        or str(execution.get("executor_status") or "").strip().lower()
        != "completed"
        or str(execution.get("result_id") or "") != result_id
        or str(execution.get("claim_id") or "") != claim_id
        or str(execution.get("executor_worker_id") or "") != request.worker_id
        or str(execution.get("result_runner_id") or "") != request.runner_id
        or str(execution.get("result_author_agent") or "") != request.author_agent
        or str(execution.get("execution_packet_sha256") or "")
        != request.execution_packet_sha256
        or not str(execution.get("claimed_execution_gate_intent_hash") or "")
        or str(execution.get("claimed_execution_gate_intent_hash") or "")
        != str(dict(payload.get("execution_gate") or {}).get("intent_hash") or "")
        or str(execution.get("assigned_runner") or "")
        != expected_assigned_runner
    ):
        return False
    matching_history = any(
        isinstance(item, dict)
        and item.get("event") == expected_history_event
        and str(item.get("state") or "").strip().lower()
        == expected_execution_state
        and str(item.get("result_id") or "") == result_id
        and str(item.get("claim_id") or "") == claim_id
        and str(item.get("runner_id") or "") == request.runner_id
        and str(item.get("at") or "") == committed_at_raw
        for item in execution.get("history") or []
    )
    if not matching_history:
        return False

    unsigned_receipt = dict(result)
    unsigned_receipt.pop("commit_authorization", None)
    proof_payload = {**unsigned_receipt, AUTH_FIELD: authorization}
    return verify_execution_payload(
        _execution_result_commit_authorization_id(card_id, result_id),
        proof_payload,
    )


def has_canonical_execution_result_commit(card: PMCard) -> bool:
    """Return whether `card` has a canonical completed (`done`) result."""

    result = dict(card.payload or {}).get("latest_execution_result")
    return bool(
        isinstance(result, dict)
        and str(result.get("status") or "").strip().lower() == "done"
        and _has_authorized_execution_result_commit(card)
    )


def _require_safe_execution_result_references(request: PMExecutionResultCommitRequest) -> None:
    """Reject host-private paths before they can enter remote PM state."""

    try:
        validate_remote_execution_artifact_reference(request.result_path)
        validate_remote_execution_artifact_reference(request.memo_path)
        validate_remote_execution_artifact_reference(request.work_order_path)
        if request.workspace_result_path:
            validate_remote_execution_artifact_reference(request.workspace_result_path)
        for artifact in request.artifacts:
            validate_remote_execution_artifact_reference(artifact, allow_web_url=True)
    except ValueError as exc:
        raise PMExecutionResultCommitConflict(
            "Execution result artifacts must use safe logical references; local filesystem paths are not accepted."
        ) from exc
    if contains_private_filesystem_reference(request.model_dump_json()):
        raise PMExecutionResultCommitConflict(
            "Execution result content must not expose a private local filesystem path."
        )


def claim_execution(
    card_id: str,
    request: PMExecutionClaimRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> tuple[PMCard, str] | None:
    """Atomically claim one signed runnable card for one exact local worker."""

    try:
        validate_remote_execution_artifact_reference(request.execution_packet_path)
    except ValueError as exc:
        raise PMExecutionClaimConflict(
            "PM execution packet must use a control-plane-safe logical reference."
        ) from exc
    pool = get_pool()
    claim_id = str(request.claim_id)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            card = _row_to_card(row)
            payload = dict(card.payload or {})
            if (
                _is_workspace_owner_review_card(card)
                and legacy_owner_review_compatibility is not True
                and payload.get("legacy_owner_review_compatibility") is not True
            ):
                raise PMExecutionClaimConflict(
                    "Historical owner-review PM rows are read-only without rollback compatibility."
                )
            if not verify_execution_payload(card.id, payload):
                raise PMExecutionClaimConflict("PM card execution authorization is missing or invalid.")
            try:
                current_gate = require_current_execution_gate(
                    card_id=card.id,
                    title=card.title,
                    source=card.source,
                    workspace_key=_workspace_key_from_card(card),
                    payload=payload,
                )
            except ValueError as exc:
                raise PMExecutionClaimConflict(str(exc)) from exc
            if _is_closed_pm_status(card.status) or str(card.status or "").strip().lower() in {"blocked", "failed"}:
                raise PMExecutionClaimConflict("PM card is not in a claimable status.")
            execution = payload.get("execution")
            if not isinstance(execution, dict):
                raise PMExecutionClaimConflict("PM card has no execution contract to claim.")
            current_workspace = _workspace_key_from_card(card)
            effective_execution = _merge_execution_defaults(
                execution,
                execution_defaults_for_workspace(current_workspace),
            )
            raw_mode = str(execution.get("execution_mode") or "").strip()
            raw_target = str(execution.get("target_agent") or "").strip()
            current_mode = str(effective_execution.get("execution_mode") or "").strip()
            current_target = str(effective_execution.get("target_agent") or "").strip()
            if current_workspace != request.workspace_key:
                raise PMExecutionClaimConflict("PM card execution workspace does not match the claim request.")
            if current_mode != request.execution_mode:
                raise PMExecutionClaimConflict("PM card execution mode does not match the claim request.")
            if current_target != request.target_agent:
                raise PMExecutionClaimConflict("PM card execution target does not match the claim request.")

            current_state = str(execution.get("state") or "").strip().lower()
            current_executor_status = str(execution.get("executor_status") or "").strip().lower()
            current_claim_id = str(execution.get("claim_id") or "").strip()
            current_worker_id = str(execution.get("executor_worker_id") or "").strip()
            current_packet_path = str(execution.get("execution_packet_path") or "").strip()
            current_packet_sha256 = str(execution.get("execution_packet_sha256") or "").strip()
            if current_state == "running" and current_executor_status == "running":
                if (
                    current_claim_id == claim_id
                    and current_worker_id == request.worker_id
                    and current_packet_path == request.execution_packet_path
                    and current_packet_sha256 == request.execution_packet_sha256
                ):
                    return card, "already_claimed"
                raise PMExecutionClaimConflict("PM card already has a different active execution claim.")
            if current_state not in {"queued", "running"} or current_executor_status not in {"", "queued"}:
                raise PMExecutionClaimConflict("PM card execution is not currently claimable.")

            now = datetime.now(timezone.utc)
            result_author_agent = current_target
            result_runner_id = _result_runner_id_for_target(result_author_agent)
            history = list(execution.get("history") or [])
            history.append(
                {
                    "event": "codex_execution_claimed",
                    "state": "running",
                    "runner_id": request.runner_id,
                    "requested_by": request.worker_id,
                    "at": now.isoformat(),
                    "claim_id": claim_id,
                }
            )
            next_execution = {
                **effective_execution,
                "state": "running",
                "execution_packet_path": request.execution_packet_path,
                "execution_packet_sha256": request.execution_packet_sha256,
                "result_author_agent": result_author_agent,
                "result_runner_id": result_runner_id,
                "claimed_execution_gate_intent_hash": str(current_gate.get("intent_hash") or ""),
                "executor_status": "running",
                "executor_worker_id": request.worker_id,
                "claim_id": claim_id,
                "executor_started_at": now.isoformat(),
                "executor_finished_at": None,
                "executor_last_error": None,
                "last_transition_at": now.isoformat(),
                "history": history[-16:],
            }
            next_payload = dict(payload)
            next_payload["execution"] = next_execution
            next_payload = apply_execution_gate(
                card_id=card.id,
                title=card.title,
                source=card.source,
                workspace_key=current_workspace,
                payload=next_payload,
            )
            signed_payload = sign_execution_payload(card.id, next_payload)
            next_status = (
                "in_progress"
                if str(card.status or "").strip().lower() in {"", "todo", "queued", "ready"}
                else str(card.status or "in_progress")
            )
            cur.execute(
                """
                UPDATE pm_cards
                SET status = %s,
                    payload = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND updated_at = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled', 'blocked', 'failed')
                  AND LOWER(COALESCE(payload->'execution'->>'state', '')) IN ('queued', 'running')
                  AND LOWER(COALESCE(payload->'execution'->>'executor_status', '')) IN ('', 'queued')
                  AND COALESCE(payload->'execution'->>'execution_mode', '') = %s
                  AND COALESCE(payload->'execution'->>'target_agent', '') = %s
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    next_status,
                    Json(signed_payload),
                    card.id,
                    row["updated_at"],
                    raw_mode,
                    raw_target,
                ),
            )
            updated_row = cur.fetchone()
        conn.commit()
    if updated_row is None:
        raise PMExecutionClaimConflict("PM card changed before its execution claim could be committed.")
    return _row_to_card(updated_row), "claimed"


def _execution_claim_failure_digest(request: PMExecutionClaimFailureRequest) -> str:
    canonical = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def fail_execution_claim(
    card_id: str,
    request: PMExecutionClaimFailureRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> tuple[PMCard, str] | None:
    """Atomically fail only the exact signed execution claim observed by a runner.

    The runner's detached card payload is never accepted as write input. The
    canonical row is locked, its signature and current execution gate are
    revalidated, and the update repeats the claim, worker, gate, running state,
    and ``updated_at`` predicates. A result commit, owner reconciliation, stale
    recovery, heartbeat, or replacement claim therefore wins without being
    overwritten by a delayed failure report.
    """

    if str(request.card_id) != str(card_id):
        raise PMExecutionClaimFailureConflict("Execution failure card_id does not match the route.")

    expected_updated_at = request.expected_updated_at.astimezone(timezone.utc)
    claim_id = str(request.claim_id)
    failure_id = str(request.failure_id)
    failure_digest = _execution_claim_failure_digest(request)
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            card = _row_to_card(row)
            current_payload = dict(card.payload or {})
            if (
                _is_workspace_owner_review_card(card)
                and legacy_owner_review_compatibility is not True
                and current_payload.get("legacy_owner_review_compatibility") is not True
            ):
                raise PMExecutionClaimFailureConflict(
                    "Historical owner-review PM rows are read-only without rollback compatibility."
                )
            if not verify_execution_payload(card.id, current_payload):
                raise PMExecutionClaimFailureConflict(
                    "PM card execution authorization is missing or invalid."
                )

            # An exact signed receipt replay is a read-only success even when
            # later governed work has moved the card to a non-runnable gate.
            # It must never reopen or replace that newer truth.
            latest_failure = current_payload.get("latest_execution_failure")
            if isinstance(latest_failure, dict) and str(latest_failure.get("failure_id") or "") == failure_id:
                if str(latest_failure.get("failure_digest") or "") != failure_digest:
                    raise PMExecutionClaimFailureConflict(
                        "The failure id is already recorded with different content."
                    )
                return card, "already_failed"

            try:
                require_current_execution_gate(
                    card_id=card.id,
                    title=card.title,
                    source=card.source,
                    workspace_key=_workspace_key_from_card(card),
                    payload=current_payload,
                )
            except ValueError as exc:
                raise PMExecutionClaimFailureConflict(str(exc)) from exc

            row_updated_at = row.get("updated_at")
            if not isinstance(row_updated_at, datetime) or row_updated_at.astimezone(timezone.utc) != expected_updated_at:
                raise PMExecutionClaimFailureConflict(
                    "PM card changed after this execution claim was observed; no stale failure was written."
                )
            if _is_closed_pm_status(card.status) or str(card.status or "").strip().lower() in {"blocked", "failed"}:
                raise PMExecutionClaimFailureConflict("PM card is no longer in a fail-able execution status.")

            execution = current_payload.get("execution")
            if not isinstance(execution, dict):
                raise PMExecutionClaimFailureConflict("PM card has no active execution claim.")
            if str(execution.get("state") or "").strip().lower() != "running" or str(
                execution.get("executor_status") or ""
            ).strip().lower() != "running":
                raise PMExecutionClaimFailureConflict("PM card execution is no longer running.")
            if str(execution.get("claim_id") or "") != claim_id:
                raise PMExecutionClaimFailureConflict("PM card execution claim_id does not match.")
            if str(execution.get("executor_worker_id") or "") != request.worker_id:
                raise PMExecutionClaimFailureConflict("PM card execution worker does not match.")

            safe_error = sanitize_brain_text(" ".join(request.error_message.split()).strip())[:4000]
            if not safe_error:
                safe_error = "Execution failed without a safe error message."
            recorded_at = datetime.now(timezone.utc)
            failed_at = recorded_at
            history = list(execution.get("history") or [])
            history.append(
                {
                    "event": "codex_execution_failed",
                    "state": "failed",
                    "runner_id": request.runner_id,
                    "requested_by": request.worker_id,
                    "at": failed_at.isoformat(),
                    "recorded_at": recorded_at.isoformat(),
                    "claim_id": claim_id,
                    "failure_id": failure_id,
                    "error": safe_error[:400],
                }
            )
            next_execution = {
                **execution,
                "state": "failed",
                "executor_status": "failed",
                "executor_finished_at": failed_at.isoformat(),
                "executor_last_error": safe_error,
                "manager_attention_required": True,
                "last_transition_at": failed_at.isoformat(),
                "history": history[-16:],
            }
            next_payload = dict(current_payload)
            next_payload["execution"] = next_execution
            next_payload["latest_execution_failure"] = {
                "schema_version": "pm_execution_claim_failure_receipt/v1",
                "failure_id": failure_id,
                "failure_digest": failure_digest,
                "claim_id": claim_id,
                "worker_id": request.worker_id,
                "runner_id": request.runner_id,
                "failed_at": failed_at.isoformat(),
                "recorded_at": recorded_at.isoformat(),
                "error": safe_error,
            }
            current_workspace = _workspace_key_from_card(card)
            current_gate = dict(current_payload.get("execution_gate") or {})
            current_gate_intent_hash = str(current_gate.get("intent_hash") or "")
            next_payload = apply_execution_gate(
                card_id=card.id,
                title=card.title,
                source=card.source,
                workspace_key=current_workspace,
                payload=next_payload,
            )
            signed_payload = sign_execution_payload(card.id, next_payload)
            cur.execute(
                """
                UPDATE pm_cards
                SET payload = %s,
                    updated_at = clock_timestamp()
                WHERE id = %s
                  AND updated_at = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled', 'blocked', 'failed')
                  AND LOWER(COALESCE(payload->'execution'->>'state', '')) = 'running'
                  AND LOWER(COALESCE(payload->'execution'->>'executor_status', '')) = 'running'
                  AND COALESCE(payload->'execution'->>'claim_id', '') = %s
                  AND COALESCE(payload->'execution'->>'executor_worker_id', '') = %s
                  AND COALESCE(payload->'execution_gate'->>'intent_hash', '') = %s
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    Json(signed_payload),
                    card.id,
                    row["updated_at"],
                    claim_id,
                    request.worker_id,
                    current_gate_intent_hash,
                ),
            )
            updated_row = cur.fetchone()
        conn.commit()
    if updated_row is None:
        raise PMExecutionClaimFailureConflict(
            "PM card changed before its execution failure could be committed; no stale failure was written."
        )
    return _row_to_card(updated_row), "failed"


def commit_execution_result(
    card_id: str,
    request: PMExecutionResultCommitRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> tuple[PMCard, str] | None:
    """Atomically commit one result iff its signed PM execution claim is current.

    The row lock makes claim validation and result persistence one operation. A
    replay with the same result id and digest is a successful no-op; all other
    stale, mismatched, or tampered claims fail closed.
    """

    if str(request.card_id) != str(card_id):
        raise PMExecutionResultCommitConflict("Execution result card_id does not match the route.")
    _require_safe_execution_result_references(request)
    pool = get_pool()
    result_id = str(request.result_id)
    claim_id = str(request.claim_id)
    commit_digest = _execution_result_commit_digest(request)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            card = _row_to_card(row)
            current_payload = dict(card.payload or {})
            if (
                _is_workspace_owner_review_card(card)
                and legacy_owner_review_compatibility is not True
                and current_payload.get("legacy_owner_review_compatibility") is not True
            ):
                raise PMExecutionResultCommitConflict(
                    "Historical owner-review PM rows are read-only without rollback compatibility."
                )
            if not verify_execution_payload(card.id, current_payload):
                raise PMExecutionResultCommitConflict("PM card execution authorization is missing or invalid.")

            latest_result = current_payload.get("latest_execution_result")
            if isinstance(latest_result, dict) and str(latest_result.get("result_id") or "") == result_id:
                if str(latest_result.get("commit_digest") or "") != commit_digest:
                    raise PMExecutionResultCommitConflict(
                        "The result id is already committed with different content."
                    )
                if not _has_purpose_authorized_execution_result_receipt(card):
                    raise PMExecutionResultCommitConflict(
                        "The committed result receipt is incomplete or tampered."
                    )
                return card, "already_committed"

            execution = current_payload.get("execution")
            if not isinstance(execution, dict):
                raise PMExecutionResultCommitConflict("PM card has no active execution claim.")
            if str(execution.get("state") or "").strip().lower() != "running" or str(
                execution.get("executor_status") or ""
            ).strip().lower() != "running":
                raise PMExecutionResultCommitConflict("PM card execution is no longer running.")
            if str(execution.get("claim_id") or "") != claim_id:
                raise PMExecutionResultCommitConflict("PM card execution claim_id does not match.")
            if str(execution.get("executor_worker_id") or "") != request.worker_id:
                raise PMExecutionResultCommitConflict("PM card execution worker does not match.")
            if _workspace_key_from_card(card) != request.workspace_key:
                raise PMExecutionResultCommitConflict("PM card execution workspace does not match.")
            if card.title != request.title:
                raise PMExecutionResultCommitConflict("PM card execution title does not match.")

            try:
                current_gate = require_current_execution_gate(
                    card_id=card.id,
                    title=card.title,
                    source=card.source,
                    workspace_key=_workspace_key_from_card(card),
                    payload=current_payload,
                )
            except ValueError as exc:
                raise PMExecutionResultCommitConflict(str(exc)) from exc
            if str(execution.get("claimed_execution_gate_intent_hash") or "") != str(
                current_gate.get("intent_hash") or ""
            ):
                raise PMExecutionResultCommitConflict(
                    "PM card execution intent changed after the live claim was acquired."
                )
            if (
                _is_closed_pm_status(card.status)
                or str(card.status or "").strip().lower() in {"blocked", "failed"}
            ):
                raise PMExecutionResultCommitConflict(
                    "PM card status changed after the live claim was acquired."
                )

            now = utc_now()
            expected_result_runner_id = str(execution.get("result_runner_id") or "").strip()
            expected_result_author_agent = str(execution.get("result_author_agent") or "").strip()
            expected_packet_sha256 = str(execution.get("execution_packet_sha256") or "").strip()
            if not expected_result_runner_id or request.runner_id != expected_result_runner_id:
                raise PMExecutionResultCommitConflict(
                    "Execution result runner does not match the identity bound to the live claim."
                )
            if not expected_result_author_agent or request.author_agent != expected_result_author_agent:
                raise PMExecutionResultCommitConflict(
                    "Execution result author does not match the identity bound to the live claim."
                )
            if not expected_packet_sha256 or request.execution_packet_sha256 != expected_packet_sha256:
                raise PMExecutionResultCommitConflict(
                    "Execution result work order does not match the exact packet bound to the live claim."
                )
            executor_started_at = _parse_datetime(execution.get("executor_started_at"))
            result_created_at = as_utc(request.created_at)
            if executor_started_at is None or result_created_at < executor_started_at.astimezone(timezone.utc):
                raise PMExecutionResultCommitConflict(
                    "Execution result creation time predates the live execution claim."
                )
            if result_created_at > now:
                raise PMExecutionResultCommitConflict(
                    "Execution result creation time is in the future relative to canonical PM time."
                )
            history = list(execution.get("history") or [])
            next_execution_state = request.status
            next_pm_status = "done" if request.status == "done" else ("blocked" if request.status == "blocked" else "review")
            next_target_agent = execution.get("target_agent") or request.author_agent
            next_assigned_runner = expected_result_runner_id
            if request.status == "blocked":
                next_execution_state = "queued"
                next_target_agent = "Jean-Claude"
                next_assigned_runner = "jean-claude"
            history.append(
                {
                    "event": "blocked_return" if request.status == "blocked" else "result",
                    "state": next_execution_state,
                    "runner_id": request.runner_id,
                    "requested_by": request.author_agent,
                    "at": now.isoformat(),
                    "claim_id": claim_id,
                    "result_id": result_id,
                }
            )
            next_execution = {
                **execution,
                "state": next_execution_state,
                "target_agent": next_target_agent,
                "assigned_runner": next_assigned_runner,
                "manager_agent": execution.get("manager_agent") or "Jean-Claude",
                "manager_attention_required": request.status == "blocked",
                "workspace_agent": execution.get("workspace_agent") or execution.get("target_agent"),
                "execution_mode": "direct" if request.status == "blocked" else execution.get("execution_mode"),
                "executor_status": "completed",
                "executor_finished_at": result_created_at.isoformat(),
                "executor_last_error": None,
                "returned_from_agent": (
                    request.author_agent if request.status == "blocked" else execution.get("returned_from_agent")
                ),
                "queued_at": now.isoformat() if request.status == "blocked" else execution.get("queued_at"),
                "last_transition_at": now.isoformat(),
                "result_id": result_id,
                "result_path": request.result_path,
                "workspace_result_path": request.workspace_result_path,
                "history": history[-16:],
            }
            next_payload = dict(current_payload)
            next_payload["execution"] = next_execution
            result_receipt = request.model_dump(mode="json")
            result_receipt["commit_digest"] = commit_digest
            result_receipt["committed_at"] = now.isoformat()
            result_receipt["timestamp_semantics"] = (
                PM_EXECUTION_RESULT_TIMESTAMP_SEMANTICS
            )
            next_payload["latest_execution_result"] = (
                _authorize_execution_result_commit_receipt(result_receipt)
            )
            signed_payload = sign_execution_payload(card.id, next_payload)
            cur.execute(
                """
                UPDATE pm_cards
                SET status = %s,
                    payload = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (next_pm_status, Json(signed_payload), card.id),
            )
            updated_row = cur.fetchone()
            if updated_row is None:  # pragma: no cover - row remains locked until this update.
                conn.rollback()
                raise RuntimeError(f"Failed to commit execution result for PM card {card_id}.")
            updated_card = _row_to_card(updated_row)
            if not _has_authorized_execution_result_commit(updated_card):
                conn.rollback()
                raise PMExecutionResultCommitConflict(
                    "Canonical PM result failed post-write verification; the transaction was rolled back."
                )
        conn.commit()
    return updated_card, "committed"


def recover_stale_execution_claims(
    request: PMStaleExecutionClaimRecoveryRequest,
    *,
    now: datetime | None = None,
    legacy_owner_review_compatibility: bool = False,
) -> PMStaleExecutionClaimRecoveryResult:
    """Recover only deterministic Brain claims; quarantine every other stale claim.

    Database ``updated_at`` is the lease clock. Each candidate is locked and the
    write repeats the worker, claim, running-state, age, and exact ``updated_at``
    predicates as a compare-and-swap. This prevents a delayed recovery request
    from overwriting a heartbeat, result commit, or replacement claim.
    """

    recovered_at = now or datetime.now(timezone.utc)
    if recovered_at.tzinfo is None or recovered_at.utcoffset() is None:
        raise ValueError("Recovery time must be timezone-aware.")
    recovered_at = recovered_at.astimezone(timezone.utc)
    cutoff = recovered_at - timedelta(seconds=request.stale_after_seconds)
    worker_id = request.worker_id
    items: list[dict[str, Any]] = []
    requeued_count = 0
    surfaced_count = 0
    quarantined_count = 0
    cas_miss_count = 0

    if not execution_signing_configured():
        raise RuntimeError("Stale-claim recovery is unavailable because signed-job authorization is not configured.")

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled', 'blocked')
                  AND LOWER(COALESCE(payload->'execution'->>'state', '')) = 'running'
                  AND LOWER(COALESCE(payload->'execution'->>'executor_status', '')) = 'running'
                  AND COALESCE(payload->'execution'->>'executor_worker_id', '') = %s
                  AND COALESCE(payload->'execution'->>'claim_id', '') <> ''
                  AND updated_at <= %s
                ORDER BY updated_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (worker_id, cutoff, request.limit),
            )
            rows = list(cur.fetchall())
            for row in rows:
                card = _row_to_card(row)
                if (
                    _is_workspace_owner_review_card(card)
                    and legacy_owner_review_compatibility is not True
                    and (card.payload or {}).get("legacy_owner_review_compatibility") is not True
                ):
                    items.append(
                        {
                            "card_id": card.id,
                            "claim_id": str(((card.payload or {}).get("execution") or {}).get("claim_id") or ""),
                            "disposition": "skipped_legacy_owner_review_read_only",
                            "reason": "Historical owner-review PM rows remain read-only without compatibility.",
                        }
                    )
                    continue
                payload = dict(card.payload or {})
                execution = dict(payload.get("execution") or {})
                claim_id = str(execution.get("claim_id") or "").strip()
                if not verify_execution_payload(card.id, payload):
                    cur.execute(
                        """
                        UPDATE pm_cards
                        SET status = 'blocked',
                            updated_at = NOW()
                        WHERE id = %s
                          AND updated_at = %s
                          AND updated_at <= %s
                          AND LOWER(COALESCE(payload->'execution'->>'state', '')) = 'running'
                          AND LOWER(COALESCE(payload->'execution'->>'executor_status', '')) = 'running'
                          AND COALESCE(payload->'execution'->>'executor_worker_id', '') = %s
                          AND COALESCE(payload->'execution'->>'claim_id', '') = %s
                        RETURNING id
                        """,
                        (card.id, row["updated_at"], cutoff, worker_id, claim_id),
                    )
                    if cur.fetchone() is None:
                        cas_miss_count += 1
                        items.append(
                            {
                                "card_id": card.id,
                                "claim_id": claim_id,
                                "disposition": "cas_miss",
                                "reason": "The invalidly signed claim changed after selection and was left untouched.",
                            }
                        )
                        continue
                    quarantined_count += 1
                    items.append(
                        {
                            "card_id": card.id,
                            "claim_id": claim_id,
                            "disposition": "quarantined_invalid_signature",
                            "reason": (
                                "The stale claim payload was left untouched and its card was blocked because "
                                "the execution authorization is invalid."
                            ),
                        }
                    )
                    continue

                validated_brain_action: dict[str, Any] | None = None
                if str(execution.get("execution_mode") or "").strip().lower() == "brain_local_action":
                    try:
                        # Local import avoids the queue service's module-level
                        # dependency on this PM service.
                        from app.services.brain_local_action_queue_service import validate_brain_local_action

                        candidate = validate_brain_local_action(payload.get("brain_local_action"))
                        if str(execution.get("target_agent") or "").strip() == "Brain Local Action":
                            validated_brain_action = candidate
                    except (TypeError, ValueError):
                        validated_brain_action = None
                brain_action = (
                    validated_brain_action
                    if validated_brain_action is not None
                    and validated_brain_action["action"] in STALE_CLAIM_AUTO_RECOVERABLE_BRAIN_ACTIONS
                    else None
                )

                history = list(execution.get("history") or [])
                recovery_record = {
                    "claim_id": claim_id,
                    "worker_id": worker_id,
                    "claimed_at": execution.get("executor_started_at") or row.get("updated_at").isoformat(),
                    "detected_at": recovered_at.isoformat(),
                    "automatic_replay": brain_action is not None,
                }
                if brain_action is not None:
                    disposition = "requeued_brain_action"
                    reason = (
                        "Recovered a stale, signed deterministic Brain local-action claim; "
                        "the action may be replayed by its idempotency key."
                    )
                    history.append(
                        {
                            "event": "stale_brain_claim_requeued",
                            "state": "queued",
                            "runner_id": "codex-workspace-execution",
                            "requested_by": worker_id,
                            "at": recovered_at.isoformat(),
                            "claim_id": claim_id,
                            "idempotency_key": brain_action["idempotency_key"],
                        }
                    )
                    next_execution = {
                        **execution,
                        "state": "queued",
                        "executor_status": "queued",
                        "executor_worker_id": None,
                        "claim_id": None,
                        "executor_started_at": None,
                        "executor_finished_at": None,
                        "executor_last_error": None,
                        "execution_packet_path": None,
                        "manager_attention_required": False,
                        "queued_at": recovered_at.isoformat(),
                        "last_transition_at": recovered_at.isoformat(),
                        "last_recovered_claim": recovery_record,
                        "history": history[-16:],
                    }
                    next_status = "todo"
                else:
                    disposition = "surfaced_manual_review"
                    reason = (
                        "A signed Brain ingestion claim became stale and requires manual reconciliation because its "
                        "filesystem destination is not guaranteed stable across replay."
                        if validated_brain_action is not None
                        else "Execution claim became stale before a durable result was prepared. Automatic replay is "
                        "disabled because this is not a validated deterministic Brain local action."
                    )
                    history.append(
                        {
                            "event": "stale_execution_claim_surfaced",
                            "state": "stale_claim",
                            "runner_id": "codex-workspace-execution",
                            "requested_by": worker_id,
                            "at": recovered_at.isoformat(),
                            "claim_id": claim_id,
                            "automatic_replay": False,
                        }
                    )
                    next_execution = {
                        **execution,
                        "state": "stale_claim",
                        "executor_status": "stale_claim",
                        "executor_last_error": reason,
                        "manager_attention_required": True,
                        "last_transition_at": recovered_at.isoformat(),
                        "stale_claim": recovery_record,
                        "history": history[-16:],
                    }
                    next_status = "blocked"

                next_payload = dict(payload)
                next_payload["execution"] = next_execution
                signed_payload = sign_execution_payload(card.id, next_payload)
                cur.execute(
                    """
                    UPDATE pm_cards
                    SET status = %s,
                        payload = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND updated_at = %s
                      AND updated_at <= %s
                      AND LOWER(COALESCE(payload->'execution'->>'state', '')) = 'running'
                      AND LOWER(COALESCE(payload->'execution'->>'executor_status', '')) = 'running'
                      AND COALESCE(payload->'execution'->>'executor_worker_id', '') = %s
                      AND COALESCE(payload->'execution'->>'claim_id', '') = %s
                    RETURNING id
                    """,
                    (
                        next_status,
                        Json(signed_payload),
                        card.id,
                        row["updated_at"],
                        cutoff,
                        worker_id,
                        claim_id,
                    ),
                )
                if cur.fetchone() is None:
                    cas_miss_count += 1
                    items.append(
                        {
                            "card_id": card.id,
                            "claim_id": claim_id,
                            "disposition": "cas_miss",
                            "action": validated_brain_action.get("action") if validated_brain_action else None,
                            "reason": "The claim changed after selection and was left untouched.",
                        }
                    )
                    continue
                if brain_action is not None:
                    requeued_count += 1
                else:
                    surfaced_count += 1
                items.append(
                    {
                        "card_id": card.id,
                        "claim_id": claim_id,
                        "disposition": disposition,
                        "action": validated_brain_action.get("action") if validated_brain_action else None,
                        "reason": reason,
                    }
                )
        conn.commit()

    return PMStaleExecutionClaimRecoveryResult(
        worker_id=worker_id,
        stale_after_seconds=request.stale_after_seconds,
        cutoff_at=cutoff,
        examined_count=len(rows),
        requeued_count=requeued_count,
        surfaced_count=surfaced_count,
        quarantined_count=quarantined_count,
        cas_miss_count=cas_miss_count,
        items=items,
    )


def get_card(card_id: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                """,
                (card_id,),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def _row_to_card(row: dict) -> PMCard:
    if not row:
        raise ValueError("PM card row is empty")
    return PMCard(
        id=str(row["id"]),
        title=row.get("title") or "Untitled",
        owner=row.get("owner"),
        status=row.get("status") or "todo",
        source=row.get("source"),
        link_type=row.get("link_type"),
        link_id=str(row.get("link_id")) if row.get("link_id") else None,
        due_at=row.get("due_at"),
        payload=row.get("payload") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def find_card_by_signature(title: str, source: Optional[str]) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if source is None:
                cur.execute(
                    """
                    SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                    FROM pm_cards
                    WHERE title = %s AND source IS NULL
                    LIMIT 1
                    """,
                    (title,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                    FROM pm_cards
                    WHERE title = %s AND source = %s
                    LIMIT 1
                    """,
                    (title, source),
                )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def find_active_card_by_title(title: str, workspace_key: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE title = %s
                  AND COALESCE(payload->>'workspace_key', payload->>'workspace', payload->>'belongs_to_workspace', 'shared_ops') = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (title, workspace_key),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def find_active_card_by_trigger_key(trigger_key: str) -> Optional[PMCard]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE payload->>'trigger_key' = %s
                  AND LOWER(COALESCE(status, 'todo')) NOT IN ('done', 'closed', 'cancelled')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (trigger_key,),
            )
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def list_execution_queue(
    limit: int = 100,
    target_agent: Optional[str] = None,
    manager_agent: Optional[str] = None,
    workspace_key: Optional[str] = None,
    execution_state: Optional[str] = None,
    legacy_owner_review_compatibility: bool = False,
) -> List[ExecutionQueueEntry]:
    repair_execution_contracts(
        limit=max(limit, 250),
        workspace_key=workspace_key,
        legacy_owner_review_compatibility=legacy_owner_review_compatibility,
    )
    cards = list_cards(limit=limit, workspace_key=workspace_key)
    entries: List[ExecutionQueueEntry] = []
    for card in cards:
        if _is_workspace_owner_review_card(card) and legacy_owner_review_compatibility is not True:
            continue
        entry = build_execution_queue_entry(card)
        if entry is None:
            continue
        if manager_agent and entry.manager_agent.lower() != manager_agent.lower():
            continue
        if target_agent and entry.target_agent.lower() != target_agent.lower():
            continue
        if execution_state and entry.execution_state.lower() != execution_state.lower():
            continue
        entries.append(entry)
    entries.sort(
        key=lambda entry: (
            _execution_sort_rank(entry.execution_state),
            entry.last_transition_at or entry.queued_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return entries[:limit]


def dispatch_card(
    card_id: str,
    payload: PMCardDispatchRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> Optional[PMCardDispatchResult]:
    card = get_card(card_id)
    if card is None:
        return None
    if (
        _is_workspace_owner_review_card(card)
        and legacy_owner_review_compatibility is not True
        and (card.payload or {}).get("legacy_owner_review_compatibility") is not True
    ):
        raise ValueError("Historical owner-review PM rows are read-only without rollback compatibility.")
    if _is_host_action_required_card(card):
        raise ValueError("Host-action cards cannot be dispatched into execution. Confirm, return, or block the host step instead.")

    now = datetime.now(timezone.utc)
    workspace_key = _workspace_key_from_card(card)
    execution_ready_payload = _build_missing_execution_contract_payload(card) or dict(card.payload or {})
    card_payload = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key=workspace_key,
        payload=execution_ready_payload,
    )
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    current_execution = dict(card_payload.get("execution") or {})
    if not current_execution:
        current_execution.update(defaults)
    else:
        current_execution = _merge_execution_defaults(current_execution, defaults)
    requested_by = payload.requested_by or current_execution.get("requested_by") or card.owner or defaults["manager_agent"]
    effective_target_agent = payload.target_agent or current_execution.get("target_agent") or defaults["target_agent"]
    history = list(current_execution.get("history") or [])
    current_execution.update(
        {
            "lane": payload.lane or current_execution.get("lane") or "codex",
            "state": payload.execution_state or current_execution.get("state") or "queued",
            "manager_agent": current_execution.get("manager_agent") or defaults["manager_agent"],
            "target_agent": effective_target_agent,
            "workspace_agent": current_execution.get("workspace_agent") or defaults.get("workspace_agent"),
            "execution_mode": current_execution.get("execution_mode") or defaults["execution_mode"],
            "requested_by": requested_by,
            "assigned_runner": current_execution.get("assigned_runner") or "codex",
            "reason": current_execution.get("reason")
            or _payload_value(card_payload, "reason")
            or "Queued from PM board for Codex execution.",
            "queued_at": current_execution.get("queued_at") or now.isoformat(),
            "last_transition_at": now.isoformat(),
            "execution_packet_path": None,
            "executor_status": None,
            "executor_worker_id": None,
            "executor_started_at": None,
            "executor_finished_at": None,
            "executor_last_error": None,
        }
    )
    card_payload["execution"] = current_execution
    card_payload = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key=workspace_key,
        payload=card_payload,
    )
    gate = dict(card_payload.get("execution_gate") or {})
    governed_execution_approval_transition = False
    if not execution_gate_allows_run(gate):
        if not payload.approval_confirmed:
            raise ValueError(
                str(gate.get("reason") or "This execution requires owner approval.")
                + " Review the exact intent, then use Approve & queue."
            )
        card_payload = grant_execution_approval(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=workspace_key,
            payload=card_payload,
            approved_by=payload.requested_by or "Neo",
            reason=payload.approval_reason,
        )
        governed_execution_approval_transition = True
        gate = dict(card_payload.get("execution_gate") or {})
    if not execution_gate_allows_run(gate):
        raise ValueError(
            str(
                gate.get("reason")
                or "This execution is not authorized for the local Codex runner."
            )
        )
    history.append(
        {
            "event": "dispatch",
            "state": payload.execution_state,
            "target_agent": effective_target_agent,
            "requested_by": requested_by,
            "at": now.isoformat(),
            "execution_gate_intent_hash": gate.get("intent_hash"),
            "execution_gate_approval_state": gate.get("approval_state"),
        }
    )
    current_execution["history"] = history[-12:]
    card_payload["execution"] = current_execution

    updated = update_card(
        card_id,
        PMCardUpdate(payload=card_payload),
        **(
            {"_governed_execution_approval_transition": True}
            if governed_execution_approval_transition
            else {}
        ),
    )
    if updated is None:
        return None
    return PMCardDispatchResult(card=updated, queue_entry=build_execution_queue_entry(updated) or _fallback_execution_entry(updated))


def act_on_card(
    card_id: str,
    payload: PMCardActionRequest,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> Optional[PMCardActionResult]:
    card = get_card(card_id)
    if card is None:
        return None
    if (
        _is_workspace_owner_review_card(card)
        and legacy_owner_review_compatibility is not True
        and (card.payload or {}).get("legacy_owner_review_compatibility") is not True
    ):
        raise ValueError("Historical owner-review PM rows are read-only without rollback compatibility.")
    return _apply_card_action(
        card,
        action=payload.action,
        requested_by=payload.requested_by,
        reason=payload.reason,
        resolution_mode=payload.resolution_mode,
        next_title=payload.next_title,
        next_reason=payload.next_reason,
        proof_items=payload.proof_items,
        proof_field_values=[entry.model_dump() for entry in payload.proof_field_values],
    )


def queue_host_action_automation(
    card_id: str,
    *,
    legacy_owner_review_compatibility: bool = False,
    requested_by: str = "Neo",
    reason: str | None = None,
    proof_items: list[str] | None = None,
    proof_field_values: list[dict[str, Any]] | None = None,
    scheduled_at: str | None = None,
    asset_decision: str | None = None,
    confirmation_path: str | None = None,
    queue_id: str | None = None,
) -> Optional[PMCardActionResult]:
    card = get_card(card_id)
    if card is None:
        return None
    if (
        _is_workspace_owner_review_card(card)
        and legacy_owner_review_compatibility is not True
        and (card.payload or {}).get("legacy_owner_review_compatibility") is not True
    ):
        raise ValueError("Historical owner-review PM rows are read-only without rollback compatibility.")
    if _is_closed_pm_status(card.status):
        raise ValueError("Host-action card is already closed.")
    automation = _infer_host_action_automation(card)
    if automation is None:
        raise ValueError("This host-action card does not have a supported automation.")

    payload = dict(card.payload or {})
    existing_execution = dict(_execution_payload(card) or {})
    now = datetime.now(timezone.utc).isoformat()
    normalized_proof_field_values = _normalize_host_action_proof_field_values(proof_field_values)
    combined_proof_items = _dedupe_nonempty_strings([*(proof_items or []), *_host_action_proof_items_from_values(normalized_proof_field_values)])
    if combined_proof_items:
        automation["proof_items"] = combined_proof_items
    if normalized_proof_field_values:
        automation["proof_field_values"] = normalized_proof_field_values
    inferred_scheduled_at = _host_action_timestamp_from_values(normalized_proof_field_values)
    if scheduled_at:
        automation["scheduled_at"] = str(scheduled_at).strip()
    elif inferred_scheduled_at:
        automation["scheduled_at"] = inferred_scheduled_at
    if asset_decision:
        automation["asset_decision"] = str(asset_decision).strip()
    elif automation.get("automation_id") == HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULED_WRITEBACK:
        automation["asset_decision"] = _optional_str(automation.get("asset_decision")) or "text-only"
    inferred_confirmation_path = _host_action_field_value(normalized_proof_field_values, "screenshot_path") or _host_action_field_value(
        normalized_proof_field_values,
        "publish_url",
    )
    if confirmation_path:
        automation["confirmation_path"] = str(confirmation_path).strip()
    elif inferred_confirmation_path:
        automation["confirmation_path"] = inferred_confirmation_path
    if queue_id:
        requested_queue_id = _extract_feezie_queue_id(str(queue_id))
        existing_queue_id = _optional_str(automation.get("queue_id"))
        if requested_queue_id and existing_queue_id and requested_queue_id != existing_queue_id:
            raise ValueError(f"Requested queue_id {requested_queue_id} does not match host-action queue_id {existing_queue_id}.")
        if requested_queue_id:
            automation["queue_id"] = requested_queue_id
    if reason:
        automation["queue_reason"] = reason
    current_state = str(automation.get("state") or "ready").strip().lower()
    if current_state in {"queued", "running"}:
        payload["host_action_automation"] = automation
        governed_execution_approval_transition = bool(
            automation.get("requires_host_confirmation")
        )
        if governed_execution_approval_transition:
            payload = grant_execution_approval(
                card_id=card.id,
                title=card.title,
                source=card.source,
                workspace_key=_workspace_key_from_card(card),
                payload=payload,
                approved_by=requested_by,
                reason=reason or "Owner confirmed this exact host-action automation.",
            )
        governed_update_kwargs = (
            {"_governed_execution_approval_transition": True}
            if governed_execution_approval_transition
            else {}
        )
        updated = _persist_status_payload_update(
            card,
            operation="queued host-action automation confirmation",
            status=card.status,
            payload=payload,
            update_kwargs=governed_update_kwargs,
        )
    else:
        automation.update(
            {
                "state": "queued",
                "queued_at": now,
                "queued_by": requested_by,
                "last_error": None,
            }
        )

        history = list(existing_execution.get("history") or [])
        history.append(
            {
                "event": "host_action_automation_queued",
                "state": "queued",
                "requested_by": requested_by,
                "automation_id": automation.get("automation_id"),
                "at": now,
            }
        )
        payload["host_action_automation"] = automation
        payload["execution"] = {
            **existing_execution,
            "state": "host_action_automation_queued",
            "manager_agent": existing_execution.get("manager_agent") or "Jean-Claude",
            "target_agent": existing_execution.get("target_agent") or "Host Action Automation",
            "assigned_runner": "codex_workspace_execution",
            "execution_mode": "host_action_automation",
            "requested_by": requested_by,
            "manager_attention_required": False,
            "queued_at": existing_execution.get("queued_at") or now,
            "last_transition_at": now,
            "executor_status": "queued",
            "executor_worker_id": None,
            "executor_last_error": None,
            "history": history[-12:],
        }
        governed_execution_approval_transition = bool(
            automation.get("requires_host_confirmation")
        )
        if governed_execution_approval_transition:
            payload = grant_execution_approval(
                card_id=card.id,
                title=card.title,
                source=card.source,
                workspace_key=_workspace_key_from_card(card),
                payload=payload,
                approved_by=requested_by,
                reason=reason or "Owner confirmed this exact host-action automation.",
            )
        updated = update_card(
            card.id,
            PMCardUpdate(status="in_progress", payload=payload),
            **(
                {"_governed_execution_approval_transition": True}
                if governed_execution_approval_transition
                else {}
            ),
        )
        if updated is None:
            return None

    return PMCardActionResult(card=updated, queue_entry=None, successor_card=None)


def _apply_card_action(
    card: PMCard,
    *,
    action: str,
    requested_by: str,
    reason: str | None = None,
    resolution_mode: str | None = None,
    next_title: str | None = None,
    next_reason: str | None = None,
    proof_items: list[str] | None = None,
    proof_field_values: list[dict[str, Any]] | None = None,
    review_metadata: dict[str, Any] | None = None,
) -> Optional[PMCardActionResult]:
    host_action_completion: dict[str, Any] | None = None
    host_action_followup: dict[str, Any] | None = None
    host_action_followup_gate: dict[str, Any] | None = None
    if action == "approve" and _is_host_action_required_card(card):
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        host_action_completion = _build_host_action_completion_payload(
            card,
            requested_by=requested_by,
            completion_note=reason,
            proof_items=proof_items,
            proof_field_values=proof_field_values,
        )
        if isinstance(host_action_followup, dict):
            host_action_followup_gate = _evaluate_host_action_followup_readiness(host_action_followup, host_action_completion)
    status, card_payload = build_card_action_update(
        card,
        action=action,
        requested_by=requested_by,
        reason=reason,
        resolution_mode=resolution_mode,
        next_title=next_title,
        next_reason=next_reason,
    )
    if host_action_completion is not None:
        card_payload["host_action_completion"] = host_action_completion
    if host_action_followup_gate is not None and not bool(host_action_followup_gate.get("ready")):
        card_payload["host_action_followup_pending"] = host_action_followup_gate
    update_kwargs = (
        {"_governed_review_transition": True}
        if _has_purpose_authorized_execution_result_receipt(card)
        else {}
    )
    updated = update_card(
        card.id,
        PMCardUpdate(status=status, payload=card_payload),
        **update_kwargs,
    )
    if updated is None:
        return None

    successor_card: PMCard | None = None
    if action == "approve" and resolution_mode == "close_and_spawn_next":
        successor_card = _create_resolution_successor_card(
            card,
            requested_by=requested_by,
            next_title=next_title,
            next_reason=next_reason,
        )
        updated_payload = dict(updated.payload or {})
        latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
        latest_manual_review["successor_card_id"] = successor_card.id
        latest_manual_review["successor_card_title"] = successor_card.title
        updated_payload["latest_manual_review"] = latest_manual_review
        updated_payload["resolution_successor"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        updated = _persist_status_payload_update(
            updated,
            operation="PM resolution-successor link receipt",
            status=updated.status,
            payload=updated_payload,
        )

    if (
        action == "approve"
        and host_action_completion is not None
        and isinstance(host_action_followup, dict)
        and bool((host_action_followup_gate or {}).get("ready"))
    ):
        successor_card = _create_host_action_required_card(
            updated,
            requested_by=requested_by,
            host_action_required=host_action_followup,
            due_at=host_action_followup_gate.get("due_at") if isinstance(host_action_followup_gate, dict) else None,
        )
        updated_payload = dict(updated.payload or {})
        host_completion = dict(updated_payload.get("host_action_completion") or host_action_completion)
        host_completion["follow_up_card_id"] = successor_card.id
        host_completion["follow_up_card_title"] = successor_card.title
        updated_payload["host_action_completion"] = host_completion
        updated_payload["host_action_followup_spawned"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        updated_payload.pop("host_action_followup_pending", None)
        updated = _persist_status_payload_update(
            updated,
            operation="host-action follow-up link receipt",
            status=updated.status,
            payload=updated_payload,
        )

    if review_metadata:
        updated_payload = dict(updated.payload or {})
        latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
        latest_manual_review.update(review_metadata)
        updated_payload["latest_manual_review"] = latest_manual_review
        updated = _persist_status_payload_update(
            updated,
            operation="PM review metadata receipt",
            status=updated.status,
            payload=updated_payload,
        )

    return PMCardActionResult(card=updated, queue_entry=build_execution_queue_entry(updated), successor_card=successor_card)


def _create_resolution_successor_card(
    card: PMCard,
    *,
    requested_by: str,
    next_title: str | None,
    next_reason: str | None,
) -> PMCard:
    cleaned_title = str(next_title or "").strip()
    if not cleaned_title:
        raise ValueError("A next card title is required when resolving with a spawned follow-up.")

    source_payload = dict(card.payload or {})
    workspace_key = _workspace_key_from_card(card)
    successor_reason = str(next_reason or "").strip() or f"Follow-on work spawned from resolving '{card.title}'."
    execution_defaults = execution_defaults_for_workspace(workspace_key)
    contract = build_execution_contract(
        title=cleaned_title,
        workspace_key=workspace_key,
        source="pm_review_resolution",
        reason=successor_reason,
        instructions=[
            f"Continue the PM loop after resolving `{card.title}`.",
            "Use the predecessor PM card and latest execution result as the source of truth for this next lane.",
            "Write back a bounded result with outcomes, blockers, and follow-up actions.",
        ],
        acceptance_criteria=[
            f"`{cleaned_title}` advances to a concrete next state instead of remaining a placeholder.",
            "PM write-back includes a bounded summary and at least one concrete outcome or artifact.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "bounded workspace artifact or execution memo when the next lane produces one",
        ],
    )
    successor_payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "reason": successor_reason,
        "source_agent": requested_by,
        "front_door_agent": requested_by,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": {
            "lane": "codex",
            "state": "queued",
            "manager_agent": execution_defaults["manager_agent"],
            "target_agent": execution_defaults["target_agent"],
            "workspace_agent": execution_defaults.get("workspace_agent"),
            "execution_mode": execution_defaults["execution_mode"],
            "requested_by": requested_by,
            "assigned_runner": "jean-claude" if str(execution_defaults["execution_mode"]) == "direct" else "codex",
            "reason": successor_reason,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "last_transition_at": datetime.now(timezone.utc).isoformat(),
            "source": "pm_review_resolution",
        },
        "resolution_predecessor": {
            "card_id": card.id,
            "title": card.title,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    for key in [
        "created_from_standup_id",
        "created_from_standup_kind",
        "created_from_standup_workspace",
        "created_from_prep_id",
        "recommendation_path",
    ]:
        value = source_payload.get(key)
        if value is not None:
            successor_payload[key] = value

    successor_payload["trigger_key"] = _build_trigger_key(
        title=cleaned_title,
        workspace_key=workspace_key,
        source="pm_review_resolution",
        payload=successor_payload,
    )
    existing = find_active_card_by_trigger_key(str(successor_payload["trigger_key"]))
    if existing is not None:
        return existing

    return create_card(
        PMCardCreate(
            title=cleaned_title,
            owner=card.owner or execution_defaults["manager_agent"],
            status="todo",
            source="pm_review_resolution",
            link_type=card.link_type,
            link_id=card.link_id,
            payload=successor_payload,
        )
    )


def build_card_action_update(
    card: PMCard,
    *,
    action: str,
    requested_by: str = "Neo",
    reason: str | None = None,
    resolution_mode: str | None = None,
    next_title: str | None = None,
    next_reason: str | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = dict(card.payload or {})
    current_execution = dict(_execution_payload(card) or {})
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    queue_entry = build_execution_queue_entry(card)
    now = datetime.now(timezone.utc).isoformat()
    history = list(current_execution.get("history") or [])
    cleaned_resolution_mode = str(resolution_mode or "").strip() or None
    cleaned_next_title = str(next_title or "").strip()
    cleaned_next_reason = str(next_reason or "").strip()

    next_status = card.status or "review"
    next_state = str(current_execution.get("state") or (queue_entry.execution_state if queue_entry else "review"))
    next_target = str(current_execution.get("target_agent") or (queue_entry.target_agent if queue_entry else defaults["target_agent"]))
    next_assigned_runner = str(current_execution.get("assigned_runner") or (queue_entry.assigned_runner if queue_entry else "codex"))
    next_execution_mode = str(current_execution.get("execution_mode") or (queue_entry.execution_mode if queue_entry else defaults["execution_mode"]))
    manager_attention_required = bool(current_execution.get("manager_attention_required"))
    effective_reason = str(
        reason
        or current_execution.get("reason")
        or (queue_entry.reason if queue_entry else "")
        or _payload_value(payload, "reason")
        or ""
    ).strip()

    if action == "approve":
        if cleaned_resolution_mode not in {"close_only", "close_and_spawn_next"}:
            raise ValueError("Resolve requires an explicit next-step mode.")
        if cleaned_resolution_mode == "close_and_spawn_next" and not cleaned_next_title:
            raise ValueError("A next card title is required when resolving with a spawned follow-up.")
        next_status = "done"
        next_state = "done"
        manager_attention_required = False
    elif action == "return":
        next_status = "todo"
        next_state = "queued"
        if str(defaults["execution_mode"]) == "delegated":
            next_target = str(
                current_execution.get("workspace_agent")
                or (queue_entry.workspace_agent if queue_entry else "")
                or defaults.get("workspace_agent")
                or defaults["target_agent"]
            )
            next_assigned_runner = str(
                current_execution.get("assigned_runner")
                or (queue_entry.assigned_runner if queue_entry else "")
                or "codex"
            )
            next_execution_mode = str(defaults["execution_mode"])
        else:
            next_target = "Jean-Claude"
            next_assigned_runner = "jean-claude"
            next_execution_mode = "direct"
        manager_attention_required = False
        if not effective_reason:
            effective_reason = "Returned for another pass with corrected PM guidance."
    elif action == "blocked":
        next_status = "blocked"
        next_state = "queued"
        next_target = "Jean-Claude"
        next_assigned_runner = "jean-claude"
        next_execution_mode = "direct"
        manager_attention_required = True
        if not effective_reason:
            effective_reason = "Marked blocked during manual review. Jean-Claude needs a closure decision."
    else:
        raise ValueError(f"Unsupported PM card action: {action}")

    history.append(
        {
            "event": (
                "manual_approve"
                if action == "approve"
                else "manual_return"
                if action == "return"
                else "manual_blocked"
            ),
            "state": next_state,
            "requested_by": requested_by,
            "at": now,
        }
    )

    payload["execution"] = {
        **defaults,
        **current_execution,
        "lane": str(current_execution.get("lane") or (queue_entry.lane if queue_entry else "codex")),
        "state": next_state,
        "manager_agent": str(current_execution.get("manager_agent") or (queue_entry.manager_agent if queue_entry else defaults["manager_agent"])),
        "target_agent": next_target,
        "workspace_agent": current_execution.get("workspace_agent") or (queue_entry.workspace_agent if queue_entry else defaults.get("workspace_agent")),
        "execution_mode": next_execution_mode,
        "requested_by": requested_by,
        "assigned_runner": next_assigned_runner,
        "queued_at": current_execution.get("queued_at") if action == "approve" else now,
        "last_transition_at": now,
        "manager_attention_required": manager_attention_required,
        "execution_packet_path": None if action in {"return", "blocked"} else current_execution.get("execution_packet_path"),
        "executor_status": None if action in {"return", "blocked"} else current_execution.get("executor_status"),
        "executor_worker_id": None if action in {"return", "blocked"} else current_execution.get("executor_worker_id"),
        "executor_started_at": None if action in {"return", "blocked"} else current_execution.get("executor_started_at"),
        "executor_finished_at": None if action in {"return", "blocked"} else current_execution.get("executor_finished_at"),
        "executor_last_error": None if action in {"return", "blocked"} else current_execution.get("executor_last_error"),
        "returned_from_agent": (
            str(current_execution.get("target_agent") or (queue_entry.target_agent if queue_entry else ""))
            if action == "blocked"
            else current_execution.get("returned_from_agent")
        ),
        "reason": effective_reason,
        "history": history[-12:],
    }

    payload["latest_manual_review"] = {
        "action": action,
        "reviewed_at": now,
        "reviewed_by": requested_by,
        "from_lane": queue_entry.execution_state if queue_entry else (card.status or "todo"),
        "resolution_mode": cleaned_resolution_mode,
        "next_title": cleaned_next_title or None,
        "next_reason": cleaned_next_reason or None,
    }

    return next_status, payload


def auto_resolve_review_cards(
    limit: int = 250,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> dict[str, Any]:
    cards = list_cards(limit=limit)
    resolved: list[dict[str, Any]] = []

    for card in cards:
        if _is_workspace_owner_review_card(card) and legacy_owner_review_compatibility is not True:
            continue
        policy = _auto_resolve_review_policy(card)
        if policy is None:
            continue
        result = _apply_card_action(
            card,
            action="approve",
            requested_by=AUTO_RESOLVE_REQUESTED_BY,
            reason=policy["reason"],
            resolution_mode="close_only",
            review_metadata={
                "auto_resolved": True,
                "policy_rule": policy["rule"],
                "worker_action": "close_only",
            },
        )
        if result is None:
            continue
        updated = result.card
        resolved.append(
            {
                "card_id": updated.id,
                "title": updated.title,
                "workspace_key": _workspace_key_from_card(updated),
                "rule": policy["rule"],
                "reason": policy["reason"],
            }
        )

    return {
        "resolved_count": len(resolved),
        "resolved": resolved,
    }


def auto_progress_review_cards(
    limit: int = 250,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> dict[str, Any]:
    repair_result = repair_execution_contracts(
        limit=limit,
        legacy_owner_review_compatibility=legacy_owner_review_compatibility,
    )
    cards = list_cards(limit=limit)
    if legacy_owner_review_compatibility is not True:
        cards = [card for card in cards if not _is_workspace_owner_review_card(card)]
    cards_by_id = {card.id: card for card in cards}
    owner_review_duplicates = _auto_close_stale_owner_review_duplicates(cards)
    closed_owner_review_duplicate_ids = {str(item.get("card_id")) for item in owner_review_duplicates if item.get("card_id")}
    processed: list[dict[str, Any]] = []

    for card in cards:
        if card.id in closed_owner_review_duplicate_ids:
            continue
        progress_result = _auto_progress_single_card(card, cards_by_id=cards_by_id)
        if progress_result is None:
            continue
        processed_item, _ = progress_result
        processed.append(processed_item)

    result = {
        "repair_count": int(repair_result.get("repaired_count") or 0),
        "repaired": repair_result.get("repaired") or [],
        "owner_review_duplicate_closed_count": len(owner_review_duplicates),
        "owner_review_duplicates_closed": owner_review_duplicates,
        "processed_count": len(processed),
        "advanced_count": sum(1 for item in processed if item.get("action") == "approve"),
        "returned_count": sum(1 for item in processed if item.get("action") == "return"),
        "escalated_count": sum(1 for item in processed if item.get("action") == "blocked"),
        "closed_count": sum(1 for item in processed if item.get("resolution_mode") == "close_only"),
        "continued_count": sum(1 for item in processed if item.get("resolution_mode") == "close_and_spawn_next"),
        "processed": processed,
    }
    audit_entry = record_review_hygiene_audit(result)
    if audit_entry is not None:
        result["audit_entry"] = audit_entry
    return result


def auto_progress_card(
    card_id: str,
    *,
    limit: int = 250,
    record_audit: bool = False,
    legacy_owner_review_compatibility: bool = False,
) -> dict[str, Any]:
    cards = list_cards(limit=limit)
    cards_by_id = {card.id: card for card in cards}
    card = cards_by_id.get(card_id) or get_card(card_id)
    if card is not None and _is_workspace_owner_review_card(card) and legacy_owner_review_compatibility is not True:
        result = {
            "card_id": card_id,
            "processed": False,
            "reason": "Historical owner-review cards are read-only outside rollback compatibility mode.",
            "rule": "legacy_owner_review_read_only",
            "action": None,
            "resolution_mode": None,
            "successor_card_id": None,
            "successor_card_title": None,
            "host_action_card_id": None,
            "host_action_card_title": None,
            "card": decorate_card_for_client(card),
        }
    elif card is None:
        result = {
            "card_id": card_id,
            "processed": False,
            "reason": "PM card not found.",
            "rule": None,
            "action": None,
            "resolution_mode": None,
            "successor_card_id": None,
            "successor_card_title": None,
            "host_action_card_id": None,
            "host_action_card_title": None,
            "card": None,
        }
    else:
        progress_result = _auto_progress_single_card(card, cards_by_id=cards_by_id)
        if progress_result is None:
            latest_card = get_card(card_id) or card
            result = {
                "card_id": card_id,
                "processed": False,
                "reason": "No automatic PM review progression applied.",
                "rule": None,
                "action": None,
                "resolution_mode": None,
                "successor_card_id": None,
                "successor_card_title": None,
                "host_action_card_id": None,
                "host_action_card_title": None,
                "card": latest_card.model_dump(mode="json"),
            }
        else:
            processed_item, action_result = progress_result
            result = {
                "card_id": card_id,
                "processed": True,
                "reason": processed_item.get("reason"),
                "rule": processed_item.get("rule"),
                "action": processed_item.get("action"),
                "resolution_mode": processed_item.get("resolution_mode"),
                "successor_card_id": processed_item.get("successor_card_id"),
                "successor_card_title": processed_item.get("successor_card_title"),
                "host_action_card_id": processed_item.get("host_action_card_id"),
                "host_action_card_title": processed_item.get("host_action_card_title"),
                "card": action_result.card.model_dump(mode="json"),
            }
    if record_audit:
        audit_payload = {
            "repair_count": 0,
            "repaired": [],
            "owner_review_duplicate_closed_count": 0,
            "owner_review_duplicates_closed": [],
            "processed_count": 1 if result.get("processed") else 0,
            "advanced_count": 1 if result.get("processed") and result.get("action") == "approve" else 0,
            "returned_count": 1 if result.get("processed") and result.get("action") == "return" else 0,
            "escalated_count": 1 if result.get("processed") and result.get("action") == "blocked" else 0,
            "closed_count": 1 if result.get("processed") and result.get("resolution_mode") == "close_only" else 0,
            "continued_count": 1 if result.get("processed") and result.get("resolution_mode") == "close_and_spawn_next" else 0,
            "processed": [result] if result.get("processed") else [],
        }
        audit_entry = record_review_hygiene_audit(audit_payload)
        if audit_entry is not None:
            result["audit_entry"] = audit_entry
    return result


def review_hygiene_audit(limit: int = 12, hours: int = 24) -> dict[str, Any]:
    return list_review_hygiene_audit(limit=limit, hours=hours)


def decorate_card_for_client(card: PMCard | None) -> PMCard | None:
    if card is None:
        return None
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    normalized_status = card.status
    if isinstance(host_action_required, dict):
        source_card = _resolve_host_action_source_card(host_action_required)
        phases = _split_host_action_timeline(host_action_required)
        current_phase = phases.get("current")
        follow_up_phase = _normalize_host_action_payload(payload.get("host_action_followup")) or phases.get("follow_up")
        if current_phase is not None:
            proof_required = _dedupe_nonempty_strings(current_phase.get("proof_required"))
            payload["host_action_required"] = {
                **host_action_required,
                **current_phase,
                "proof_fields": _enrich_host_action_proof_fields(
                    _build_host_action_proof_fields(proof_required),
                    current_phase,
                    source_card=source_card,
                ),
                "source_artifact_paths": _source_card_artifact_paths(source_card),
            }
        if follow_up_phase is not None:
            payload["host_action_followup"] = {
                **follow_up_phase,
                "proof_fields": _enrich_host_action_proof_fields(
                    _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
                    follow_up_phase,
                    source_card=source_card,
                ),
            }
        activation = _host_action_activation_status(card)
        if activation is not None:
            payload["host_action_activation"] = activation
        automation = _infer_host_action_automation(card)
        if automation is not None:
            payload["host_action_automation"] = automation
        execution = dict(payload.get("execution") or {}) if isinstance(payload.get("execution"), dict) else {}
        if not _is_closed_pm_status(card.status):
            if str(card.status or "").strip().lower() in {"queued", "running", "in_progress", "review", "failed"}:
                normalized_status = "todo"
            payload["execution"] = {
                **execution,
                "state": "host_step_only",
                "manager_attention_required": False,
                "executor_status": None,
                "executor_worker_id": None,
                "executor_last_error": None,
                "execution_packet_path": None,
                "sop_path": None,
                "briefing_path": None,
            }
    policy_card = card.model_copy(update={"status": normalized_status})
    payload["execution_gate"] = _execution_gate_for_card(card)
    payload["pm_review_policy"] = _build_client_review_policy(policy_card)
    return card.model_copy(update={"status": normalized_status, "payload": payload})


def decorate_cards_for_client(cards: List[PMCard]) -> List[PMCard]:
    return [decorate_card_for_client(card) or card for card in cards]


def build_execution_queue_entry(card: PMCard) -> Optional[ExecutionQueueEntry]:
    if _is_closed_pm_status(card.status):
        return None
    if _is_host_action_required_card(card):
        return None
    payload = dict(card.payload or {})
    execution = _execution_payload(card)
    if not execution and not _is_execution_candidate(card):
        return None
    execution_gate = _execution_gate_for_card(card)

    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    effective_execution = dict(execution or {})
    if not effective_execution:
        default_state = _default_execution_state_for_card(card)
        effective_execution = {
            **defaults,
            "lane": "codex",
            "state": default_state,
            "requested_by": _payload_value(payload, "source_agent") or card.owner or defaults["manager_agent"],
            "assigned_runner": "jean-claude" if str(defaults["execution_mode"]) == "direct" else "codex",
            "reason": _payload_value(payload, "reason")
            or (
                "Standup promoted this card and it is ready for Jean-Claude to open a direct SOP."
                if defaults["execution_mode"] == "direct"
                else "Standup promoted this card and it is ready for Jean-Claude to open a delegated SOP for the workspace agent."
            ),
            "last_transition_at": _datetime_to_iso(card.updated_at),
        }
        if default_state == "queued":
            effective_execution["queued_at"] = _datetime_to_iso(card.updated_at)
    else:
        effective_execution = _merge_execution_defaults(effective_execution, defaults)

    if (
        not _execution_gate_authorizes_card(card, gate=execution_gate)
        and str(card.status or "").strip().lower() not in {"review", "blocked", "failed"}
        and str(effective_execution.get("state") or "ready").strip().lower()
        in {"ready", "queued", "todo", "pending", "dispatching"}
    ):
        effective_execution["state"] = "approval_required"
        effective_execution["manager_attention_required"] = True

    latest_execution_result = payload.get("latest_execution_result")
    latest_result = latest_execution_result if isinstance(latest_execution_result, dict) else {}
    latest_result_artifacts = latest_result.get("artifacts")
    artifact_items = (
        [str(item).strip() for item in latest_result_artifacts if isinstance(item, str) and str(item).strip()]
        if isinstance(latest_result_artifacts, list)
        else []
    )

    return ExecutionQueueEntry(
        card_id=card.id,
        title=card.title,
        workspace_key=_workspace_key_from_card(card),
        pm_status=card.status or "todo",
        execution_state=str(effective_execution.get("state") or "ready"),
        manager_agent=str(effective_execution.get("manager_agent") or defaults["manager_agent"]),
        target_agent=str(effective_execution.get("target_agent") or defaults["target_agent"]),
        workspace_agent=_optional_str(effective_execution.get("workspace_agent")),
        execution_mode=str(effective_execution.get("execution_mode") or defaults["execution_mode"]),
        requested_by=_optional_str(effective_execution.get("requested_by")),
        assigned_runner=_optional_str(effective_execution.get("assigned_runner")),
        lane=str(effective_execution.get("lane") or "codex"),
        reason=_optional_str(effective_execution.get("reason")),
        source=card.source,
        link_type=card.link_type,
        front_door_agent=_optional_str(payload.get("front_door_agent")),
        trigger_key=_optional_str(payload.get("trigger_key")),
        manager_attention_required=bool(effective_execution.get("manager_attention_required")),
        executor_status=_optional_str(effective_execution.get("executor_status")),
        executor_worker_id=_optional_str(effective_execution.get("executor_worker_id")),
        execution_packet_path=(
            _optional_str(effective_execution.get("execution_packet_path"))
            or _optional_str(effective_execution.get("workspace_agent_packet_path"))
        ),
        sop_path=_optional_str(effective_execution.get("sop_path")),
        briefing_path=(
            _optional_str(effective_execution.get("briefing_path"))
            or _optional_str(effective_execution.get("workspace_agent_briefing_path"))
        ),
        latest_result_status=_optional_str(latest_result.get("status")),
        latest_result_summary=_optional_str(latest_result.get("summary")),
        latest_result_artifacts=artifact_items,
        execution_gate_decision=str(execution_gate.get("decision") or REQUIRE_APPROVAL),
        execution_gate_reason=_optional_str(execution_gate.get("reason")),
        execution_gate_risk_class=str(execution_gate.get("risk_class") or "unknown"),
        execution_gate_risk_factors=[str(item) for item in execution_gate.get("risk_factors") or []],
        execution_gate_approval_state=str(execution_gate.get("approval_state") or "missing"),
        execution_gate_intent_hash=_optional_str(execution_gate.get("intent_hash")),
        execution_gate_authorization_current=bool(execution_gate.get("authorization_current")),
        queued_at=_parse_datetime(effective_execution.get("queued_at")),
        last_transition_at=_parse_datetime(effective_execution.get("last_transition_at")) or card.updated_at,
    )


def _auto_resolve_review_policy(card: PMCard) -> dict[str, str] | None:
    if _is_closed_pm_status(card.status):
        return None
    if _is_host_action_required_card(card) or _is_owner_decision_gate(card):
        return None
    if str(card.status or "").strip().lower() != "review":
        return None

    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    if not bool(workspace_policy.get("auto_resolve_review_residue")):
        return None

    payload = dict(card.payload or {})
    execution = _execution_payload(card) or {}
    if bool(execution.get("manager_attention_required")):
        return None
    reason_text = str(
        execution.get("reason")
        or _payload_value(payload, "reason")
        or ""
    ).strip().lower()

    if "accountability sweep rerouted this stale" in reason_text:
        return {
            "rule": "accountability_stale_review_autoclose",
            "reason": "Auto-closed stale accountability-sweep review residue that did not require an owner decision.",
        }

    review_reference = (
        _parse_datetime(execution.get("last_transition_at"))
        or _parse_datetime(execution.get("queued_at"))
        or card.updated_at
        or card.created_at
    )
    age_hours = 0.0
    if review_reference is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - review_reference.astimezone(timezone.utc)).total_seconds() / 3600)
    if age_hours >= 168:
        return {
            "rule": "aged_review_autoclose",
            "reason": "Auto-closed an old review card in a self-managed workspace because no explicit owner gate was present.",
        }

    return None


def _auto_resolve_execution_residue_policy(card: PMCard, cards_by_id: dict[str, PMCard]) -> dict[str, str] | None:
    if _is_closed_pm_status(card.status):
        return None
    if _is_host_action_required_card(card) or _is_owner_decision_gate(card):
        return None

    payload = dict(card.payload or {})
    if card.source != "accountability_sweep:executive_followup" and not bool(payload.get("created_from_accountability_sweep")):
        return None

    execution = _execution_payload(card) or {}
    normalized_state = str(execution.get("state") or "").strip().lower()
    normalized_executor_status = str(execution.get("executor_status") or "").strip().lower()
    if normalized_state != "failed" and normalized_executor_status != "failed":
        return None

    tracked_card_ids = _accountability_followup_tracked_card_ids(card)
    if not tracked_card_ids:
        return None
    pending_card_ids = [
        card_id
        for card_id in tracked_card_ids
        if not _accountability_tracked_card_is_healthy(cards_by_id.get(card_id))
    ]
    if pending_card_ids:
        return None

    return {
        "rule": "accountability_followup_resolved_after_tracked_lanes_closed",
        "reason": "Auto-closed failed accountability-sweep follow-up because every tracked stale PM lane is now back in review, done, or closed.",
    }


def _auto_close_stale_owner_review_duplicates(cards: list[PMCard]) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    completed = [card for card in cards if _is_closed_pm_status(card.status)]
    for card in cards:
        if _is_closed_pm_status(card.status):
            continue
        if not _is_workspace_owner_review_card(card):
            continue
        if _is_owner_decision_gate(card):
            continue
        if not _owner_review_has_decision(card):
            continue
        completed_sibling = _completed_owner_review_sibling(card, completed)
        if completed_sibling is None:
            continue
        payload = dict(card.payload or {})
        payload["duplicate_resolution"] = {
            "rule": "owner_review_completed_sibling_autoclose",
            "completed_card_id": completed_sibling.id,
            "completed_card_title": completed_sibling.title,
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Closed stale owner-review duplicate because a completed sibling card already resolved the same owner-approved work.",
        }
        effective = _persist_status_payload_update(
            card,
            operation="stale owner-review duplicate closure",
            status="done",
            payload=payload,
        )
        closed.append(
            {
                "card_id": effective.id,
                "title": effective.title,
                "workspace_key": _workspace_key_from_card(effective),
                "completed_card_id": completed_sibling.id,
                "completed_card_title": completed_sibling.title,
                "rule": "owner_review_completed_sibling_autoclose",
                "reason": payload["duplicate_resolution"]["reason"],
            }
        )
    return closed


def _is_workspace_owner_review_card(card: PMCard) -> bool:
    return str(card.source or "").strip() in {
        "codex_native:workspace-owner-review",
        "openclaw:workspace-owner-review",
    } or str(card.link_type or "").strip() == "owner_review"


def _owner_review_has_decision(card: PMCard) -> bool:
    owner_review = (card.payload or {}).get("owner_review")
    if not isinstance(owner_review, dict):
        return False
    return bool(str(owner_review.get("decision") or "").strip())


def _completed_owner_review_sibling(card: PMCard, completed_cards: list[PMCard]) -> PMCard | None:
    workspace_key = _workspace_key_from_card(card)
    tokens = _owner_review_match_tokens(card)
    if not tokens:
        return None
    matches: list[PMCard] = []
    for candidate in completed_cards:
        if candidate.id == card.id:
            continue
        if _workspace_key_from_card(candidate) != workspace_key:
            continue
        candidate_text = _owner_review_search_text(candidate)
        if any(token in candidate_text for token in tokens):
            matches.append(candidate)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.updated_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]


def _owner_review_match_tokens(card: PMCard) -> list[str]:
    payload = dict(card.payload or {})
    owner_review = payload.get("owner_review") if isinstance(payload.get("owner_review"), dict) else {}
    raw_tokens = [
        owner_review.get("queue_id") if isinstance(owner_review, dict) else None,
        owner_review.get("draft_path") if isinstance(owner_review, dict) else None,
        owner_review.get("title") if isinstance(owner_review, dict) else None,
        card.title,
    ]
    tokens: list[str] = []
    for value in raw_tokens:
        normalized = _normalize_owner_review_token(value)
        if normalized and len(normalized) >= 6 and normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _owner_review_search_text(card: PMCard) -> str:
    payload = dict(card.payload or {})
    return _normalize_owner_review_token(
        " ".join(
            [
                str(card.title or ""),
                str(card.source or ""),
                str(card.link_type or ""),
                str(payload),
            ]
        )
    )


def _normalize_owner_review_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _accountability_followup_tracked_card_ids(card: PMCard) -> list[str]:
    payload = dict(card.payload or {})
    tracked: list[str] = []
    for key in ("rerouted_card_ids", "stale_card_ids", "stale_review_card_ids", "stale_running_card_ids"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            normalized = str(item or "").strip()
            if normalized and normalized != card.id and normalized not in tracked:
                tracked.append(normalized)
    return tracked


def _accountability_tracked_card_is_healthy(card: PMCard | None) -> bool:
    if card is None:
        return False
    status = str(card.status or "").strip().lower()
    if status in {"review", "done", "closed", "cancelled"}:
        return True
    execution = _execution_payload(card) or {}
    state = str(execution.get("state") or "").strip().lower()
    return state in {"review", "done"}


def _current_gate_allows_failed_execution_recovery(card: PMCard, gate: dict[str, Any]) -> bool:
    """Allow retries only for a current, signed, bounded internal execution."""

    payload = dict(card.payload or {})
    if _is_closed_pm_status(card.status):
        return False
    if _is_workspace_owner_review_card(card) or _is_owner_decision_gate(card) or _is_host_action_required_card(card):
        return False
    if isinstance(payload.get("host_action_required"), dict) or isinstance(payload.get("host_action_automation"), dict):
        return False
    return bool(
        gate.get("decision") == AUTO_EXECUTE
        and gate.get("approval_state") == "not_required"
        and gate.get("authorization_current") is True
        and gate.get("risk_class") == "safe_internal_reversible"
        and gate.get("capability_id") == BOUNDED_PROJECT_CAPABILITY
        and gate.get("runner_profile") == "codex_workspace"
        and not gate.get("risk_factors")
    )


def _failed_execution_evidence(card: PMCard) -> dict[str, Any]:
    payload = dict(card.payload or {})
    execution = dict(_execution_payload(card) or {})
    latest_result = payload.get("latest_execution_result")
    latest_result_status = (
        str(latest_result.get("status") or "").strip().lower()
        if isinstance(latest_result, dict)
        else ""
    )
    error_text = sanitize_brain_text(
        " ".join(str(execution.get("executor_last_error") or "").split()).strip()
    )
    packet_reference = (
        "legacy-execution-packet-present"
        if str(execution.get("execution_packet_path") or "").strip()
        else ""
    )
    evidence = {
        "pm_status": str(card.status or "").strip().lower(),
        "execution_state": str(execution.get("state") or "").strip().lower(),
        "executor_status": str(execution.get("executor_status") or "").strip().lower(),
        "latest_result_status": latest_result_status,
        "latest_result_id": (
            str(latest_result.get("result_id") or "").strip() or None
            if isinstance(latest_result, dict)
            else None
        ),
        "latest_result_claim_id": (
            str(latest_result.get("claim_id") or "").strip() or None
            if isinstance(latest_result, dict)
            else None
        ),
        "latest_result_commit_digest": (
            str(latest_result.get("commit_digest") or "").strip() or None
            if isinstance(latest_result, dict)
            else None
        ),
        "execution_claim_id": str(execution.get("claim_id") or "").strip() or None,
        "execution_result_id": str(execution.get("result_id") or "").strip() or None,
        "executor_worker_id": str(execution.get("executor_worker_id") or "").strip() or None,
        "executor_started_at": str(execution.get("executor_started_at") or "").strip() or None,
        "executor_finished_at": str(execution.get("executor_finished_at") or "").strip() or None,
        "last_transition_at": str(execution.get("last_transition_at") or "").strip() or None,
        "executor_last_error": error_text[:1000] or None,
        "execution_packet_reference": packet_reference[:1000] or None,
    }
    evidence["evidence_sha256"] = hashlib.sha256(
        json.dumps(evidence, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return evidence


def _failed_execution_recovery_history(
    card: PMCard,
    *,
    evidence: dict[str, Any],
    retry_count: int,
    retry_limit: int,
    captured_at: str,
) -> list[dict[str, Any]]:
    latest_manual_review = dict((card.payload or {}).get("latest_manual_review") or {})
    history = [
        dict(item)
        for item in latest_manual_review.get("failed_execution_recovery_history") or []
        if isinstance(item, dict)
    ]
    evidence_sha256 = str(evidence.get("evidence_sha256") or "")
    if not any(str(item.get("evidence_sha256") or "") == evidence_sha256 for item in history):
        history.append(
            {
                **evidence,
                "captured_at": captured_at,
                "retry_count_before_resolution": retry_count,
                "retry_limit": retry_limit,
            }
        )
    return history[-(AUTO_CONTRACT_RETRY_LIMIT + 1) :]


def _autonomous_failed_execution_progression(
    card: PMCard,
    *,
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    if not _current_gate_allows_failed_execution_recovery(card, gate):
        return None

    payload = dict(card.payload or {})
    execution = dict(_execution_payload(card) or {})
    failure_states = {
        str(card.status or "").strip().lower(),
        str(execution.get("state") or "").strip().lower(),
        str(execution.get("executor_status") or "").strip().lower(),
    }
    if "failed" not in failure_states:
        return None
    contract = payload.get("completion_contract")
    if not isinstance(contract, dict) or not contract:
        return None

    retry_limit = _bounded_completion_contract_retry_limit(contract.get("auto_return_limit"))
    retry_count = _completion_contract_auto_retry_count(card)
    evidence = _failed_execution_evidence(card)
    evidence_sha256 = str(evidence.get("evidence_sha256") or "")
    latest_manual_review = dict(payload.get("latest_manual_review") or {})
    if str(latest_manual_review.get("failed_execution_fingerprint") or "") == evidence_sha256:
        return None

    captured_at = datetime.now(timezone.utc).isoformat()
    recovery_history = _failed_execution_recovery_history(
        card,
        evidence=evidence,
        retry_count=retry_count,
        retry_limit=retry_limit,
        captured_at=captured_at,
    )
    contract_assessment = _completion_contract_assessment(card)
    assessment_summary = (
        _contract_assessment_summary(contract_assessment)
        if isinstance(contract_assessment, dict)
        else "The failed execution did not produce a completion receipt."
    )
    error_summary = str(evidence.get("executor_last_error") or "").strip()
    failure_summary = f" Last failure: {error_summary[:240]}" if error_summary else ""
    shared = {
        "contract_assessment": contract_assessment,
        "failed_execution_fingerprint": evidence_sha256,
        "failed_execution_gate_intent_hash": str(gate.get("intent_hash") or "") or None,
        "failed_execution_recovery_history": recovery_history,
        "failed_execution_retry_limit": retry_limit,
        "failed_execution_recovery_schema_version": FAILED_EXECUTION_RECOVERY_SCHEMA_VERSION,
    }

    if retry_count >= retry_limit:
        return {
            **shared,
            "action": "blocked",
            "rule": "failed_execution_retry_exhausted",
            "reason": (
                f"Codex kept this execution failed for manager attention because its bounded automatic retry limit "
                f"of {retry_limit} was exhausted. {assessment_summary}{failure_summary}"
            ),
            "worker_action": "escalate_for_attention",
            "contract_auto_return_count": retry_count,
        }

    return {
        **shared,
        "action": "return",
        "rule": "failed_execution_return_for_retry",
        "reason": (
            f"Codex returned this failed safe internal execution for bounded retry {retry_count + 1} of "
            f"{retry_limit}. {assessment_summary}{failure_summary}"
        ),
        "worker_action": "return_to_execution",
        "contract_auto_return_count": retry_count + 1,
    }


def _build_failed_execution_progression_update(
    card: PMCard,
    *,
    progression: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if progression.get("action") == "return":
        status, payload = build_card_action_update(
            card,
            action="return",
            requested_by=AUTO_PROGRESS_REQUESTED_BY,
            reason=progression["reason"],
        )
        latest_manual_review = dict(payload.get("latest_manual_review") or {})
        latest_manual_review.update(
            {
                "auto_progressed": True,
                "policy_rule": progression["rule"],
                "worker_action": progression["worker_action"],
                "worker_id": AUTO_PROGRESS_REQUESTED_BY,
                "contract_assessment": progression.get("contract_assessment"),
                "contract_auto_return_count": progression.get("contract_auto_return_count"),
                "failed_execution_fingerprint": progression.get("failed_execution_fingerprint"),
                "failed_execution_recovery_history": progression.get("failed_execution_recovery_history") or [],
                "failed_execution_retry_limit": progression.get("failed_execution_retry_limit"),
                "failed_execution_recovery_schema_version": progression.get(
                    "failed_execution_recovery_schema_version"
                ),
            }
        )
        payload["latest_manual_review"] = latest_manual_review
        return status, payload

    payload = dict(card.payload or {})
    execution = dict(_execution_payload(card) or {})
    now = datetime.now(timezone.utc).isoformat()
    history = list(execution.get("history") or [])
    history.append(
        {
            "event": "failed_execution_retry_exhausted",
            "state": "failed",
            "requested_by": AUTO_PROGRESS_REQUESTED_BY,
            "at": now,
            "evidence_sha256": progression.get("failed_execution_fingerprint"),
            "retry_count": progression.get("contract_auto_return_count"),
            "retry_limit": progression.get("failed_execution_retry_limit"),
        }
    )
    execution.update(
        {
            "state": "failed",
            "executor_status": "failed",
            "manager_attention_required": True,
            "reason": progression["reason"],
            "failed_execution_retry_exhausted_at": now,
            "history": history[-12:],
        }
    )
    payload["execution"] = execution
    latest_manual_review = dict(payload.get("latest_manual_review") or {})
    latest_manual_review.update(
        {
            "action": "blocked",
            "reviewed_at": now,
            "reviewed_by": AUTO_PROGRESS_REQUESTED_BY,
            "from_lane": "failed",
            "auto_progressed": True,
            "policy_rule": progression["rule"],
            "worker_action": progression["worker_action"],
            "worker_id": AUTO_PROGRESS_REQUESTED_BY,
            "contract_assessment": progression.get("contract_assessment"),
            "contract_auto_return_count": progression.get("contract_auto_return_count"),
            "failed_execution_fingerprint": progression.get("failed_execution_fingerprint"),
            "failed_execution_recovery_history": progression.get("failed_execution_recovery_history") or [],
            "failed_execution_retry_limit": progression.get("failed_execution_retry_limit"),
            "failed_execution_recovery_schema_version": progression.get(
                "failed_execution_recovery_schema_version"
            ),
            "reason": progression["reason"],
        }
    )
    payload["latest_manual_review"] = latest_manual_review
    return str(card.status or "in_progress"), payload


def _failed_execution_progression_result(
    updated: PMCard,
    *,
    progression: dict[str, Any],
) -> tuple[dict[str, Any], PMCardActionResult]:
    action = str(progression.get("action") or "return")
    action_result = PMCardActionResult(
        card=updated,
        queue_entry=build_execution_queue_entry(updated),
        successor_card=None,
    )
    return (
        {
            "card_id": updated.id,
            "title": updated.title,
            "workspace_key": _workspace_key_from_card(updated),
            "action": action,
            "resolution_mode": None,
            "rule": progression["rule"],
            "reason": progression["reason"],
            "successor_card_id": None,
            "successor_card_title": None,
            "host_action_card_id": None,
            "host_action_card_title": None,
        },
        action_result,
    )


def _commit_autonomous_failed_execution_progression(
    card: PMCard,
    *,
    expected_progression: dict[str, Any],
) -> tuple[dict[str, Any], PMCardActionResult] | None:
    """Commit one failed-result transition only from the exact selected row.

    The PM review worker starts from a detached list snapshot.  A generic
    ``update_card`` here would replace the complete JSON payload even when an
    owner action, a newer result, or a gate change had landed since selection.
    Lock and re-read the authoritative row, require the exact timestamp,
    failure identity, and current signed gate selected by the worker, then
    build the transition from that locked row.  A mismatch is an intentional
    no-op; the next worker pass may evaluate the newer state.
    """

    expected_updated_at = card.updated_at
    expected_fingerprint = str(expected_progression.get("failed_execution_fingerprint") or "")
    expected_gate_intent_hash = str(expected_progression.get("failed_execution_gate_intent_hash") or "")
    if expected_updated_at is None or not expected_fingerprint or not expected_gate_intent_hash:
        return None

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                FROM pm_cards
                WHERE id = %s
                FOR UPDATE
                """,
                (card.id,),
            )
            row = cur.fetchone()
            if row is None or row.get("updated_at") != expected_updated_at:
                conn.rollback()
                return None

            current_card = _row_to_card(row)
            current_gate = _execution_gate_for_card(current_card)
            current_progression = _autonomous_failed_execution_progression(
                current_card,
                gate=current_gate,
            )
            if current_progression is None:
                conn.rollback()
                return None
            if (
                str(current_progression.get("failed_execution_fingerprint") or "")
                != expected_fingerprint
                or str(current_progression.get("failed_execution_gate_intent_hash") or "")
                != expected_gate_intent_hash
                or str(current_progression.get("action") or "")
                != str(expected_progression.get("action") or "")
                or str(current_progression.get("rule") or "")
                != str(expected_progression.get("rule") or "")
                or int(current_progression.get("contract_auto_return_count") or 0)
                != int(expected_progression.get("contract_auto_return_count") or 0)
                or int(current_progression.get("failed_execution_retry_limit") or 0)
                != int(expected_progression.get("failed_execution_retry_limit") or 0)
            ):
                conn.rollback()
                return None

            next_status, next_payload = _build_failed_execution_progression_update(
                current_card,
                progression=current_progression,
            )
            next_payload = apply_execution_gate(
                card_id=current_card.id,
                title=current_card.title,
                source=current_card.source,
                workspace_key=_workspace_key_from_card(current_card),
                payload=next_payload,
            )
            signed_payload = sign_execution_payload(current_card.id, next_payload)
            cur.execute(
                """
                UPDATE pm_cards
                SET status = %s,
                    payload = %s,
                    updated_at = clock_timestamp()
                WHERE id = %s
                  AND updated_at = %s
                  AND (
                    LOWER(COALESCE(status, '')) = 'failed'
                    OR LOWER(COALESCE(payload->'execution'->>'state', '')) = 'failed'
                    OR LOWER(COALESCE(payload->'execution'->>'executor_status', '')) = 'failed'
                  )
                RETURNING id, title, owner, status, source, link_type, link_id, due_at, payload, created_at, updated_at
                """,
                (
                    next_status,
                    Json(signed_payload),
                    current_card.id,
                    row["updated_at"],
                ),
            )
            updated_row = cur.fetchone()
        if updated_row is None:
            conn.rollback()
            return None
        conn.commit()

    updated = _row_to_card(updated_row)
    return _failed_execution_progression_result(
        updated,
        progression=current_progression,
    )


def _auto_progress_single_card(
    card: PMCard,
    *,
    cards_by_id: dict[str, PMCard],
) -> tuple[dict[str, Any], PMCardActionResult] | None:
    residue_policy = _auto_resolve_execution_residue_policy(card, cards_by_id)
    if residue_policy is not None:
        result = _apply_card_action(
            card,
            action="approve",
            requested_by=AUTO_PROGRESS_REQUESTED_BY,
            reason=residue_policy["reason"],
            resolution_mode="close_only",
            review_metadata={
                "auto_resolved": True,
                "auto_progressed": True,
                "policy_rule": residue_policy["rule"],
                "worker_action": "close_only",
                "worker_id": AUTO_PROGRESS_REQUESTED_BY,
            },
        )
        if result is None:
            return None
        return (
            {
                "card_id": result.card.id,
                "title": result.card.title,
                "workspace_key": _workspace_key_from_card(result.card),
                "action": "approve",
                "resolution_mode": "close_only",
                "rule": residue_policy["rule"],
                "reason": residue_policy["reason"],
                "successor_card_id": result.successor_card.id if result.successor_card else None,
                "successor_card_title": result.successor_card.title if result.successor_card else None,
                "host_action_card_id": None,
                "host_action_card_title": None,
            },
            result,
        )

    gate = _execution_gate_for_card(card)
    if not _execution_gate_authorizes_card(card, gate=gate):
        return None

    progression = _autonomous_failed_execution_progression(card, gate=gate)
    if progression is not None:
        return _commit_autonomous_failed_execution_progression(
            card,
            expected_progression=progression,
        )

    stale_policy = _auto_resolve_review_policy(card) if progression is None else None
    if stale_policy is not None:
        result = _apply_card_action(
            card,
            action="approve",
            requested_by=AUTO_PROGRESS_REQUESTED_BY,
            reason=stale_policy["reason"],
            resolution_mode="close_only",
            review_metadata={
                "auto_resolved": True,
                "auto_progressed": True,
                "policy_rule": stale_policy["rule"],
                "worker_action": "close_only",
                "worker_id": AUTO_PROGRESS_REQUESTED_BY,
            },
        )
        if result is None:
            return None
        return (
            {
                "card_id": result.card.id,
                "title": result.card.title,
                "workspace_key": _workspace_key_from_card(result.card),
                "action": "approve",
                "resolution_mode": "close_only",
                "rule": stale_policy["rule"],
                "reason": stale_policy["reason"],
                "successor_card_id": result.successor_card.id if result.successor_card else None,
                "successor_card_title": result.successor_card.title if result.successor_card else None,
                "host_action_card_id": None,
                "host_action_card_title": None,
            },
            result,
        )

    if progression is None:
        progression = _autonomous_returned_host_action_progression(card)
        if progression is None:
            progression = _autonomous_review_progression(card)
    if progression is None:
        return None
    action = str(progression.get("action") or "approve")
    review_metadata = {
        "auto_progressed": True,
        "policy_rule": progression["rule"],
        "worker_action": progression.get("worker_action") or progression.get("resolution_mode") or action,
        "worker_id": AUTO_PROGRESS_REQUESTED_BY,
    }
    contract_assessment = progression.get("contract_assessment")
    if isinstance(contract_assessment, dict):
        review_metadata["contract_assessment"] = contract_assessment
    if progression.get("contract_auto_return_count") is not None:
        review_metadata["contract_auto_return_count"] = progression.get("contract_auto_return_count")
    for metadata_key in (
        "failed_execution_fingerprint",
        "failed_execution_recovery_history",
        "failed_execution_retry_limit",
        "failed_execution_recovery_schema_version",
    ):
        if progression.get(metadata_key) is not None:
            review_metadata[metadata_key] = progression.get(metadata_key)
    result = _apply_card_action(
        card,
        action=action,
        requested_by=AUTO_PROGRESS_REQUESTED_BY,
        reason=progression["reason"],
        resolution_mode=progression.get("resolution_mode"),
        next_title=progression.get("next_title"),
        next_reason=progression.get("next_reason"),
        proof_items=None,
        review_metadata=review_metadata,
    )
    if result is None:
        return None
    host_action_card: PMCard | None = None
    host_action_required = progression.get("host_action_required")
    if action == "approve" and isinstance(host_action_required, dict):
        host_action_card = _create_host_action_required_card(
            result.card,
            requested_by=AUTO_PROGRESS_REQUESTED_BY,
            host_action_required=host_action_required,
        )
        if host_action_card is not None:
            updated_payload = dict(result.card.payload or {})
            latest_manual_review = dict(updated_payload.get("latest_manual_review") or {})
            latest_manual_review["host_action_card_id"] = host_action_card.id
            latest_manual_review["host_action_card_title"] = host_action_card.title
            updated_payload["latest_manual_review"] = latest_manual_review
            updated_payload["host_action_successor"] = {
                "card_id": host_action_card.id,
                "title": host_action_card.title,
                "created_at": _datetime_to_iso(host_action_card.created_at),
                "workspace_key": _workspace_key_from_card(host_action_card),
            }
            refreshed = _persist_status_payload_update(
                result.card,
                operation="autonomous host-action successor link receipt",
                status=result.card.status,
                payload=updated_payload,
            )
            result = PMCardActionResult(
                card=refreshed,
                queue_entry=build_execution_queue_entry(refreshed),
                successor_card=result.successor_card,
            )
    return (
        {
            "card_id": result.card.id,
            "title": result.card.title,
            "workspace_key": _workspace_key_from_card(result.card),
            "action": action,
            "resolution_mode": progression.get("resolution_mode"),
            "rule": progression["rule"],
            "reason": progression["reason"],
            "successor_card_id": result.successor_card.id if result.successor_card else None,
            "successor_card_title": result.successor_card.title if result.successor_card else None,
            "host_action_card_id": host_action_card.id if host_action_card else None,
            "host_action_card_title": host_action_card.title if host_action_card else None,
        },
        result,
    )


def _autonomous_review_progression(card: PMCard) -> dict[str, Any] | None:
    if _is_closed_pm_status(card.status):
        return None
    if _is_host_action_required_card(card) or _is_owner_decision_gate(card):
        return None
    if str(card.status or "").strip().lower() != "review":
        return None

    execution = _execution_payload(card) or {}
    if bool(execution.get("manager_attention_required")):
        return None
    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    interrupt_policy = str(workspace_policy.get("interrupt_policy") or "manual_review")
    if interrupt_policy not in {"owner_gate_only", "manager_attention_only"}:
        return None

    host_action_required = _extract_host_action_required(card)
    contract_assessment = _completion_contract_assessment(card, host_action_required=host_action_required)
    if contract_assessment is not None and not bool(contract_assessment.get("satisfied")):
        retry_limit = _bounded_completion_contract_retry_limit(contract_assessment.get("auto_return_limit"))
        current_retry_count = _completion_contract_auto_retry_count(card)
        assessment_summary = _contract_assessment_summary(contract_assessment)
        if current_retry_count >= retry_limit:
            return {
                "action": "blocked",
                "rule": "completion_contract_escalation_after_retries",
                "reason": (
                    "Codex review worker could not satisfy the PM completion contract after repeated automatic passes. "
                    + assessment_summary
                ),
                "worker_action": "escalate_for_attention",
                "contract_assessment": contract_assessment,
            }
        return {
            "action": "return",
            "rule": "completion_contract_return_for_rework",
            "reason": (
                "Codex review worker returned this card to execution because the PM completion contract was not met yet. "
                + assessment_summary
            ),
            "worker_action": "return_to_execution",
            "contract_assessment": contract_assessment,
            "contract_auto_return_count": current_retry_count + 1,
        }

    if host_action_required is not None:
        return {
            "action": "approve",
            "rule": "completion_contract_host_action_required",
            "reason": "Codex review worker accepted the internal execution result and routed the remaining external step into a host action card.",
            "resolution_mode": "close_only",
            "contract_assessment": contract_assessment,
            "host_action_required": host_action_required,
        }

    auto_resolve_policy = _auto_resolve_review_policy(card)
    if auto_resolve_policy is not None:
        return {
            "action": "approve",
            "rule": str(auto_resolve_policy.get("rule") or "auto_resolve_review_residue"),
            "reason": str(auto_resolve_policy.get("reason") or "Automatically resolved routine review residue."),
            "resolution_mode": "close_only",
            "worker_action": "close_only",
            "contract_assessment": contract_assessment,
        }

    resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode")) or "close_only"
    next_title: str | None = None
    next_reason: str | None = None
    if resolution_mode == "close_and_spawn_next":
        suggestion = _suggest_review_followup(card, workspace_policy)
        if suggestion is None or not str(suggestion.get("title") or "").strip():
            return None
        if _is_repeated_review_followup(card, suggestion):
            return {
                "action": "approve",
                "rule": "workspace_policy_accept_and_close_repeated_successor",
                "reason": "Codex review worker accepted this routine review result and closed it because the suggested follow-up repeats the current PM lane.",
                "resolution_mode": "close_only",
                "worker_action": "close_only",
                "contract_assessment": contract_assessment,
            }
        next_title = str(suggestion.get("title") or "").strip()
        next_reason = str(suggestion.get("reason") or "").strip() or None

    if resolution_mode == "close_and_spawn_next":
        return {
            "action": "approve",
            "rule": "workspace_policy_accept_and_continue",
            "reason": "Codex review worker accepted this routine review result and opened the next PM lane under the workspace review policy.",
            "resolution_mode": resolution_mode,
            "next_title": next_title or "",
            "next_reason": next_reason or "",
            "contract_assessment": contract_assessment,
        }

    return {
        "action": "approve",
        "rule": "workspace_policy_accept_and_close",
        "reason": "Codex review worker accepted this routine review result and closed the lane under the workspace review policy.",
        "resolution_mode": resolution_mode,
        "contract_assessment": contract_assessment,
    }


def _autonomous_returned_host_action_progression(card: PMCard) -> dict[str, Any] | None:
    if _is_closed_pm_status(card.status):
        return None
    status = str(card.status or "").strip().lower()
    if status not in {"todo", "queued"}:
        return None
    if _is_host_action_required_card(card) or _is_owner_decision_gate(card):
        return None

    payload = dict(card.payload or {})
    if _payload_contract_source(payload) not in {
        "standup_promotion",
        "post_sync_dispatch",
    }:
        return None

    latest_manual_review = dict(payload.get("latest_manual_review") or {})
    if str(latest_manual_review.get("action") or "").strip().lower() != "return":
        return None

    execution = _execution_payload(card) or {}
    if bool(execution.get("manager_attention_required")):
        return None
    if str(execution.get("state") or "").strip().lower() in {"running", "in_progress"}:
        return None

    host_action_required = _extract_host_action_required(card)
    if host_action_required is None:
        return None
    contract_assessment = _completion_contract_assessment(card, host_action_required=host_action_required)
    if contract_assessment is not None and not bool(contract_assessment.get("satisfied")):
        return None

    return {
        "action": "approve",
        "rule": "completion_contract_host_action_after_return",
        "reason": (
            "Codex review worker converted this returned standup lane into a host action because the repo-side work "
            "is complete and only the external proof step remains."
        ),
        "resolution_mode": "close_only",
        "worker_action": "route_host_action",
        "contract_assessment": contract_assessment,
        "host_action_required": host_action_required,
    }


def _bounded_completion_contract_retry_limit(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return AUTO_CONTRACT_RETRY_LIMIT
    try:
        requested_limit = int(value)
    except (TypeError, ValueError):
        return AUTO_CONTRACT_RETRY_LIMIT
    return max(0, min(requested_limit, AUTO_CONTRACT_RETRY_LIMIT))


def _completion_contract_assessment(
    card: PMCard,
    *,
    host_action_required: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = dict(card.payload or {})
    contract = payload.get("completion_contract")
    if not isinstance(contract, dict) or not contract:
        return None

    workspace_key = _workspace_key_from_card(card)
    latest_result = payload.get("latest_execution_result")
    done_when = [
        str(item).strip()
        for item in contract.get("done_when") or []
        if str(item).strip()
    ]
    requirements = dict(contract.get("result_requirements") or {})
    summary_min_length = max(1, int(requirements.get("summary_min_length") or 20))
    require_outcome_or_artifact = bool(requirements.get("require_outcome_or_artifact", True))
    require_writeback = bool(requirements.get("require_writeback", True))
    allow_blockers = bool(requirements.get("allow_blockers", False))
    require_local_artifact_citation = bool(requirements.get("require_local_artifact_citation", False))
    require_lane_constraint = bool(requirements.get("require_lane_constraint", False))

    missing: list[str] = []
    summary = ""
    status = ""
    outcomes: list[str] = []
    artifacts: list[str] = []
    blockers: list[str] = []

    if not isinstance(latest_result, dict):
        if require_writeback:
            missing.append("No execution result has been written back yet.")
    else:
        summary = str(latest_result.get("summary") or "").strip()
        status = str(latest_result.get("status") or "").strip().lower()
        outcomes = [str(item).strip() for item in latest_result.get("outcomes") or [] if str(item).strip()]
        artifacts = [str(item).strip() for item in latest_result.get("artifacts") or [] if str(item).strip()]
        blockers = [str(item).strip() for item in latest_result.get("blockers") or [] if str(item).strip()]
        if len(summary) < summary_min_length:
            missing.append("Result summary is too thin to prove completion.")
        if require_outcome_or_artifact and not outcomes and not artifacts:
            missing.append("Result is missing a concrete outcome or artifact.")
        if not allow_blockers and blockers and host_action_required is None:
            missing.append("Result still contains unresolved blockers.")
        if status == "blocked" and host_action_required is None:
            missing.append("Result reported a blocked status.")
        if require_local_artifact_citation and not _result_has_local_artifact_reference(latest_result, workspace_key):
            missing.append("Result does not cite local artifact context for the active workspace.")
        out_of_scope_roots = _out_of_scope_execution_log_roots(latest_result, workspace_key)
        if require_lane_constraint and out_of_scope_roots:
            missing.append(
                "Result cites another workspace execution log instead of staying inside the active lane: "
                + ", ".join(f"`{root}`" for root in out_of_scope_roots[:3])
            )

    return {
        "active": True,
        "satisfied": not missing,
        "missing": missing,
        "done_when": done_when,
        "summary": summary,
        "status": status,
        "auto_return_limit": _bounded_completion_contract_retry_limit(contract.get("auto_return_limit")),
    }


def _extract_host_action_required(card: PMCard) -> dict[str, Any] | None:
    payload = dict(card.payload or {})
    latest_result = payload.get("latest_execution_result")
    if not isinstance(latest_result, dict):
        return None

    steps: list[str] = []
    proof_required: list[str] = []
    detected_from = "follow_up_prefix"

    explicit_host_actions = latest_result.get("host_actions")
    if isinstance(explicit_host_actions, list):
        detected_from = "explicit_host_actions"
        for item in explicit_host_actions:
            if isinstance(item, dict):
                summary = _optional_str(item.get("summary"))
                if summary:
                    steps.append(summary)
                steps.extend(_normalize_string_list(item.get("steps")))
                proof_required.extend(_normalize_string_list(item.get("proof_required")))
            else:
                normalized = str(item).strip()
                if normalized:
                    steps.append(normalized)

    if not steps:
        for follow_up in _normalize_string_list(latest_result.get("follow_ups")):
            match = HOST_ACTION_PREFIX.match(follow_up)
            if match:
                normalized = str(match.group(1) or "").strip()
                if normalized:
                    steps.append(normalized)

    proof_required.extend(_normalize_string_list(latest_result.get("host_action_proof")))
    deduped_steps = _dedupe_nonempty_strings(steps)
    if not deduped_steps:
        return None

    return {
        "summary": deduped_steps[0],
        "steps": deduped_steps,
        "proof_required": _dedupe_nonempty_strings(proof_required),
        "source_result_id": _optional_str(latest_result.get("result_id")),
        "source_result_summary": _optional_str(latest_result.get("summary")),
        "detected_from": detected_from,
    }


def _result_text_fragments(latest_result: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    summary = str(latest_result.get("summary") or "").strip()
    if summary:
        fragments.append(summary)
    for key in ("outcomes", "artifacts", "follow_ups", "learnings", "host_action_proof"):
        for item in latest_result.get(key) or []:
            normalized = str(item).strip()
            if normalized:
                fragments.append(normalized)
    for key in ("memo_path", "result_path"):
        normalized = str(latest_result.get(key) or "").strip()
        if normalized:
            fragments.append(normalized)
    for item in latest_result.get("host_actions") or []:
        if isinstance(item, dict):
            summary = str(item.get("summary") or "").strip()
            if summary:
                fragments.append(summary)
            for key in ("steps", "proof_required"):
                for step in item.get(key) or []:
                    normalized = str(step).strip()
                    if normalized:
                        fragments.append(normalized)
        else:
            normalized = str(item).strip()
            if normalized:
                fragments.append(normalized)
    return fragments


def _result_has_local_artifact_reference(latest_result: dict[str, Any], workspace_key: str) -> bool:
    normalized_workspace = canonicalize_workspace_key(workspace_key, default="shared_ops")
    workspace_root = workspace_root_slug(normalized_workspace).lower()
    for fragment in _result_text_fragments(latest_result):
        lowered = fragment.lower()
        if not lowered:
            continue
        if normalized_workspace == "shared_ops":
            if lowered.startswith("/users/") or "memory/" in lowered or "workspaces/shared-ops/" in lowered:
                return True
            continue
        if f"/workspaces/{workspace_root}/" in lowered or f"workspaces/{workspace_root}/" in lowered:
            return True
        if lowered.startswith("/users/") and ("/memory/runner-results/" in lowered or "/memory/runner-memos/" in lowered):
            return True
    return False


def _out_of_scope_execution_log_roots(latest_result: dict[str, Any], workspace_key: str) -> list[str]:
    normalized_workspace = canonicalize_workspace_key(workspace_key, default="shared_ops")
    if normalized_workspace == "shared_ops":
        return []
    allowed_root = workspace_root_slug(normalized_workspace).lower()
    seen: list[str] = []
    candidate_roots = [
        str(entry.get("workspace_root") or entry.get("key") or "").strip().lower()
        for entry in workspace_registry_entries()
    ]
    for fragment in _result_text_fragments(latest_result):
        lowered = fragment.lower()
        if "execution log" not in lowered and "execution_log.md" not in lowered:
            continue
        for root in candidate_roots:
            if not root or root == allowed_root or root in seen:
                continue
            if root in lowered:
                seen.append(root)
    return seen


def _is_delayed_host_action_text(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_DELAYED_PATTERNS)


def _normalize_host_action_payload(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    summary = _optional_str(value.get("summary"))
    steps = _dedupe_nonempty_strings(value.get("steps"))
    proof_required = _dedupe_nonempty_strings(value.get("proof_required"))
    normalized: dict[str, Any] = {
        "summary": summary or (steps[0] if steps else (proof_required[0] if proof_required else None)),
        "steps": steps,
        "proof_required": proof_required,
        "workspace_key": _optional_str(value.get("workspace_key")),
        "source_card_id": _optional_str(value.get("source_card_id")),
        "source_card_title": _optional_str(value.get("source_card_title")),
        "source_result_id": _optional_str(value.get("source_result_id")),
        "source_result_summary": _optional_str(value.get("source_result_summary")),
        "detected_from": _optional_str(value.get("detected_from")),
    }
    return normalized if normalized.get("summary") else None


def _split_host_action_timeline(host_action_required: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    current = _normalize_host_action_payload(host_action_required)
    if current is None:
        return {"current": None, "follow_up": None}

    existing_follow_up = _normalize_host_action_payload(host_action_required.get("follow_up_host_action"))
    if existing_follow_up is not None:
        return {"current": current, "follow_up": existing_follow_up}

    steps = _dedupe_nonempty_strings(current.get("steps"))
    proof_required = _dedupe_nonempty_strings(current.get("proof_required"))
    current_steps = [item for item in steps if not _is_delayed_host_action_text(item)]
    follow_up_steps = [item for item in steps if _is_delayed_host_action_text(item)]
    current_proof = [item for item in proof_required if not _is_delayed_host_action_text(item)]
    follow_up_proof = [item for item in proof_required if _is_delayed_host_action_text(item)]
    current_summary = _optional_str(current.get("summary"))

    if current_summary and _is_delayed_host_action_text(current_summary):
        if follow_up_steps and current_summary not in follow_up_steps:
            follow_up_steps.insert(0, current_summary)
        current_summary = current_steps[0] if current_steps else None
    elif current_summary and not current_steps:
        current_steps = [current_summary]

    if not current_steps and not current_proof:
        return {"current": current, "follow_up": None}

    if not current_summary:
        current_summary = current_steps[0] if current_steps else (current_proof[0] if current_proof else None)

    follow_up_summary = follow_up_steps[0] if follow_up_steps else (follow_up_proof[0] if follow_up_proof else None)
    follow_up = None
    if follow_up_summary:
        follow_up = {
            "summary": follow_up_summary,
            "steps": follow_up_steps,
            "proof_required": follow_up_proof,
            "workspace_key": current.get("workspace_key"),
            "source_card_id": current.get("source_card_id"),
            "source_card_title": current.get("source_card_title"),
            "source_result_id": current.get("source_result_id"),
            "source_result_summary": current.get("source_result_summary"),
            "detected_from": current.get("detected_from"),
        }

    return {
        "current": {
            "summary": current_summary,
            "steps": current_steps,
            "proof_required": current_proof,
            "workspace_key": current.get("workspace_key"),
            "source_card_id": current.get("source_card_id"),
            "source_card_title": current.get("source_card_title"),
            "source_result_id": current.get("source_result_id"),
            "source_result_summary": current.get("source_result_summary"),
            "detected_from": current.get("detected_from"),
        },
        "follow_up": follow_up,
    }


def _host_action_text_items(host_action: dict[str, Any] | None) -> list[str]:
    if not isinstance(host_action, dict):
        return []
    items = [_optional_str(host_action.get("summary"))]
    items.extend(_dedupe_nonempty_strings(host_action.get("steps")))
    items.extend(_dedupe_nonempty_strings(host_action.get("proof_required")))
    return [item for item in items if item]


def _host_action_text_blob(host_action: dict[str, Any] | None) -> str:
    return "\n".join(_host_action_text_items(host_action))


def _host_action_requires_publish_state(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_PUBLISH_PATTERNS) and _is_delayed_host_action_text(text)


def _host_action_mentions_publish(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_PUBLISH_PATTERNS)


def _host_action_mentions_scheduling(host_action: dict[str, Any] | None) -> bool:
    text = _host_action_text_blob(host_action)
    if not text:
        return False
    return any(pattern.search(text) for pattern in HOST_ACTION_SCHEDULE_PATTERNS)


def _host_action_required_state_key(host_action: dict[str, Any] | None) -> str | None:
    if _host_action_requires_publish_state(host_action):
        return "published_at"
    if _is_delayed_host_action_text(_host_action_text_blob(host_action)) and _host_action_mentions_scheduling(host_action):
        return "scheduled_at"
    return None


def _parse_host_action_datetime(value: str | None) -> datetime | None:
    text = _optional_str(value)
    if not text:
        return None

    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=NEW_YORK_TZ)

    normalized = re.sub(r"\s+", " ", text.strip())
    timezone_hint = None
    upper = normalized.upper()
    for suffix in (" EDT", " EST", " ET", " UTC"):
        if upper.endswith(suffix):
            timezone_hint = suffix.strip()
            normalized = normalized[: -len(suffix)].strip()
            break
    normalized = normalized.replace("T", " ")
    for fmt in (
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%A, %B %d, %Y at %H:%M",
        "%A, %B %d, %Y at %I:%M %p",
        "%A %B %d, %Y at %H:%M",
        "%A %B %d, %Y at %I:%M %p",
        "%B %d, %Y at %H:%M",
        "%B %d, %Y at %I:%M %p",
        "%a, %d %b %Y - %H:%M",
    ):
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if timezone_hint == "UTC":
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.replace(tzinfo=NEW_YORK_TZ)
    return None


def _extract_host_action_datetime(text_values: list[str]) -> str | None:
    for raw in text_values:
        text = _optional_str(raw)
        if not text:
            continue
        for pattern in HOST_ACTION_TIMESTAMP_PATTERNS:
            for match in pattern.findall(text):
                parsed = _parse_host_action_datetime(match)
                if parsed is not None:
                    return parsed.astimezone(timezone.utc).isoformat()
        parsed_full = _parse_host_action_datetime(text)
        if parsed_full is not None:
            return parsed_full.astimezone(timezone.utc).isoformat()
    return None


def _extract_host_action_external_state(
    host_action_required: dict[str, Any] | None,
    *,
    completion_note: str | None,
    proof_items: list[str] | None,
    proof_field_values: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    normalized_proof_field_values = _normalize_host_action_proof_field_values(proof_field_values)
    for entry in normalized_proof_field_values:
        kind = _optional_str(entry.get("kind")) or ""
        value = _optional_str(entry.get("value"))
        if not value:
            continue
        if kind == "publish_url":
            state["publish_url"] = value
        elif kind == "screenshot_path":
            state["confirmation_path"] = value
            state["screenshot_paths"] = _dedupe_nonempty_strings([*state.get("screenshot_paths", []), value])
        elif kind == "artifact_path":
            state["artifact_paths"] = _dedupe_nonempty_strings([*state.get("artifact_paths", []), value])
        elif kind == "metric_reference":
            state["metric_references"] = _dedupe_nonempty_strings([*state.get("metric_references", []), value])
        elif kind == "proof_note":
            state["proof_notes"] = _dedupe_nonempty_strings([*state.get("proof_notes", []), value])
    evidence_items = [item for item in [completion_note, *list(proof_items or [])] if _optional_str(item)]
    timestamp = _extract_host_action_datetime(
        [entry["value"] for entry in normalized_proof_field_values if _optional_str(entry.get("kind")) == "scheduled_timestamp"]
        + [str(item) for item in evidence_items]
    )
    if not timestamp:
        return state
    if _host_action_mentions_publish(host_action_required):
        state["published_at"] = timestamp
    elif _host_action_mentions_scheduling(host_action_required):
        state["scheduled_at"] = timestamp
    return state


def _host_action_followup_due_at(host_action: dict[str, Any] | None, external_state: dict[str, Any]) -> datetime | None:
    required_state_key = _host_action_required_state_key(host_action)
    if not required_state_key:
        return None
    state_value = _optional_str(external_state.get(required_state_key))
    anchor = _parse_host_action_datetime(state_value)
    if anchor is None:
        return None
    text = _host_action_text_blob(host_action)
    if not text:
        return anchor
    hours_match = re.search(r"\bwithin\s+(\d+)\s*(?:hours?|hrs?|h)\b", text, re.IGNORECASE)
    if hours_match:
        return anchor + timedelta(hours=int(hours_match.group(1)))
    if re.search(r"\bfirst[-\s]24h\b|\bfirst[-\s]24[-\s]hour\b", text, re.IGNORECASE):
        return anchor + timedelta(hours=24)
    return anchor


def _evaluate_host_action_followup_readiness(
    host_action: dict[str, Any] | None,
    completion_payload: dict[str, Any],
) -> dict[str, Any]:
    follow_up = _normalize_host_action_payload(host_action)
    if follow_up is None:
        return {"ready": False, "reason": "No delayed host follow-up is attached."}
    required_state_key = _host_action_required_state_key(follow_up)
    external_state = dict(completion_payload.get("external_state") or {})
    if required_state_key is None:
        return {
            "ready": True,
            "required_state_key": None,
            "due_at": None,
            "reason": "This follow-up does not depend on a delayed external state token.",
        }
    state_value = _optional_str(external_state.get(required_state_key))
    if not state_value:
        if required_state_key == "published_at":
            scheduled_value = _optional_str(external_state.get("scheduled_at"))
            scheduled_anchor = _parse_host_action_datetime(scheduled_value)
            if scheduled_value and scheduled_anchor is not None:
                provisional_due_at = _host_action_followup_due_at(follow_up, {"published_at": scheduled_value})
                return {
                    "ready": False,
                    "required_state_key": required_state_key,
                    "activation_source_state_key": "scheduled_at",
                    "activation_source_value": scheduled_value,
                    "activate_after": scheduled_anchor.astimezone(timezone.utc).isoformat(),
                    "due_at": provisional_due_at.astimezone(timezone.utc).isoformat() if provisional_due_at else None,
                    "reason": (
                        "Waiting until the scheduled publish window opens before creating the delayed host follow-up; "
                        "actual publish still needs host confirmation inside that later step."
                    ),
                }
        return {
            "ready": False,
            "required_state_key": required_state_key,
            "due_at": None,
            "reason": f"Waiting on explicit `{required_state_key}` before the delayed host follow-up can exist.",
        }
    return {
        "ready": True,
        "required_state_key": required_state_key,
        "state_value": state_value,
        "due_at": _host_action_followup_due_at(follow_up, external_state),
        "reason": f"Delayed host follow-up unlocked by `{required_state_key}`.",
    }


def _host_action_activation_status(card: PMCard) -> dict[str, Any] | None:
    if not _is_host_action_required_card(card):
        return None
    payload = dict(card.payload or {})
    host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
    if host_action_required is None:
        return None
    required_state_key = _host_action_required_state_key(host_action_required)
    if required_state_key is None:
        return None
    now = datetime.now(timezone.utc)
    due_at = card.due_at
    if due_at is None:
        return {
            "state": "waiting_on_prerequisite",
            "required_state_key": required_state_key,
            "reason": f"This delayed host follow-up should wait until `{required_state_key}` is recorded upstream.",
        }
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if due_at > now:
        return {
            "state": "not_due_yet",
            "required_state_key": required_state_key,
            "due_at": due_at.isoformat(),
            "reason": f"This delayed host follow-up is not due until `{due_at.astimezone(timezone.utc).isoformat()}`.",
        }
    return {
        "state": "due",
        "required_state_key": required_state_key,
        "due_at": due_at.isoformat(),
        "reason": "This delayed host follow-up is now due.",
    }


def _pending_followup_gate_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = _optional_str(value)
    if not text:
        return None
    parsed = _parse_host_action_datetime(text)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc)


def _resolved_host_action_phases(card: PMCard) -> dict[str, dict[str, Any] | None]:
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    current = _normalize_host_action_payload(host_action_required)
    if current is None:
        return {"current": None, "follow_up": None}

    host_action_followup = _normalize_host_action_payload(payload.get("host_action_followup"))
    if host_action_followup is not None:
        return {"current": current, "follow_up": host_action_followup}
    return _split_host_action_timeline(current)


def _completion_contract_auto_retry_count(card: PMCard) -> int:
    payload = dict(card.payload or {})
    latest_manual_review = payload.get("latest_manual_review")
    if not isinstance(latest_manual_review, dict):
        return 0
    return max(0, int(latest_manual_review.get("contract_auto_return_count") or 0))


def _contract_assessment_summary(assessment: dict[str, Any]) -> str:
    missing = [
        str(item).strip()
        for item in assessment.get("missing") or []
        if str(item).strip()
    ]
    if missing:
        return "Missing: " + "; ".join(missing[:3])
    done_when = [
        str(item).strip()
        for item in assessment.get("done_when") or []
        if str(item).strip()
    ]
    if done_when:
        return "Expected: " + "; ".join(done_when[:2])
    return "The completion contract did not pass."


def _is_owner_decision_gate(card: PMCard) -> bool:
    payload = dict(card.payload or {})
    owner_review_payload = payload.get("owner_review")
    normalized_status = str(card.status or "").strip().lower()
    if isinstance(owner_review_payload, dict):
        queue_id = str(owner_review_payload.get("queue_id") or "").strip()
        sync_state = str(owner_review_payload.get("sync_state") or "").strip().lower()
        decision = str(owner_review_payload.get("decision") or "").strip().lower()
        if decision:
            return False
        if sync_state == "pending_owner_review" and queue_id:
            return True
        if queue_id and normalized_status == "review":
            return True
    if isinstance(card.source, str) and "workspace-owner-review" in card.source and normalized_status == "review":
        return True
    return False


def _execution_payload(card: PMCard) -> dict | None:
    payload = card.payload or {}
    execution = payload.get("execution")
    return dict(execution) if isinstance(execution, dict) else None


def _execution_gate_for_card(card: PMCard) -> dict[str, Any]:
    payload = dict(card.payload or {})
    current = evaluate_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key=_workspace_key_from_card(card),
        payload=payload,
    )
    authorization_current = bool(
        execution_gate_matches_current(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=_workspace_key_from_card(card),
            payload=payload,
        )
        and verify_execution_payload(card.id, payload)
    )
    current["authorization_current"] = authorization_current
    if not authorization_current and current.get("decision") == AUTO_EXECUTE:
        current["reason"] = (
            "This bounded internal card must receive a current signed execution gate before it can run automatically."
        )
    return current


def _execution_gate_authorizes_card(card: PMCard, *, gate: dict[str, Any] | None = None) -> bool:
    current = gate or _execution_gate_for_card(card)
    return bool(current.get("authorization_current")) and execution_gate_allows_run(current)


def execution_defaults_for_workspace(workspace_key: str) -> dict[str, object]:
    return runtime_execution_defaults_for_workspace(workspace_key)


def review_policy_for_workspace(workspace_key: str) -> dict[str, object]:
    return runtime_pm_review_policy_for_workspace(workspace_key)


def _merge_execution_defaults(current_execution: dict, defaults: dict[str, object]) -> dict:
    merged = dict(current_execution)
    for key, value in defaults.items():
        if merged.get(key) in (None, "", []):
            merged[key] = value
    if (
        merged.get("source") == "standup_promotion"
        and str(merged.get("target_agent") or "").strip().lower() == "neo"
        and str(merged.get("manager_agent") or "").strip() == ""
    ):
        merged["manager_agent"] = defaults["manager_agent"]
        merged["target_agent"] = defaults["target_agent"]
        merged["workspace_agent"] = defaults["workspace_agent"]
        merged["execution_mode"] = defaults["execution_mode"]
    return merged


def _workspace_key_from_card(card: PMCard) -> str:
    return _workspace_key_from_payload(card.payload or {})


def _workspace_key_from_payload(payload: dict[str, Any]) -> str:
    for key in ("workspace_key", "workspace", "belongs_to_workspace"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "shared_ops"


def _build_client_review_policy(card: PMCard) -> dict[str, Any]:
    workspace_key = _workspace_key_from_card(card)
    workspace_policy = review_policy_for_workspace(workspace_key)
    execution = dict(_execution_payload(card) or {})
    normalized_status = str(card.status or "").strip().lower()
    owner_gate = _is_owner_decision_gate(card)
    host_action_required = _is_host_action_required_card(card)
    host_action_activation = _host_action_activation_status(card)
    execution_gate = _execution_gate_for_card(card)
    execution_authorized = _execution_gate_authorizes_card(card, gate=execution_gate)
    auto_resolve_policy = _auto_resolve_review_policy(card)
    attention_class = "fyi"
    attention_reason = "This card is visible for context, but it does not currently need your judgment."
    recommended_resolution_mode: str | None = None
    suggested_next_title: str | None = None
    suggested_next_reason: str | None = None
    interrupt_policy = str(workspace_policy.get("interrupt_policy") or "manual_review")

    if _is_closed_pm_status(card.status):
        attention_reason = "This card is already closed and kept here as traceable history."
    elif owner_gate:
        attention_class = "needs_owner"
        attention_reason = "This card is an explicit owner gate and should wait for your call."
    elif host_action_activation is not None and str(host_action_activation.get("state") or "").strip() in {
        "waiting_on_prerequisite",
        "not_due_yet",
    }:
        attention_class = "autonomous"
        attention_reason = _optional_str(host_action_activation.get("reason")) or (
            "This delayed host follow-up is waiting on an upstream state change and should stay out of your action surface."
        )
    elif host_action_required:
        attention_class = "needs_host"
        attention_reason = "This card requires a host action outside the runtime before the loop can fully close."
    elif (
        interrupt_policy in {"owner_gate_only", "manager_attention_only"}
        and execution_authorized
        and not owner_gate
        and not host_action_required
        and (
            str(execution.get("state") or "").strip().lower() == "failed"
            or str(execution.get("executor_status") or "").strip().lower() == "failed"
        )
    ):
        attention_class = "autonomous"
        attention_reason = "This autonomous execution lane failed and should go back through Codex or Jean-Claude, not your owner inbox."
    elif not execution_authorized:
        attention_class = "needs_owner"
        attention_reason = str(execution_gate.get("reason") or "This execution requires your approval before it can run.")
    elif bool(execution.get("manager_attention_required")) or normalized_status in {"blocked", "failed"}:
        attention_class = "needs_owner"
        attention_reason = "This lane is blocked or flagged for manager attention and needs a human decision."
    elif auto_resolve_policy is not None:
        attention_class = "stale"
        attention_reason = auto_resolve_policy["reason"]
    elif normalized_status == "review":
        if interrupt_policy == "manual_review":
            attention_class = "needs_owner"
            attention_reason = "This workspace expects a human review before a returned result is accepted or continued."
        elif interrupt_policy == "owner_gate_only":
            attention_class = "autonomous"
            attention_reason = "Routine review results in this workspace should keep moving unless they hit an owner gate or blocker."
            recommended_resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode"))
        elif interrupt_policy == "manager_attention_only":
            attention_class = "autonomous"
            attention_reason = "Routine review residue in this workspace should close quietly unless manager attention is required."
            recommended_resolution_mode = _valid_resolution_mode(workspace_policy.get("default_resolution_mode"))
    elif normalized_status in {"queued", "running", "in_progress"}:
        attention_reason = "This card is active system work. You usually only need to step in if it blocks or priorities change."

    if recommended_resolution_mode == "close_and_spawn_next":
        suggestion = _suggest_review_followup(card, workspace_policy)
        if suggestion is not None and _is_repeated_review_followup(card, suggestion):
            recommended_resolution_mode = "close_only"
        elif suggestion is not None:
            suggested_next_title = suggestion.get("title")
            suggested_next_reason = suggestion.get("reason")

    return {
        "attention_class": attention_class,
        "attention_reason": attention_reason,
        "policy_label": _optional_str(workspace_policy.get("policy_label")),
        "interrupt_policy": _optional_str(workspace_policy.get("interrupt_policy")),
        "recommended_resolution_mode": recommended_resolution_mode,
        "suggested_next_title": suggested_next_title,
        "suggested_next_reason": suggested_next_reason,
        "auto_resolve_eligible": auto_resolve_policy is not None,
        "owner_decision_gate": owner_gate,
        "host_action_activation": host_action_activation,
        "execution_approval_required": not execution_authorized,
        "execution_gate_reason": _optional_str(execution_gate.get("reason")),
    }


def _is_closed_pm_status(status: Optional[str]) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {"done", "closed", "cancelled"}


def _is_execution_candidate(card: PMCard) -> bool:
    if _is_closed_pm_status(card.status):
        return False
    return _execution_contract_source(card) is not None


def repair_execution_contracts(
    limit: int = 250,
    workspace_key: str | None = None,
    *,
    legacy_owner_review_compatibility: bool = False,
) -> dict[str, Any]:
    cards = list_cards(limit=limit, workspace_key=workspace_key)
    if legacy_owner_review_compatibility is not True:
        cards = [card for card in cards if not _is_workspace_owner_review_card(card)]
    deduped = _dedupe_active_pm_review_resolution_cards(cards)
    host_followup_repairs = _repair_legacy_host_action_cards(cards)
    closed_duplicate_ids = {str(item.get("card_id")) for item in deduped}
    cards = [card for card in cards if card.id not in closed_duplicate_ids]
    repaired: list[dict[str, Any]] = []

    for card in cards:
        patched_payload = _build_missing_execution_contract_payload(card)
        if patched_payload is None:
            continue
        expected_contract_source = _execution_contract_source(card)

        def contract_repair_is_committed(current: PMCard) -> bool:
            current_payload = dict(current.payload or {})
            return bool(
                not _is_closed_pm_status(current.status)
                and _execution_contract_source(current) == expected_contract_source
                and _payload_contract_source(current_payload) == expected_contract_source
                and isinstance(current_payload.get("completion_contract"), dict)
                and bool(current_payload.get("completion_contract"))
                and isinstance(current_payload.get("execution"), dict)
                and bool(current_payload.get("execution"))
                and _build_missing_execution_contract_payload(current) is None
            )

        def build_contract_repair(current: PMCard) -> PMCardUpdate | None:
            if (
                _is_closed_pm_status(current.status)
                or _execution_contract_source(current) != expected_contract_source
            ):
                return None
            current_patch = _build_missing_execution_contract_payload(current)
            return PMCardUpdate(payload=current_patch) if current_patch is not None else None

        effective = _persist_reconciled_card_update(
            card,
            operation="PM execution-contract repair",
            build_update=build_contract_repair,
            is_committed=contract_repair_is_committed,
        )
        repaired.append(
            {
                "card_id": effective.id,
                "title": effective.title,
                "workspace_key": _workspace_key_from_card(effective),
                "status": effective.status,
                "source": effective.source,
                "contract_source": _payload_contract_source(effective.payload or {}),
            }
        )

    return {
        "deduped_count": len(deduped),
        "deduped": deduped,
        "host_followup_repaired_count": len(host_followup_repairs),
        "host_followup_repaired": host_followup_repairs,
        "repaired_count": len(repaired),
        "repaired": repaired,
    }


def _repair_legacy_host_action_cards(cards: list[PMCard]) -> list[dict[str, Any]]:
    cards_by_id = {card.id: card for card in cards}
    repaired: list[dict[str, Any]] = []
    requested_by = "PM Host Action Repair"

    def apply_card_update(card: PMCard, *, status: str | None = None, payload: dict[str, Any] | None = None) -> PMCard:
        effective = _persist_status_payload_update(
            card,
            operation="legacy host-action repair",
            status=status,
            payload=payload,
        )
        cards_by_id[effective.id] = effective
        return effective

    def clear_source_followup_references(source_payload: dict[str, Any], follow_up_card_id: str) -> dict[str, Any]:
        completion = dict(source_payload.get("host_action_completion") or {})
        if _optional_str(completion.get("follow_up_card_id")) == follow_up_card_id:
            completion.pop("follow_up_card_id", None)
            completion.pop("follow_up_card_title", None)
        if completion:
            source_payload["host_action_completion"] = completion
        else:
            source_payload.pop("host_action_completion", None)
        spawned = dict(source_payload.get("host_action_followup_spawned") or {})
        if _optional_str(spawned.get("card_id")) == follow_up_card_id:
            source_payload.pop("host_action_followup_spawned", None)
        return source_payload

    def persist_resolved_host_action_phases(card: PMCard, payload: dict[str, Any]) -> dict[str, Any]:
        phases = _resolved_host_action_phases(card)
        current_phase = phases.get("current")
        follow_up_phase = phases.get("follow_up")
        if current_phase is not None:
            payload["host_action_required"] = {
                **current_phase,
                "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(current_phase.get("proof_required"))),
            }
        if follow_up_phase is not None:
            payload["host_action_followup"] = {
                **follow_up_phase,
                "proof_fields": _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
            }
        else:
            payload.pop("host_action_followup", None)
        return payload

    def build_host_execution_payload(
        current_execution: dict[str, Any],
        *,
        state: str,
        event: str,
        reason: str,
    ) -> dict[str, Any]:
        history = list(current_execution.get("history") or [])
        history.append(
            {
                "event": event,
                "state": state,
                "requested_by": requested_by,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            **current_execution,
            "state": state,
            "requested_by": requested_by,
            "manager_attention_required": False,
            "executor_status": None,
            "executor_worker_id": None,
            "executor_last_error": None,
            "execution_packet_path": None,
            "executor_started_at": None,
            "executor_finished_at": None,
            "briefing_path": None,
            "sop_path": None,
            "reason": reason,
            "last_transition_at": datetime.now(timezone.utc).isoformat(),
            "history": history[-12:],
        }

    def should_reopen_source(
        source_card: PMCard,
        *,
        required_state_key: str | None,
        follow_up_card_id: str,
    ) -> bool:
        if not _is_closed_pm_status(source_card.status):
            return False
        payload = dict(source_card.payload or {})
        completion = dict(payload.get("host_action_completion") or {})
        if _optional_str(completion.get("host_confirmation_mode")) != "confirmed_without_context":
            return False
        external_state = dict(completion.get("external_state") or {})
        if required_state_key and _optional_str(external_state.get(required_state_key)):
            return False
        spawned = dict(payload.get("host_action_followup_spawned") or {})
        references_followup = _optional_str(completion.get("follow_up_card_id")) == follow_up_card_id or _optional_str(
            spawned.get("card_id")
        ) == follow_up_card_id
        return references_followup

    # First, cancel legacy delayed follow-up cards that should not exist yet.
    for card in cards:
        current = cards_by_id.get(card.id, card)
        if _is_closed_pm_status(current.status) or not _is_host_action_required_card(current):
            continue
        activation = _host_action_activation_status(current)
        if not isinstance(activation, dict) or str(activation.get("state") or "").strip() != "waiting_on_prerequisite":
            continue

        payload = dict(current.payload or {})
        host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
        if host_action_required is None:
            continue
        current_completion = dict(payload.get("host_action_completion") or {})
        current_follow_up = _resolved_host_action_phases(current).get("follow_up")
        required_state_key = _optional_str(activation.get("required_state_key"))
        source_card_id = _optional_str(host_action_required.get("source_card_id"))
        source_card = cards_by_id.get(source_card_id) if source_card_id else None
        source_is_host_action = source_card is not None and _is_host_action_required_card(source_card)
        has_follow_up_context = current_follow_up is not None or bool(
            _optional_str(current_completion.get("follow_up_card_id"))
        ) or bool(dict(payload.get("host_action_followup_spawned") or {}))
        if not source_is_host_action and has_follow_up_context:
            continue
        source_payload = dict(source_card.payload or {}) if source_card is not None else {}
        source_follow_up = _resolved_host_action_phases(source_card).get("follow_up") if source_card is not None else None
        source_completion = dict(source_payload.get("host_action_completion") or {}) if source_card is not None else {}
        follow_up_gate = (
            _evaluate_host_action_followup_readiness(source_follow_up, source_completion)
            if source_card is not None and source_follow_up is not None
            else None
        )

        cancel_reason = (
            f"Cancelled legacy delayed host follow-up because `{required_state_key}` was never recorded upstream."
            if required_state_key
            else "Cancelled legacy delayed host follow-up because its prerequisite state was missing upstream."
        )
        cancel_payload = dict(payload)
        cancel_payload["execution"] = build_host_execution_payload(
            dict(cancel_payload.get("execution") or {}),
            state="cancelled",
            event="legacy_host_followup_cancelled",
            reason=cancel_reason,
        )
        cancel_payload["legacy_host_repair"] = {
            "action": "cancel_invalid_delayed_followup",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "required_state_key": required_state_key,
            "source_card_id": source_card_id,
            "reason": cancel_reason,
        }
        apply_card_update(current, status="cancelled", payload=cancel_payload)

        reopened_source: PMCard | None = None
        replacement_followup: PMCard | None = None

        if source_card is not None:
            source_payload = clear_source_followup_references(dict(source_payload), current.id)
            if should_reopen_source(source_card, required_state_key=required_state_key, follow_up_card_id=current.id):
                source_payload.pop("host_action_followup_pending", None)
                source_payload = persist_resolved_host_action_phases(source_card, source_payload)
                source_payload["execution"] = build_host_execution_payload(
                    dict(source_payload.get("execution") or {}),
                    state="host_step_only",
                    event="legacy_host_source_reopened",
                    reason="Reopened host step because a delayed follow-up had been spawned without any recorded external state.",
                )
                source_payload["legacy_host_repair"] = {
                    "action": "reopen_source_host_step",
                    "repaired_at": datetime.now(timezone.utc).isoformat(),
                    "repaired_by": requested_by,
                    "cancelled_followup_card_id": current.id,
                    "required_state_key": required_state_key,
                    "reason": "Reopened the source host step because it had been confirmed without context and no prerequisite external state was recorded.",
                }
                reopened_source = apply_card_update(source_card, status="todo", payload=source_payload)
            else:
                if isinstance(follow_up_gate, dict):
                    source_payload["host_action_followup_pending"] = follow_up_gate
                source_payload["legacy_host_repair"] = {
                    "action": "normalize_followup_pending",
                    "repaired_at": datetime.now(timezone.utc).isoformat(),
                    "repaired_by": requested_by,
                    "cancelled_followup_card_id": current.id,
                    "required_state_key": required_state_key,
                    "reason": "Removed a legacy delayed host follow-up and restored the pending gate on the source host step.",
                }
                source_card = apply_card_update(source_card, status=source_card.status, payload=source_payload)
                cards_by_id[source_card.id] = source_card
                if isinstance(follow_up_gate, dict) and bool(follow_up_gate.get("ready")) and source_follow_up is not None:
                    replacement_followup = _create_host_action_required_card(
                        source_card,
                        requested_by=requested_by,
                        host_action_required=source_follow_up,
                        due_at=follow_up_gate.get("due_at"),
                    )
                    replacement_payload = dict(source_card.payload or {})
                    completion = dict(replacement_payload.get("host_action_completion") or {})
                    completion["follow_up_card_id"] = replacement_followup.id
                    completion["follow_up_card_title"] = replacement_followup.title
                    replacement_payload["host_action_completion"] = completion
                    replacement_payload["host_action_followup_spawned"] = {
                        "card_id": replacement_followup.id,
                        "title": replacement_followup.title,
                        "created_at": _datetime_to_iso(replacement_followup.created_at),
                        "workspace_key": _workspace_key_from_card(replacement_followup),
                    }
                    replacement_payload.pop("host_action_followup_pending", None)
                    source_card = apply_card_update(source_card, status=source_card.status, payload=replacement_payload)

        repaired.append(
            {
                "card_id": current.id,
                "title": current.title,
                "action": "cancelled_invalid_delayed_followup",
                "workspace_key": _workspace_key_from_card(current),
                "source_card_id": source_card_id,
                "reopened_source_card_id": reopened_source.id if reopened_source is not None else None,
                "replacement_followup_card_id": replacement_followup.id if replacement_followup is not None else None,
            }
        )

    # Then, reopen malformed legacy source host cards that were closed without any usable external state.
    for card in list(cards_by_id.values()):
        if not _is_closed_pm_status(card.status) or not _is_host_action_required_card(card):
            continue
        payload = dict(card.payload or {})
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        if host_action_followup is None:
            continue
        completion = dict(payload.get("host_action_completion") or {})
        if _optional_str(completion.get("host_confirmation_mode")) != "confirmed_without_context":
            continue
        required_state_key = _host_action_required_state_key(host_action_followup)
        external_state = dict(completion.get("external_state") or {})
        if required_state_key and _optional_str(external_state.get(required_state_key)):
            continue
        spawned = dict(payload.get("host_action_followup_spawned") or {})
        follow_up_card_id = _optional_str(completion.get("follow_up_card_id")) or _optional_str(spawned.get("card_id"))
        follow_up_card = cards_by_id.get(follow_up_card_id) if follow_up_card_id else None
        if follow_up_card is not None and not _is_closed_pm_status(follow_up_card.status):
            continue
        reopened_payload = clear_source_followup_references(dict(payload), follow_up_card_id or "")
        reopened_payload.pop("host_action_followup_pending", None)
        reopened_payload = persist_resolved_host_action_phases(card, reopened_payload)
        reopened_payload["execution"] = build_host_execution_payload(
            dict(reopened_payload.get("execution") or {}),
            state="host_step_only",
            event="legacy_host_source_reopened",
            reason="Reopened host step because the legacy closure did not record the external state needed for follow-through.",
        )
        reopened_payload["legacy_host_repair"] = {
            "action": "reopen_source_host_step",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "cancelled_followup_card_id": follow_up_card_id,
            "required_state_key": required_state_key,
            "reason": "Reopened the source host step because it had been confirmed without context and no prerequisite external state was recorded.",
        }
        apply_card_update(card, status="todo", payload=reopened_payload)
        repaired.append(
            {
                "card_id": card.id,
                "title": card.title,
                "action": "reopened_legacy_source_host_step",
                "workspace_key": _workspace_key_from_card(card),
                "followup_card_id": follow_up_card_id,
            }
        )

    # Normalize already-open legacy source host cards so they render as the real current host step.
    for card in list(cards_by_id.values()):
        if _is_closed_pm_status(card.status) or not _is_host_action_required_card(card):
            continue
        payload = dict(card.payload or {})
        host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
        if host_action_required is None:
            continue
        source_card_id = _optional_str(host_action_required.get("source_card_id"))
        source_card = cards_by_id.get(source_card_id) if source_card_id else None
        if source_card is not None and _is_host_action_required_card(source_card):
            continue
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        activation = _host_action_activation_status(card)
        if host_action_followup is None or not isinstance(activation, dict) or str(activation.get("state") or "").strip() != "waiting_on_prerequisite":
            continue
        normalized_payload = persist_resolved_host_action_phases(card, dict(payload))
        normalized_payload.pop("host_action_followup_pending", None)
        normalized_payload["legacy_host_repair"] = {
            "action": "normalize_open_source_host_step",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "required_state_key": activation.get("required_state_key"),
            "reason": "Normalized an already-open legacy host step so the current host action no longer inherits the delayed follow-up state.",
        }
        apply_card_update(card, status=card.status, payload=normalized_payload)
        repaired.append(
            {
                "card_id": card.id,
                "title": card.title,
                "action": "normalized_open_source_host_step",
                "workspace_key": _workspace_key_from_card(card),
            }
        )

    # Then, activate any delayed follow-up that is now ready from explicit external state.
    for card in list(cards_by_id.values()):
        if not _is_closed_pm_status(card.status) or not _is_host_action_required_card(card):
            continue
        payload = dict(card.payload or {})
        pending_gate = dict(payload.get("host_action_followup_pending") or {})
        if not pending_gate:
            continue
        host_action_followup = _resolved_host_action_phases(card).get("follow_up")
        if host_action_followup is None:
            continue
        completion = dict(payload.get("host_action_completion") or {})
        follow_up_gate = _evaluate_host_action_followup_readiness(host_action_followup, completion)
        activate_after = _pending_followup_gate_datetime(
            follow_up_gate.get("activate_after") or pending_gate.get("activate_after")
        )
        ready_from_scheduled_anchor = activate_after is not None and activate_after <= datetime.now(timezone.utc)
        if not bool(follow_up_gate.get("ready")) and not ready_from_scheduled_anchor:
            continue
        successor_due_at = None
        if bool(follow_up_gate.get("ready")):
            raw_due_at = follow_up_gate.get("due_at")
            successor_due_at = raw_due_at if isinstance(raw_due_at, datetime) else _pending_followup_gate_datetime(raw_due_at)
        else:
            successor_due_at = _pending_followup_gate_datetime(
                follow_up_gate.get("due_at") or pending_gate.get("due_at")
            )
        successor_card = _create_host_action_required_card(
            card,
            requested_by=requested_by,
            host_action_required=host_action_followup,
            due_at=successor_due_at,
        )
        updated_payload = dict(payload)
        completion["follow_up_card_id"] = successor_card.id
        completion["follow_up_card_title"] = successor_card.title
        updated_payload["host_action_completion"] = completion
        updated_payload["host_action_followup_spawned"] = {
            "card_id": successor_card.id,
            "title": successor_card.title,
            "created_at": _datetime_to_iso(successor_card.created_at),
            "workspace_key": _workspace_key_from_card(successor_card),
        }
        updated_payload.pop("host_action_followup_pending", None)
        updated_payload["legacy_host_repair"] = {
            "action": "activate_scheduled_pending_host_followup" if ready_from_scheduled_anchor and not bool(follow_up_gate.get("ready")) else "activate_ready_delayed_followup",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "repaired_by": requested_by,
            "spawned_followup_card_id": successor_card.id,
            "required_state_key": follow_up_gate.get("required_state_key"),
            "reason": (
                "Activated a delayed host follow-up because the prerequisite external state is now recorded."
                if bool(follow_up_gate.get("ready"))
                else "Activated a delayed host follow-up because the scheduled publish window has opened and the host still needs to confirm the external result."
            ),
        }
        apply_card_update(card, status=card.status, payload=updated_payload)
        cards_by_id[successor_card.id] = successor_card
        repaired.append(
            {
                "card_id": card.id,
                "title": card.title,
                "action": "activated_scheduled_pending_host_followup" if ready_from_scheduled_anchor and not bool(follow_up_gate.get("ready")) else "activated_ready_delayed_followup",
                "workspace_key": _workspace_key_from_card(card),
                "spawned_followup_card_id": successor_card.id,
            }
        )

    return repaired


def _build_missing_execution_contract_payload(card: PMCard) -> dict[str, Any] | None:
    if _is_closed_pm_status(card.status):
        return None

    payload = dict(card.payload or {})
    contract_source = _execution_contract_source(card)
    if contract_source is None:
        return None

    current_contract = payload.get("completion_contract")
    current_execution = _execution_payload(card)
    needs_contract = not isinstance(current_contract, dict) or not current_contract
    needs_execution = not isinstance(current_execution, dict) or not current_execution

    if not needs_contract and not needs_execution:
        return None

    workspace_key = _workspace_key_from_card(card)
    existing_reason = _payload_value(payload, "reason") or _optional_str((current_execution or {}).get("reason"))
    normalized_reason = existing_reason or f"Autonomous PM execution for `{card.title}` in `{workspace_key}`."
    contract = build_execution_contract(
        title=card.title,
        workspace_key=workspace_key,
        source=contract_source,
        reason=normalized_reason,
        instructions=payload.get("instructions"),
        acceptance_criteria=payload.get("acceptance_criteria"),
        artifacts_expected=payload.get("artifacts_expected"),
    )

    updated_payload = dict(payload)
    if needs_contract:
        updated_payload["instructions"] = contract["instructions"]
        updated_payload["acceptance_criteria"] = contract["acceptance_criteria"]
        updated_payload["artifacts_expected"] = contract["artifacts_expected"]
        updated_payload["completion_contract"] = contract["completion_contract"]

    if needs_execution:
        defaults = execution_defaults_for_workspace(workspace_key)
        now_iso = datetime.now(timezone.utc).isoformat()
        normalized_status = str(card.status or "").strip().lower()
        prospective_gate = evaluate_execution_gate(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=workspace_key,
            payload=updated_payload,
        )
        if normalized_status in {"review", "blocked", "failed"}:
            state = normalized_status
        elif normalized_status in {"running", "in_progress"}:
            state = "running"
        elif not execution_gate_allows_run(prospective_gate):
            state = "approval_required"
        else:
            state = "queued"
        updated_payload["execution"] = {
            "lane": "codex",
            "state": state,
            "manager_agent": defaults["manager_agent"],
            "target_agent": defaults["target_agent"],
            "workspace_agent": defaults.get("workspace_agent"),
            "execution_mode": defaults["execution_mode"],
            "requested_by": _payload_value(payload, "requested_by")
            or _payload_value(payload, "source_agent")
            or card.owner
            or defaults["manager_agent"],
            "assigned_runner": "jean-claude" if str(defaults["execution_mode"]) == "direct" else "codex",
            "reason": normalized_reason,
            "last_transition_at": now_iso,
            "source": contract_source,
        }
        if state == "queued":
            updated_payload["execution"]["queued_at"] = now_iso

    return updated_payload


def _dedupe_active_pm_review_resolution_cards(cards: list[PMCard]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[PMCard]] = {}
    for card in cards:
        if _is_closed_pm_status(card.status):
            continue
        if str(card.source or "").strip() != "pm_review_resolution":
            continue
        workspace_key = _workspace_key_from_card(card)
        group_key = (workspace_key, str(card.source or "").strip(), str(card.title or "").strip().lower())
        groups.setdefault(group_key, []).append(card)

    deduped: list[dict[str, Any]] = []
    for siblings in groups.values():
        if len(siblings) <= 1:
            continue
        ranked = sorted(siblings, key=_pm_resolution_dedupe_rank, reverse=True)
        keep = ranked[0]
        for duplicate in ranked[1:]:
            payload = dict(duplicate.payload or {})
            payload["duplicate_resolution"] = {
                "kept_card_id": keep.id,
                "kept_card_title": keep.title,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Closed duplicate pm_review_resolution lane because an equivalent active successor card already exists.",
            }
            effective = _persist_status_payload_update(
                duplicate,
                operation="duplicate PM review-resolution closure",
                status="done",
                payload=payload,
            )
            deduped.append(
                {
                    "card_id": effective.id,
                    "title": effective.title,
                    "workspace_key": _workspace_key_from_card(effective),
                    "kept_card_id": keep.id,
                    "kept_card_title": keep.title,
                }
            )
    return deduped


def _pm_resolution_dedupe_rank(card: PMCard) -> tuple[int, int, datetime]:
    execution = _execution_payload(card) or {}
    execution_state = str(execution.get("state") or "").strip().lower()
    status = str(card.status or "").strip().lower()
    status_rank = {
        "in_progress": 4,
        "running": 4,
        "queued": 3,
        "todo": 2,
        "review": 1,
    }.get(status, 0)
    execution_rank = _execution_sort_rank(execution_state)
    updated_at = card.updated_at or card.created_at or datetime.min.replace(tzinfo=timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (status_rank, execution_rank, updated_at)


def _execution_contract_source(card: PMCard) -> str | None:
    payload = dict(card.payload or {})
    source = str(card.source or "").strip()
    if _is_owner_decision_gate(card):
        return None
    if source == "pm_host_action_required" or _is_host_action_required_card(card):
        return None
    if source == "pm_review_resolution":
        return "pm_review_resolution"
    if source.startswith("brain-triage:"):
        return "brain_triage"
    if source.startswith("accountability_sweep"):
        return "accountability_sweep"
    if source in {"codex_native:workspace-owner-review", "openclaw:workspace-owner-review"}:
        return "owner_review_followup"
    trigger_origin = str(payload.get("trigger_origin") or "").strip()
    if source == "codex_native:remote_queue" or trigger_origin == "codex_native_remote_queue":
        return "codex_native_remote_queue"
    if source == "openclaw:thin-trigger" or trigger_origin == "openclaw_thin_trigger":
        return "legacy_remote_queue"
    if card.link_type == "standup" or source.startswith("standup-prep:") or payload.get("created_from_standup_id"):
        return "standup_promotion"
    return None


def _payload_contract_source(payload: dict[str, Any]) -> str | None:
    contract = payload.get("completion_contract")
    if not isinstance(contract, dict):
        return None
    return _optional_str(contract.get("source"))


def _default_execution_state_for_card(card: PMCard) -> str:
    normalized_status = str(card.status or "").strip().lower()
    if normalized_status in {"review", "blocked", "failed"}:
        return normalized_status
    if normalized_status in {"running", "in_progress"}:
        return "running"
    gate = _execution_gate_for_card(card)
    if not _execution_gate_authorizes_card(card, gate=gate):
        return "approval_required"
    if normalized_status == "queued":
        return "queued"
    payload = dict(card.payload or {})
    contract = payload.get("completion_contract")
    autostart = isinstance(contract, dict) and bool(contract.get("autostart"))
    if autostart or _execution_contract_source(card) is not None:
        return "queued"
    return "ready"


def _is_host_action_required_card(card: PMCard) -> bool:
    payload = dict(card.payload or {})
    host_action_required = payload.get("host_action_required")
    return isinstance(host_action_required, dict) and bool(host_action_required)


def _infer_host_action_automation(card: PMCard) -> dict[str, Any] | None:
    if not _is_host_action_required_card(card):
        return None

    payload = dict(card.payload or {})
    existing = payload.get("host_action_automation")
    existing_payload = dict(existing) if isinstance(existing, dict) else {}
    existing_id = _optional_str(existing_payload.get("automation_id"))
    closed_host_automation_ids = {
        HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_WRITEBACK,
        HOST_ACTION_AUTOMATION_STANDUP_PREP_WRITEBACK,
        HOST_ACTION_AUTOMATION_EXECUTION_RESULT_WRITEBACK_PROOF,
    }
    if _is_closed_pm_status(card.status) and existing_id not in closed_host_automation_ids:
        return None

    host_action_required = _normalize_host_action_payload(payload.get("host_action_required"))
    if host_action_required is None:
        return existing_payload if existing_id in closed_host_automation_ids else None

    text = _host_action_text_blob(host_action_required)
    source_card_id = (
        _optional_str(host_action_required.get("source_card_id"))
        or _optional_str(existing_payload.get("source_card_id"))
        or _extract_pm_card_id_from_text(text)
    )
    normalized_text = text.lower()
    is_watchdog_writeback = (
        any(marker in normalized_text for marker in HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_MARKERS)
        and any(pattern.search(text) for pattern in HOST_ACTION_AUTOMATION_WRITEBACK_PATTERNS)
        and bool(source_card_id)
    )
    if existing_id == HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_WRITEBACK and source_card_id:
        is_watchdog_writeback = True
    if is_watchdog_writeback:
        requires_host_confirmation = _optional_bool(existing_payload.get("requires_host_confirmation"), False)
        return {
            **existing_payload,
            "automation_id": HOST_ACTION_AUTOMATION_FALLBACK_WATCHDOG_WRITEBACK,
            "label": "Run fallback watchdog refresh and PM write-back",
            "state": _optional_str(existing_payload.get("state")) or "ready",
            "autonomous": _optional_bool(existing_payload.get("autonomous"), not requires_host_confirmation),
            "autostart": _optional_bool(existing_payload.get("autostart"), not requires_host_confirmation),
            "requires_host_confirmation": requires_host_confirmation,
            "safety_class": _optional_str(existing_payload.get("safety_class")) or "local_durable_writeback",
            "source_card_id": source_card_id,
            "report_path": _optional_str(existing_payload.get("report_path"))
            or "memory/reports/fallback_watchdog_latest.json",
            "runner_id": "codex_workspace_execution",
        }

    mentions_standup_prep_writeback = (
        bool(source_card_id)
        and "decision_loop" in normalized_text
        and any(marker in normalized_text for marker in HOST_ACTION_AUTOMATION_STANDUP_PREP_MARKERS)
    )
    if existing_id == HOST_ACTION_AUTOMATION_STANDUP_PREP_WRITEBACK and source_card_id:
        mentions_standup_prep_writeback = True
    if mentions_standup_prep_writeback:
        prep_path_match = re.search(r"memory/standup-prep/([a-z0-9_-]+)", text, flags=re.IGNORECASE)
        standup_kind = _optional_str(existing_payload.get("standup_kind")) or (
            prep_path_match.group(1) if prep_path_match else "executive_ops"
        )
        workspace_key = _optional_str(existing_payload.get("standup_workspace_key")) or "shared_ops"
        return {
            **existing_payload,
            "automation_id": HOST_ACTION_AUTOMATION_STANDUP_PREP_WRITEBACK,
            "label": "Generate standup prep proof and close host action",
            "state": _optional_str(existing_payload.get("state")) or "ready",
            "autonomous": _optional_bool(existing_payload.get("autonomous"), True),
            "autostart": _optional_bool(existing_payload.get("autostart"), True),
            "requires_host_confirmation": _optional_bool(existing_payload.get("requires_host_confirmation"), False),
            "safety_class": _optional_str(existing_payload.get("safety_class")) or "local_durable_writeback",
            "source_card_id": source_card_id,
            "runner_id": "codex_workspace_execution",
            "standup_workspace_key": workspace_key,
            "standup_kind": standup_kind,
            "required_routing_targets": list(HOST_ACTION_STANDUP_DECISION_LOOP_TARGETS),
        }

    queue_id = _optional_str(existing_payload.get("queue_id")) or _extract_feezie_queue_id(text)
    mentions_linkedin_scheduler = (
        bool(queue_id)
        and HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULER_PATTERNS[0].search(text) is not None
        and any(pattern.search(text) for pattern in HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULER_PATTERNS[1:])
    )
    if existing_id == HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULED_WRITEBACK and queue_id:
        mentions_linkedin_scheduler = True
    if mentions_linkedin_scheduler and queue_id:
        return {
            **existing_payload,
            "automation_id": HOST_ACTION_AUTOMATION_LINKEDIN_SCHEDULED_WRITEBACK,
            "label": "Record scheduled LinkedIn banked post",
            "state": _optional_str(existing_payload.get("state")) or "ready",
            "autonomous": False,
            "autostart": False,
            "requires_host_confirmation": True,
            "safety_class": _optional_str(existing_payload.get("safety_class")) or "host_confirmed_external_schedule_writeback",
            "queue_id": queue_id,
            "source_card_id": source_card_id,
            "runner_id": "codex_workspace_execution",
            "asset_decision": _optional_str(existing_payload.get("asset_decision")) or "text-only",
        }

    mentions_execution_result_writeback = (
        bool(source_card_id)
        and any(pattern.search(text) for pattern in HOST_ACTION_AUTOMATION_WRITEBACK_PATTERNS)
    )
    if existing_id == HOST_ACTION_AUTOMATION_EXECUTION_RESULT_WRITEBACK_PROOF and source_card_id:
        mentions_execution_result_writeback = True
    if mentions_execution_result_writeback:
        return {
            **existing_payload,
            "automation_id": HOST_ACTION_AUTOMATION_EXECUTION_RESULT_WRITEBACK_PROOF,
            "label": "Verify execution-result writer proof and close host action",
            "state": _optional_str(existing_payload.get("state")) or "ready",
            "autonomous": _optional_bool(existing_payload.get("autonomous"), True),
            "autostart": _optional_bool(existing_payload.get("autostart"), True),
            "requires_host_confirmation": _optional_bool(existing_payload.get("requires_host_confirmation"), False),
            "safety_class": _optional_str(existing_payload.get("safety_class")) or "local_durable_writeback",
            "source_card_id": source_card_id,
            "runner_id": "codex_workspace_execution",
        }

    return None


def _extract_pm_card_id_from_text(text: str) -> str | None:
    match = PM_CARD_UUID_PATTERN.search(text)
    return match.group(0) if match else None


def _extract_feezie_queue_id(text: str) -> str | None:
    match = FEEZIE_QUEUE_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None


def _resolve_host_action_source_card(host_action: dict[str, Any] | None) -> PMCard | None:
    source_card_id = _optional_str((host_action or {}).get("source_card_id"))
    if not source_card_id:
        return None
    try:
        return get_card(source_card_id)
    except RuntimeError:
        return None


def _source_card_artifact_paths(source_card: PMCard | None) -> list[str]:
    if source_card is None:
        return []
    payload = dict(source_card.payload or {})
    latest_result = payload.get("latest_execution_result")
    if not isinstance(latest_result, dict):
        return []
    return _dedupe_nonempty_strings(latest_result.get("artifacts"))


def _host_action_workspace_key(host_action: dict[str, Any] | None, source_card: PMCard | None) -> str:
    workspace_key = _optional_str((host_action or {}).get("workspace_key"))
    if workspace_key:
        return workspace_key
    if source_card is not None:
        return _workspace_key_from_card(source_card)
    return "shared_ops"


def _host_action_queue_id(host_action: dict[str, Any] | None, source_card: PMCard | None) -> str | None:
    text = _host_action_text_blob(host_action)
    queue_id = _extract_feezie_queue_id(text)
    if queue_id:
        return queue_id
    if source_card is not None:
        return _extract_feezie_queue_id(source_card.title)
    return None


def _host_action_expected_capture_paths(
    host_action: dict[str, Any] | None,
    *,
    source_card: PMCard | None = None,
) -> dict[str, str]:
    queue_id = _host_action_queue_id(host_action, source_card)
    scheduled_at_iso = _extract_host_action_datetime(
        _host_action_text_items(host_action)
        + (
            [_optional_str(dict((source_card.payload or {}).get("latest_execution_result") or {}).get("summary"))]
            if source_card is not None
            else []
        )
    )
    scheduled_at = _parse_host_action_datetime(scheduled_at_iso)
    if not queue_id or scheduled_at is None:
        return {}
    workspace_key = _host_action_workspace_key(host_action, source_card)
    workspace_root = workspace_root_slug(workspace_key)
    eastern_date = scheduled_at.astimezone(NEW_YORK_TZ).date().isoformat()
    analytics_root = f"workspaces/{workspace_root}/analytics/{eastern_date}_{queue_id.lower()}"
    return {
        "confirmation_path": f"{analytics_root}/confirmation.png",
        "receipt_path": f"{analytics_root}/scheduled_receipt.json",
        "analytics_log_path": f"{analytics_root}/log_template.md",
    }


def _matching_host_action_artifact_path(requirement: str, kind: str | None, artifact_paths: list[str]) -> str | None:
    if not artifact_paths:
        return None
    normalized_requirement = requirement.lower()
    preference_groups: list[tuple[str, ...]] = []
    if "publishing schedule" in normalized_requirement or "schedule path" in normalized_requirement:
        preference_groups.append(("publishing_schedule",))
    if "release packet" in normalized_requirement:
        preference_groups.append(("release_packet", "release_packets"))
    if "analytics" in normalized_requirement or "metric" in normalized_requirement:
        preference_groups.append(("/analytics/", "log_template", "analytics_log"))
    if "queue" in normalized_requirement:
        preference_groups.append(("/queue", "_queue", "queue_"))
    if "receipt" in normalized_requirement or "confirmation" in normalized_requirement or kind == "screenshot_path":
        preference_groups.append(("receipt", "confirmation", ".png", ".jpg", ".jpeg", ".webp"))

    lowered_paths = [(path, path.lower()) for path in artifact_paths]
    for markers in preference_groups:
        match = next((path for path, lowered in lowered_paths if any(marker in lowered for marker in markers)), None)
        if match:
            return match
    if len(artifact_paths) == 1 and kind in {"artifact_path", "metric_reference", "screenshot_path"}:
        return artifact_paths[0]
    return None


def _enrich_host_action_proof_fields(
    proof_fields: list[dict[str, Any]],
    host_action: dict[str, Any] | None,
    *,
    source_card: PMCard | None = None,
) -> list[dict[str, Any]]:
    latest_result_summary = None
    if source_card is not None:
        latest_result = dict(source_card.payload or {}).get("latest_execution_result")
        if isinstance(latest_result, dict):
            latest_result_summary = _optional_str(latest_result.get("summary"))
    timestamp_suggestion = _extract_host_action_datetime(
        _host_action_text_items(host_action) + ([latest_result_summary] if latest_result_summary else [])
    )
    artifact_paths = _source_card_artifact_paths(source_card)
    expected_capture_paths = _host_action_expected_capture_paths(host_action, source_card=source_card)
    enriched: list[dict[str, Any]] = []
    for field in proof_fields:
        enriched_field = dict(field)
        requirement = _optional_str(field.get("requirement")) or ""
        kind = _optional_str(field.get("kind"))
        if kind == "scheduled_timestamp" and timestamp_suggestion:
            enriched_field["suggested_value"] = timestamp_suggestion
            enriched_field["suggestion_reason"] = (
                "Prefilled from the source scheduling plan. Adjust it if the actual host receipt differs."
            )
        elif kind in {"artifact_path", "metric_reference", "screenshot_path"}:
            matched_path = _matching_host_action_artifact_path(requirement, kind, artifact_paths)
            if matched_path:
                enriched_field["suggested_value"] = matched_path
                enriched_field["suggestion_reason"] = "Prefilled from the latest source execution artifacts."
            elif kind == "screenshot_path" and expected_capture_paths.get("confirmation_path"):
                enriched_field["suggested_value"] = expected_capture_paths["confirmation_path"]
                enriched_field["suggestion_reason"] = (
                    "Default runner pickup path. Save the confirmation screenshot here and the host automation can detect it automatically."
                )
            elif kind == "metric_reference" and expected_capture_paths.get("analytics_log_path"):
                enriched_field["suggested_value"] = expected_capture_paths["analytics_log_path"]
                enriched_field["suggestion_reason"] = "Default analytics log path for this scheduled slot."
        enriched.append(enriched_field)
    return enriched


def _create_host_action_required_card(
    source_card: PMCard,
    *,
    requested_by: str,
    host_action_required: dict[str, Any],
    due_at: datetime | None = None,
) -> PMCard:
    workspace_key = _workspace_key_from_card(source_card)
    phases = _split_host_action_timeline(host_action_required)
    current_phase = phases.get("current") or {}
    follow_up_phase = phases.get("follow_up")
    steps = _dedupe_nonempty_strings(current_phase.get("steps"))
    summary = _optional_str(current_phase.get("summary")) or (steps[0] if steps else f"Complete host action for {source_card.title}")
    proof_required = _dedupe_nonempty_strings(current_phase.get("proof_required"))
    proof_fields = _enrich_host_action_proof_fields(_build_host_action_proof_fields(proof_required), current_phase, source_card=source_card)
    title = _truncate_pm_card_title(f"Host action required - {summary}")
    reason = (
        "Codex completed the internal PM lane, but the last external step still needs to happen outside the runtime. "
        + summary
    )
    payload: dict[str, Any] = {
        "workspace_key": workspace_key,
        "reason": reason,
        "source_agent": requested_by,
        "front_door_agent": requested_by,
        "host_action_required": {
            "summary": summary,
            "steps": steps,
            "proof_required": proof_required,
            "proof_fields": proof_fields,
            "workspace_key": workspace_key,
            "source_card_id": source_card.id,
            "source_card_title": source_card.title,
            "source_result_id": _optional_str(current_phase.get("source_result_id")),
            "source_result_summary": _optional_str(current_phase.get("source_result_summary")),
            "detected_from": _optional_str(current_phase.get("detected_from")),
            "source_artifact_paths": _source_card_artifact_paths(source_card),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        # These fields make the trigger key stable without turning the card into an execution candidate.
        "instructions": steps,
        "acceptance_criteria": proof_required,
    }
    if (source_card.payload or {}).get("legacy_owner_review_compatibility") is True:
        payload["legacy_owner_review_compatibility"] = True
    if follow_up_phase is not None:
        payload["host_action_followup"] = {
            **follow_up_phase,
            "workspace_key": workspace_key,
            "proof_fields": _enrich_host_action_proof_fields(
                _build_host_action_proof_fields(_dedupe_nonempty_strings(follow_up_phase.get("proof_required"))),
                follow_up_phase,
                source_card=source_card,
            ),
        }
    automation_probe = PMCard(
        id=source_card.id,
        title=title,
        owner="Neo",
        status="todo",
        source="pm_host_action_required",
        link_type=source_card.link_type,
        link_id=source_card.link_id,
        due_at=due_at,
        payload=payload,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    automation = _infer_host_action_automation(automation_probe)
    if automation is not None:
        payload["host_action_automation"] = automation
    payload["trigger_key"] = _build_trigger_key(
        title=title,
        workspace_key=workspace_key,
        source="pm_host_action_required",
        payload=payload,
    )
    existing = find_active_card_by_trigger_key(str(payload["trigger_key"]))
    if existing is not None:
        return existing

    return create_card(
        PMCardCreate(
            title=title,
            owner="Neo",
            status="todo",
            source="pm_host_action_required",
            link_type=source_card.link_type,
            link_id=source_card.link_id,
            due_at=due_at,
            payload=payload,
        )
    )


def _build_host_action_proof_fields(proof_required: list[str]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for requirement in proof_required:
        normalized = requirement.lower()
        if "screenshot" in normalized:
            fields.append(
                {
                    "kind": "screenshot_path",
                    "label": "Screenshot path",
                    "placeholder": "Enter the screenshot path or link.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "timestamp" in normalized or "scheduled" in normalized:
            fields.append(
                {
                    "kind": "scheduled_timestamp",
                    "label": "Scheduled timestamp",
                    "placeholder": "Enter the exact scheduled timestamp or confirmation detail.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "url" in normalized:
            fields.append(
                {
                    "kind": "publish_url",
                    "label": "Publish URL",
                    "placeholder": "Enter the publish URL or confirmation link.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "path" in normalized or "artifact" in normalized:
            fields.append(
                {
                    "kind": "artifact_path",
                    "label": "Artifact update path",
                    "placeholder": "Enter the updated file path or artifact reference.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        elif "metric" in normalized or "analytics" in normalized:
            fields.append(
                {
                    "kind": "metric_reference",
                    "label": "Metric log reference",
                    "placeholder": "Enter where the metric or analytics proof was recorded.",
                    "multiline": False,
                    "requirement": requirement,
                }
            )
        else:
            fields.append(
                {
                    "kind": "proof_note",
                    "label": "Proof note",
                    "placeholder": "Enter the proof that satisfies this requirement.",
                    "multiline": True,
                    "requirement": requirement,
                }
            )
    return fields


def _build_host_action_completion_payload(
    card: PMCard,
    *,
    requested_by: str,
    completion_note: str | None,
    proof_items: list[str] | None,
    proof_field_values: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = dict(card.payload or {})
    phases = _resolved_host_action_phases(card)
    host_action_required = dict(phases.get("current") or payload.get("host_action_required") or {})
    follow_up_host_action = dict(phases.get("follow_up") or payload.get("host_action_followup") or {})
    required = _dedupe_nonempty_strings(host_action_required.get("proof_required"))
    normalized_proof_field_values = _normalize_host_action_proof_field_values(proof_field_values)
    provided = _dedupe_nonempty_strings([*(proof_items or []), *_host_action_proof_items_from_values(normalized_proof_field_values)])
    note = _optional_str(completion_note)
    external_state = _extract_host_action_external_state(
        host_action_required,
        completion_note=note,
        proof_items=provided,
        proof_field_values=normalized_proof_field_values,
    )
    follow_up_gate = _evaluate_host_action_followup_readiness(follow_up_host_action, {"external_state": external_state})

    return {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_by": requested_by,
        "completion_note": note,
        "proof_items": provided,
        "proof_field_values": normalized_proof_field_values,
        "proof_required": required,
        "external_state": external_state,
        "source_card_id": _optional_str(host_action_required.get("source_card_id")),
        "source_card_title": _optional_str(host_action_required.get("source_card_title")),
        "follow_up_summary": _optional_str(follow_up_host_action.get("summary")),
        "follow_up_proof_required": _dedupe_nonempty_strings(follow_up_host_action.get("proof_required")),
        "follow_up_gate": follow_up_gate,
        "host_confirmation_mode": "confirmed_with_context" if note or provided or normalized_proof_field_values else "confirmed_without_context",
    }


def _normalize_host_action_proof_field_values(values: list[Any] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in list(values or []):
        candidate = raw.model_dump() if hasattr(raw, "model_dump") else raw
        if not isinstance(candidate, dict):
            continue
        value = _optional_str(candidate.get("value"))
        if not value:
            continue
        kind = _optional_str(candidate.get("kind")) or ""
        label = _optional_str(candidate.get("label")) or ""
        requirement = _optional_str(candidate.get("requirement")) or ""
        dedupe_key = (kind, label, requirement, value)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        entry: dict[str, str] = {"value": value}
        if kind:
            entry["kind"] = kind
        if label:
            entry["label"] = label
        if requirement:
            entry["requirement"] = requirement
        normalized.append(entry)
    return normalized


def _humanize_host_action_proof_kind(kind: str | None) -> str:
    value = _optional_str(kind)
    if not value:
        return "Proof"
    return value.replace("_", " ")


def _host_action_proof_items_from_values(values: list[dict[str, str]] | None) -> list[str]:
    items: list[str] = []
    for entry in _normalize_host_action_proof_field_values(values):
        value = _optional_str(entry.get("value"))
        if not value:
            continue
        label = _optional_str(entry.get("label")) or _humanize_host_action_proof_kind(entry.get("kind"))
        items.append(f"{label}: {value}" if label else value)
    return _dedupe_nonempty_strings(items)


def _host_action_field_value(values: list[dict[str, str]] | None, kind: str) -> str | None:
    for entry in _normalize_host_action_proof_field_values(values):
        if _optional_str(entry.get("kind")) == kind:
            return _optional_str(entry.get("value"))
    return None


def _host_action_timestamp_from_values(values: list[dict[str, str]] | None) -> str | None:
    return _extract_host_action_datetime(
        [
            entry["value"]
            for entry in _normalize_host_action_proof_field_values(values)
            if _optional_str(entry.get("kind")) == "scheduled_timestamp" and _optional_str(entry.get("value"))
        ]
    )


def _execution_sort_rank(state: str) -> int:
    normalized = state.lower()
    if normalized == "running":
        return 4
    if normalized == "queued":
        return 3
    if normalized == "review":
        return 2
    if normalized == "ready":
        return 1
    if normalized in {"failed", "blocked"}:
        return 0
    return 0


def _payload_value(payload: dict, key: str) -> Optional[str]:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _optional_str(value: object) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "yes", "y", "on"}:
            return True
        if cleaned in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _normalize_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _dedupe_nonempty_strings(values: object) -> list[str]:
    if isinstance(values, list):
        source = values
    else:
        source = []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in source:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _truncate_pm_card_title(value: str, limit: int = 108) -> str:
    cleaned = str(value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _valid_resolution_mode(value: object) -> str | None:
    normalized = str(value or "").strip()
    if normalized in {"close_only", "close_and_spawn_next"}:
        return normalized
    return None


def _is_repeated_review_followup(card: PMCard, suggestion: dict[str, str] | None) -> bool:
    if not isinstance(suggestion, dict):
        return False
    suggested_title = _optional_str(suggestion.get("title"))
    current_title = str(card.title or "").strip()
    return bool(suggested_title and current_title and suggested_title.lower() == current_title.lower())


def _suggest_review_followup(card: PMCard, workspace_policy: dict[str, object]) -> dict[str, str] | None:
    payload = dict(card.payload or {})
    execution = dict(_execution_payload(card) or {})
    latest_result = payload.get("latest_execution_result")
    latest_summary = ""
    if isinstance(latest_result, dict):
        latest_summary = str(latest_result.get("summary") or "").strip()
    haystack = " ".join(
        item
        for item in [
            card.title,
            str(payload.get("reason") or "").strip(),
            str(execution.get("reason") or "").strip(),
            latest_summary,
        ]
        if item
    ).lower()

    templates = workspace_policy.get("followup_templates")
    if isinstance(templates, list):
        for template in templates:
            if not isinstance(template, dict):
                continue
            keywords = [str(item).strip().lower() for item in (template.get("match_any") or []) if str(item).strip()]
            if keywords and any(keyword in haystack for keyword in keywords):
                title = _optional_str(template.get("title"))
                if title:
                    return {
                        "title": title,
                        "reason": _optional_str(template.get("reason")) or f"Follow-on work continues after accepting '{card.title}'.",
                    }

    fallback_title = _optional_str(workspace_policy.get("default_next_title"))
    if fallback_title:
        return {
            "title": fallback_title,
            "reason": _optional_str(workspace_policy.get("default_next_reason")) or f"Follow-on work continues after accepting '{card.title}'.",
        }
    return None


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _fallback_execution_entry(card: PMCard) -> ExecutionQueueEntry:
    defaults = execution_defaults_for_workspace(_workspace_key_from_card(card))
    execution_gate = _execution_gate_for_card(card)
    return ExecutionQueueEntry(
        card_id=card.id,
        title=card.title,
        workspace_key=_workspace_key_from_card(card),
        pm_status=card.status or "todo",
        execution_state="queued",
        manager_agent=str(defaults["manager_agent"]),
        target_agent=str(defaults["target_agent"]),
        workspace_agent=_optional_str(defaults.get("workspace_agent")),
        execution_mode=str(defaults["execution_mode"]),
        requested_by=card.owner or "Jean-Claude",
        assigned_runner="codex",
        lane="codex",
        reason="Queued from PM board for Codex execution.",
        source=card.source,
        link_type=card.link_type,
        front_door_agent=_payload_value(card.payload or {}, "front_door_agent"),
        trigger_key=_payload_value(card.payload or {}, "trigger_key"),
        execution_gate_decision=str(execution_gate.get("decision") or REQUIRE_APPROVAL),
        execution_gate_reason=_optional_str(execution_gate.get("reason")),
        execution_gate_risk_class=str(execution_gate.get("risk_class") or "unknown"),
        execution_gate_risk_factors=[str(item) for item in execution_gate.get("risk_factors") or []],
        execution_gate_approval_state=str(execution_gate.get("approval_state") or "missing"),
        execution_gate_intent_hash=_optional_str(execution_gate.get("intent_hash")),
        execution_gate_authorization_current=bool(execution_gate.get("authorization_current")),
        queued_at=card.updated_at,
        last_transition_at=card.updated_at,
    )


def _normalize_card_create_payload(payload: PMCardCreate) -> PMCardCreate:
    card_payload = dict(payload.payload or {})
    if "owner_decision_resolution" in card_payload:
        raise ValueError(
            "Generic PM card creation cannot write canonical owner-decision authority; "
            "use the locked canonical decision reconciler."
        )
    if "execution_approval" in card_payload:
        raise ValueError(
            "Generic PM card creation cannot write execution-approval authority; "
            "use a governed PM approval action."
        )
    # No existing governed scheduler writer owns this field. Generic PM create
    # payloads cannot mint authority merely by supplying a receipt-shaped map.
    card_payload.pop("scheduler_receipt", None)
    execution = dict(card_payload.get("execution") or {})
    source = str(payload.source or "").strip() or None
    workspace_key = _payload_value(card_payload, "workspace_key") or "shared_ops"
    card_payload["workspace_key"] = workspace_key

    if _is_human_front_door_payload(source, card_payload):
        card_payload["front_door_agent"] = "Neo"
        card_payload["source_agent"] = "Neo"
        card_payload["requested_by"] = "Neo"
        if not execution.get("requested_by"):
            execution["requested_by"] = "Neo"

    if execution:
        card_payload["execution"] = execution

    trigger_key = _payload_value(card_payload, "trigger_key")
    if not trigger_key and _is_human_front_door_payload(source, card_payload):
        card_payload["trigger_key"] = _build_trigger_key(
            title=payload.title,
            workspace_key=workspace_key,
            source=source,
            payload=card_payload,
        )
        card_payload["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
        card_payload["trigger_replays"] = int(card_payload.get("trigger_replays") or 0)

    owner = payload.owner or ("Neo" if card_payload.get("front_door_agent") == "Neo" else payload.owner)
    return payload.model_copy(update={"owner": owner, "payload": card_payload, "source": source})


def _is_human_front_door_payload(source: str | None, payload: dict[str, Any]) -> bool:
    front_door_agent = _payload_value(payload, "front_door_agent")
    source_agent = _payload_value(payload, "source_agent")
    trigger_origin = _payload_value(payload, "trigger_origin")
    normalized_source = str(source or "").strip().lower()
    return bool(
        front_door_agent == "Neo"
        or source_agent == "Neo"
        or trigger_origin in {"codex_native_remote_queue", "openclaw_thin_trigger"}
        or normalized_source.startswith(("codex_native:", "openclaw:"))
    )


def _build_trigger_key(*, title: str, workspace_key: str, source: str | None, payload: dict[str, Any]) -> str:
    return build_pm_trigger_key(title=title, workspace_key=workspace_key, source=source, payload=payload)
