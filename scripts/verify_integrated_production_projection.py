#!/usr/bin/env python3
"""Verify the deployed owner projection proves the integrated content/Ops story."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class ProjectionVerificationError(AssertionError):
    pass


CONTENT_KEYS = {
    "schema_version",
    "generated_at",
    "state",
    "reason_codes",
    "counts",
    "sources",
    "opportunities",
    "posts",
    "activity_summary",
    "controller_capabilities",
    "controller_gaps",
    "data_policy",
}
OPS_KEYS = {
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
WORKSPACE_GOAL_FIELDS = frozenset(
    {
        "schema_version",
        "goal",
        "progress_signals",
        "phase_gate",
        "no_action_trigger",
    }
)
WORKSPACE_RECURSION_FIELDS = frozenset(
    {
        "workspace_key",
        "display_name",
        "goal",
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
    }
)
SHARED_OPS_RECONCILIATION_LIST_FIELDS = (
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
SHARED_OPS_RECONCILIATION_FIELDS = frozenset(
    {
        "display_name",
        "role",
        "summary",
        "goal",
        *SHARED_OPS_RECONCILIATION_LIST_FIELDS,
    }
)
SHARED_OPS_RECONCILIATION_ACTION_FIELDS = frozenset(
    {"kind", "summary", "status"}
)
MAX_RECURSION_ITEMS = 20
ACTIVE_WORKSPACE_STATUSES = {"live", "standing_up"}
RECOMMENDATION_RESOLUTION_STATES = {
    "executed_automatically",
    "scheduled_in_existing_canonical_scheduler",
    "placed_in_execution_queue",
    "bounded_owner_decision",
    "blocked",
    "rejected_by_policy",
    "intentionally_retained",
}
CONTENT_STRUCTURE_COUNT_MINIMUMS = {
    "sources": 1,
    "discoveries": 2,
    "evidence": 1,
    "interpretations": 1,
    "opportunities": 1,
    "posts": 1,
    "revisions": 2,
}
CONTENT_LIFECYCLE_COUNT_MINIMUMS = {
    "learning_events": 3,
    "persona_candidates": 1,
}
STRICT_LIFECYCLE_EVENT_KINDS = frozenset({"owner_approved", "publication_confirmed"})
PROJECTED_LEARNING_RECEIPT_KEYS = frozenset(
    {
        "learning_event_id",
        "revision_id",
        "event_kind",
        "edit_classification",
        "occurred_at",
        "summary",
    }
)
PROJECTED_PERSONA_CANDIDATE_KEYS = frozenset(
    {
        "persona_candidate_id",
        "candidate_kind",
        "status",
        "claim",
        "evidence_count",
        "qualifying_post_count",
        "independent_context_count",
        "automatic_promotion_eligible",
        "lifecycle_authority",
        "promotion",
        "updated_at",
    }
)
PROJECTED_DECISION_KEYS = frozenset(
    {
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
)
CONTENT_DECISION_PROJECTION_LIMIT = 50
OPS_DECISION_PROJECTION_LIMIT = 100
NON_BLOCKING_OPS_HEALTH_KEYS = frozenset({"backup_recovery", "firestore_readiness"})
OPS_HEALTHY_SUBSYSTEM_STATES = frozenset(
    {"ready", "healthy", "complete", "completed", "available", "ok"}
)
OPS_UNHEALTHY_SUBSYSTEM_STATES = frozenset(
    {"degraded", "failed", "unhealthy", "not_verified", "unavailable", "unknown"}
)
CONTROLLER_CAPABILITIES = frozenset(
    {
        "owner_requested_post",
        "portfolio_selected_drafting",
        "variant_generation",
        "variant_selection",
        "variant_rejection",
        "manual_edit_classification",
        "owner_approval",
        "publication_confirmation",
        "persona_promotion",
        "persona_reversal",
        "decision_resolution",
    }
)
QUEUE_BACKED_CONTROLLER_CAPABILITIES = frozenset(
    {
        "owner_requested_post",
        "variant_generation",
        "variant_selection",
        "variant_rejection",
        "manual_edit_classification",
        "owner_approval",
        "publication_confirmation",
        "persona_reversal",
        "decision_resolution",
    }
)


def classify_ops_subsystem_health(system_health: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the closed Ops health taxonomy and fail closed on drift."""

    normalized_health: dict[str, str] = {}
    for raw_key, raw_value in system_health.items():
        key = str(raw_key).strip().lower()
        value = raw_value
        if isinstance(value, bool):
            state = "healthy" if value else "failed"
        else:
            if isinstance(value, Mapping):
                value = value.get("state") or value.get("status")
            state = str(value or "unknown").strip().lower().replace(" ", "_")
            if state.startswith("failed:"):
                state = "failed"
            elif state.startswith("degraded:"):
                state = "degraded"
        if (
            state not in OPS_HEALTHY_SUBSYSTEM_STATES
            and state not in OPS_UNHEALTHY_SUBSYSTEM_STATES
        ):
            state = "unknown"
        normalized_health[key] = state
    unhealthy_keys = sorted(
        key
        for key, state in normalized_health.items()
        if state not in OPS_HEALTHY_SUBSYSTEM_STATES
    )
    warning_only_keys = sorted(
        set(unhealthy_keys).intersection(NON_BLOCKING_OPS_HEALTH_KEYS)
    )
    blocking_keys = sorted(set(unhealthy_keys) - NON_BLOCKING_OPS_HEALTH_KEYS)
    return {
        "normalized_health": dict(sorted(normalized_health.items())),
        "unhealthy_keys": unhealthy_keys,
        "warning_only_keys": warning_only_keys,
        "blocking_keys": blocking_keys,
    }
CONTROLLER_DEGRADED_REASON_CODES = frozenset(
    {
        "signed_job_authorization_unavailable",
        "controller_database_unavailable",
        "controller_queue_unavailable",
        "controller_worker_unavailable",
    }
)
CONTROLLER_SAFE_BEHAVIOR = (
    "The owner action remains disabled until the signed local-action queue is ready."
)
PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "file://",
    "AI_CLONE_STATE_ROOT",
    "BEGIN PRIVATE KEY",
    "private_notes",
    "transcript_body",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectionVerificationError(message)


def _active_registry_workspace_keys(registry: dict[str, Any]) -> set[str]:
    _require(
        isinstance(registry, dict)
        and registry.get("schema_version") == "workspace_registry/v2"
        and isinstance(registry.get("workspaces"), list),
        "Structural workspace registry projection is missing or invalid",
    )
    active: list[str] = []
    forbidden_goal_fields = {
        "goal_contract",
        "goal_contract_source_path",
        "goal_contract_observed_at",
        "goal_contract_authority_sha256",
        "safe_internal_boundary",
        "owner_required_boundary",
        "authority_refs",
    }
    for raw in registry["workspaces"]:
        _require(isinstance(raw, dict), "Structural workspace registry contains a non-object entry")
        _require(
            not (forbidden_goal_fields & set(raw)),
            "Structural workspace registry leaked private goal authority fields",
        )
        if (
            raw.get("kind") == "workspace"
            and raw.get("portfolio_visible") is True
            and str(raw.get("status") or "") in ACTIVE_WORKSPACE_STATUSES
        ):
            key = str(raw.get("key") or "").strip()
            _require(
                bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key)),
                "Structural workspace registry contains an invalid active key",
            )
            active.append(key)
    _require(bool(active), "Structural workspace registry has no active project workspaces")
    _require(len(active) == len(set(active)), "Structural workspace registry duplicates an active key")
    _verify_privacy(registry, label="Structural workspace registry")
    return set(active)


def _string_set(value: Any) -> set[str]:
    return {
        str(item)
        for item in value
        if isinstance(value, list) and isinstance(item, str) and item
    } if isinstance(value, list) else set()


def _verify_privacy(payload: dict[str, Any], *, label: str) -> None:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    _require(
        not any(marker.lower() in rendered.lower() for marker in PRIVATE_MARKERS),
        f"{label} projection contains private implementation material",
    )


def _verify_controller_health(content: dict[str, Any]) -> dict[str, Any]:
    capabilities = content.get("controller_capabilities")
    _require(
        isinstance(capabilities, dict)
        and set(capabilities) == CONTROLLER_CAPABILITIES
        and all(isinstance(value, bool) for value in capabilities.values()),
        "content controller capabilities are open or incomplete",
    )
    gaps = content.get("controller_gaps")
    _require(isinstance(gaps, list), "content controller gaps are missing")
    state = content.get("state")
    reason_codes = content.get("reason_codes")
    _require(
        isinstance(reason_codes, list)
        and all(isinstance(code, str) and code for code in reason_codes),
        "content degradation reasons are malformed",
    )

    if state == "ready":
        _require(reason_codes == [], "ready content projection has degradation reasons")
        _require(all(capabilities.values()), "ready content projection disables controller actions")
        _require(gaps == [], "ready content projection has controller gaps")
        return {
            "controller_action_readiness": "ready",
            "controller_reason_codes": [],
        }

    _require(state == "degraded", f"content projection is {state}")
    reason_set = set(reason_codes)
    _require(
        bool(reason_set) and reason_set <= CONTROLLER_DEGRADED_REASON_CODES,
        "content degradation is not controller-only",
    )
    disabled = {key for key, available in capabilities.items() if not available}
    _require(
        disabled == QUEUE_BACKED_CONTROLLER_CAPABILITIES,
        "controller-only degradation does not disable the exact queue-backed actions",
    )
    _require(
        all(capabilities[key] is True for key in CONTROLLER_CAPABILITIES - disabled),
        "controller-only degradation disables local deterministic capabilities",
    )
    gap_capabilities: set[str] = set()
    gap_reasons: set[str] = set()
    for gap in gaps:
        _require(
            isinstance(gap, dict)
            and set(gap) == {"capability", "reason_code", "safe_behavior"},
            "content controller gap shape is open or incomplete",
        )
        capability = str(gap.get("capability") or "")
        reason_code = str(gap.get("reason_code") or "")
        _require(
            capability in disabled and capability not in gap_capabilities,
            "content controller gaps do not bind each disabled capability exactly once",
        )
        _require(
            reason_code in CONTROLLER_DEGRADED_REASON_CODES,
            "content controller gap has an unsafe degradation reason",
        )
        _require(
            gap.get("safe_behavior") == CONTROLLER_SAFE_BEHAVIOR,
            "content controller gap does not preserve the fail-closed behavior",
        )
        gap_capabilities.add(capability)
        gap_reasons.add(reason_code)
    _require(
        gap_capabilities == disabled,
        "content controller gaps do not cover the disabled action set",
    )
    _require(
        gap_reasons == reason_set,
        "content degradation reasons do not match the controller gaps",
    )
    return {
        "controller_action_readiness": "degraded",
        "controller_reason_codes": sorted(reason_set),
    }


def _content_lifecycle_evidence(
    *,
    counts: dict[str, Any],
    projected_learning_event_count: int,
    projected_persona_candidate_count: int,
    event_kinds: set[str],
    classified_edit_seen: bool,
) -> dict[str, Any]:
    lifecycle_counts: dict[str, int] = {}
    for key in CONTENT_LIFECYCLE_COUNT_MINIMUMS:
        value = counts.get(key)
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"content lifecycle count {key}={value!r} is invalid",
        )
        lifecycle_counts[key] = value
    _require(
        lifecycle_counts["learning_events"] >= projected_learning_event_count,
        "content learning count is smaller than the projected canonical receipts",
    )
    _require(
        lifecycle_counts["persona_candidates"] >= projected_persona_candidate_count,
        "content Persona count is smaller than the projected canonical candidates",
    )

    strict_event_kinds = STRICT_LIFECYCLE_EVENT_KINDS & event_kinds
    requirements = {
        "canonical_content_learning_receipts": (
            lifecycle_counts["learning_events"]
            >= CONTENT_LIFECYCLE_COUNT_MINIMUMS["learning_events"]
            and projected_learning_event_count
            >= CONTENT_LIFECYCLE_COUNT_MINIMUMS["learning_events"]
        ),
        "persona_candidate": (
            lifecycle_counts["persona_candidates"]
            >= CONTENT_LIFECYCLE_COUNT_MINIMUMS["persona_candidates"]
            and projected_persona_candidate_count
            >= CONTENT_LIFECYCLE_COUNT_MINIMUMS["persona_candidates"]
        ),
        "classified_owner_edit": classified_edit_seen,
        "owner_approval": "owner_approved" in strict_event_kinds,
        "publication_confirmation": "publication_confirmed" in strict_event_kinds,
    }
    reason_by_requirement = {
        "canonical_content_learning_receipts": "canonical_content_learning_receipts_not_proven",
        "persona_candidate": "persona_candidate_not_proven",
        "classified_owner_edit": "classified_owner_edit_not_proven",
        "owner_approval": "owner_approval_not_proven",
        "publication_confirmation": "publication_confirmation_not_proven",
    }
    reason_codes = [
        reason_by_requirement[key]
        for key, proven in requirements.items()
        if not proven
    ]
    return {
        "status": "open" if reason_codes else "passed",
        "reason_codes": reason_codes,
        "requirements": requirements,
    }


def _projected_persona_candidate_id(value: Any) -> str:
    _require(
        isinstance(value, dict) and set(value) == PROJECTED_PERSONA_CANDIDATE_KEYS,
        "projected Persona candidate is malformed",
    )
    candidate_id = str(value.get("persona_candidate_id") or "").strip()
    _require(candidate_id, "projected Persona candidate has no canonical identity")
    _require(
        bool(str(value.get("candidate_kind") or "").strip())
        and bool(str(value.get("status") or "").strip())
        and isinstance(value.get("claim"), dict)
        and all(
            isinstance(value.get(key), int) and not isinstance(value.get(key), bool)
            and value.get(key) >= 0
            for key in (
                "evidence_count",
                "qualifying_post_count",
                "independent_context_count",
            )
        )
        and isinstance(value.get("automatic_promotion_eligible"), bool)
        and value.get("lifecycle_authority") == "canonical_content_learning_events/v1"
        and isinstance(value.get("updated_at"), str)
        and bool(value["updated_at"].strip())
        and isinstance(value.get("promotion"), (dict, type(None))),
        "projected Persona candidate is not canonically bound",
    )
    return candidate_id


def _validated_decision_rows(
    value: Any,
    *,
    label: str,
    canonical_count: int,
    projection_limit: int,
) -> list[dict[str, Any]]:
    _require(isinstance(value, list), f"{label} canonical decisions are malformed")
    _require(
        len(value) == min(canonical_count, projection_limit),
        f"{label} canonical decision rows do not match the canonical count and bound",
    )
    rows: list[dict[str, Any]] = []
    decision_ids: set[str] = set()
    for item in value:
        _require(
            isinstance(item, dict)
            and set(item) == PROJECTED_DECISION_KEYS
            and bool(str(item.get("decision_id") or "").strip())
            and bool(str(item.get("decision_type") or "").strip())
            and bool(str(item.get("status") or "").strip())
            and bool(str(item.get("title") or "").strip())
            and isinstance(item.get("state_version"), int)
            and not isinstance(item.get("state_version"), bool)
            and item["state_version"] >= 1
            and item.get("interaction_mode") in {"simple", "complex"}
            and bool(str(item.get("route") or "").strip())
            and isinstance(item.get("resolution"), dict)
            and isinstance(item.get("session_ref"), (str, type(None)))
            and isinstance(item.get("updated_at"), str)
            and bool(item["updated_at"].strip())
            and isinstance(item.get("links"), list),
            f"{label} canonical decision row is malformed",
        )
        decision_id = str(item["decision_id"])
        _require(
            decision_id not in decision_ids,
            f"{label} canonical decision identity is duplicated",
        )
        decision_ids.add(decision_id)
        rows.append(item)
    return rows


def _decision_reconciliation_binding(value: dict[str, Any]) -> dict[str, Any]:
    resolution = value.get("resolution")
    safe_resolution = (
        {"choice": resolution["choice"]}
        if isinstance(resolution, dict) and "choice" in resolution
        else {}
    )
    return {
        "decision_id": value["decision_id"],
        "decision_type": value["decision_type"],
        "status": value["status"],
        "title": value["title"],
        "state_version": value["state_version"],
        "interaction_mode": value["interaction_mode"],
        "route": value["route"],
        "resolution": safe_resolution,
        "session_ref": value["session_ref"],
        "updated_at": value["updated_at"],
        "links": value["links"],
    }


def _verify_content(content: dict[str, Any]) -> dict[str, Any]:
    _require(set(content) == CONTENT_KEYS, "integrated content projection shape is open or incomplete")
    _require(content.get("schema_version") == "integrated_content_portfolio/v1", "wrong content schema")
    controller_health = _verify_controller_health(content)
    _require(
        content.get("data_policy")
        == {
            "canonical_authority": "mac_local_sql",
            "railway_role": "authenticated_bounded_review_projection",
            "raw_sources_included": False,
            "private_paths_included": False,
            "exact_review_copy_included": True,
            "bounded_evidence_references_included": True,
        },
        "content authority or privacy policy is wrong",
    )
    counts = content.get("counts")
    _require(isinstance(counts, dict), "content counts are missing")
    for key, minimum in CONTENT_STRUCTURE_COUNT_MINIMUMS.items():
        value = counts.get(key)
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
            f"content count {key}={value!r} does not prove the complete story",
        )

    sources = content.get("sources")
    opportunities = content.get("opportunities")
    posts = content.get("posts")
    _require(isinstance(sources, list) and sources, "no source lineage is projected")
    _require(isinstance(opportunities, list) and opportunities, "no content opportunity is projected")
    _require(isinstance(posts, list) and posts, "no canonical post is projected")

    source_ids: set[str] = set()
    evidence_ids: set[str] = set()
    interpretation_ids: set[str] = set()
    duplicate_route_source_seen = False
    for source in sources:
        _require(isinstance(source, dict), "source row is not structured")
        source_id = str(source.get("source_id") or "")
        _require(source_id and source_id not in source_ids, "source identity is missing or duplicated")
        source_ids.add(source_id)
        discoveries = source.get("discoveries")
        _require(isinstance(discoveries, list) and discoveries, "source has no discovery event")
        origins = {str(item.get("origin") or "") for item in discoveries if isinstance(item, dict)}
        if len(discoveries) >= 2 and len(origins) >= 2:
            duplicate_route_source_seen = True
        capture = source.get("capture")
        _require(isinstance(capture, dict) and capture.get("captured") is True, "source capture is not verified")
        digest = str(capture.get("content_sha256") or "")
        _require(len(digest) == 64 and all(char in "0123456789abcdef" for char in digest), "source hash is invalid")
        evidence_rows = source.get("evidence")
        _require(isinstance(evidence_rows, list) and evidence_rows, "source evidence is missing")
        for evidence in evidence_rows:
            evidence_id = str(evidence.get("evidence_id") or "")
            _require(evidence_id and evidence_id not in evidence_ids, "evidence identity is missing or duplicated")
            evidence_ids.add(evidence_id)
            _require(evidence.get("references"), "evidence has no source-bound reference")
            interpretations = evidence.get("interpretations")
            _require(isinstance(interpretations, list) and interpretations, "evidence has no named interpretation")
            for interpretation in interpretations:
                interpretation_id = str(interpretation.get("interpretation_id") or "")
                _require(
                    interpretation_id and interpretation_id not in interpretation_ids,
                    "interpretation identity is missing or duplicated",
                )
                interpretation_ids.add(interpretation_id)
                _require(
                    interpretation.get("provenance_kind")
                    in {"independent_agent", "deterministic_policy", "synthesized_lens"},
                    "interpretation provenance is invalid",
                )
    _require(duplicate_route_source_seen, "no canonical source preserves multiple discovery origins")

    opportunity_by_id: dict[str, dict[str, Any]] = {}
    selected_seen = False
    for opportunity in opportunities:
        opportunity_id = str(opportunity.get("opportunity_id") or "")
        _require(opportunity_id and opportunity_id not in opportunity_by_id, "opportunity identity is missing or duplicated")
        opportunity_by_id[opportunity_id] = opportunity
        lineage = opportunity.get("lineage") or {}
        _require(_string_set(lineage.get("source_ids")) <= source_ids, "opportunity references an unknown source")
        _require(_string_set(lineage.get("evidence_ids")) <= evidence_ids, "opportunity references unknown evidence")
        _require(
            _string_set(lineage.get("interpretation_ids")) <= interpretation_ids,
            "opportunity references an unknown interpretation",
        )
        _require(_string_set(lineage.get("source_ids")), "opportunity has no source lineage")
        _require(_string_set(lineage.get("evidence_ids")), "opportunity has no evidence lineage")
        _require(_string_set(lineage.get("interpretation_ids")), "opportunity has no interpretation lineage")
        if isinstance(opportunity.get("selection"), dict) and opportunity["selection"].get("disposition") == "selected":
            selected_seen = True
    _require(selected_seen, "portfolio selection did not select an opportunity")

    event_kinds: set[str] = set()
    classified_edit_seen = False
    variant_seen = False
    linked_revision_family_seen = False
    attribution_seen = False
    complete_post_seen = False
    projected_learning_event_ids: set[str] = set()
    projected_persona_candidate_ids: set[str] = set()
    for post in posts:
        post_id = str(post.get("post_id") or "")
        opportunity_id = str(post.get("opportunity_id") or "")
        _require(post_id and opportunity_id in opportunity_by_id, "post is not bound to a known opportunity")
        revisions = post.get("revisions")
        _require(isinstance(revisions, list) and revisions, "post has no base revision")
        revision_ids = {str(item.get("revision_id") or "") for item in revisions if isinstance(item, dict)}
        _require("" not in revision_ids and len(revision_ids) == len(revisions), "revision identities are invalid")
        _require(post.get("current_revision_id") in revision_ids, "current revision is outside the post family")
        base_revisions = [
            item for item in revisions
            if isinstance(item, dict) and item.get("revision_kind") == "base"
        ]
        _require(len(base_revisions) == 1, "post must preserve exactly one base revision")
        _require(
            base_revisions[0].get("parent_revision_id") in {None, ""},
            "base revision cannot have a parent",
        )
        if len(revisions) == 1:
            _require(
                post.get("current_revision_id") == base_revisions[0].get("revision_id"),
                "single-base post current revision is invalid",
            )
        else:
            linked_revision_family_seen = True
        for revision in revisions:
            body = revision.get("body")
            digest = str(revision.get("content_sha256") or "")
            _require(isinstance(body, str) and body.strip(), "projected review revision has no body")
            _require(hashlib.sha256(body.encode("utf-8")).hexdigest() == digest, "revision bytes do not match their hash")
            if revision.get("revision_kind") != "base":
                _require(
                    str(revision.get("parent_revision_id") or "") in revision_ids,
                    "derived revision parent is outside the post family",
                )
            if revision.get("revision_kind") == "variant":
                parent_id = str(revision.get("parent_revision_id") or "")
                _require(parent_id in revision_ids, "variant parent is outside the revision family")
                _require(isinstance(revision.get("controls"), dict) and revision["controls"], "variant controls are missing")
                _require(revision.get("platform") in {"linkedin", "instagram"}, "variant platform is unsupported")
                variant_seen = True
            attribution = revision.get("attribution") or {}
            if (
                attribution.get("required") is True
                and str(attribution.get("public_source_name") or "").strip()
                and str(attribution.get("public_source_url") or "").startswith(("http://", "https://"))
            ):
                attribution_seen = True
        events = post.get("learning_events")
        _require(isinstance(events, list), "learning events are not projected")
        for event in events:
            _require(
                isinstance(event, dict)
                and set(event) == PROJECTED_LEARNING_RECEIPT_KEYS
                and bool(str(event.get("learning_event_id") or "").strip())
                and bool(str(event.get("event_kind") or "").strip())
                and str(event.get("revision_id") or "") in revision_ids
                and isinstance(event.get("occurred_at"), str)
                and bool(event["occurred_at"].strip())
                and isinstance(event.get("summary"), dict),
                "projected learning receipt is malformed",
            )
            learning_event_id = str(event["learning_event_id"])
            _require(
                learning_event_id not in projected_learning_event_ids,
                "projected learning receipt identity is duplicated",
            )
            projected_learning_event_ids.add(learning_event_id)
            event_kinds.add(str(event.get("event_kind") or ""))
            if event.get("edit_classification") in {
                "factual_correction",
                "voice",
                "audience",
                "strategy",
                "evidence_or_attribution",
                "safety_or_privacy",
                "platform",
                "worldview",
                "one_off_preference",
            }:
                classified_edit_seen = True
        post_persona = post.get("persona_candidates")
        _require(isinstance(post_persona, list), "Persona candidates are not projected")
        for candidate in post_persona:
            projected_persona_candidate_ids.add(
                _projected_persona_candidate_id(candidate)
            )
        lineage = post.get("lineage") or {}
        complete_post = bool(
            _string_set(lineage.get("source_ids"))
            and _string_set(lineage.get("evidence_ids"))
            and _string_set(lineage.get("interpretation_ids"))
            and _string_set(lineage.get("revision_ids")) == revision_ids
            and lineage.get("opportunity_id") == opportunity_id
            and lineage.get("post_id") == post_id
        )
        _require(complete_post, "post does not preserve complete source-to-revision lineage")
        complete_post_seen = True
    _require(complete_post_seen, "no post preserves complete source-to-revision lineage")
    _require(linked_revision_family_seen, "no representative linked revision family is projected")
    _require(variant_seen, "no on-demand platform variant is projected")
    _require(attribution_seen, "no revision preserves required public attribution")
    activity_summary = content.get("activity_summary")
    _require(isinstance(activity_summary, dict), "content activity summary is missing")
    persona_recent = ((activity_summary.get("persona") or {}).get("recent") or [])
    _require(isinstance(persona_recent, list), "content Persona activity is malformed")
    for candidate in persona_recent:
        projected_persona_candidate_ids.add(_projected_persona_candidate_id(candidate))
    lifecycle_evidence = _content_lifecycle_evidence(
        counts=counts,
        projected_learning_event_count=len(projected_learning_event_ids),
        projected_persona_candidate_count=len(projected_persona_candidate_ids),
        event_kinds=event_kinds,
        classified_edit_seen=classified_edit_seen,
    )

    decision_count = counts.get("decisions")
    _require(
        isinstance(decision_count, int)
        and not isinstance(decision_count, bool)
        and decision_count >= 0,
        f"content canonical decision count {decision_count!r} is invalid",
    )
    decision_activity = activity_summary.get("decisions")
    _require(
        isinstance(decision_activity, dict)
        and set(decision_activity) == {"total", "by_status", "recent"}
        and decision_activity.get("total") == decision_count
        and isinstance(decision_activity.get("by_status"), dict)
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in decision_activity["by_status"].values()
        )
        and sum(decision_activity["by_status"].values())
        == min(decision_count, CONTENT_DECISION_PROJECTION_LIMIT),
        "content canonical decision activity does not match its canonical count",
    )
    decisions = _validated_decision_rows(
        decision_activity.get("recent"),
        label="content",
        canonical_count=decision_count,
        projection_limit=CONTENT_DECISION_PROJECTION_LIMIT,
    )
    projected_decision_status_counts: dict[str, int] = {}
    for decision in decisions:
        status = str(decision["status"])
        projected_decision_status_counts[status] = (
            projected_decision_status_counts.get(status, 0) + 1
        )
    _require(
        decision_activity["by_status"] == projected_decision_status_counts,
        "content canonical decision status counts do not match projected rows",
    )
    _verify_privacy(content, label="content")
    return {
        "counts": counts,
        "decision_count": decision_count,
        "decisions": decisions,
        "content_lifecycle_evidence": lifecycle_evidence,
        **controller_health,
    }


def _verify_ops_health(ops: dict[str, Any]) -> dict[str, Any]:
    health = ops.get("endpoint_and_subsystem_health")
    _require(isinstance(health, dict), "Ops subsystem health is missing")
    health_verdict = classify_ops_subsystem_health(health)
    unhealthy_keys = set(health_verdict["unhealthy_keys"])
    process_updates = ops.get("ai_clone_process_updates")
    memory_readiness = (
        process_updates.get("memory_readiness")
        if isinstance(process_updates, dict)
        else None
    )
    blocking_keys = set(health_verdict["blocking_keys"])
    if isinstance(memory_readiness, dict) and str(
        memory_readiness.get("status") or ""
    ).strip().lower() not in {"", "ready"}:
        blocking_keys.add("memory_readiness")
    _require(
        not blocking_keys,
        f"Ops has blocking degraded subsystem health: {', '.join(sorted(blocking_keys))}",
    )

    warnings = ops.get("degraded_system_warnings")
    _require(
        isinstance(warnings, list)
        and all(isinstance(item, str) and item.strip() for item in warnings),
        "Ops degraded-system warnings are malformed",
    )
    status = str(ops.get("status") or "").strip().lower()
    state = str(ops.get("state") or "").strip().lower()
    reason_codes = ops.get("reason_codes")
    _require(
        isinstance(reason_codes, list)
        and all(isinstance(item, str) and item for item in reason_codes),
        "Ops projection degradation reasons are malformed",
    )

    if unhealthy_keys:
        _require(
            status == "degraded"
            and state == "degraded"
            and reason_codes == ["ops_cycle_degraded"],
            "Ops nonblocking subsystem degradation is not represented explicitly",
        )
        expected_warning = (
            "Unhealthy or unverified subsystems: "
            f"{', '.join(sorted(unhealthy_keys))}."
        )
        _require(
            warnings == [expected_warning],
            "Ops nonblocking subsystem warning is missing, incomplete, or contains a blocking warning",
        )
        return {
            "ops_health_status": "degraded_nonblocking",
            "ops_nonblocking_warning_keys": health_verdict["warning_only_keys"],
            "ops_warnings": warnings,
        }

    _require(
        status == "complete" and state == "ready",
        "Ops conclusion is not complete",
    )
    _require(reason_codes == [], "Ops projection has degradation reasons")
    _require(warnings == [], "ready Ops projection has degraded-system warnings")
    return {
        "ops_health_status": "ready",
        "ops_nonblocking_warning_keys": [],
        "ops_warnings": [],
    }


def _verify_goal_contract(value: Any, *, label: str) -> None:
    _require(
        isinstance(value, dict) and set(value) == WORKSPACE_GOAL_FIELDS,
        f"{label} goal contract shape is open or incomplete",
    )
    _require(
        value.get("schema_version") == "workspace_goal_contract/v1",
        f"{label} goal contract has the wrong schema",
    )
    for key in ("goal", "phase_gate", "no_action_trigger"):
        cell = value.get(key)
        _require(
            isinstance(cell, str) and bool(cell.strip()) and len(cell) <= 2000,
            f"{label} goal contract has an invalid {key}",
        )
    progress_signals = value.get("progress_signals")
    _require(
        isinstance(progress_signals, list)
        and 0 < len(progress_signals) <= 20
        and all(
            isinstance(item, str) and bool(item.strip()) and len(item) <= 500
            for item in progress_signals
        ),
        f"{label} goal contract has invalid progress signals",
    )


def _verify_shared_ops_reconciliation(
    value: Any,
    *,
    expected_workspaces: set[str],
) -> dict[str, Any]:
    """Verify Shared Ops is one bounded read-only reconciler, not project seven."""

    _require(
        isinstance(value, dict)
        and set(value) == SHARED_OPS_RECONCILIATION_FIELDS,
        "Shared Ops reconciliation shape is open or incomplete",
    )
    _require(
        value.get("display_name") == "Executive Standup"
        and value.get("role") == "portfolio_reconciler",
        "Shared Ops reconciliation does not retain its read-only portfolio role",
    )
    summary = value.get("summary")
    _require(
        isinstance(summary, str) and bool(summary.strip()) and len(summary) <= 1000,
        "Shared Ops reconciliation summary is missing or invalid",
    )
    _verify_goal_contract(value.get("goal"), label="Shared Ops reconciliation")

    for key in SHARED_OPS_RECONCILIATION_LIST_FIELDS:
        items = value.get(key)
        _require(
            isinstance(items, list)
            and len(items) <= MAX_RECURSION_ITEMS
            and all(isinstance(item, dict) for item in items),
            f"Shared Ops reconciliation {key} is not a bounded item list",
        )
        for item in items:
            workspace_key = item.get("workspace_key")
            if workspace_key is not None:
                _require(
                    workspace_key in expected_workspaces,
                    "Shared Ops reconciliation references a non-project workspace",
                )

    evaluated_keys = [
        str(item.get("workspace_key") or "") for item in value["evaluated"]
    ]
    _require(
        len(evaluated_keys) == len(set(evaluated_keys))
        and set(evaluated_keys) == expected_workspaces,
        "Shared Ops reconciliation does not evaluate each active project exactly once",
    )

    actions = value["actions_taken"]
    _require(
        len(actions) == 1
        and set(actions[0]) == SHARED_OPS_RECONCILIATION_ACTION_FIELDS
        and actions[0].get("kind") == "portfolio_reconciliation"
        and isinstance(actions[0].get("summary"), str)
        and bool(str(actions[0].get("summary") or "").strip())
        and actions[0].get("status") in {"complete", "degraded"},
        "Shared Ops reconciliation claims project execution or lacks its read-only receipt",
    )
    return {
        "status": "passed",
        "role": "portfolio_reconciler",
        "evaluated_project_count": len(expected_workspaces),
        "project_writer": False,
    }


def _verify_ops(
    ops: dict[str, Any],
    content_decisions: list[dict[str, Any]],
    *,
    canonical_decision_count: int,
    expected_workspaces: set[str],
) -> dict[str, Any]:
    _require(set(ops) == OPS_KEYS, "Ops projection shape is open or incomplete")
    _require(ops.get("schema_version") == "ops_standup_summary_conclusion/v3", "wrong Ops schema")
    _require(str(ops.get("portfolio_cycle_id") or "").strip(), "Ops portfolio cycle is missing")
    _require(str(ops.get("ops_conclusion_id") or "").strip(), "Ops conclusion identity is missing")
    attempt_number = ops.get("ops_conclusion_attempt_number")
    _require(
        isinstance(attempt_number, int)
        and not isinstance(attempt_number, bool)
        and attempt_number >= 1,
        "Ops canonical conclusion attempt number is missing or invalid",
    )
    _require(
        ops.get("ops_conclusion_attempt_id")
        == str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"ai-clone:ops-attempt:{ops['ops_conclusion_id']}:{attempt_number}",
            )
        ),
        "Ops canonical conclusion attempt identity is invalid",
    )
    _require(
        re.fullmatch(
            r"[0-9a-f]{64}",
            str(ops.get("ops_conclusion_attempt_payload_sha256") or ""),
        )
        is not None,
        "Ops canonical conclusion attempt payload hash is invalid",
    )
    clock = ops.get("clock")
    _require(
        isinstance(clock, dict)
        and set(clock) == {"schema_version", "authority", "timezone", "observed_at"}
        and clock.get("schema_version") == "ai_clone_clock/v1"
        and clock.get("authority") == "ai_clone_utc"
        and clock.get("timezone") == "UTC",
        "Ops ai_clone_utc clock receipt is missing or invalid",
    )
    try:
        observed = datetime.fromisoformat(str(ops.get("observed_at") or "").replace("Z", "+00:00"))
        clock_observed = datetime.fromisoformat(str(clock.get("observed_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionVerificationError("Ops semantic observation is invalid") from exc
    _require(
        observed.tzinfo is not None
        and observed.utcoffset() == timezone.utc.utcoffset(observed)
        and clock_observed == observed,
        "Ops observation is not exactly bound to its ai_clone_utc receipt",
    )
    _require(
        observed.date().isoformat() == str(ops.get("cycle_date") or ""),
        "Ops observation does not match its UTC cycle date",
    )
    _require(isinstance(ops.get("workspace_updates"), list) and ops["workspace_updates"], "Ops has no workspace update")
    workspace_recursion = ops.get("workspace_recursion")
    _require(
        isinstance(workspace_recursion, list) and workspace_recursion,
        "Ops has no workspace recursion truth",
    )
    _require(
        all(
            isinstance(item, dict) and set(item) == WORKSPACE_RECURSION_FIELDS
            for item in workspace_recursion
        ),
        "Ops workspace recursion shape is incomplete",
    )
    recursion_keys = [str(item.get("workspace_key") or "") for item in workspace_recursion]
    _require(
        len(recursion_keys) == len(set(recursion_keys))
        and set(recursion_keys) == expected_workspaces,
        "Ops workspace recursion does not cover each active project exactly once",
    )
    _require(
        all(isinstance(item, dict) for item in ops["workspace_updates"]),
        "Ops workspace updates contain a malformed row",
    )
    workspace_update_keys = [
        str(item.get("workspace_key") or item.get("workspace") or "")
        for item in ops["workspace_updates"]
    ]
    _require(
        len(workspace_update_keys) == len(set(workspace_update_keys))
        and set(workspace_update_keys) == expected_workspaces,
        "Ops workspace updates do not align with the active recursion set",
    )
    _require(
        all(
            str(item.get("state") or item.get("status") or "").strip().lower() != "missing"
            for item in ops["workspace_updates"]
            if isinstance(item, dict)
            and str(item.get("workspace_key") or item.get("workspace") or "")
            in expected_workspaces
        ),
        "Ops workspace updates contain a missing active conclusion",
    )
    shared_ops_reconciliation_evidence = _verify_shared_ops_reconciliation(
        ops.get("shared_ops_reconciliation"),
        expected_workspaces=expected_workspaces,
    )
    disposition_fields = (
        "changes_since_prior",
        "system_decisions",
        "actions_taken",
        "completed_work",
        "failed_work",
        "carried_forward",
        "owner_decisions",
        "blocked",
        "no_action",
        "recommendation_resolutions",
    )
    for item in workspace_recursion:
        goal = item.get("goal")
        _require(
            isinstance(goal, dict) and set(goal) == WORKSPACE_GOAL_FIELDS,
            "Ops workspace recursion has no machine-readable goal contract for "
            f"{item.get('workspace_key')}",
        )
        _verify_goal_contract(
            goal,
            label=f"Ops workspace recursion {item.get('workspace_key')}",
        )
        _require(
            any(bool(item.get(field)) for field in disposition_fields),
            f"Ops workspace recursion has no evidenced disposition for {item.get('workspace_key')}",
        )
        for resolution in item.get("recommendation_resolutions") or []:
            _require(
                not isinstance(resolution, dict)
                or resolution.get("state")
                != "scheduled_in_existing_canonical_scheduler",
                "Ops workspace scheduled recommendation has no projected canonical scheduler authority binding",
            )
            _require(
                isinstance(resolution, dict)
                and resolution.get("state") in RECOMMENDATION_RESOLUTION_STATES,
                f"Ops workspace recommendation has no canonical resolution state for {item.get('workspace_key')}",
            )
            if resolution.get("state") in {
                "scheduled_in_existing_canonical_scheduler",
                "placed_in_execution_queue",
                "blocked",
                "rejected_by_policy",
                "intentionally_retained",
            }:
                _require(
                    bool(str(resolution.get("future_trigger") or "").strip()),
                    f"Ops workspace recommendation has no future trigger for {item.get('workspace_key')}",
                )
    _require(isinstance(ops.get("workspace_cycle_evaluations"), list), "Ops workspace cycle evaluations are missing")
    decision_readiness = ops.get("decision_readiness")
    _require(
        isinstance(decision_readiness, dict)
        and decision_readiness.get("schema_version") == "canonical_decision_projection_readiness/v1"
        and decision_readiness.get("state") == "ready"
        and decision_readiness.get("clock_authority") == "ai_clone_utc"
        and decision_readiness.get("blocking_reason_codes") == [],
        "Ops canonical decision projection is not ready on the AI Clone clock",
    )
    ops_health = _verify_ops_health(ops)
    _require(
        ops.get("data_policy")
        == {
            "canonical_authority": "mac_local_sql",
            "railway_role": "authenticated_bounded_ops_projection",
            "private_bodies_included": False,
        },
        "Ops authority or privacy policy is wrong",
    )
    ops_decisions = _validated_decision_rows(
        ops.get("canonical_decisions"),
        label="Ops",
        canonical_count=canonical_decision_count,
        projection_limit=OPS_DECISION_PROJECTION_LIMIT,
    )
    _require(
        [
            _decision_reconciliation_binding(item)
            for item in ops_decisions[: len(content_decisions)]
        ]
        == [_decision_reconciliation_binding(item) for item in content_decisions],
        "content and Ops do not share the same canonical decision state",
    )
    canonical_decision_projection_evidence = {
        "status": "passed",
        "reason_codes": [],
        "history_state": "empty" if canonical_decision_count == 0 else "present",
        "canonical_decision_count": canonical_decision_count,
        "content_projected_count": len(content_decisions),
        "ops_projected_count": len(ops_decisions),
    }
    # Canonical row presence and cross-surface consistency do not prove that a
    # genuine owner choice was later consumed by a normal Dream/standup cycle.
    # The current bounded projections carry no such natural-cycle proof, so this
    # lane must remain explicitly open even when resolved decision rows exist.
    natural_owner_longitudinal_evidence = {
        "status": "open",
        "reason_codes": [
            "resolved_owner_decision_consumed_by_later_normal_cycle_not_proven"
        ],
        "resolved_owner_decision_consumed_by_later_normal_cycle": False,
    }
    _verify_privacy(ops, label="Ops")
    return {
        "portfolio_cycle_id": ops["portfolio_cycle_id"],
        "shared_decisions": len(content_decisions),
        "canonical_decision_projection_evidence": canonical_decision_projection_evidence,
        "natural_owner_longitudinal_evidence": natural_owner_longitudinal_evidence,
        "ops_recursion_status": "passing",
        "shared_ops_reconciliation_evidence": shared_ops_reconciliation_evidence,
        **ops_health,
    }


def verify(
    content: dict[str, Any],
    ops: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    workspace_html: str | None = None,
    require_action_readiness: bool = True,
) -> dict[str, Any]:
    if registry is None:
        from app.services.workspace_registry_service import workspace_registry_payload

        registry = workspace_registry_payload(include_executive=False)
    expected_workspaces = _active_registry_workspace_keys(registry)
    content_result = _verify_content(content)
    ops_result = _verify_ops(
        ops,
        content_result["decisions"],
        canonical_decision_count=content_result["decision_count"],
        expected_workspaces=expected_workspaces,
    )
    if workspace_html is not None:
        for expected in (
            "Sources → Opportunities → Posts",
            "Ops Standup Summary and Conclusion",
            "Owner Decisions",
        ):
            _require(expected in workspace_html, f"authenticated workspace HTML is missing {expected!r}")
    action_ready = content_result["controller_action_readiness"] == "ready"
    if require_action_readiness:
        _require(action_ready, "controller action readiness is degraded")
    return {
        "schema_version": "integrated_production_projection_verification/v2",
        "status": "passing" if action_ready else "degraded",
        "data_integrity_status": "passing",
        "readability_status": "readable",
        "controller_action_readiness": content_result["controller_action_readiness"],
        "release_readiness": "passing" if action_ready else "failing",
        "controller_reason_codes": content_result["controller_reason_codes"],
        "content_lifecycle_evidence": content_result["content_lifecycle_evidence"],
        "counts": content_result["counts"],
        "active_workspace_count": len(expected_workspaces),
        **ops_result,
        "frontend_owner_surfaces_verified": workspace_html is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--ops", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--workspace-html", type=Path)
    args = parser.parse_args()
    content = json.loads(args.content.read_text(encoding="utf-8"))
    ops = json.loads(args.ops.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    html = args.workspace_html.read_text(encoding="utf-8") if args.workspace_html else None
    result = verify(content, ops, registry=registry, workspace_html=html)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
