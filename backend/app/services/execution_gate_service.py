from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from app.security.execution_authorization import AUTH_FIELD
from app.services.workspace_registry_service import (
    canonicalize_workspace_key,
    workspace_registry_map,
    workspace_root_slug,
)


SCHEMA_VERSION = "execution_gate/v1"
POLICY_VERSION = 2

CURRENT_GATE_FIELDS = (
    "schema_version",
    "policy_version",
    "decision",
    "capability_id",
    "runner_profile",
    "risk_factors",
    "reason_codes",
    "intent_hash",
    "approval_state",
)

AUTO_EXECUTE = "AUTO_EXECUTE"
REQUIRE_APPROVAL = "REQUIRE_APPROVAL"

BOUNDED_PROJECT_CAPABILITY = "codex.bounded_project_work/v1"

KNOWN_CAPABILITIES = frozenset(
    {
        BOUNDED_PROJECT_CAPABILITY,
        "brain.signal_create/v1",
        "brain.signal_review/v1",
        "brain.signal_route/v1",
        "brain.signal_intake/v1",
        "brain.long_form_ingest/v1",
        "brain.linkedin_performance_record/v1",
        "brain.youtube_watchlist_ingest/v1",
        "brain.refresh_feezie_workspace/v1",
        "brain.refresh_persona_review/v1",
        "brain.integrated_content_variant/v1",
        "brain.integrated_owner_post/v1",
        "brain.integrated_content_manual_edit/v1",
        "brain.integrated_content_learning/v1",
        "brain.integrated_persona_reversal/v1",
        "brain.canonical_decision_create/v1",
        "brain.canonical_decision_transition/v1",
        "host.local_durable_writeback/v1",
        "host.execution_result_writeback/v1",
        "host.linkedin_schedule_writeback/v1",
    }
)

SAFE_BRAIN_ACTION_CAPABILITIES = {
    "signal_create": "brain.signal_create/v1",
    "signal_review": "brain.signal_review/v1",
    "signal_route": "brain.signal_route/v1",
    "signal_intake": "brain.signal_intake/v1",
    "long_form_ingest": "brain.long_form_ingest/v1",
    "linkedin_performance_record": "brain.linkedin_performance_record/v1",
    "youtube_watchlist_ingest": "brain.youtube_watchlist_ingest/v1",
    "refresh_feezie_workspace": "brain.refresh_feezie_workspace/v1",
    "refresh_persona_review": "brain.refresh_persona_review/v1",
    "integrated_content_variant": "brain.integrated_content_variant/v1",
    "integrated_owner_post": "brain.integrated_owner_post/v1",
    "integrated_content_manual_edit": "brain.integrated_content_manual_edit/v1",
    "integrated_content_learning": "brain.integrated_content_learning/v1",
    "integrated_persona_reversal": "brain.integrated_persona_reversal/v1",
    "canonical_decision_create": "brain.canonical_decision_create/v1",
    "canonical_decision_transition": "brain.canonical_decision_transition/v1",
}

SAFE_HOST_AUTOMATION_CAPABILITIES = {
    "fallback_watchdog_writeback": "host.local_durable_writeback/v1",
    "standup_prep_writeback": "host.local_durable_writeback/v1",
    "execution_result_writeback_proof": "host.execution_result_writeback/v1",
    "linkedin_scheduled_writeback": "host.linkedin_schedule_writeback/v1",
}

TRUSTED_CONTRACT_SOURCES = frozenset(
    {
        "accountability_sweep",
        "brain_triage",
        "codex_native_remote_queue",
        "owner_review_followup",
        "pm_review_resolution",
        "post_sync_dispatch",
        "standup_promotion",
    }
)

TRUSTED_SOURCE_PREFIXES = (
    "accountability_sweep",
    "brain-triage:",
    "brain_local_action:",
    "codex_native:",
    "pm_review_resolution",
    "standup-prep:",
)

NON_OVERRIDABLE_RISK_FACTORS = frozenset(
    {
        "UNKNOWN_CAPABILITY",
        "UNKNOWN_EFFECT",
        "UNSAFE_RUNNER_PROFILE",
        "PROMPT_CREDENTIAL_EXPOSURE",
        "CREDENTIAL_ACCESS_REQUEST",
    }
)

_DYNAMIC_EXECUTION_FIELDS = frozenset(
    {
        "assigned_runner",
        "briefing_path",
        "claim_id",
        "executor_finished_at",
        "executor_last_error",
        "executor_started_at",
        "executor_status",
        "executor_worker_id",
        "execution_packet_path",
        "history",
        "last_transition_at",
        "manager_attention_required",
        "queued_at",
        "sop_path",
        "state",
        "workspace_agent_briefing_path",
        "workspace_agent_packet_path",
    }
)

_IGNORED_PAYLOAD_FIELDS = frozenset(
    {
        AUTH_FIELD,
        "execution_approval",
        "execution_gate",
        "latest_execution_result",
        "latest_manual_review",
        "pm_review_policy",
    }
)


def _compiled(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns)


RISK_PATTERNS: tuple[tuple[str, str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "CODE_MERGE",
        "CODE_MERGE_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:git\s+merge|gh\s+pr\s+(?:merge|review\s+--approve))\b",
                r"\b(?:merge|approve)\b.{0,48}\b(?:pull\s+request|merge\s+request|pr\s*#?\d+)\b",
                r"\bmerge\b.{0,48}\b(?:branch|into\s+(?:main|master)|main\s+branch|master\s+branch)\b",
            )
        ),
    ),
    (
        "DEPLOYMENT",
        "DEPLOYMENT_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:deploy|release|ship|promote)\b.{0,48}\b(?:production|prod|railway|vercel|live)\b",
                r"\b(?:restart|redeploy|rollback|roll\s+back|stop|start|scale)\b.{0,48}\b(?:production|prod|railway|vercel|live\s+(?:service|site|environment|deployment))\b",
                r"\b(?:production|prod|railway|vercel|live\s+(?:service|site|environment|deployment))\b.{0,48}\b(?:restart|redeploy|rollback|roll\s+back|deploy|release|stop|start|scale)\b",
                r"\b(?:railway\s+up|vercel\s+deploy|go\s+live|production\s+deploy)\b",
            )
        ),
    ),
    (
        "PUBLICATION",
        "PUBLICATION_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:publish|schedule)\b.{0,64}\b(?:linkedin|instagram|youtube|twitter|newsletter|public|social|article|post)\b",
                r"\bschedule\s+approved\b.{0,40}\bdraft\b",
                r"\b(?:linkedin|instagram|youtube|twitter|newsletter|public|social)\b.{0,64}\b(?:publish|schedule|send|go\s+live)\b",
                r"\bpost\b.{0,32}\b(?:to|on)\b.{0,20}\b(?:linkedin|instagram|youtube|twitter|public|social)\b",
                r"\bpost\b.{0,24}\b(?:linkedin|instagram|youtube|twitter|public|social)\b",
                r"\bupload\b.{0,48}\b(?:to|on)\b.{0,16}\b(?:youtube|instagram|linkedin|twitter|public|social)\b",
                r"\bsend\b.{0,32}\bnewsletter\b",
            )
        ),
    ),
    (
        "EXTERNAL_COMMUNICATION",
        "EXTERNAL_COMMUNICATION_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\bsend\b.{0,72}\b(?:client|customer|recipient|person|user|gmail|inbox|email|message|reply)\b",
                r"\breply\s+to\b.{0,72}\b(?:client|customer|recipient|person|user|gmail|inbox|email|message)\b",
                r"\bforward\b.{0,72}\bto\b.{0,48}\b(?:client|customer|recipient|person|user|email|inbox)\b",
                r"\b(?:message|contact|email)\b.{0,48}\b(?:the\s+)?(?:client|customer|recipient|person|user)\b",
                r"\b(?:gmail|outlook|email|inbox)\b.{0,72}\b(?:send|forward|message)\b",
            )
        ),
    ),
    (
        "FINANCIAL",
        "FINANCIAL_ACTION_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:pay|purchase|buy|charge|refund|transfer|subscribe|spend)\b.{0,64}\b(?:money|card|account|invoice|subscription|plan|service|dollars?|\$)\b",
                r"\b(?:stripe|bank|credit\s+card|invoice)\b.{0,64}\b(?:pay|refund|charge|transfer|purchase)\b",
            )
        ),
    ),
    (
        "DESTRUCTIVE_OR_IRREVERSIBLE",
        "DESTRUCTIVE_ACTION_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\brm\s+-rf\b",
                r"\b(?:delete|drop|truncate|purge|erase|wipe)\b.{0,72}\b(?:data|database|table|account|project|repository|repo|files?|records?|history)\b",
                r"\b(?:force[- ]?push|rewrite\s+history|hard\s+reset)\b",
            )
        ),
    ),
    (
        "ACCESS_OR_PERMISSION_CHANGE",
        "ACCESS_CHANGE_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:grant|revoke|rotate|reset|change|create|delete)\b.{0,64}\b(?:access|permission|role|credential|secret|token|password|api\s*key)\b",
                r"\b(?:access|permission|role|credential|secret|token|password|api\s*key)\b.{0,64}\b(?:grant|revoke|rotate|reset|change|create|delete)\b",
                r"\b(?:invite|add|remove)\b.{0,64}\b(?:administrator|admin|member|user|owner)\b",
                r"\b(?:make|set|promote)\b.{0,48}\b(?:administrator|admin|owner)\b",
            )
        ),
    ),
    (
        "CREDENTIAL_ACCESS_REQUEST",
        "CREDENTIAL_ACCESS_REQUEST_BLOCKED",
        _compiled(
            (
                r"\b(?:reveal|show|export|print|return|write|log|expose)\b.{0,64}\b(?:credential|secret|token|password|api\s*key)\b",
                r"\b(?:credential|secret|token|password|api\s*key)\b.{0,64}\b(?:reveal|show|export|print|return|write|log|expose)\b",
            )
        ),
    ),
    (
        "PRIVILEGED_OR_PRODUCTION",
        "PRIVILEGED_CHANGE_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:migrate|alter|backfill)\b.{0,64}\b(?:production|database|schema|customer\s+data|live\s+data)\b",
                r"\b(?:change|replace|disable|bypass)\b.{0,64}\b(?:authentication|authorization|auth|security|firewall|environment\s+variables?|env\s+vars?)\b",
            )
        ),
    ),
    (
        "OWNER_JUDGMENT_REQUIRED",
        "OWNER_REVIEW_DECISION_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:run|execute|complete|resolve)\b.{0,64}\bowner[- ]review\b",
                r"\bowner[- ]review\b.{0,64}\b(?:record|apply|resolve|approve|reject|decide)\b",
                r"\brecord\b.{0,40}\b(?:owner|approval|review)[- ]?decisions?\b",
            )
        ),
    ),
    (
        "OWNER_JUDGMENT_REQUIRED",
        "PERSONA_CANON_REQUIRES_APPROVAL",
        _compiled(
            (
                r"\b(?:approve|commit|merge|promote|write|update|change|modify|delete|remove)\b.{0,72}\b(?:persona\s+canon|identity/claims|identity\s+claims|voice[_ ]patterns|story[_ ]bank|canonical\s+identity)\b",
                r"\b(?:persona\s+canon|identity/claims|identity\s+claims|voice[_ ]patterns|story[_ ]bank|canonical\s+identity)\b.{0,72}\b(?:approve|commit|merge|promote|write|update|change|modify|delete|remove)\b",
            )
        ),
    ),
)

_PROMPT_CREDENTIAL_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|(?:password|secret|token|api[_ -]?key)\s*[:=]\s*[^\s,;]{8,})",
    re.IGNORECASE,
)


def evaluate_execution_gate(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    payload: dict[str, Any] | None,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Classify executable intent without trusting producer-supplied safety labels."""

    raw_payload = dict(payload or {})
    canonical_workspace_key = canonicalize_workspace_key(workspace_key)
    capability_id, capability_reason = _capability_for(source=source, payload=raw_payload)
    runner_profile = _runner_profile_for(capability_id, raw_payload)
    intent = _intent_payload(
        card_id=str(card_id),
        title=title,
        source=source,
        workspace_key=canonical_workspace_key,
        capability_id=capability_id,
        runner_profile=runner_profile,
        payload=raw_payload,
    )
    intent_hash = _sha256_json(intent)

    risk_factors: list[str] = []
    reason_codes: list[str] = []

    if capability_id not in KNOWN_CAPABILITIES:
        risk_factors.append("UNKNOWN_CAPABILITY")
        reason_codes.append("UNKNOWN_CAPABILITY_FAILS_CLOSED")
    if not _trusted_capability_provenance(source=source, payload=raw_payload):
        risk_factors.append("UNKNOWN_EFFECT")
        reason_codes.append("UNTRUSTED_CAPABILITY_PROVENANCE")
    if canonical_workspace_key not in workspace_registry_map():
        risk_factors.append("UNBOUNDED_SCOPE")
        reason_codes.append("UNKNOWN_WORKSPACE_SCOPE")
    if not _has_bounded_intent(raw_payload):
        risk_factors.append("UNBOUNDED_SCOPE")
        reason_codes.append("BOUNDED_EXECUTION_CONTRACT_MISSING")

    execution = _mapping(raw_payload.get("execution"))
    if _owner_review_pending(raw_payload):
        risk_factors.append("OWNER_REVIEW_REQUIRED")
        reason_codes.append("OWNER_REVIEW_GATE_PRESENT")

    host_action = _mapping(raw_payload.get("host_action_required"))
    host_automation = _mapping(raw_payload.get("host_action_automation"))
    if host_action and not _is_supported_host_automation(host_automation):
        risk_factors.append("HOST_ACTION_REQUIRED")
        reason_codes.append("HOST_ACTION_GATE_PRESENT")

    if capability_id == "brain.signal_route/v1" and _brain_route_target(raw_payload) == "persona_canon":
        risk_factors.append("OWNER_JUDGMENT_REQUIRED")
        reason_codes.append("PERSONA_CANON_REQUIRES_APPROVAL")

    if capability_id == "host.linkedin_schedule_writeback/v1":
        risk_factors.append("EXTERNAL_WRITE")
        reason_codes.append("HOST_CONFIRMED_EXTERNAL_WRITEBACK")

    searchable_segments = _intent_search_segments(title=title, source=source, payload=raw_payload)
    searchable_text = "\n".join(searchable_segments)
    if _PROMPT_CREDENTIAL_PATTERN.search(searchable_text):
        risk_factors.append("PROMPT_CREDENTIAL_EXPOSURE")
        reason_codes.append("PROMPT_CONTAINS_CREDENTIAL_LIKE_VALUE")
    for risk_factor, reason_code, patterns in RISK_PATTERNS:
        if (
            capability_id == "brain.integrated_persona_reversal/v1"
            and reason_code == "PERSONA_CANON_REQUIRES_APPROVAL"
        ):
            # This exact signed capability is created only from the bounded
            # owner-confirmed reversal contract.  The owner judgment already
            # occurred at the controller; all other persona-canon mutations
            # remain subject to the general approval rule above.
            continue
        if any(
            pattern.search(_mask_negated_risk_clause(segment))
            for segment in searchable_segments
            for pattern in patterns
        ):
            risk_factors.append(risk_factor)
            reason_codes.append(reason_code)

    if runner_profile not in {"codex_workspace", "deterministic_local", "host_action_adapter"}:
        risk_factors.append("UNSAFE_RUNNER_PROFILE")
        reason_codes.append("RUNNER_PROFILE_NOT_ALLOWLISTED")

    risk_factors = _sorted_unique(risk_factors)
    reason_codes = _sorted_unique(reason_codes)
    decision = AUTO_EXECUTE if not risk_factors else REQUIRE_APPROVAL
    approval = _valid_approval(
        raw_payload.get("execution_approval"),
        intent_hash=intent_hash,
        risk_factors=risk_factors,
    )
    approval_state = "not_required" if decision == AUTO_EXECUTE else "missing"
    if decision == REQUIRE_APPROVAL:
        if approval is not None:
            approval_state = "approved"
        elif isinstance(raw_payload.get("execution_approval"), dict):
            approval_state = "stale"

    previous_gate = _mapping(raw_payload.get("execution_gate"))
    timestamp = evaluated_at or datetime.now(timezone.utc)
    if (
        previous_gate.get("schema_version") == SCHEMA_VERSION
        and previous_gate.get("policy_version") == POLICY_VERSION
        and previous_gate.get("intent_hash") == intent_hash
        and previous_gate.get("decision") == decision
        and previous_gate.get("risk_factors") == risk_factors
        and previous_gate.get("reason_codes") == reason_codes
        and previous_gate.get("evaluated_at")
    ):
        evaluated_at_iso = str(previous_gate["evaluated_at"])
    else:
        evaluated_at_iso = timestamp.astimezone(timezone.utc).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "decision": decision,
        "capability_id": capability_id,
        "runner_profile": runner_profile,
        "risk_class": _risk_class(risk_factors),
        "risk_factors": risk_factors,
        "reason_codes": reason_codes or ["BOUNDED_INTERNAL_PROJECT_WORK"],
        "reason": _human_reason(
            decision=decision,
            risk_factors=risk_factors,
            approval_state=approval_state,
            capability_reason=capability_reason,
        ),
        "intent_hash": intent_hash,
        "allowed_roots": _allowed_roots(canonical_workspace_key),
        "approval_state": approval_state,
        "evaluated_at": evaluated_at_iso,
    }


def apply_execution_gate(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    next_payload = dict(payload or {})
    next_payload["execution_gate"] = evaluate_execution_gate(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=next_payload,
    )
    return next_payload


def grant_execution_approval(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    payload: dict[str, Any] | None,
    approved_by: str,
    reason: str | None = None,
    surface: str = "authenticated_railway_frontend",
) -> dict[str, Any]:
    next_payload = apply_execution_gate(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=payload,
    )
    gate = _mapping(next_payload.get("execution_gate"))
    if gate.get("decision") == AUTO_EXECUTE:
        return next_payload
    blocking = sorted(set(gate.get("risk_factors") or []).intersection(NON_OVERRIDABLE_RISK_FACTORS))
    if blocking:
        raise ValueError(
            "This request cannot be approved into the Codex runner until its unsafe or unknown intent is corrected: "
            + ", ".join(blocking)
            + "."
        )
    approved_at = datetime.now(timezone.utc).isoformat()
    next_payload["execution_approval"] = {
        "schema_version": "execution_approval/v1",
        "approval_id": str(uuid4()),
        "approved_by": str(approved_by or "Neo").strip() or "Neo",
        "approved_at": approved_at,
        "surface": str(surface or "authenticated_railway_frontend").strip(),
        "intent_hash": str(gate.get("intent_hash") or ""),
        "policy_version": POLICY_VERSION,
        "reason": " ".join(str(reason or "").split()).strip() or "Owner approved this exact execution intent.",
        "approved_risk_factors": list(gate.get("risk_factors") or []),
    }
    return apply_execution_gate(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=next_payload,
    )


def execution_gate_allows_run(gate_or_payload: dict[str, Any] | None) -> bool:
    value = dict(gate_or_payload or {})
    gate = _mapping(value.get("execution_gate")) if "execution_gate" in value else value
    return bool(
        gate.get("schema_version") == SCHEMA_VERSION
        and gate.get("policy_version") == POLICY_VERSION
        and (
            gate.get("decision") == AUTO_EXECUTE
            or (gate.get("decision") == REQUIRE_APPROVAL and gate.get("approval_state") == "approved")
        )
    )


def execution_gate_matches_current(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    payload: dict[str, Any] | None,
) -> bool:
    raw_payload = dict(payload or {})
    stored = _mapping(raw_payload.get("execution_gate"))
    if not stored:
        return False
    current = evaluate_execution_gate(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=raw_payload,
    )
    return all(stored.get(field) == current.get(field) for field in CURRENT_GATE_FIELDS)


def require_current_execution_gate(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    stored = _mapping(raw_payload.get("execution_gate"))
    current = evaluate_execution_gate(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=raw_payload,
    )
    if not stored or not execution_gate_matches_current(
        card_id=card_id,
        title=title,
        source=source,
        workspace_key=workspace_key,
        payload=raw_payload,
    ):
        raise ValueError("Execution gate is missing or stale for the current PM card intent.")
    if not execution_gate_allows_run(current):
        raise ValueError(str(current.get("reason") or "Execution requires owner approval."))
    return current


def _capability_for(*, source: str | None, payload: dict[str, Any]) -> tuple[str, str]:
    execution = _mapping(payload.get("execution"))
    explicit = str(
        payload.get("capability_id")
        or execution.get("capability_id")
        or ""
    ).strip()
    if explicit:
        return explicit, "explicit capability"

    brain_action = _mapping(payload.get("brain_local_action"))
    action = str(brain_action.get("action") or "").strip()
    if action in SAFE_BRAIN_ACTION_CAPABILITIES:
        return SAFE_BRAIN_ACTION_CAPABILITIES[action], "validated Brain local action"

    automation = _mapping(payload.get("host_action_automation"))
    automation_id = str(automation.get("automation_id") or "").strip()
    if automation_id in SAFE_HOST_AUTOMATION_CAPABILITIES:
        return SAFE_HOST_AUTOMATION_CAPABILITIES[automation_id], "supported host-action adapter"

    completion_contract = _mapping(payload.get("completion_contract"))
    contract_source = str(completion_contract.get("source") or execution.get("source") or "").strip()
    normalized_source = str(source or "").strip()
    if contract_source in TRUSTED_CONTRACT_SOURCES:
        return BOUNDED_PROJECT_CAPABILITY, "trusted bounded execution contract"
    if normalized_source.startswith(TRUSTED_SOURCE_PREFIXES):
        return BOUNDED_PROJECT_CAPABILITY, "trusted PM producer"
    return "unknown", "unclassified producer"


def _runner_profile_for(capability_id: str, payload: dict[str, Any]) -> str:
    if capability_id.startswith("brain."):
        return "deterministic_local"
    if capability_id.startswith("host."):
        return "host_action_adapter"
    execution = _mapping(payload.get("execution"))
    execution_mode = str(execution.get("execution_mode") or "").strip()
    if capability_id == BOUNDED_PROJECT_CAPABILITY and execution_mode in {"", "direct", "delegated"}:
        return "codex_workspace"
    return "none"


def _trusted_capability_provenance(*, source: str | None, payload: dict[str, Any]) -> bool:
    if _mapping(payload.get("brain_local_action")):
        return True
    if _is_supported_host_automation(_mapping(payload.get("host_action_automation"))):
        return True
    completion_contract = _mapping(payload.get("completion_contract"))
    execution = _mapping(payload.get("execution"))
    contract_source = str(completion_contract.get("source") or execution.get("source") or "").strip()
    if contract_source in TRUSTED_CONTRACT_SOURCES:
        return True
    return str(source or "").strip().startswith(TRUSTED_SOURCE_PREFIXES)


def _intent_payload(
    *,
    card_id: str,
    title: str,
    source: str | None,
    workspace_key: str,
    capability_id: str,
    runner_profile: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    execution = {
        key: value
        for key, value in _mapping(payload.get("execution")).items()
        if key not in _DYNAMIC_EXECUTION_FIELDS
    }
    intent_payload = {
        key: value
        for key, value in payload.items()
        if key not in _IGNORED_PAYLOAD_FIELDS and key != "execution"
    }
    return {
        "card_id": card_id,
        "title": " ".join(str(title or "").split()).strip(),
        "source": str(source or "").strip() or None,
        "workspace_key": str(workspace_key or "shared_ops").strip() or "shared_ops",
        "capability_id": capability_id,
        "runner_profile": runner_profile,
        "execution": execution,
        "payload": intent_payload,
    }


def _has_bounded_intent(payload: dict[str, Any]) -> bool:
    if _mapping(payload.get("brain_local_action")):
        return True
    if _is_supported_host_automation(_mapping(payload.get("host_action_automation"))):
        return True
    contract = _mapping(payload.get("completion_contract"))
    if contract and isinstance(contract.get("done_when"), list) and bool(contract.get("done_when")):
        return True
    instructions = payload.get("instructions")
    criteria = payload.get("acceptance_criteria")
    return bool(
        isinstance(instructions, list)
        and any(str(item or "").strip() for item in instructions)
        and isinstance(criteria, list)
        and any(str(item or "").strip() for item in criteria)
    )


def _owner_review_pending(payload: dict[str, Any]) -> bool:
    owner_review = _mapping(payload.get("owner_review"))
    if not owner_review:
        return False
    if str(owner_review.get("decision") or "").strip():
        return False
    return bool(
        str(owner_review.get("queue_id") or "").strip()
        or str(owner_review.get("sync_state") or "").strip().lower() == "pending_owner_review"
    )


def _brain_route_target(payload: dict[str, Any]) -> str:
    action = _mapping(payload.get("brain_local_action"))
    parameters = _mapping(action.get("parameters"))
    route = _mapping(parameters.get("route"))
    return str(route.get("route") or "").strip()


def _is_supported_host_automation(automation: dict[str, Any]) -> bool:
    return str(automation.get("automation_id") or "").strip() in SAFE_HOST_AUTOMATION_CAPABILITIES


def _valid_approval(
    value: Any,
    *,
    intent_hash: str,
    risk_factors: list[str],
) -> dict[str, Any] | None:
    approval = _mapping(value)
    if not approval:
        return None
    if approval.get("schema_version") != "execution_approval/v1":
        return None
    if int(approval.get("policy_version") or 0) != POLICY_VERSION:
        return None
    if str(approval.get("intent_hash") or "") != intent_hash:
        return None
    if not str(approval.get("approval_id") or "").strip():
        return None
    if not str(approval.get("approved_by") or "").strip():
        return None
    if not str(approval.get("approved_at") or "").strip():
        return None
    approved_risks = _sorted_unique(approval.get("approved_risk_factors") or [])
    if approved_risks != _sorted_unique(risk_factors):
        return None
    return approval


def _intent_search_segments(*, title: str, source: str | None, payload: dict[str, Any]) -> list[str]:
    values: list[Any] = [
        title,
        source,
        payload.get("goal"),
        payload.get("context"),
        payload.get("reason"),
        payload.get("instructions"),
        payload.get("acceptance_criteria"),
        payload.get("artifacts_expected"),
        payload.get("brain_local_action"),
        payload.get("host_action_required"),
        payload.get("host_action_automation"),
    ]
    segments: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            normalized = " ".join(value.split()).strip()
            if normalized:
                segments.append(normalized)
            return
        if isinstance(value, dict):
            for key in sorted(value):
                collect(value[key])
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)

    for value in values:
        collect(value)
    return segments


_NEGATED_RISK_CLAUSE = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|not\s+to|without|avoid)\b[^.;\n]*",
    re.IGNORECASE,
)


def _mask_negated_risk_clause(value: str) -> str:
    return _NEGATED_RISK_CLAUSE.sub(" ", value)


def _allowed_roots(workspace_key: str) -> list[str]:
    if workspace_key == "shared_ops":
        return ["."]
    if workspace_key not in workspace_registry_map():
        return []
    return [f"workspaces/{workspace_root_slug(workspace_key)}"]


def _risk_class(risk_factors: list[str]) -> str:
    if not risk_factors:
        return "safe_internal_reversible"
    if "UNKNOWN_CAPABILITY" in risk_factors or "UNKNOWN_EFFECT" in risk_factors:
        return "unknown"
    for candidate in (
        "DESTRUCTIVE_OR_IRREVERSIBLE",
        "FINANCIAL",
        "CODE_MERGE",
        "DEPLOYMENT",
        "PUBLICATION",
        "EXTERNAL_COMMUNICATION",
        "EXTERNAL_WRITE",
        "ACCESS_OR_PERMISSION_CHANGE",
        "CREDENTIAL_ACCESS_REQUEST",
        "PRIVILEGED_OR_PRODUCTION",
        "OWNER_JUDGMENT_REQUIRED",
    ):
        if candidate in risk_factors:
            return candidate.lower()
    return "owner_approval"


def _human_reason(
    *,
    decision: str,
    risk_factors: list[str],
    approval_state: str,
    capability_reason: str,
) -> str:
    if decision == AUTO_EXECUTE:
        return "Bounded internal project work can run automatically on the local Codex runner."
    if approval_state == "approved":
        return "Feeze approved this exact execution intent; the approval will become stale if the intent changes."
    friendly = {
        "ACCESS_OR_PERMISSION_CHANGE": "changes access, permissions, or credentials",
        "CREDENTIAL_ACCESS_REQUEST": "requests credential material that must stay outside Codex",
        "CODE_MERGE": "merges or approves a code change",
        "DEPLOYMENT": "changes a deployment or live environment",
        "DESTRUCTIVE_OR_IRREVERSIBLE": "may be destructive or difficult to reverse",
        "EXTERNAL_COMMUNICATION": "communicates with someone outside the system",
        "EXTERNAL_WRITE": "records or changes external state",
        "FINANCIAL": "can move or commit money",
        "HOST_ACTION_REQUIRED": "requires a host-only step",
        "OWNER_JUDGMENT_REQUIRED": "changes owner-controlled judgment or persona canon",
        "OWNER_REVIEW_REQUIRED": "is an explicit owner-review gate",
        "PRIVILEGED_OR_PRODUCTION": "changes privileged or production state",
        "PROMPT_CREDENTIAL_EXPOSURE": "contains credential-like material that must not reach Codex",
        "PUBLICATION": "publishes or schedules public content",
        "UNBOUNDED_SCOPE": "does not yet have a bounded execution contract",
        "UNKNOWN_CAPABILITY": "does not map to an allowlisted execution capability",
        "UNKNOWN_EFFECT": "has an unknown side effect",
        "UNSAFE_RUNNER_PROFILE": "does not map to a safe runner profile",
    }
    descriptions = [friendly.get(item, item.lower().replace("_", " ")) for item in risk_factors[:3]]
    if descriptions:
        return "Approval is required because this work " + ", ".join(descriptions) + "."
    return f"Approval is required because this work came from an {capability_reason}."


def _sha256_json(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})
