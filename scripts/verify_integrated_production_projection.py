#!/usr/bin/env python3
"""Verify the deployed owner projection proves the integrated content/Ops story."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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
    "portfolio_cycle_id",
    "cycle_date",
    "observed_at",
    "status",
    "workspace_updates",
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
CORE_COUNT_MINIMUMS = {
    "sources": 1,
    "discoveries": 2,
    "evidence": 1,
    "interpretations": 1,
    "opportunities": 1,
    "posts": 1,
    "revisions": 2,
    "learning_events": 3,
    "persona_candidates": 1,
    "decisions": 1,
}
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
    for key, minimum in CORE_COUNT_MINIMUMS.items():
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
    _require(classified_edit_seen, "no owner edit classification is projected")
    _require({"owner_approved", "publication_confirmed"} <= event_kinds, "approval/publication learning evidence is incomplete")

    decisions = ((content.get("activity_summary") or {}).get("decisions") or {}).get("recent")
    _require(isinstance(decisions, list) and decisions, "content view has no canonical decision")
    _verify_privacy(content, label="content")
    return {
        "counts": counts,
        "decisions": {str(item.get("decision_id")): item for item in decisions if isinstance(item, dict)},
        **controller_health,
    }


def _verify_ops(ops: dict[str, Any], content_decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    _require(set(ops) == OPS_KEYS, "Ops projection shape is open or incomplete")
    _require(ops.get("schema_version") == "ops_standup_summary_conclusion/v1", "wrong Ops schema")
    _require(
        ops.get("state") == "ready" and ops.get("status") == "complete",
        "Ops conclusion is not complete",
    )
    _require(ops.get("reason_codes") == [], "Ops projection has degradation reasons")
    _require(str(ops.get("portfolio_cycle_id") or "").strip(), "Ops portfolio cycle is missing")
    _require(str(ops.get("ops_conclusion_id") or "").strip(), "Ops conclusion identity is missing")
    _require(isinstance(ops.get("workspace_updates"), list) and ops["workspace_updates"], "Ops has no workspace update")
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
    _require(isinstance(ops.get("endpoint_and_subsystem_health"), dict), "Ops subsystem health is missing")
    _require(
        ops.get("data_policy")
        == {
            "canonical_authority": "mac_local_sql",
            "railway_role": "authenticated_bounded_ops_projection",
            "private_bodies_included": False,
        },
        "Ops authority or privacy policy is wrong",
    )
    ops_decisions = ops.get("canonical_decisions")
    _require(isinstance(ops_decisions, list) and ops_decisions, "Ops view has no canonical decision")
    matching = []
    for decision in ops_decisions:
        decision_id = str(decision.get("decision_id") or "") if isinstance(decision, dict) else ""
        other = content_decisions.get(decision_id)
        if other and (
            decision.get("status") == other.get("status")
            and decision.get("state_version") == other.get("state_version")
        ):
            matching.append(decision_id)
    _require(matching, "content and Ops do not share the same canonical decision state")
    _verify_privacy(ops, label="Ops")
    return {"portfolio_cycle_id": ops["portfolio_cycle_id"], "shared_decisions": len(matching)}


def verify(
    content: dict[str, Any],
    ops: dict[str, Any],
    *,
    workspace_html: str | None = None,
    require_action_readiness: bool = True,
) -> dict[str, Any]:
    content_result = _verify_content(content)
    ops_result = _verify_ops(ops, content_result["decisions"])
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
        "counts": content_result["counts"],
        **ops_result,
        "frontend_owner_surfaces_verified": workspace_html is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--ops", type=Path, required=True)
    parser.add_argument("--workspace-html", type=Path)
    args = parser.parse_args()
    content = json.loads(args.content.read_text(encoding="utf-8"))
    ops = json.loads(args.ops.read_text(encoding="utf-8"))
    html = args.workspace_html.read_text(encoding="utf-8") if args.workspace_html else None
    result = verify(content, ops, workspace_html=html)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
