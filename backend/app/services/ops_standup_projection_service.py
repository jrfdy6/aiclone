from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.models.automations import AutomationRun
from app.services.automation_service import CODEX_RUN_LEDGER_PATH, is_codex_run
from app.services.brain_response_privacy_service import sanitize_brain_text
from app.services.execution_artifact_reference_service import contains_private_filesystem_reference
from app.services.integrated_content_projection_service import _decision_summary
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.workspace_registry_service import (
    ACTIVE_PORTFOLIO_WORKSPACE_STATUSES,
    workspace_registry_entries,
    workspace_registry_entry,
)
from app.utils.ai_clone_clock import (
    CLOCK_AUTHORITY,
    CLOCK_SCHEMA_VERSION,
    resolve_payload_observation,
)


PROJECTION_SCHEMA = "ops_standup_summary_conclusion/v3"
PRE_CLOCK_PROJECTION_SCHEMA = "ops_standup_summary_conclusion/v2"
LEGACY_PROJECTION_SCHEMA = "ops_standup_summary_conclusion/v1"
SNAPSHOT_TYPE = "ops_standup_summary_conclusion"
WORKSPACE_KEY = "shared_ops"
MAX_ITEMS = 100
MAX_BYTES = 256 * 1024
MAX_WORKSPACE_RECURSION = 25
MAX_RECURSION_ITEMS = 20
_LEGACY_CLOCK_LEDGER_MAX_BYTES = 128 * 1024 * 1024
_LEGACY_CLOCK_LEDGER_MAX_ROWS = 100_000
_LEGACY_CLOCK_LEDGER_MAX_LINE_BYTES = 2 * 1024 * 1024
_PRIVATE_KEYS = {
    "absolute_path",
    "body",
    "content",
    "local_path",
    "path",
    "payload",
    "private_notes",
    "raw_body",
    "source_path",
    "transcript",
}
_WORKSPACE_RECURSION_LIST_FIELDS = (
    "changes_since_prior",
    "system_decisions",
    "actions_taken",
    "completed_work",
    "failed_work",
    "carried_forward",
    "owner_decisions",
    "blocked",
    "no_action",
    "recommendations",
    "reference_only",
    "next_cycle_inputs",
    "recommendation_resolutions",
)
_WORKSPACE_RECURSION_FIELDS = frozenset(
    {"workspace_key", "display_name", "goal", *_WORKSPACE_RECURSION_LIST_FIELDS}
)
_MISSING_ACTIVE_WORKSPACE_RECURSION_REASON = (
    "ops_conclusion_missing_active_workspace_recursion"
)
_DUPLICATE_WORKSPACE_RECURSION_REASON = (
    "ops_conclusion_duplicate_workspace_recursion"
)
_UNEXPECTED_WORKSPACE_RECURSION_REASON = (
    "ops_conclusion_unexpected_workspace_recursion"
)
_MISSING_SHARED_OPS_RECONCILIATION_REASON = (
    "ops_conclusion_missing_shared_ops_reconciliation"
)
_SHARED_OPS_RECONCILIATION_LIST_FIELDS = (
    "evaluated",
    "system_decisions",
    "actions_taken",
    "owner_calls",
    "blocked",
    "no_action",
    "recommendations",
    "reference_only",
    "next_cycle_inputs",
)
_SHARED_OPS_RECONCILIATION_FIELDS = frozenset(
    {
        "display_name",
        "role",
        "summary",
        "goal",
        *_SHARED_OPS_RECONCILIATION_LIST_FIELDS,
    }
)
_GOAL_FIELD_ORDER = (
    "schema_version",
    "goal",
    "progress_signals",
    "phase_gate",
    "no_action_trigger",
)
_GOAL_FIELDS = frozenset(_GOAL_FIELD_ORDER)
_SAFE_ITEM_URL_FIELDS = frozenset({"url", "href", "source_url"})
_SAFE_ITEM_FIELDS = frozenset(
    {
        "action_at",
        "action_id",
        "approval_state",
        "authorization_current",
        "backup_status",
        "basis_created_at",
        "card_id",
        "claim_id",
        "classification",
        "commitment",
        "conclusion_id",
        "count",
        "created_this_cycle",
        "cycle_evaluation_only",
        "cycle_id",
        "decision",
        "decision_id",
        "decision_record_id",
        "decision_record_owner_role",
        "decision_record_schema_version",
        "dependency",
        "display_name",
        "effective_state",
        "execution_state",
        "evaluation_schema_version",
        "explanation",
        "future_trigger",
        "gate_decision",
        "href",
        "kind",
        "label",
        "latest_created_at",
        "latest_standup_id",
        "meeting_held",
        "observed_at",
        "outcome_receipt_available",
        "owner",
        "owner_decision_status",
        "promotion_suppressed",
        "provenance_kind",
        "reason",
        "reason_code",
        "recommendation_id",
        "ref",
        "required",
        "resolution_state",
        "result_at",
        "result_id",
        "result_status",
        "retryable",
        "route",
        "scope",
        "selected",
        "standup_id",
        "standup_kind",
        "state",
        "status",
        "summary",
        "title",
        "top_status",
        "trigger",
        "type",
        "source_url",
        "url",
        "verified_receipt",
        "workspace",
        "workspace_key",
    }
)
_MEMORY_READINESS_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "cycle_id",
        "checked_at",
        "observed_at",
        "last_verified_memory_at",
        "failed_component",
        "memory_entry_count",
        "consolidation_id",
        "readiness_id",
        "event_cursor",
    }
)
_PROCESS_UPDATE_FIELDS = frozenset({"memory_readiness", "morning_brief_ref"})
_SAFE_SUBSYSTEM_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,79}")
_CANONICAL_UTC_OBSERVATION_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z"
)
_SAFE_SUBSYSTEM_STATES = frozenset(
    {
        "ready",
        "healthy",
        "complete",
        "completed",
        "available",
        "ok",
        "degraded",
        "failed",
        "unhealthy",
        "not_verified",
        "unavailable",
        "unknown",
    }
)
_DECISION_ROUTES = frozenset(
    {
        "ops",
        "workspace",
        "content",
        "feezie-os",
        "fusion-os",
        "easyoutfitapp",
        "ai-swag-store",
        "agc",
        "work-life-tools",
    }
)
_DECISION_STATUSES = frozenset(
    {"open", "in_session", "resolved", "superseded", "canceled", "blocked"}
)
_DECISION_RESOLUTION_FIELDS = frozenset({"choice"})
_EXPECTED_DATA_POLICY = {
    "canonical_authority": "mac_local_sql",
    "railway_role": "authenticated_bounded_ops_projection",
    "private_bodies_included": False,
}
_PROJECTION_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "state",
        "reason_codes",
        "ops_conclusion_id",
        "ops_conclusion_attempt_id",
        "ops_conclusion_attempt_number",
        "ops_conclusion_attempt_payload_sha256",
        "portfolio_cycle_id",
        "cycle_date",
        "observed_at",
        "clock",
        "status",
        "workspace_updates",
        "workspace_recursion",
        "shared_ops_reconciliation",
        "workspace_cycle_evaluations",
        "ai_clone_process_updates",
        "endpoint_and_subsystem_health",
        "work_underway",
        "completed_work",
        "blockers",
        "urgent_escalations",
        "workspace_decisions",
        "ops_decisions",
        "owner_calls",
        "canonical_decisions",
        "decision_readiness",
        "degraded_system_warnings",
        "supporting_evidence_links",
        "recommended_next_actions",
        "data_policy",
    }
)


class OpsStandupProjectionError(ValueError):
    pass


def _active_project_workspace_keys() -> tuple[str, ...]:
    """Return the structural project scope that Ops must reconcile exactly.

    Shared Ops is the portfolio reconciler, not a project recursion row.  A
    workspace name, route, or payload claim cannot make a registry entry
    active: kind, visibility, and lifecycle status are the authority.
    """

    keys = tuple(
        str(entry.get("key") or "").strip()
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace"
        and entry.get("portfolio_visible") is True
        and str(entry.get("status") or "")
        in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
        and str(entry.get("key") or "").strip()
        and str(entry.get("key") or "").strip() != WORKSPACE_KEY
    )
    if len(keys) != len(set(keys)):
        raise OpsStandupProjectionError(
            "canonical active workspace registry contains duplicate keys"
        )
    return keys


def _raw_workspace_recursion_scope_defects(
    value: Any,
) -> tuple[list[str], list[str]]:
    """Describe duplicate and out-of-scope rows before bounding can hide them.

    The public projection deliberately drops malformed and out-of-scope rows.
    Inspecting the canonical input first ensures that truncation or sanitization
    cannot turn such an input into an apparently complete, ready projection.
    """

    expected = set(_active_project_workspace_keys())
    seen: set[str] = set()
    duplicate_keys: set[str] = set()
    unexpected_keys: set[str] = set()
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            unexpected_keys.add("<invalid-recursion-row>")
            continue
        key = str(raw.get("workspace_key") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key):
            unexpected_keys.add(key or "<missing-workspace-key>")
            continue
        if key in seen:
            duplicate_keys.add(key)
        seen.add(key)
        if key not in expected:
            unexpected_keys.add(key)
    return sorted(duplicate_keys), sorted(unexpected_keys)


def _normalize_active_workspace_recursion(
    workspace_recursion: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    """Bound recursion to one row per canonical active project.

    The returned defect lists describe the canonical conclusion input.  The
    bounded projection itself excludes duplicate and out-of-scope rows so
    Shared Ops cannot become a competing workspace writer.
    """

    expected = _active_project_workspace_keys()
    expected_set = set(expected)
    rows_by_key: dict[str, dict[str, Any]] = {}
    duplicate_keys: set[str] = set()
    unexpected_keys: set[str] = set()
    for row in workspace_recursion:
        key = str(row.get("workspace_key") or "")
        if key not in expected_set:
            unexpected_keys.add(key)
            continue
        if key in rows_by_key:
            duplicate_keys.add(key)
            continue
        rows_by_key[key] = row
    missing_keys = [key for key in expected if key not in rows_by_key]
    normalized = [rows_by_key[key] for key in expected if key in rows_by_key]
    return (
        normalized,
        missing_keys,
        sorted(duplicate_keys),
        sorted(unexpected_keys),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    # Query strings and fragments can contain credentials or opaque private
    # identifiers.  The public projection only needs a stable evidence link.
    return parsed._replace(query="", fragment="").geturl()


def _bounded_text(value: Any, *, limit: int = 1000) -> str:
    return " ".join(sanitize_brain_text(str(value or "")).split())[:limit]


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_bounded_text(value: Any, *, limit: int) -> str | None:
    return _bounded_text(value, limit=limit) if isinstance(value, str) else None


def _private_key(value: Any) -> bool:
    key = str(value or "").strip().lower()
    return (
        key in _PRIVATE_KEYS
        or key.endswith("_path")
        or "private" in key
        or "transcript" in key
        or "raw_body" in key
    )


def _bounded_items(value: Any, *, evidence: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            if not isinstance(raw, (str, int, float, bool)) or (
                isinstance(raw, float) and not math.isfinite(raw)
            ):
                continue
            raw = {"summary": raw}
        item: dict[str, Any] = {}
        for key, cell in raw.items():
            key = str(key)
            if key not in _SAFE_ITEM_FIELDS or _private_key(key):
                continue
            if key in _SAFE_ITEM_URL_FIELDS:
                if evidence:
                    safe = _safe_url(cell)
                    if safe:
                        item[key] = safe
            elif isinstance(cell, bool):
                item[key] = cell
            elif isinstance(cell, (int, float)):
                if not isinstance(cell, float) or math.isfinite(cell):
                    item[key] = cell
            elif cell is None:
                item[key] = None
            elif isinstance(cell, str):
                item[key] = _bounded_text(cell)
        if item:
            result.append(item)
        if len(result) >= MAX_ITEMS:
            break
    return result


def _bounded_process_updates(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    readiness = value.get("memory_readiness")
    if isinstance(readiness, dict):
        bounded_readiness: dict[str, Any] = {}
        for key in _MEMORY_READINESS_FIELDS:
            if key not in readiness:
                continue
            cell = readiness.get(key)
            if isinstance(cell, bool) or isinstance(cell, (int, float)) or cell is None:
                if not isinstance(cell, float) or math.isfinite(cell):
                    bounded_readiness[key] = cell
            elif isinstance(cell, str):
                bounded_readiness[key] = _bounded_text(cell)
        if bounded_readiness:
            result["memory_readiness"] = bounded_readiness
    if "morning_brief_ref" in value:
        brief_ref = value.get("morning_brief_ref")
        result["morning_brief_ref"] = (
            _bounded_text(brief_ref) if isinstance(brief_ref, str) else None
        )
    return result


def _bounded_subsystem_health(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for raw_key, cell in list(value.items())[:MAX_ITEMS]:
        key = str(raw_key).strip().lower()
        if not _SAFE_SUBSYSTEM_NAME_RE.fullmatch(key) or _private_key(key):
            continue
        if isinstance(cell, bool):
            result[key] = "healthy" if cell else "failed"
            continue
        if isinstance(cell, dict):
            cell = cell.get("state") or cell.get("status")
        state = str(cell or "unknown").strip().lower().replace(" ", "_")
        if state.startswith("failed:"):
            state = "failed"
        elif state.startswith("degraded:"):
            state = "degraded"
        result[key] = state if state in _SAFE_SUBSYSTEM_STATES else "unknown"
    return result


def _bounded_goal(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    goal: dict[str, Any] = {}
    for key in _GOAL_FIELD_ORDER:
        cell = value.get(key)
        if key == "progress_signals":
            if isinstance(cell, list):
                goal[key] = [
                    _bounded_text(item, limit=500)
                    for item in cell[:20]
                    if isinstance(item, (str, int, float, bool))
                ]
        elif isinstance(cell, str) and cell.strip():
            goal[key] = _bounded_text(cell, limit=2000)
    return goal


def _bounded_workspace_recursion(
    value: Any,
    *,
    blockers: Any,
) -> list[dict[str, Any]]:
    blockers_by_workspace: dict[str, list[dict[str, Any]]] = {}
    for item in _bounded_items(blockers):
        workspace_key = str(item.get("workspace_key") or "").strip()
        if workspace_key:
            blockers_by_workspace.setdefault(workspace_key, []).append(item)

    result: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        workspace_key = str(raw.get("workspace_key") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", workspace_key):
            continue
        raw_blocked = raw.get("blocked") or raw.get("blockers") or []
        bounded_blocked = _bounded_items(raw_blocked)[:MAX_RECURSION_ITEMS]
        if not bounded_blocked:
            bounded_blocked = blockers_by_workspace.get(workspace_key, [])[
                :MAX_RECURSION_ITEMS
            ]
        recursion = {
            "workspace_key": workspace_key,
            "display_name": _bounded_text(
                workspace_registry_entry(workspace_key).get("display_name") or workspace_key,
                limit=120,
            ),
            "goal": _bounded_goal(raw.get("goal")),
            "changes_since_prior": _bounded_items(raw.get("changes_since_prior"))[:MAX_RECURSION_ITEMS],
            "system_decisions": _bounded_items(raw.get("system_decisions"))[:MAX_RECURSION_ITEMS],
            "actions_taken": _bounded_items(raw.get("actions_taken"))[:MAX_RECURSION_ITEMS],
            "completed_work": _bounded_items(raw.get("completed_work"))[:MAX_RECURSION_ITEMS],
            "failed_work": _bounded_items(raw.get("failed_work"))[:MAX_RECURSION_ITEMS],
            "carried_forward": _bounded_items(raw.get("carried_forward"))[:MAX_RECURSION_ITEMS],
            "owner_decisions": _bounded_items(raw.get("owner_decisions"))[:MAX_RECURSION_ITEMS],
            "blocked": bounded_blocked,
            "no_action": _bounded_items(raw.get("no_action"))[:MAX_RECURSION_ITEMS],
            "recommendations": _bounded_items(raw.get("recommendations"))[:MAX_RECURSION_ITEMS],
            "reference_only": _bounded_items(raw.get("reference_only"))[:MAX_RECURSION_ITEMS],
            "next_cycle_inputs": _bounded_items(raw.get("next_cycle_inputs"))[:MAX_RECURSION_ITEMS],
            "recommendation_resolutions": _bounded_items(
                raw.get("recommendation_resolutions")
            )[:MAX_RECURSION_ITEMS],
        }
        result.append(recursion)
        if len(result) >= MAX_WORKSPACE_RECURSION:
            break
    return result


def _bounded_shared_ops_reconciliation(value: Any) -> dict[str, Any] | None:
    """Project Shared Ops as the read-only reconciler, never a project row."""

    if not isinstance(value, dict):
        return None
    summary = _bounded_text(value.get("summary"), limit=1000)
    if not summary:
        return None
    result: dict[str, Any] = {
        "display_name": "Executive Standup",
        "role": "portfolio_reconciler",
        "summary": summary,
        "goal": _bounded_goal(value.get("goal")),
    }
    for key in _SHARED_OPS_RECONCILIATION_LIST_FIELDS:
        result[key] = _bounded_items(
            value.get(key),
            evidence=key == "reference_only",
        )[:MAX_RECURSION_ITEMS]
    return result


def _bounded_canonical_decisions(value: Any) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        if not isinstance(raw.get("decision_id"), str) or not isinstance(
            raw.get("decision_type"), str
        ):
            continue
        decision_id = _bounded_text(raw.get("decision_id"), limit=160)
        decision_type = _bounded_text(raw.get("decision_type"), limit=120)
        status = str(raw.get("status") or "").strip().lower()
        route = str(raw.get("route") or "").strip().lower()
        state_version = raw.get("state_version")
        updated_at = raw.get("updated_at")
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", decision_id)
            or not decision_type
            or len(decision_type) > 120
            or status not in _DECISION_STATUSES
            or route not in _DECISION_ROUTES
            or isinstance(state_version, bool)
            or not isinstance(state_version, int)
            or state_version < 1
            or not _aware_iso(updated_at)
        ):
            continue
        resolution: dict[str, Any] = {}
        raw_resolution = raw.get("resolution")
        if isinstance(raw_resolution, dict):
            for key in _DECISION_RESOLUTION_FIELDS:
                if key not in raw_resolution:
                    continue
                cell = raw_resolution.get(key)
                if isinstance(cell, bool) or isinstance(cell, (int, float)) or cell is None:
                    if not isinstance(cell, float) or math.isfinite(cell):
                        resolution[key] = cell
                elif isinstance(cell, str):
                    resolution[key] = _bounded_text(cell)
        links: list[dict[str, str]] = []
        for link in raw.get("links") if isinstance(raw.get("links"), list) else []:
            if not isinstance(link, dict):
                continue
            if not isinstance(link.get("surface"), str) or not isinstance(
                link.get("external_ref"), str
            ):
                continue
            surface = _bounded_text(link.get("surface"), limit=100)
            external_ref = _bounded_text(link.get("external_ref"), limit=300)
            if (
                surface
                and external_ref
                and not contains_private_filesystem_reference(external_ref)
            ):
                links.append({"surface": surface, "external_ref": external_ref})
            if len(links) >= 12:
                break
        session_ref = raw.get("session_ref")
        bounded_session_ref = (
            _bounded_text(session_ref, limit=300) if isinstance(session_ref, str) else None
        )
        if bounded_session_ref and contains_private_filesystem_reference(bounded_session_ref):
            bounded_session_ref = None
        decisions.append(
            {
                "decision_id": decision_id,
                "decision_type": decision_type,
                "status": status,
                "title": (
                    _bounded_text(raw.get("title"), limit=300)
                    if isinstance(raw.get("title"), str)
                    else "Untitled decision"
                )
                or "Untitled decision",
                "state_version": state_version,
                "interaction_mode": "complex" if raw.get("interaction_mode") == "complex" else "simple",
                "route": route,
                "resolution": resolution,
                "session_ref": bounded_session_ref,
                "updated_at": str(updated_at),
                "links": links,
            }
        )
        if len(decisions) >= MAX_ITEMS:
            break
    return decisions


def _bounded_decision_readiness(
    value: Any,
    *,
    fallback_reason: str,
    fallback_checked_at: str | None,
) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    state = str(raw.get("state") or "degraded").strip().lower()
    if state not in {"ready", "degraded"}:
        state = "degraded"
    raw_checked_at = raw.get("checked_at")
    checked_at_valid = _aware_iso(raw_checked_at)
    checked_at = (
        str(raw_checked_at)
        if checked_at_valid
        else str(fallback_checked_at)
        if _aware_iso(fallback_checked_at)
        else "1970-01-01T00:00:00+00:00"
    )
    if not checked_at_valid:
        state = "degraded"
    raw_source_updated_at = raw.get("source_updated_at")
    source_updated_at_valid = _aware_iso(raw_source_updated_at, allow_none=True)
    source_updated_at = str(raw_source_updated_at) if _aware_iso(raw_source_updated_at) else None
    if not source_updated_at_valid:
        state = "degraded"
    blocking_reason_codes = [
        _bounded_text(item, limit=200)
        for item in _list_value(raw.get("blocking_reason_codes"))[:20]
        if isinstance(item, (str, int, float, bool))
    ]
    if state == "degraded" and not blocking_reason_codes:
        blocking_reason_codes = [fallback_reason]
    return {
        "schema_version": "canonical_decision_projection_readiness/v1",
        "state": state,
        "clock_authority": "ai_clone_utc",
        "checked_at": checked_at,
        "source_updated_at": source_updated_at,
        "blocking_reason_codes": blocking_reason_codes,
        "context_warnings": [
            _bounded_text(item, limit=500)
            for item in _list_value(raw.get("context_warnings"))[:20]
            if isinstance(item, (str, int, float, bool))
        ],
    }


def _upgrade_legacy_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a stored pre-clock snapshot through the closed projection contract.

    Railway may still hold the last bounded v1 snapshot while the new backend is
    rolling out.  Re-projecting known fields keeps that snapshot readable without
    trusting v1's open-ended nested mappings.
    """

    source_schema = payload.get("schema_version")
    if source_schema not in {
        LEGACY_PROJECTION_SCHEMA,
        PRE_CLOCK_PROJECTION_SCHEMA,
    }:
        raise OpsStandupProjectionError("invalid legacy Ops projection schema")
    if payload.get("data_policy") != _EXPECTED_DATA_POLICY:
        raise OpsStandupProjectionError("invalid legacy Ops data policy")
    state = (
        str(payload.get("state") or "degraded").strip().lower()
        if isinstance(payload.get("state"), str)
        else "degraded"
    )
    if state not in {"ready", "empty", "degraded", "error"}:
        state = "degraded"
    reason_codes = [
        _bounded_text(item, limit=200)
        for item in _list_value(payload.get("reason_codes"))[:20]
        if isinstance(item, (str, int, float, bool))
    ]
    if payload.get("ops_conclusion_id") is not None:
        state = "degraded"
        if "ops_conclusion_attempt_missing" not in reason_codes:
            reason_codes.append("ops_conclusion_attempt_missing")
    (
        raw_duplicate_workspace_recursion,
        raw_unexpected_workspace_recursion,
    ) = _raw_workspace_recursion_scope_defects(payload.get("workspace_recursion"))
    bounded_legacy_workspace_recursion = _bounded_workspace_recursion(
        payload.get("workspace_recursion"), blockers=payload.get("blockers")
    )
    (
        legacy_workspace_recursion,
        missing_workspace_recursion,
        bounded_duplicate_workspace_recursion,
        bounded_unexpected_workspace_recursion,
    ) = _normalize_active_workspace_recursion(
        bounded_legacy_workspace_recursion
    )
    duplicate_workspace_recursion = sorted(
        set(raw_duplicate_workspace_recursion)
        | set(bounded_duplicate_workspace_recursion)
    )
    unexpected_workspace_recursion = sorted(
        set(raw_unexpected_workspace_recursion)
        | set(bounded_unexpected_workspace_recursion)
    )
    coverage_applies = state in {"ready", "degraded"} or payload.get(
        "ops_conclusion_id"
    ) is not None
    if coverage_applies and (
        missing_workspace_recursion
        or duplicate_workspace_recursion
        or unexpected_workspace_recursion
    ):
        if state == "ready":
            state = "degraded"
        if not legacy_workspace_recursion:
            if "legacy_projection_missing_workspace_recursion" not in reason_codes:
                reason_codes.append("legacy_projection_missing_workspace_recursion")
        elif (
            missing_workspace_recursion
            and _MISSING_ACTIVE_WORKSPACE_RECURSION_REASON not in reason_codes
        ):
            reason_codes.append(_MISSING_ACTIVE_WORKSPACE_RECURSION_REASON)
        if (
            duplicate_workspace_recursion
            and _DUPLICATE_WORKSPACE_RECURSION_REASON not in reason_codes
        ):
            reason_codes.append(_DUPLICATE_WORKSPACE_RECURSION_REASON)
        if (
            unexpected_workspace_recursion
            and _UNEXPECTED_WORKSPACE_RECURSION_REASON not in reason_codes
        ):
            reason_codes.append(_UNEXPECTED_WORKSPACE_RECURSION_REASON)
    legacy_observed_at, legacy_observation_error = _validated_projection_observation(
        payload
    )
    legacy_clock = (
        dict(payload.get("clock") or {})
        if legacy_observed_at is not None
        else None
    )
    if legacy_observation_error:
        if state == "ready":
            state = "degraded"
        if "legacy_projection_missing_clock_receipt" not in reason_codes:
            reason_codes.append("legacy_projection_missing_clock_receipt")
    legacy_shared_ops_reconciliation = _bounded_shared_ops_reconciliation(
        payload.get("shared_ops_reconciliation")
    )
    if coverage_applies and legacy_shared_ops_reconciliation is None:
        if state == "ready":
            state = "degraded"
        if _MISSING_SHARED_OPS_RECONCILIATION_REASON not in reason_codes:
            reason_codes.append(_MISSING_SHARED_OPS_RECONCILIATION_REASON)
    projected = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _optional_bounded_text(payload.get("generated_at"), limit=100) or "",
        "state": state,
        "reason_codes": reason_codes,
        "ops_conclusion_id": (
            _optional_bounded_text(payload.get("ops_conclusion_id"), limit=200)
        ),
        "ops_conclusion_attempt_id": None,
        "ops_conclusion_attempt_number": None,
        "ops_conclusion_attempt_payload_sha256": None,
        "portfolio_cycle_id": (
            _optional_bounded_text(payload.get("portfolio_cycle_id"), limit=200)
        ),
        "cycle_date": (
            _optional_bounded_text(payload.get("cycle_date"), limit=40)
        ),
        "observed_at": (
            _optional_bounded_text(payload.get("observed_at"), limit=100)
            if legacy_observed_at is not None
            else None
        ),
        "clock": legacy_clock,
        "status": _optional_bounded_text(payload.get("status"), limit=80) or "degraded",
        "workspace_updates": _bounded_items(payload.get("workspace_updates")),
        "workspace_recursion": legacy_workspace_recursion,
        "shared_ops_reconciliation": legacy_shared_ops_reconciliation,
        "workspace_cycle_evaluations": _bounded_items(
            payload.get("workspace_cycle_evaluations")
        ),
        "ai_clone_process_updates": _bounded_process_updates(
            payload.get("ai_clone_process_updates")
        ),
        "endpoint_and_subsystem_health": _bounded_subsystem_health(
            payload.get("endpoint_and_subsystem_health")
        ),
        "work_underway": _bounded_items(payload.get("work_underway")),
        "completed_work": _bounded_items(payload.get("completed_work")),
        "blockers": _bounded_items(payload.get("blockers")),
        "urgent_escalations": _bounded_items(payload.get("urgent_escalations")),
        "workspace_decisions": _bounded_items(payload.get("workspace_decisions")),
        "ops_decisions": _bounded_items(payload.get("ops_decisions")),
        "owner_calls": _bounded_items(payload.get("owner_calls")),
        "canonical_decisions": _bounded_canonical_decisions(payload.get("canonical_decisions")),
        "decision_readiness": _bounded_decision_readiness(
            payload.get("decision_readiness"),
            fallback_reason="legacy_projection_readiness_unknown",
            fallback_checked_at=(
                str(payload.get("generated_at"))
                if isinstance(payload.get("generated_at"), str)
                else None
            ),
        ),
        "degraded_system_warnings": [
            _bounded_text(item)
            for item in _list_value(payload.get("degraded_system_warnings"))[:MAX_ITEMS]
            if isinstance(item, (str, int, float, bool))
        ],
        "supporting_evidence_links": _bounded_items(
            payload.get("supporting_evidence_links"), evidence=True
        ),
        "recommended_next_actions": _bounded_items(payload.get("recommended_next_actions")),
        "data_policy": dict(_EXPECTED_DATA_POLICY),
    }
    return projected


def _valid_projected_item(value: Any, *, allow_urls: bool = False) -> bool:
    if not isinstance(value, dict) or not value or set(value) - _SAFE_ITEM_FIELDS:
        return False
    for key, cell in value.items():
        if key in _SAFE_ITEM_URL_FIELDS:
            if not allow_urls or not isinstance(cell, str) or _safe_url(cell) != cell:
                return False
            continue
        if not isinstance(cell, (str, int, float, bool, type(None))):
            return False
        if isinstance(cell, float) and not math.isfinite(cell):
            return False
        if isinstance(cell, str) and len(cell) > 1000:
            return False
    return True


def _aware_iso(value: Any, *, allow_none: bool = False) -> bool:
    if value is None:
        return allow_none
    if not isinstance(value, str) or not value or len(value) > 100:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validated_projection_observation(
    payload: dict[str, Any],
) -> tuple[datetime | None, str | None]:
    """Validate one projected observation against the sole clock and cycle.

    ``generated_at`` remains a projection-write timestamp and is deliberately
    absent from this check. Only the canonical Ops observation, its
    ``ai_clone_utc`` receipt, UTC cycle date, and (when encoded) cycle identity
    may establish semantic freshness.
    """

    observed_at = payload.get("observed_at")
    clock = payload.get("clock")
    portfolio_cycle_id = str(payload.get("portfolio_cycle_id") or "").strip()
    cycle_date = str(payload.get("cycle_date") or "").strip()
    if not isinstance(observed_at, str) or not observed_at.strip():
        return None, "missing_semantic_observation"
    if not isinstance(clock, dict) or set(clock) != {
        "schema_version",
        "authority",
        "timezone",
        "observed_at",
    }:
        return None, "missing_or_invalid_clock_receipt"
    if (
        clock.get("schema_version") != CLOCK_SCHEMA_VERSION
        or clock.get("authority") != CLOCK_AUTHORITY
        or clock.get("timezone") != "UTC"
    ):
        return None, "invalid_clock_receipt"
    clock_observed_at = clock.get("observed_at")
    if (
        _CANONICAL_UTC_OBSERVATION_RE.fullmatch(observed_at) is None
        or not isinstance(clock_observed_at, str)
        or _CANONICAL_UTC_OBSERVATION_RE.fullmatch(clock_observed_at) is None
    ):
        return None, "semantic_observation_not_canonical_ai_clone_utc"
    if not portfolio_cycle_id:
        return None, "missing_portfolio_cycle_identity"

    observation, observation_source = resolve_payload_observation(
        {
            "cycle_id": portfolio_cycle_id,
            "observed_at": observed_at,
            "clock": clock,
        },
        created_at=None,
    )
    if observation is None or observation_source not in {
        "semantic_observed_at",
        "semantic_cycle_observation",
    }:
        return None, "conflicting_or_invalid_semantic_observation"
    try:
        raw_observation = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        raw_clock_observation = datetime.fromisoformat(
            clock_observed_at.replace("Z", "+00:00")
        )
        parsed_cycle_date = datetime.strptime(cycle_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "invalid_utc_observation_or_cycle_date"
    if (
        raw_observation.tzinfo is None
        or raw_observation.utcoffset() != timezone.utc.utcoffset(raw_observation)
        or raw_clock_observation.tzinfo is None
        or raw_clock_observation.utcoffset()
        != timezone.utc.utcoffset(raw_clock_observation)
    ):
        return None, "semantic_observation_must_be_utc"
    if raw_observation != raw_clock_observation:
        return None, "clock_observation_mismatch"
    if observation.date() != parsed_cycle_date:
        return None, "utc_cycle_date_mismatch"
    return observation, None


def _exact_utc_instant(value: Any) -> datetime | None:
    """Parse an exact, timezone-aware UTC instant without inventing a clock."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 100
    ):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
    ):
        return None
    return parsed.astimezone(timezone.utc)


def _recover_legacy_ops_clock_from_run_ledger(
    payload: dict[str, Any],
    *,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Bind one pre-clock Ops payload to its exact daily-cycle clock receipt.

    The append-only local automation ledger is already the authority for the
    daily coordinator's run receipt.  This bridge is intentionally narrow: it
    only fills a missing clock when every daily-cycle receipt claiming the
    exact UTC instant already stored by Ops carries the same canonical
    ``ai_clone_utc`` observation. Any malformed or conflicting exact-instant
    receipt leaves the payload untouched and therefore degraded by the
    existing semantic-observation validator.

    ``generated_at`` and calendar/display timezone values are deliberately not
    inputs to this recovery path.
    """

    if not isinstance(payload, dict) or payload.get("clock") is not None:
        return payload
    portfolio_cycle_id = payload.get("portfolio_cycle_id")
    if (
        not isinstance(portfolio_cycle_id, str)
        or not portfolio_cycle_id
        or portfolio_cycle_id != portfolio_cycle_id.strip()
    ):
        return payload
    stored_observation = _exact_utc_instant(payload.get("observed_at"))
    if stored_observation is None:
        return payload

    target = Path(ledger_path or CODEX_RUN_LEDGER_PATH)
    try:
        target_stat = target.lstat()
        size = target_stat.st_size
        if (
            stat.S_ISLNK(target_stat.st_mode)
            or not stat.S_ISREG(target_stat.st_mode)
            or size <= 0
            or size > _LEGACY_CLOCK_LEDGER_MAX_BYTES
        ):
            return payload
    except OSError:
        return payload

    recovered_receipt: tuple[str, dict[str, Any]] | None = None
    consumed_bytes = 0
    row_count = 0
    try:
        with target.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened_stat.st_mode)
                or opened_stat.st_dev != target_stat.st_dev
                or opened_stat.st_ino != target_stat.st_ino
                or opened_stat.st_size != size
            ):
                return payload
            while consumed_bytes < size:
                remaining = size - consumed_bytes
                raw_line = handle.readline(
                    min(_LEGACY_CLOCK_LEDGER_MAX_LINE_BYTES + 1, remaining + 1)
                )
                if (
                    not raw_line
                    or len(raw_line) > _LEGACY_CLOCK_LEDGER_MAX_LINE_BYTES
                    or len(raw_line) > remaining
                    or not raw_line.endswith(b"\n")
                ):
                    return payload
                consumed_bytes += len(raw_line)
                row_count += 1
                if row_count > _LEGACY_CLOCK_LEDGER_MAX_ROWS:
                    return payload
                try:
                    decoded_line = raw_line.decode("utf-8", errors="strict")
                    row = json.loads(decoded_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return payload
                if not isinstance(row, dict):
                    return payload
                if row.get("automation_id") != "daily_integrated_cycle":
                    continue
                metadata = row.get("metadata")
                if not isinstance(metadata, dict):
                    return payload
                if metadata.get("cycle_id") != portfolio_cycle_id:
                    continue
                receipt_observed_at = metadata.get("observed_at")
                receipt_instant = _exact_utc_instant(receipt_observed_at)
                if receipt_instant is None or receipt_instant != stored_observation:
                    continue
                try:
                    run = AutomationRun.model_validate(row)
                except (TypeError, ValueError):
                    return payload
                if not is_codex_run(run):
                    return payload

                receipt_clock = metadata.get("clock")
                if (
                    not isinstance(receipt_observed_at, str)
                    or _CANONICAL_UTC_OBSERVATION_RE.fullmatch(receipt_observed_at)
                    is None
                    or not isinstance(receipt_clock, dict)
                    or set(receipt_clock)
                    != {"schema_version", "authority", "timezone", "observed_at"}
                    or receipt_clock.get("schema_version") != CLOCK_SCHEMA_VERSION
                    or receipt_clock.get("authority") != CLOCK_AUTHORITY
                    or receipt_clock.get("timezone") != "UTC"
                    or receipt_clock.get("observed_at") != receipt_observed_at
                ):
                    return payload

                candidate = (receipt_observed_at, dict(receipt_clock))
                if recovered_receipt is not None and recovered_receipt != candidate:
                    return payload
                recovered_receipt = candidate
            if consumed_bytes != size or handle.read(1):
                return payload
    except OSError:
        return payload
    if row_count == 0:
        return payload

    if recovered_receipt is None:
        return payload
    recovered = dict(payload)
    recovered["observed_at"] = recovered_receipt[0]
    recovered["clock"] = recovered_receipt[1]
    observation, observation_error = _validated_projection_observation(recovered)
    if observation is None or observation_error is not None:
        return payload
    return recovered


def _valid_canonical_decision(value: Any) -> bool:
    decision_fields = {
        "decision_id",
        "decision_type",
        "status",
        "title",
        "state_version",
        "interaction_mode",
        "route",
        "resolution",
        "session_ref",
        "updated_at",
        "links",
    }
    if not isinstance(value, dict) or set(value) != decision_fields:
        return False
    decision_id = value.get("decision_id")
    if not isinstance(decision_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", decision_id
    ):
        return False
    decision_type = value.get("decision_type")
    if not isinstance(decision_type, str) or not decision_type.strip() or len(decision_type) > 120:
        return False
    if (
        value.get("status") not in _DECISION_STATUSES
        or value.get("interaction_mode") not in {"simple", "complex"}
        or value.get("route") not in _DECISION_ROUTES
        or isinstance(value.get("state_version"), bool)
        or not isinstance(value.get("state_version"), int)
        or value.get("state_version", 0) < 1
        or not isinstance(value.get("title"), str)
        or not str(value.get("title") or "").strip()
        or len(value["title"]) > 300
        or not _aware_iso(value.get("updated_at"))
    ):
        return False
    session_ref = value.get("session_ref")
    if not isinstance(session_ref, (str, type(None))) or (
        isinstance(session_ref, str) and len(session_ref) > 300
    ):
        return False
    resolution = value.get("resolution")
    if not isinstance(resolution, dict) or set(resolution) - _DECISION_RESOLUTION_FIELDS:
        return False
    if any(
        not isinstance(cell, (str, int, float, bool, type(None)))
        or (isinstance(cell, float) and not math.isfinite(cell))
        or (isinstance(cell, str) and len(cell) > 1000)
        for cell in resolution.values()
    ):
        return False
    links = value.get("links")
    if not isinstance(links, list) or len(links) > 12:
        return False
    return not any(
        not isinstance(link, dict)
        or set(link) != {"surface", "external_ref"}
        or not isinstance(link.get("surface"), str)
        or not str(link.get("surface") or "").strip()
        or len(link["surface"]) > 100
        or not isinstance(link.get("external_ref"), str)
        or not str(link.get("external_ref") or "").strip()
        or len(link["external_ref"]) > 300
        for link in links
    )


def _ops_semantic_order_key(row: Any) -> tuple[int, datetime, int, str]:
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    try:
        payload = json.loads(row["attempt_payload_json"] or row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        payload = {}
    observed, observation_error = _validated_projection_observation(payload)
    semantic_valid = int(observed is not None and observation_error is None)
    if not semantic_valid:
        observed = minimum
    try:
        attempt_number = int(row["attempt_number"] or 0)
    except (TypeError, ValueError):
        attempt_number = 0
    return semantic_valid, observed, attempt_number, str(row["ops_conclusion_id"])


def build_ops_standup_projection(*, store: IntegratedSystemStore | None = None) -> dict[str, Any]:
    store = store or IntegratedSystemStore()
    store.migrate()
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT oc.*,
                   oa.attempt_id,
                   oa.attempt_number,
                   oa.payload_json AS attempt_payload_json,
                   oa.status AS attempt_status
            FROM ops_conclusions AS oc
            LEFT JOIN ops_conclusion_attempts AS oa
              ON oa.ops_conclusion_id = oc.ops_conclusion_id
             AND oa.attempt_number = (
                 SELECT MAX(latest.attempt_number)
                 FROM ops_conclusion_attempts AS latest
                 WHERE latest.ops_conclusion_id = oc.ops_conclusion_id
             )
            """
        ).fetchall()
        row = max(rows, key=_ops_semantic_order_key, default=None)
        decision_rows = connection.execute(
            "SELECT * FROM decision_records ORDER BY updated_at DESC,decision_id LIMIT ?",
            (MAX_ITEMS,),
        ).fetchall()
        canonical_decisions = []
        for decision in decision_rows:
            links = [
                dict(item)
                for item in connection.execute(
                    "SELECT surface,external_ref FROM decision_links WHERE decision_id=? ORDER BY surface,external_ref",
                    (decision["decision_id"],),
                )
            ]
            canonical_decisions.append(_decision_summary(decision, links))
    if not row:
        return unavailable_ops_standup_projection(
            "ops_conclusion_not_generated",
            state="empty",
            canonical_decisions=canonical_decisions,
        )
    raw_attempt_payload = row["attempt_payload_json"]
    payload = json.loads(raw_attempt_payload or row["payload_json"])
    payload = _recover_legacy_ops_clock_from_run_ledger(payload)
    attempt_number = int(row["attempt_number"] or 0)
    attempt_id = str(row["attempt_id"] or "").strip() or None
    attempt_payload_sha256 = (
        hashlib.sha256(str(raw_attempt_payload).encode("utf-8")).hexdigest()
        if raw_attempt_payload is not None
        else None
    )
    generated_at = _now_iso()
    decision_source_updated_at = max(
        [str(row["created_at"])]
        + [str(decision["updated_at"]) for decision in decision_rows if decision["updated_at"]],
    )
    (
        raw_duplicate_workspace_recursion,
        raw_unexpected_workspace_recursion,
    ) = _raw_workspace_recursion_scope_defects(payload.get("workspace_recursion"))
    bounded_workspace_recursion = _bounded_workspace_recursion(
        payload.get("workspace_recursion"),
        blockers=payload.get("blockers"),
    )
    (
        workspace_recursion,
        missing_workspace_recursion,
        duplicate_workspace_recursion,
        unexpected_workspace_recursion,
    ) = _normalize_active_workspace_recursion(bounded_workspace_recursion)
    duplicate_workspace_recursion = sorted(
        set(raw_duplicate_workspace_recursion)
        | set(duplicate_workspace_recursion)
    )
    unexpected_workspace_recursion = sorted(
        set(raw_unexpected_workspace_recursion)
        | set(unexpected_workspace_recursion)
    )
    shared_ops_reconciliation = _bounded_shared_ops_reconciliation(
        payload.get("shared_ops_reconciliation")
    )
    workspace_coverage_degraded = bool(
        missing_workspace_recursion
        or duplicate_workspace_recursion
        or unexpected_workspace_recursion
    )
    semantic_observation, semantic_observation_error = (
        _validated_projection_observation(payload)
    )
    ops_projection_degraded = (
        payload.get("status") == "degraded"
        or not workspace_recursion
        or workspace_coverage_degraded
        or semantic_observation_error is not None
        or attempt_number < 1
        or attempt_id is None
        or shared_ops_reconciliation is None
    )
    projection_reason_codes = []
    if payload.get("status") == "degraded":
        projection_reason_codes.append("ops_cycle_degraded")
    if not workspace_recursion:
        projection_reason_codes.append("ops_conclusion_missing_workspace_recursion")
    if missing_workspace_recursion:
        projection_reason_codes.append(
            _MISSING_ACTIVE_WORKSPACE_RECURSION_REASON
        )
    if duplicate_workspace_recursion:
        projection_reason_codes.append(
            _DUPLICATE_WORKSPACE_RECURSION_REASON
        )
    if unexpected_workspace_recursion:
        projection_reason_codes.append(
            _UNEXPECTED_WORKSPACE_RECURSION_REASON
        )
    if semantic_observation_error is not None:
        projection_reason_codes.append("ops_conclusion_clock_unverified")
    if attempt_number < 1 or attempt_id is None:
        projection_reason_codes.append("ops_conclusion_attempt_missing")
    if shared_ops_reconciliation is None:
        projection_reason_codes.append(
            _MISSING_SHARED_OPS_RECONCILIATION_REASON
        )
    projected_warnings = [
        _bounded_text(item)
        for item in _list_value(payload.get("degraded_system_warnings"))[:MAX_ITEMS]
    ]
    if not workspace_recursion:
        projected_warnings.append(
            "The latest canonical Ops conclusion predates workspace-recursion truth; "
            "decision readiness remains separate, but workspace recursion is not ready."
        )
    if missing_workspace_recursion:
        projected_warnings.append(
            "The canonical Ops conclusion is missing active workspace recursion rows: "
            f"{', '.join(missing_workspace_recursion)}."
        )
    if duplicate_workspace_recursion:
        projected_warnings.append(
            "The canonical Ops conclusion repeated workspace recursion rows: "
            f"{', '.join(duplicate_workspace_recursion)}."
        )
    if unexpected_workspace_recursion:
        projected_warnings.append(
            "The canonical Ops conclusion included out-of-scope recursion rows that "
            "were excluded from the bounded projection: "
            f"{', '.join(unexpected_workspace_recursion)}."
        )
    if shared_ops_reconciliation is None:
        projected_warnings.append(
            "The latest canonical Ops conclusion does not contain the bounded "
            "Shared Ops reconciler summary; Shared Ops is not projected as a project row."
        )
    projected = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": generated_at,
        "state": "degraded" if ops_projection_degraded else "ready",
        "reason_codes": projection_reason_codes,
        "ops_conclusion_id": row["ops_conclusion_id"],
        "ops_conclusion_attempt_id": attempt_id,
        "ops_conclusion_attempt_number": attempt_number or None,
        "ops_conclusion_attempt_payload_sha256": attempt_payload_sha256,
        "portfolio_cycle_id": payload.get("portfolio_cycle_id"),
        "cycle_date": payload.get("cycle_date"),
        "observed_at": (
            payload.get("observed_at")
            if semantic_observation is not None
            else None
        ),
        "clock": (
            dict(payload.get("clock") or {})
            if semantic_observation is not None
            else None
        ),
        "status": payload.get("status"),
        "workspace_updates": _bounded_items(payload.get("workspace_updates")),
        "workspace_recursion": workspace_recursion,
        "shared_ops_reconciliation": shared_ops_reconciliation,
        "workspace_cycle_evaluations": _bounded_items(payload.get("workspace_cycle_evaluations")),
        "ai_clone_process_updates": _bounded_process_updates(payload.get("ai_clone_process_updates")),
        "endpoint_and_subsystem_health": _bounded_subsystem_health(payload.get("endpoint_and_subsystem_health")),
        "work_underway": _bounded_items(payload.get("work_underway")),
        "completed_work": _bounded_items(payload.get("completed_work")),
        "blockers": _bounded_items(payload.get("blockers")),
        "urgent_escalations": _bounded_items(payload.get("urgent_escalations")),
        "workspace_decisions": _bounded_items(payload.get("workspace_decisions")),
        "ops_decisions": _bounded_items(payload.get("ops_decisions")),
        "owner_calls": _bounded_items(payload.get("owner_calls")),
        "canonical_decisions": _bounded_canonical_decisions(canonical_decisions),
        "decision_readiness": {
            "schema_version": "canonical_decision_projection_readiness/v1",
            "state": "ready",
            "clock_authority": "ai_clone_utc",
            "checked_at": generated_at,
            "source_updated_at": decision_source_updated_at,
            "blocking_reason_codes": [],
            "context_warnings": [
                _bounded_text(item, limit=500) for item in projected_warnings[:20]
            ],
        },
        "degraded_system_warnings": projected_warnings[:MAX_ITEMS],
        "supporting_evidence_links": _bounded_items(payload.get("supporting_evidence_links"), evidence=True),
        "recommended_next_actions": _bounded_items(payload.get("recommended_next_actions")),
        "data_policy": dict(_EXPECTED_DATA_POLICY),
    }
    return validate_ops_standup_projection(projected)


def _upgrade_pre_reconciler_v3(payload: dict[str, Any]) -> dict[str, Any]:
    """Losslessly adapt the prior v3 shape after an additive owner-truth field.

    The only accepted compatibility shape is the exact former envelope and the
    exact former workspace-recursion row. Unknown fields still fail closed.
    A conclusion without the new reconciler truth is explicitly degraded; it
    can never be upgraded into a readiness claim.
    """

    if "shared_ops_reconciliation" in payload:
        return payload
    former_projection_fields = _PROJECTION_FIELDS - {"shared_ops_reconciliation"}
    if set(payload) != former_projection_fields:
        return payload
    former_recursion_fields = _WORKSPACE_RECURSION_FIELDS - {
        "recommendations",
        "reference_only",
    }
    upgraded = json.loads(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    recursion = upgraded.get("workspace_recursion")
    if not isinstance(recursion, list):
        return payload
    for item in recursion:
        if not isinstance(item, dict) or set(item) != former_recursion_fields:
            return payload
        item["recommendations"] = []
        item["reference_only"] = []
    upgraded["shared_ops_reconciliation"] = None
    if upgraded.get("ops_conclusion_id") is not None:
        upgraded["state"] = "degraded"
        reason_codes = upgraded.get("reason_codes")
        if not isinstance(reason_codes, list):
            return payload
        if _MISSING_SHARED_OPS_RECONCILIATION_REASON not in reason_codes:
            reason_codes.append(_MISSING_SHARED_OPS_RECONCILIATION_REASON)
        warnings = upgraded.get("degraded_system_warnings")
        if not isinstance(warnings, list):
            return payload
        warnings.append(
            "The stored v3 Ops projection predates the bounded Shared Ops "
            "reconciler summary and remains degraded until a canonical later cycle."
        )
    return upgraded


def validate_ops_standup_projection(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("schema_version") in {
        LEGACY_PROJECTION_SCHEMA,
        PRE_CLOCK_PROJECTION_SCHEMA,
    }:
        payload = _upgrade_legacy_projection(payload)
    elif isinstance(payload, dict) and payload.get("schema_version") == PROJECTION_SCHEMA:
        payload = _upgrade_pre_reconciler_v3(payload)
    if not isinstance(payload, dict) or payload.get("schema_version") != PROJECTION_SCHEMA:
        raise OpsStandupProjectionError("invalid Ops projection schema")
    if set(payload) != _PROJECTION_FIELDS or payload.get("state") not in {
        "ready",
        "empty",
        "degraded",
        "error",
    }:
        raise OpsStandupProjectionError("invalid Ops projection envelope")
    try:
        generated_at = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpsStandupProjectionError("invalid generated_at") from exc
    if generated_at.tzinfo is None or len(str(payload.get("generated_at") or "")) > 100:
        raise OpsStandupProjectionError("generated_at must be timezone aware")
    scalar_limits = {
        "ops_conclusion_id": 200,
        "ops_conclusion_attempt_id": 200,
        "ops_conclusion_attempt_payload_sha256": 64,
        "portfolio_cycle_id": 200,
        "cycle_date": 40,
        "observed_at": 100,
        "status": 80,
    }
    for key, limit in scalar_limits.items():
        cell = payload.get(key)
        if not isinstance(cell, (str, type(None))) or (
            isinstance(cell, str) and len(cell) > limit
        ):
            raise OpsStandupProjectionError(f"invalid Ops scalar {key}")
    for identity_field in ("ops_conclusion_id", "portfolio_cycle_id"):
        identity = payload.get(identity_field)
        if isinstance(identity, str) and (
            not identity or identity != identity.strip()
        ):
            raise OpsStandupProjectionError(
                f"invalid Ops identity {identity_field}"
            )
    semantic_observation, semantic_observation_error = (
        _validated_projection_observation(payload)
    )
    has_conclusion = payload.get("ops_conclusion_id") is not None
    attempt_id = payload.get("ops_conclusion_attempt_id")
    attempt_number = payload.get("ops_conclusion_attempt_number")
    attempt_payload_sha256 = payload.get("ops_conclusion_attempt_payload_sha256")
    attempt_missing = "ops_conclusion_attempt_missing" in (payload.get("reason_codes") or [])
    if has_conclusion and not attempt_missing:
        if (
            not isinstance(attempt_number, int)
            or isinstance(attempt_number, bool)
            or not 1 <= attempt_number <= 1_000_000
            or not isinstance(attempt_id, str)
            or attempt_id
            != str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"ai-clone:ops-attempt:{payload['ops_conclusion_id']}:{attempt_number}",
                )
            )
            or not isinstance(attempt_payload_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", attempt_payload_sha256) is None
        ):
            raise OpsStandupProjectionError("invalid canonical Ops conclusion attempt")
    elif any(
        value is not None
        for value in (attempt_id, attempt_number, attempt_payload_sha256)
    ):
        raise OpsStandupProjectionError("invalid missing Ops conclusion attempt")
    unverified_legacy_reasons = {
        "legacy_projection_missing_clock_receipt",
        "ops_conclusion_clock_unverified",
    }
    raw_reason_codes = payload.get("reason_codes")
    explicitly_unverified = bool(
        isinstance(raw_reason_codes, list)
        and any(item in unverified_legacy_reasons for item in raw_reason_codes)
    )
    if semantic_observation_error is not None:
        if not (
            payload.get("state") in {"empty", "degraded", "error"}
            and payload.get("observed_at") is None
            and payload.get("clock") is None
            and (not has_conclusion or explicitly_unverified)
        ):
            raise OpsStandupProjectionError(
                f"invalid Ops semantic observation: {semantic_observation_error}"
            )
    elif semantic_observation is None:
        raise OpsStandupProjectionError("invalid Ops semantic observation")
    if (
        not isinstance(payload.get("reason_codes"), list)
        or len(payload["reason_codes"]) > 20
        or any(
            not isinstance(item, str) or len(item) > 200
            for item in payload["reason_codes"]
        )
    ):
        raise OpsStandupProjectionError("invalid Ops reason codes")
    for key in (
        "workspace_updates",
        "workspace_cycle_evaluations",
        "work_underway",
        "completed_work",
        "blockers",
        "urgent_escalations",
        "workspace_decisions",
        "ops_decisions",
        "owner_calls",
        "supporting_evidence_links",
        "recommended_next_actions",
    ):
        if not isinstance(payload.get(key), list) or len(payload[key]) > MAX_ITEMS:
            raise OpsStandupProjectionError(f"invalid {key}")
        if any(
            not _valid_projected_item(
                item,
                allow_urls=key == "supporting_evidence_links",
            )
            for item in payload[key]
        ):
            raise OpsStandupProjectionError(f"invalid {key} item")
    workspace_recursion = payload.get("workspace_recursion")
    if not isinstance(workspace_recursion, list) or len(workspace_recursion) > MAX_WORKSPACE_RECURSION:
        raise OpsStandupProjectionError("invalid workspace_recursion")
    recursion_keys = [
        str(item.get("workspace_key") or "")
        for item in workspace_recursion
        if isinstance(item, dict)
    ]
    if len(recursion_keys) != len(set(recursion_keys)):
        raise OpsStandupProjectionError("duplicate workspace recursion key")
    for item in workspace_recursion:
        if (
            not isinstance(item, dict)
            or set(item) != _WORKSPACE_RECURSION_FIELDS
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", str(item.get("workspace_key") or ""))
            or not isinstance(item.get("display_name"), str)
            or not str(item.get("display_name") or "").strip()
            or len(item.get("display_name") or "") > 120
            or not isinstance(item.get("goal"), dict)
            or set(item["goal"]) - _GOAL_FIELDS
            or any(
                not isinstance(cell, str)
                or len(cell) > (2000 if key == "goal" else 500 if key == "schema_version" else 2000)
                for key, cell in item["goal"].items()
                if key != "progress_signals"
            )
            or (
                "progress_signals" in item["goal"]
                and (
                    not isinstance(item["goal"]["progress_signals"], list)
                    or len(item["goal"]["progress_signals"]) > 20
                    or any(
                        not isinstance(cell, str)
                        or len(cell) > 500
                        for cell in item["goal"]["progress_signals"]
                    )
                )
            )
        ):
            raise OpsStandupProjectionError("invalid workspace recursion item")
        for key in _WORKSPACE_RECURSION_LIST_FIELDS:
            if (
                not isinstance(item.get(key), list)
                or len(item[key]) > MAX_RECURSION_ITEMS
                or any(not _valid_projected_item(value) for value in item[key])
            ):
                raise OpsStandupProjectionError(f"invalid workspace recursion {key}")
    shared_ops_reconciliation = payload.get("shared_ops_reconciliation")
    shared_ops_goal_complete = False
    if shared_ops_reconciliation is not None:
        if (
            not isinstance(shared_ops_reconciliation, dict)
            or set(shared_ops_reconciliation)
            != _SHARED_OPS_RECONCILIATION_FIELDS
            or not isinstance(shared_ops_reconciliation.get("display_name"), str)
            or not str(shared_ops_reconciliation.get("display_name") or "").strip()
            or len(shared_ops_reconciliation.get("display_name") or "") > 120
            or shared_ops_reconciliation.get("role") != "portfolio_reconciler"
            or not isinstance(shared_ops_reconciliation.get("summary"), str)
            or not str(shared_ops_reconciliation.get("summary") or "").strip()
            or len(shared_ops_reconciliation.get("summary") or "") > 1000
            or not isinstance(shared_ops_reconciliation.get("goal"), dict)
            or set(shared_ops_reconciliation["goal"]) - _GOAL_FIELDS
        ):
            raise OpsStandupProjectionError(
                "invalid Shared Ops reconciliation"
            )
        shared_goal = shared_ops_reconciliation["goal"]
        if any(
            not isinstance(cell, str)
            or len(cell) > (2000 if key == "goal" else 500 if key == "schema_version" else 2000)
            for key, cell in shared_goal.items()
            if key != "progress_signals"
        ) or (
            "progress_signals" in shared_goal
            and (
                not isinstance(shared_goal["progress_signals"], list)
                or len(shared_goal["progress_signals"]) > 20
                or any(
                    not isinstance(cell, str) or len(cell) > 500
                    for cell in shared_goal["progress_signals"]
                )
            )
        ):
            raise OpsStandupProjectionError(
                "invalid Shared Ops reconciliation goal"
            )
        shared_ops_goal_complete = (
            set(shared_goal) == _GOAL_FIELDS
            and shared_goal.get("schema_version") == "workspace_goal_contract/v1"
            and bool(str(shared_goal.get("goal") or "").strip())
            and bool(shared_goal.get("progress_signals"))
            and bool(str(shared_goal.get("phase_gate") or "").strip())
            and bool(str(shared_goal.get("no_action_trigger") or "").strip())
        )
        for key in _SHARED_OPS_RECONCILIATION_LIST_FIELDS:
            if (
                not isinstance(shared_ops_reconciliation.get(key), list)
                or len(shared_ops_reconciliation[key]) > MAX_RECURSION_ITEMS
                or any(
                    not _valid_projected_item(
                        value,
                        allow_urls=key == "reference_only",
                    )
                    for value in shared_ops_reconciliation[key]
                )
            ):
                raise OpsStandupProjectionError(
                    f"invalid Shared Ops reconciliation {key}"
                )
    active_workspace_keys = _active_project_workspace_keys()
    active_workspace_set = set(active_workspace_keys)
    recursion_key_set = set(recursion_keys)
    unexpected_recursion_keys = sorted(
        recursion_key_set - active_workspace_set
    )
    missing_recursion_keys = [
        key for key in active_workspace_keys if key not in recursion_key_set
    ]
    if unexpected_recursion_keys:
        raise OpsStandupProjectionError(
            "unexpected workspace recursion key outside the active project registry: "
            f"{', '.join(unexpected_recursion_keys)}"
        )
    exact_active_workspace_coverage = (
        len(recursion_keys) == len(active_workspace_keys)
        and recursion_key_set == active_workspace_set
    )
    state = str(payload.get("state") or "")
    status = str(payload.get("status") or "")
    reason_codes = payload.get("reason_codes") or []
    if status not in {"complete", "degraded", "empty", "error"}:
        raise OpsStandupProjectionError("invalid Ops status")
    if state == "ready":
        if (
            status != "complete"
            or reason_codes
            or not has_conclusion
            or not workspace_recursion
            or not exact_active_workspace_coverage
            or shared_ops_reconciliation is None
            or not shared_ops_goal_complete
            or semantic_observation is None
            or attempt_missing
        ):
            raise OpsStandupProjectionError("incoherent ready Ops projection")
    elif state == "degraded":
        if not reason_codes or status not in {"complete", "degraded"}:
            raise OpsStandupProjectionError("incoherent degraded Ops projection")
        if not has_conclusion and workspace_recursion:
            raise OpsStandupProjectionError(
                "workspace recursion requires a canonical Ops conclusion"
            )
        if (
            status == "degraded"
            and has_conclusion
            and "ops_cycle_degraded" not in reason_codes
        ):
            raise OpsStandupProjectionError(
                "degraded canonical Ops status requires its reason code"
            )
        if (
            has_conclusion
            and missing_recursion_keys
            and not {
                _MISSING_ACTIVE_WORKSPACE_RECURSION_REASON,
                "ops_conclusion_missing_workspace_recursion",
                "legacy_projection_missing_workspace_recursion",
            }.intersection(reason_codes)
        ):
            raise OpsStandupProjectionError(
                "missing active workspace recursion requires its reason code"
            )
        if (
            has_conclusion
            and shared_ops_reconciliation is None
            and _MISSING_SHARED_OPS_RECONCILIATION_REASON not in reason_codes
        ):
            raise OpsStandupProjectionError(
                "missing Shared Ops reconciliation requires its reason code"
            )
    elif state in {"empty", "error"}:
        if (
            status != state
            or not reason_codes
            or has_conclusion
            or workspace_recursion
            or shared_ops_reconciliation is not None
        ):
            raise OpsStandupProjectionError(
                f"incoherent {state} Ops projection"
            )
    if "ops_cycle_degraded" in reason_codes and (
        state != "degraded" or status != "degraded"
    ):
        raise OpsStandupProjectionError("incoherent Ops degradation reason")
    process_updates = payload.get("ai_clone_process_updates")
    if not isinstance(process_updates, dict) or set(process_updates) - _PROCESS_UPDATE_FIELDS:
        raise OpsStandupProjectionError("invalid AI Clone process updates")
    if not isinstance(process_updates.get("morning_brief_ref"), (str, type(None))) or (
        isinstance(process_updates.get("morning_brief_ref"), str)
        and len(process_updates["morning_brief_ref"]) > 1000
    ):
        raise OpsStandupProjectionError("invalid morning brief reference")
    readiness_update = process_updates.get("memory_readiness")
    if readiness_update is not None and (
        not isinstance(readiness_update, dict)
        or set(readiness_update) - _MEMORY_READINESS_FIELDS
        or any(
            not isinstance(cell, (str, int, float, bool, type(None)))
            or (isinstance(cell, float) and not math.isfinite(cell))
            or (isinstance(cell, str) and len(cell) > 1000)
            for cell in readiness_update.values()
        )
    ):
        raise OpsStandupProjectionError("invalid memory readiness update")
    health = payload.get("endpoint_and_subsystem_health")
    if not isinstance(health, dict) or len(health) > MAX_ITEMS or any(
        not _SAFE_SUBSYSTEM_NAME_RE.fullmatch(str(key)) or value not in _SAFE_SUBSYSTEM_STATES
        for key, value in health.items()
    ):
        raise OpsStandupProjectionError("invalid endpoint and subsystem health")
    canonical_decisions = payload.get("canonical_decisions")
    if not isinstance(canonical_decisions, list) or len(canonical_decisions) > MAX_ITEMS:
        raise OpsStandupProjectionError("invalid canonical_decisions")
    if any(not _valid_canonical_decision(item) for item in canonical_decisions):
        raise OpsStandupProjectionError("invalid canonical decision projection")
    decision_ids = [str(item["decision_id"]) for item in canonical_decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise OpsStandupProjectionError("duplicate canonical decision identity")
    decision_readiness = payload.get("decision_readiness")
    if (
        not isinstance(decision_readiness, dict)
        or set(decision_readiness)
        != {
            "schema_version",
            "state",
            "clock_authority",
            "checked_at",
            "source_updated_at",
            "blocking_reason_codes",
            "context_warnings",
        }
        or decision_readiness.get("schema_version") != "canonical_decision_projection_readiness/v1"
        or decision_readiness.get("state") not in {"ready", "degraded"}
        or decision_readiness.get("clock_authority") != "ai_clone_utc"
        or not isinstance(decision_readiness.get("blocking_reason_codes"), list)
        or len(decision_readiness.get("blocking_reason_codes") or []) > 20
        or any(
            not isinstance(item, str) or len(item) > 200
            for item in decision_readiness.get("blocking_reason_codes") or []
        )
        or not isinstance(decision_readiness.get("context_warnings"), list)
        or len(decision_readiness.get("context_warnings") or []) > 20
        or any(
            not isinstance(item, str) or len(item) > 500
            for item in decision_readiness.get("context_warnings") or []
        )
        or (
            decision_readiness.get("state") == "ready"
            and bool(decision_readiness.get("blocking_reason_codes"))
        )
    ):
        raise OpsStandupProjectionError("invalid canonical decision readiness")
    if not _aware_iso(decision_readiness.get("checked_at")) or not _aware_iso(
        decision_readiness.get("source_updated_at"), allow_none=True
    ):
        raise OpsStandupProjectionError("invalid canonical decision readiness timestamp")
    if payload.get("data_policy") != _EXPECTED_DATA_POLICY:
        raise OpsStandupProjectionError("invalid Ops data policy")
    if (
        not isinstance(payload.get("degraded_system_warnings"), list)
        or len(payload["degraded_system_warnings"]) > MAX_ITEMS
        or any(
            not isinstance(item, str) or len(item) > 1000
            for item in payload["degraded_system_warnings"]
        )
    ):
        raise OpsStandupProjectionError("invalid degraded system warnings")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if (
        len(serialized.encode("utf-8")) > MAX_BYTES
        or contains_private_filesystem_reference(serialized)
        or sanitize_brain_text(serialized) != serialized
        or any(
            token in serialized.lower()
            for token in ("file://", "transcript", "private_notes", "raw_body", "source_path")
        )
    ):
        raise OpsStandupProjectionError("Ops projection contains private or oversized material")
    return payload


def ops_projection_semantic_sha256(payload: dict[str, Any]) -> str:
    """Hash canonical projection meaning without projection-receipt timestamps.

    ``generated_at`` and readiness ``checked_at`` describe when the bounded
    Railway projection was built or checked. They are not a newer Ops
    observation and cannot turn an unchanged canonical conclusion attempt into
    a conflicting semantic payload on retry.
    """

    semantic_payload = json.loads(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    semantic_payload.pop("generated_at", None)
    decision_readiness = semantic_payload.get("decision_readiness")
    if isinstance(decision_readiness, dict):
        decision_readiness.pop("checked_at", None)
    return hashlib.sha256(
        json.dumps(
            semantic_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def unavailable_ops_standup_projection(
    reason: str,
    *,
    state: str = "degraded",
    canonical_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA, "generated_at": _now_iso(), "state": state, "reason_codes": [reason],
        "ops_conclusion_id": None, "ops_conclusion_attempt_id": None,
        "ops_conclusion_attempt_number": None, "ops_conclusion_attempt_payload_sha256": None,
        "portfolio_cycle_id": None, "cycle_date": None, "status": state,
        "observed_at": None, "clock": None, "workspace_updates": [], "workspace_recursion": [], "shared_ops_reconciliation": None, "workspace_cycle_evaluations": [], "ai_clone_process_updates": {}, "endpoint_and_subsystem_health": {},
        "work_underway": [], "completed_work": [], "blockers": [], "urgent_escalations": [],
        "workspace_decisions": [], "ops_decisions": [], "owner_calls": [],
        "canonical_decisions": _bounded_canonical_decisions(canonical_decisions or []), "degraded_system_warnings": [],
        "decision_readiness": {
            "schema_version": "canonical_decision_projection_readiness/v1",
            "state": "degraded",
            "clock_authority": "ai_clone_utc",
            "checked_at": _now_iso(),
            "source_updated_at": None,
            "blocking_reason_codes": [reason],
            "context_warnings": [],
        },
        "supporting_evidence_links": [], "recommended_next_actions": [],
        "data_policy": dict(_EXPECTED_DATA_POLICY),
    }
