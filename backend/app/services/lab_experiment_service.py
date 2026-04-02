from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.routes import content_generation
from app.services import social_long_form_signal_service as long_form_signal_service
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.social_signal_utils import build_variants, normalize_saved_signal
from app.services.workspace_snapshot_service import ROOT as WORKSPACE_ROOT
from app.services.workspace_snapshot_service import _ingestions_root, _transcripts_root, workspace_snapshot_service

EXPERIMENT_ID = "content-fallback-observatory"
SOCIAL_EXPERIMENT_ID = "article-response-matrix"
SOURCE_HANDOFF_EXPERIMENT_ID = "source-handoff-matrix"
TARGET_FALLBACK_RATE = 5.0
TARGET_SOCIAL_FAILURE_RATE = 0.0
TARGET_HANDOFF_MISMATCH_RATE = 10.0
TARGET_SOCIAL_BENCHMARK_SCORE = 9.5
TARGET_SOCIAL_BENCHMARK_FLOOR = 9.0
MAX_HISTORY = 8
TARGET_PROVIDER = "openai"
TARGET_MODEL = "gpt-4o-mini"

_EXPERIMENT_CACHE: dict[str, dict[str, Any]] = {}

CONTENT_PROBES: List[dict[str, str]] = [
    {"topic": "agent orchestration", "audience": "tech_ai", "category": "value", "tone": "expert_direct"},
    {"topic": "workflow clarity", "audience": "tech_ai", "category": "value", "tone": "expert_direct"},
    {"topic": "AI adoption", "audience": "tech_ai", "category": "value", "tone": "expert_direct"},
    {"topic": "change management", "audience": "leadership_management", "category": "value", "tone": "expert_direct"},
    {
        "topic": "Kentucky Senate passes bill making it easier to cut faculty",
        "audience": "education_admissions",
        "category": "value",
        "tone": "expert_direct",
    },
]

SOCIAL_LANE_MATRIX: List[dict[str, str]] = [
    {"id": "ai", "label": "AI"},
    {"id": "ops-pm", "label": "Tech"},
    {"id": "admissions", "label": "Admissions"},
    {"id": "program-leadership", "label": "Leadership"},
    {"id": "entrepreneurship", "label": "Entrepreneur"},
]

ARTICLE_RESPONSE_PROBES: List[dict[str, str]] = [
    {
        "topic": "AI tool selection in the agentic era",
        "title": "A Guide to Which AI to Use in the Agentic Era",
        "platform": "substack",
        "url": "https://signals.substack.com/p/which-ai-to-use-in-the-agentic-era",
        "author": "Signal Desk",
        "raw_text": (
            "Teams keep treating model choice like the whole strategy. "
            "The real gap usually shows up in workflow design, evaluation discipline, and operator judgment. "
            "Access to more models does not help if the team still cannot pressure-test outputs or decide when to escalate."
        ),
    },
    {
        "topic": "Tech handoff failures in product operations",
        "title": "Most Workflow Breaks Happen at the Handoff, Not the Task List",
        "platform": "rss",
        "url": "https://workflowreview.example.com/ops/handoff-failures",
        "author": "Workflow Review",
        "raw_text": (
            "Product teams rarely miss work because the tasks are invisible. "
            "They miss because ownership, context, and decision rules break at the handoff. "
            "The visible backlog is usually cleaner than the underlying operating system."
        ),
    },
    {
        "topic": "Admissions stress after higher-ed faculty cuts",
        "title": "Kentucky Senate passes bill making it easier to cut faculty",
        "platform": "rss",
        "url": "https://higherednews.example.com/faculty-cuts-kentucky",
        "author": "Natalie Schwartz",
        "raw_text": (
            "Higher-ed budget pressure does not stay confined to staffing charts. "
            "Families start asking harder questions about stability, support, and whether the institution can still deliver on trust. "
            "Admissions teams often hear those concerns before the rest of the institution changes its message."
        ),
    },
    {
        "topic": "Leadership change management and repeatability",
        "title": "Change Fails When Leaders Announce Before Teams Can Repeat the Process",
        "platform": "web",
        "url": "https://leadersignal.example.com/change/repeatability",
        "author": "Leader Signal",
        "raw_text": (
            "Executives usually communicate the change long before the team can repeat the new behavior. "
            "That leaves middle layers translating the same message over and over without shared standards. "
            "The problem is rarely urgency by itself. It is whether the change becomes coachable and repeatable."
        ),
    },
    {
        "topic": "Entrepreneurship and distribution for small AI products",
        "title": "Distribution Is Becoming the Moat for Small AI Products",
        "platform": "substack",
        "url": "https://buildernotes.substack.com/p/distribution-moat-small-ai-products",
        "author": "Builder Notes",
        "raw_text": (
            "Small AI products can ship features quickly now, which means feature speed alone stops being the moat. "
            "What compounds is distribution, user trust, and the operational system that keeps insight close to the product. "
            "The builders who turn repeated customer signals into process usually keep the edge longer."
        ),
    },
]

SOURCE_HANDOFF_PROBES: List[dict[str, str]] = [
    {
        "topic": "low-context story fragment",
        "title": "Remember that hill that I showed you, the system of record hill?",
        "platform": "manual",
        "source_channel": "manual",
        "source_type": "transcript_note",
        "url": "https://example.com/lab/source-handoff/low-context-story",
        "author": "Johnnie",
        "segment": "Remember that hill that I showed you, the system of record hill?",
        "expected_handoff_lane": "source_only",
    },
    {
        "topic": "system awareness without durable identity",
        "title": "The overnight jobs completed, but the team still needs a clearer morning picture of what changed.",
        "platform": "web",
        "source_channel": "web",
        "source_type": "article",
        "url": "https://example.com/lab/source-handoff/brief-awareness",
        "author": "Signal Desk",
        "segment": "The overnight jobs completed, but the team still needs a clearer morning picture of what changed.",
        "expected_handoff_lane": "brief_only",
    },
    {
        "topic": "public-expression seed",
        "title": "Access to more models does not help if the team still cannot pressure-test outputs or decide when to escalate.",
        "platform": "substack",
        "source_channel": "substack",
        "source_type": "article",
        "url": "https://example.com/lab/source-handoff/post-candidate",
        "author": "Signal Desk",
        "segment": "Access to more models does not help if the team still cannot pressure-test outputs or decide when to escalate.",
        "expected_handoff_lane": "post_candidate",
    },
    {
        "topic": "durable worldview evidence",
        "title": "Workflow clarity matters more than tool abundance because operator judgment is what decides whether the system earns trust.",
        "platform": "podcast",
        "source_channel": "podcast",
        "source_type": "transcript",
        "url": "https://example.com/lab/source-handoff/persona-candidate",
        "author": "Johnnie",
        "segment": "Workflow clarity matters more than tool abundance because operator judgment is what decides whether the system earns trust.",
        "expected_handoff_lane": "persona_candidate",
    },
    {
        "topic": "operational routing pressure",
        "title": "The visible backlog is usually cleaner than the underlying operating system because ownership and handoff rules are still unclear.",
        "platform": "rss",
        "source_channel": "rss",
        "source_type": "article",
        "url": "https://example.com/lab/source-handoff/route-to-pm",
        "author": "Workflow Review",
        "segment": "The visible backlog is usually cleaner than the underlying operating system because ownership and handoff rules are still unclear.",
        "expected_handoff_lane": "route_to_pm",
    },
]

STAGE_CATALOG: List[dict[str, Any]] = [
    {
        "id": "grounding",
        "label": "Grounding",
        "description": "Build the claim, proof, and story packet before drafting starts.",
        "possible_failures": [
            "no_primary_claims",
            "weak_proof_packet_grounding",
            "missing_story_or_proof_anchor",
        ],
    },
    {
        "id": "planner",
        "label": "Planner",
        "description": "Create structured option briefs with framing mode, claim, and proof.",
        "possible_failures": [
            "planner_returned_no_briefs",
            "planner_returned_too_few_briefs",
            "planner_briefs_missing_framing",
        ],
    },
    {
        "id": "writer",
        "label": "Writer",
        "description": "Draft option candidates from the structured briefs.",
        "possible_failures": [
            "writer_returned_no_options",
            "writer_returned_too_few_options",
            "writer_drifted_into_safe_patterning",
        ],
    },
    {
        "id": "critic",
        "label": "Critic",
        "description": "Rewrite and pressure-test rough drafts before finalization.",
        "possible_failures": [
            "critic_returned_no_rewrite",
            "critic_failed_to_raise_contrast",
            "critic_left_claim_not_leading",
        ],
    },
    {
        "id": "recovery",
        "label": "Recovery",
        "description": "Repair missing options or weak structure from planned briefs.",
        "possible_failures": [
            "recovered_missing_planned_options",
            "repair_loop_overused",
            "repair_output_still_flat",
        ],
    },
    {
        "id": "provider_router",
        "label": "Provider Router",
        "description": "Select the cheapest healthy model path and fail over only when needed.",
        "possible_failures": [
            "provider_failover",
            "quota_or_rate_limit_failover",
            "provider_trace_missing",
        ],
    },
    {
        "id": "editorial_finish",
        "label": "Editorial Finish",
        "description": "Apply final cleanup, taste checks, and ranking.",
        "possible_failures": [
            "claim_not_leading",
            "low_contrast",
            "paragraph_cadence_flat",
            "generic_close",
        ],
    },
    {
        "id": "legacy_escape",
        "label": "Legacy Escape",
        "description": "Emergency fallback when the staged pipeline returns no usable options.",
        "possible_failures": [
            "staged_generation_returned_no_options",
            "legacy_generator_used",
        ],
    },
]

SOCIAL_STAGE_CATALOG: List[dict[str, Any]] = [
    {
        "id": "signal_intake",
        "label": "Signal Intake",
        "section": "article",
        "description": "Capture enough clean source material for the system to reason over the article at all.",
        "possible_failures": [
            "probe_error",
            "signal_normalization_failed",
            "article_signal_missing_claims",
        ],
    },
    {
        "id": "source_contract",
        "label": "Source Contract",
        "section": "article",
        "description": "Classify channel, source class, unit kind, and response modes before drafting.",
        "possible_failures": [
            "source_contract_incomplete",
            "source_class_missing",
            "response_modes_missing",
        ],
    },
    {
        "id": "claim_extraction",
        "label": "Claim Extraction",
        "section": "article",
        "description": "Extract the core claim, supporting signal, and standout lines from the article.",
        "possible_failures": [
            "article_signal_missing_claims",
            "supporting_signal_thin",
            "standout_lines_missing",
        ],
    },
    {
        "id": "world_understanding",
        "label": "World Understanding",
        "section": "article",
        "description": "Model what the article is about in the world, who it affects, and why it matters.",
        "possible_failures": [
            "world_model_thin",
            "why_it_matters_missing",
            "role_alignment_missing",
        ],
    },
    {
        "id": "article_stance",
        "label": "Article Stance",
        "section": "article",
        "description": "Model the article's own stance, not just its topic.",
        "possible_failures": [
            "article_stance_model_missing",
            "article_stance_confidence_low",
        ],
    },
    {
        "id": "source_expression",
        "label": "Source Expression",
        "section": "article",
        "description": "Track whether the article is using contrast, boundary, directive, or story structure.",
        "possible_failures": [
            "source_expression_missing",
            "source_structure_unknown",
        ],
    },
    {
        "id": "lane_routing",
        "label": "Lane Routing",
        "section": "synthesis",
        "description": "Generate the full AI, tech, admissions, leadership, and entrepreneur lane matrix from one article signal.",
        "possible_failures": [
            "missing_lane_variant",
            "lane_matrix_incomplete",
            "lane_alias_misrouted",
        ],
    },
    {
        "id": "persona_truth",
        "label": "Persona Truth",
        "section": "johnnie",
        "description": "Load claims, stories, initiatives, and committed persona overlay before choosing a perspective.",
        "possible_failures": [
            "persona_truth_missing",
            "persona_overlay_stale",
            "story_bank_missing",
        ],
    },
    {
        "id": "persona_retrieval",
        "label": "Persona Retrieval",
        "section": "johnnie",
        "description": "Retrieve the most relevant persona artifacts for this exact article.",
        "possible_failures": [
            "persona_retrieval_not_modeled",
            "relevant_deltas_missing",
            "retrieval_diversity_thin",
        ],
    },
    {
        "id": "belief_selection",
        "label": "Belief Selection",
        "section": "johnnie",
        "description": "Choose the belief frame the system thinks Johnnie would use here.",
        "possible_failures": [
            "belief_missing",
            "belief_overused",
            "belief_relevance_thin",
        ],
    },
    {
        "id": "experience_selection",
        "label": "Experience Selection",
        "section": "johnnie",
        "description": "Choose the lived proof, anecdote, or initiative the system thinks is relevant here.",
        "possible_failures": [
            "experience_anchor_missing",
            "experience_anchor_overused",
            "experience_relevance_thin",
        ],
    },
    {
        "id": "johnnie_perspective",
        "label": "Johnnie Perspective",
        "section": "johnnie",
        "description": "Model what Johnnie would agree with, push back on, or add from lived experience.",
        "possible_failures": [
            "johnnie_reaction_not_modeled",
            "perspective_conflict_hidden",
            "lived_reaction_missing",
        ],
    },
    {
        "id": "stance_selection",
        "label": "Stance Selection",
        "section": "synthesis",
        "description": "Choose the system stance toward the article for each lane.",
        "possible_failures": [
            "stance_missing",
            "stance_diversity_thin",
            "stance_contrast_light",
        ],
    },
    {
        "id": "reaction_brief",
        "label": "Reaction Brief",
        "section": "synthesis",
        "description": "Summarize article view, Johnnie view, tension, and content angle before drafting.",
        "possible_failures": [
            "reaction_brief_missing",
            "synthesis_gap_hidden",
            "content_angle_missing",
        ],
    },
    {
        "id": "source_takeaway",
        "label": "Source Takeaway",
        "section": "synthesis",
        "description": "Rewrite the article into the core takeaway the draft should respond to.",
        "possible_failures": [
            "source_takeaway_missing",
            "source_takeaway_generic",
            "source_structure_lost",
        ],
    },
    {
        "id": "technique_selection",
        "label": "Technique Selection",
        "section": "synthesis",
        "description": "Select rhetorical techniques and emotional profile for the draft.",
        "possible_failures": [
            "technique_bundle_empty",
            "technique_reason_missing",
            "technique_overused",
        ],
    },
    {
        "id": "response_type_selection",
        "label": "Response Type",
        "section": "synthesis",
        "description": "Choose whether the response should agree, go contrarian, anchor in personal story, or stay humor-gated.",
        "possible_failures": [
            "response_type_missing",
            "response_type_diversity_thin",
            "response_type_confidence_low",
        ],
    },
    {
        "id": "comment_draft",
        "label": "Comment Draft",
        "section": "draft",
        "description": "Draft a usable comment for each lane without empty output or review-level degradation.",
        "possible_failures": [
            "comment_draft_missing",
            "comment_variant_needs_review",
            "comment_contains_generic_language",
        ],
    },
    {
        "id": "repost_draft",
        "label": "Repost Draft",
        "section": "draft",
        "description": "Draft a usable repost for each lane without empty output or review-level degradation.",
        "possible_failures": [
            "repost_draft_missing",
            "repost_variant_needs_review",
            "repost_contains_generic_language",
        ],
    },
    {
        "id": "template_composition",
        "label": "Template Composition",
        "section": "draft",
        "description": "Assemble opening, contrast, takeaway, bridge, main line, and close into final copy.",
        "possible_failures": [
            "template_trace_missing",
            "opener_family_repeated",
            "close_family_repeated",
        ],
    },
    {
        "id": "voice_normalization",
        "label": "Voice Normalization",
        "section": "draft",
        "description": "Remove forbidden phrasing, weak bridges, and obvious abstraction before returning copy.",
        "possible_failures": [
            "forbidden_phrase_survived",
            "abstract_meta_phrasing_detected",
            "voice_cleanup_overworked",
        ],
    },
    {
        "id": "lane_specificity",
        "label": "Lane Specificity",
        "section": "evaluation",
        "description": "Keep lane framing distinct so AI, tech, admissions, leadership, and entrepreneur outputs do not collapse into one pattern.",
        "possible_failures": [
            "lane_markers_light",
            "lane_differentiation_weak",
            "belief_framing_too_implicit",
            "stance_contrast_light",
        ],
    },
    {
        "id": "response_quality",
        "label": "Response Quality",
        "section": "evaluation",
        "description": "Pressure-test comments and reposts for genericity, abstract phrasing, and low-confidence drafts.",
        "possible_failures": [
            "generic_language_detected",
            "abstract_meta_phrasing_detected",
            "variant_needs_review",
            "response_overall_score_low",
            "benchmark_below_target",
        ],
    },
    {
        "id": "safety",
        "label": "Safety",
        "section": "evaluation",
        "description": "Ensure the matrix stays role-safe while still producing sharp usable drafts.",
        "possible_failures": [
            "role_safety_flagged",
            "unsafe_response_mode",
        ],
    },
    {
        "id": "humor_safety",
        "label": "Humor Safety",
        "section": "evaluation",
        "description": "Track whether humor is safely blocked or safely allowed before it becomes a response type.",
        "possible_failures": [
            "humor_safety_missing",
            "humor_boundary_missing",
            "unsafe_humor_selected",
        ],
    },
]

HANDOFF_STAGE_CATALOG: List[dict[str, Any]] = [
    {
        "id": "source_contract",
        "label": "Source Contract",
        "section": "source",
        "description": "Capture enough source metadata for the handoff classifier to reason over the segment honestly.",
        "possible_failures": [
            "source_contract_incomplete",
            "source_channel_missing",
            "source_type_missing",
        ],
    },
    {
        "id": "segment_quality",
        "label": "Segment Quality",
        "section": "source",
        "description": "Make sure the segment is clean enough and context-rich enough to classify at all.",
        "possible_failures": [
            "segment_too_weak",
            "segment_low_context",
            "segment_context_thin",
        ],
    },
    {
        "id": "belief_assessment",
        "label": "Belief Assessment",
        "section": "classification",
        "description": "Assess stance, belief relation, and lived proof context before assigning a downstream lane.",
        "possible_failures": [
            "assessment_missing",
            "stance_missing",
            "belief_signal_thin",
        ],
    },
    {
        "id": "route_classification",
        "label": "Route Classification",
        "section": "classification",
        "description": "Choose response modes, primary route, and route reason from the actual segment.",
        "possible_failures": [
            "route_modes_missing",
            "primary_route_missing",
            "route_score_low",
        ],
    },
    {
        "id": "guardrail_application",
        "label": "Guardrail Application",
        "section": "decision",
        "description": "Apply weak-fragment and manual-reference guardrails before promoting the segment downstream.",
        "possible_failures": [
            "source_guardrail_missed",
            "manual_reference_not_downgraded",
            "low_context_story_not_downgraded",
        ],
    },
    {
        "id": "handoff_decision",
        "label": "Handoff Decision",
        "section": "decision",
        "description": "Map the classifier output to the product handoff lane that Brain, Persona, and PM should consume.",
        "possible_failures": [
            "handoff_lane_mismatch",
            "persona_overpromotion",
            "post_underpromotion",
            "pm_underpromotion",
        ],
    },
]

_STAGE_ORDER = [stage["id"] for stage in STAGE_CATALOG]
_STAGE_LABELS = {stage["id"]: stage["label"] for stage in STAGE_CATALOG}
_SOCIAL_STAGE_ORDER = [stage["id"] for stage in SOCIAL_STAGE_CATALOG]
_SOCIAL_STAGE_LABELS = {stage["id"]: stage["label"] for stage in SOCIAL_STAGE_CATALOG}
_HANDOFF_STAGE_ORDER = [stage["id"] for stage in HANDOFF_STAGE_CATALOG]
_HANDOFF_STAGE_LABELS = {stage["id"]: stage["label"] for stage in HANDOFF_STAGE_CATALOG}


@contextmanager
def _lab_provider_lane() -> Any:
    previous_provider_order = os.environ.get("CONTENT_GENERATION_PROVIDER_ORDER")
    os.environ["CONTENT_GENERATION_PROVIDER_ORDER"] = "openai"
    try:
        yield
    finally:
        if previous_provider_order is None:
            os.environ.pop("CONTENT_GENERATION_PROVIDER_ORDER", None)
        else:
            os.environ["CONTENT_GENERATION_PROVIDER_ORDER"] = previous_provider_order


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _structural_fallbacks_for_probe(diagnostics: dict[str, Any]) -> list[str]:
    fallback_trace = diagnostics.get("fallback_trace") or {}
    fallbacks: list[str] = []
    if diagnostics.get("generation_strategy") == "legacy_fallback" or fallback_trace.get("legacy_fallback_triggered"):
        fallbacks.append("legacy_generation_fallback")
    if int(fallback_trace.get("recovered_missing_option_count") or 0) > 0:
        fallbacks.append("recovered_missing_planned_options")
    if fallback_trace.get("critic_used_rough_options"):
        fallbacks.append("critic_used_rough_options")
    if diagnostics.get("provider_fallback_used"):
        fallbacks.append("provider_failover")
    return fallbacks


def _top_taste_warnings(diagnostics: dict[str, Any]) -> list[str]:
    taste_scores = diagnostics.get("taste_scores") or []
    if not taste_scores:
        return []
    return [str(item) for item in ((taste_scores[0] or {}).get("warnings") or [])[:6]]


def _provider_trace_summary(provider_trace: list[dict[str, Any]]) -> str:
    if not provider_trace:
        return "No provider trace returned."
    parts: list[str] = []
    for item in provider_trace:
        provider = str(item.get("provider") or "unknown")
        model = str(item.get("actual_model") or item.get("requested_model") or "unknown")
        status = str(item.get("status") or "unknown")
        parts.append(f"{provider}:{model}:{status}")
    return " -> ".join(parts)


def _probe_held_on_target_provider(provider_trace: list[dict[str, Any]]) -> bool:
    if not provider_trace:
        return False
    saw_success = False
    for item in provider_trace:
        provider = str(item.get("provider") or "").strip().lower()
        model = str(item.get("actual_model") or item.get("requested_model") or "").strip().lower()
        if provider != TARGET_PROVIDER:
            return False
        if model and model != TARGET_MODEL:
            return False
        if str(item.get("status") or "").lower() == "success":
            saw_success = True
    return saw_success


def _stage_result(stage_id: str, status: str, reason: str, detail: str) -> dict[str, Any]:
    return {
        "id": stage_id,
        "label": _STAGE_LABELS[stage_id],
        "status": status,
        "reason": reason,
        "detail": detail,
    }


def _build_stage_results(diagnostics: dict[str, Any], top_warnings: list[str]) -> list[dict[str, Any]]:
    fallback_trace = diagnostics.get("fallback_trace") or {}
    events = fallback_trace.get("events") or []
    event_reasons = {str(item.get("reason") or "") for item in events}
    planned_briefs = diagnostics.get("planned_option_briefs") or []
    primary_claims = diagnostics.get("primary_claims") or []
    proof_packets = diagnostics.get("proof_packets") or []
    generation_strategy = str(diagnostics.get("generation_strategy") or "")
    provider_trace = diagnostics.get("llm_provider_trace") or []
    provider_fallback_used = bool(diagnostics.get("provider_fallback_used"))
    held_on_target_provider = _probe_held_on_target_provider(provider_trace)
    recovered_missing_option_count = int(fallback_trace.get("recovered_missing_option_count") or 0)
    critic_used_rough_options = bool(fallback_trace.get("critic_used_rough_options"))
    used_consolidated_refinement = bool(fallback_trace.get("used_consolidated_refinement"))
    used_compact_single_pass = bool(fallback_trace.get("used_compact_single_pass"))
    grounding_mode = str(diagnostics.get("grounding_mode") or "")

    results: list[dict[str, Any]] = []

    if not primary_claims:
        results.append(_stage_result("grounding", "fail", "no_primary_claims", "The context builder did not surface a usable primary claim."))
    elif grounding_mode != "proof_ready" or not proof_packets:
        results.append(
            _stage_result(
                "grounding",
                "warn",
                "weak_proof_packet_grounding",
                "Claims were available, but proof packets were thin or the request did not stay in proof_ready mode.",
            )
        )
    else:
        results.append(_stage_result("grounding", "pass", "grounded", "Claims and proof packets were available before drafting."))

    if not planned_briefs:
        results.append(_stage_result("planner", "fail", "planner_returned_no_briefs", "The planner did not produce structured option briefs."))
    elif len(planned_briefs) < 3:
        results.append(
            _stage_result(
                "planner",
                "warn",
                "planner_returned_too_few_briefs",
                f"The planner only produced {len(planned_briefs)} briefs instead of the target 3.",
            )
        )
    elif any(not str(brief.get("framing_mode") or "").strip() for brief in planned_briefs):
        results.append(
            _stage_result(
                "planner",
                "warn",
                "planner_briefs_missing_framing",
                "At least one planned brief was missing a framing mode.",
            )
        )
    else:
        results.append(_stage_result("planner", "pass", "briefs_ready", "Structured option briefs were created successfully."))

    if "writer_returned_no_options" in event_reasons:
        results.append(_stage_result("writer", "fail", "writer_returned_no_options", "The writer returned no options and the system had to escalate."))
    elif recovered_missing_option_count > 0:
        results.append(
            _stage_result(
                "writer",
                "warn",
                "writer_returned_too_few_options",
                f"The writer under-produced variants and missed {recovered_missing_option_count} planned option(s).",
            )
        )
    else:
        results.append(_stage_result("writer", "pass", "writer_completed", "The writer produced the expected option count."))

    if used_compact_single_pass:
        results.append(
            _stage_result(
                "critic",
                "pass",
                "writer_embedded_refinement",
                "The compact staged path pushed refinement rules into the writer and relied on deterministic finalization instead of a second model pass.",
            )
        )
    elif used_consolidated_refinement:
        results.append(
            _stage_result(
                "critic",
                "pass",
                "collapsed_into_refinement_pass",
                "The old critic, proof-enforcement, and sharpening stages were collapsed into one consolidated refinement pass.",
            )
        )
    elif critic_used_rough_options:
        results.append(
            _stage_result(
                "critic",
                "warn",
                "critic_returned_no_rewrite",
                "The critic did not return rewritten options, so the system used rough writer output.",
            )
        )
    elif any(warning == "claim_not_leading" for warning in top_warnings):
        results.append(
            _stage_result(
                "critic",
                "warn",
                "critic_left_claim_not_leading",
                "The critic path completed, but the top option still did not lead strongly enough with the claim.",
            )
        )
    else:
        results.append(_stage_result("critic", "pass", "critic_completed", "The critic path completed without a visible fallback."))

    if recovered_missing_option_count > 0:
        results.append(
            _stage_result(
                "recovery",
                "warn",
                "recovered_missing_planned_options",
                f"The repair step synthesized {recovered_missing_option_count} missing option(s) from the planned briefs.",
            )
        )
    else:
        results.append(_stage_result("recovery", "pass", "no_recovery_needed", "No repair step was needed for missing options."))

    if not provider_trace:
        results.append(_stage_result("provider_router", "fail", "provider_trace_missing", "The request returned no provider trace."))
    elif not held_on_target_provider:
        rate_limit_failover = any("429" in str(item.get("error") or "") for item in provider_trace)
        results.append(
            _stage_result(
                "provider_router",
                "fail",
                "quota_or_rate_limit_failover" if rate_limit_failover else "provider_failover",
                f"Target lane is {TARGET_PROVIDER}:{TARGET_MODEL}. Actual trace: {_provider_trace_summary(provider_trace)}",
            )
        )
    elif provider_fallback_used:
        results.append(
            _stage_result(
                "provider_router",
                "fail",
                "provider_failover",
                f"Target lane is {TARGET_PROVIDER}:{TARGET_MODEL}. Actual trace: {_provider_trace_summary(provider_trace)}",
            )
        )
    else:
        retry_count = sum(1 for item in provider_trace if str(item.get("status") or "").lower() != "success")
        results.append(
            _stage_result(
                "provider_router",
                "pass",
                "provider_recovered_on_target" if retry_count else "provider_stable",
                (
                    f"Held on {TARGET_PROVIDER}:{TARGET_MODEL} after {retry_count} internal retr"
                    f"{'ies' if retry_count != 1 else 'y'}. Trace: {_provider_trace_summary(provider_trace)}"
                    if retry_count
                    else f"Held entirely on {TARGET_PROVIDER}:{TARGET_MODEL}. Trace: {_provider_trace_summary(provider_trace)}"
                ),
            )
        )

    if top_warnings:
        results.append(
            _stage_result(
                "editorial_finish",
                "warn",
                top_warnings[0],
                f"Top taste warnings: {', '.join(top_warnings[:3])}.",
            )
        )
    elif used_compact_single_pass:
        results.append(
            _stage_result(
                "editorial_finish",
                "pass",
                "deterministic_finalizer_clean",
                "The compact writer path cleared the current taste warnings without a second model pass.",
            )
        )
    elif used_consolidated_refinement:
        results.append(
            _stage_result(
                "editorial_finish",
                "pass",
                "consolidated_refinement_clean",
                "The consolidated refinement pass cleared the current taste warnings.",
            )
        )
    else:
        results.append(_stage_result("editorial_finish", "pass", "editorial_finish_clean", "The top option cleared the current taste warnings."))

    if generation_strategy == "legacy_fallback" or fallback_trace.get("legacy_fallback_triggered"):
        results.append(
            _stage_result(
                "legacy_escape",
                "fail",
                str(fallback_trace.get("legacy_fallback_reason") or "legacy_generator_used"),
                "The staged pipeline returned no options, so the system had to use the legacy generator.",
            )
        )
    else:
        results.append(_stage_result("legacy_escape", "pass", "staged_pipeline_held", "The request stayed in the staged planner/writer/critic path."))

    return results


def _build_stage_health(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for stage in STAGE_CATALOG:
        stage_runs = [item for item in results if item.get("stage_results")]
        stage_results = [
            next((entry for entry in item["stage_results"] if entry.get("id") == stage["id"]), None)
            for item in stage_runs
        ]
        stage_results = [item for item in stage_results if item]
        reason_counts: dict[str, int] = {}
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for item in stage_results:
            status = str(item.get("status") or "warn")
            counts[status] = counts.get(status, 0) + 1
            reason = str(item.get("reason") or "")
            if status != "pass" and reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        summary.append(
            {
                **stage,
                "counts": counts,
                "top_failure_reasons": [
                    key for key, _ in sorted(reason_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
                ],
            }
        )
    return summary


_SOCIAL_SPECIFICITY_WARNINGS = {
    "lane markers are light": "lane_markers_light",
    "lane differentiation may be weak": "lane_differentiation_weak",
    "belief framing may be too implicit": "belief_framing_too_implicit",
    "stance contrast is light": "stance_contrast_light",
}

_SOCIAL_QUALITY_WARNINGS = {
    "copy still contains generic language": "generic_language_detected",
    "copy still contains abstract meta phrasing": "abstract_meta_phrasing_detected",
    "variant needs review before high-confidence use": "variant_needs_review",
}


def _metric_card(metric_id: str, label: str, value: float | int | None, tone: str) -> dict[str, Any]:
    return {"id": metric_id, "label": label, "value": value, "tone": tone}


def _social_stage_result(stage_id: str, status: str, reason: str, detail: str) -> dict[str, Any]:
    stage = next(item for item in SOCIAL_STAGE_CATALOG if item["id"] == stage_id)
    return {
        "id": stage_id,
        "label": _SOCIAL_STAGE_LABELS[stage_id],
        "section": stage.get("section") or "evaluation",
        "status": status,
        "reason": reason,
        "detail": detail,
        "score": None,
        "evidence": [],
        "missing_fields": [],
    }


def _build_social_stage_health(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for stage in SOCIAL_STAGE_CATALOG:
        stage_runs = [item for item in results if item.get("stage_results")]
        stage_results = [
            next((entry for entry in item["stage_results"] if entry.get("id") == stage["id"]), None)
            for item in stage_runs
        ]
        stage_results = [item for item in stage_results if item]
        reason_counts: dict[str, int] = {}
        counts = {"pass": 0, "warn": 0, "fail": 0, "missing": 0}
        for item in stage_results:
            status = str(item.get("status") or "warn")
            counts[status] = counts.get(status, 0) + 1
            reason = str(item.get("reason") or "")
            if status != "pass" and reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        summary.append(
            {
                **stage,
                "counts": counts,
                "top_failure_reasons": [
                    key for key, _ in sorted(reason_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
                ],
            }
        )
    return summary


def _handoff_stage_result(stage_id: str, status: str, reason: str, detail: str) -> dict[str, Any]:
    stage = next(item for item in HANDOFF_STAGE_CATALOG if item["id"] == stage_id)
    return {
        "id": stage_id,
        "label": _HANDOFF_STAGE_LABELS[stage_id],
        "section": stage.get("section") or "evaluation",
        "status": status,
        "reason": reason,
        "detail": detail,
        "score": None,
        "evidence": [],
        "missing_fields": [],
    }


def _build_handoff_stage_health(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for stage in HANDOFF_STAGE_CATALOG:
        stage_runs = [item for item in results if item.get("stage_results")]
        stage_results = [
            next((entry for entry in item["stage_results"] if entry.get("id") == stage["id"]), None)
            for item in stage_runs
        ]
        stage_results = [item for item in stage_results if item]
        reason_counts: dict[str, int] = {}
        counts = {"pass": 0, "warn": 0, "fail": 0, "missing": 0}
        for item in stage_results:
            status = str(item.get("status") or "warn")
            counts[status] = counts.get(status, 0) + 1
            reason = str(item.get("reason") or "")
            if status != "pass" and reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        summary.append(
            {
                **stage,
                "counts": counts,
                "top_failure_reasons": [
                    key for key, _ in sorted(reason_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
                ],
            }
        )
    return summary


def _evaluate_source_handoff_probe(probe: dict[str, str]) -> dict[str, Any]:
    asset = {
        "asset_id": f"lab-source::{probe['title']}",
        "title": probe["title"],
        "summary": probe.get("summary") or probe["segment"],
        "source_channel": probe.get("source_channel") or probe.get("platform") or "web",
        "source_type": probe.get("source_type") or "article",
        "source_url": probe.get("url") or "",
        "source_class": "long_form_media",
        "topics": [probe.get("topic") or ""],
        "tags": ["lab_source_handoff_probe"],
    }
    segment = str(probe.get("segment") or "").strip()
    source_context_excerpt = str(probe.get("source_context_excerpt") or segment).strip()
    worldview_score = int((long_form_signal_service._score_sentence(segment, asset) or (0, 0, 0))[0])
    lane_id = long_form_signal_service._lane_hint(segment)
    assessment = long_form_signal_service.social_belief_engine.assess_signal(
        long_form_signal_service._build_signal(asset, segment),
        lane_id,
    )
    target_file = long_form_signal_service._choose_target_file(segment, lane_id, assessment)
    response_modes, primary_route, route_reason, route_score = long_form_signal_service._classify_routes(
        segment,
        assessment,
        target_file,
        worldview_score,
        source_context_excerpt=source_context_excerpt,
    )
    manual_reference_source = long_form_signal_service._is_manual_reference_source(asset)
    lived_proof_context = long_form_signal_service._has_lived_proof_context(segment, source_context_excerpt)
    high_value_non_lived = long_form_signal_service._is_high_value_non_lived_segment(segment, assessment, route_score)
    if manual_reference_source and "belief_evidence" in response_modes and not lived_proof_context and not high_value_non_lived:
        response_modes = [mode for mode in response_modes if mode != "belief_evidence"]
        if not response_modes:
            response_modes = ["post_seed"]
        if primary_route == "belief_evidence":
            primary_route = response_modes[0]
        route_reason = (
            "segment is strategic source intelligence and should stay a post seed unless lived-proof context or exceptional value is clear"
        )
    weak_source_fragment = (
        target_file == long_form_signal_service.TARGET_STORIES
        and long_form_signal_service._is_low_context_story_fragment(segment, source_context_excerpt)
    )
    handoff_lane, handoff_reason, secondary_consumers = long_form_signal_service._handoff_lane_for_candidate(
        segment=segment,
        lane_hint=lane_id,
        target_file=target_file,
        assessment=assessment,
        response_modes=response_modes,
        primary_route=primary_route,
        route_reason=route_reason,
        route_score=route_score,
        weak_source_fragment=weak_source_fragment,
        manual_reference_source=manual_reference_source,
        lived_proof_context=lived_proof_context,
        high_value_non_lived=high_value_non_lived,
    )

    expected_lane = str(probe.get("expected_handoff_lane") or "brief_only")
    exact_match = handoff_lane == expected_lane

    source_contract_missing = [
        field
        for field, value in {
            "source_channel": asset.get("source_channel"),
            "source_type": asset.get("source_type"),
            "source_url": asset.get("source_url"),
        }.items()
        if not str(value or "").strip()
    ]

    stage_results: list[dict[str, Any]] = []
    if source_contract_missing:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "source_contract",
                    "fail",
                    "source_contract_incomplete",
                    "The probe is missing required source metadata for honest handoff classification.",
                ),
                missing_fields=source_contract_missing,
            )
        )
    else:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "source_contract",
                    "pass",
                    "source_contract_ready",
                    f"Captured {asset['source_channel']} / {asset['source_type']} metadata before classification.",
                ),
                evidence=[asset["source_channel"], asset["source_type"]],
            )
        )

    if weak_source_fragment:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "segment_quality",
                    "warn",
                    "segment_low_context",
                    "The segment depends on missing story context, so downstream promotion should be conservative.",
                ),
                score=route_score,
                evidence=[source_context_excerpt],
            )
        )
    elif route_score < 8:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "segment_quality",
                    "warn",
                    "segment_too_weak",
                    "The segment is valid, but it is not especially strong for downstream promotion.",
                ),
                score=route_score,
                evidence=[source_context_excerpt],
            )
        )
    else:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "segment_quality",
                    "pass",
                    "segment_ready",
                    "The segment is clean enough and context-rich enough for handoff classification.",
                ),
                score=route_score,
                evidence=[source_context_excerpt],
            )
        )

    assessment_fields = [
        field
        for field, value in {
            "stance": assessment.get("stance"),
            "belief_relation": assessment.get("belief_relation"),
        }.items()
        if not str(value or "").strip()
    ]
    if assessment_fields:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "belief_assessment",
                    "warn",
                    "assessment_missing",
                    "The belief engine returned a thin stance packet, which weakens downstream confidence.",
                ),
                missing_fields=assessment_fields,
                evidence=[str(assessment.get("belief_summary") or "")],
            )
        )
    else:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "belief_assessment",
                    "pass",
                    "assessment_ready",
                    "The belief engine returned enough stance context to support a handoff decision.",
                ),
                evidence=[
                    str(assessment.get("stance") or ""),
                    str(assessment.get("belief_relation") or ""),
                    str(assessment.get("belief_summary") or ""),
                ],
            )
        )

    if not response_modes or not primary_route:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "route_classification",
                    "fail",
                    "route_modes_missing",
                    "The classifier did not return enough route structure to compute a handoff lane.",
                ),
                score=route_score,
                missing_fields=["response_modes", "primary_route"],
            )
        )
    elif route_score < 5:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "route_classification",
                    "warn",
                    "route_score_low",
                    "A route was selected, but the underlying score is low enough that promotion confidence should stay light.",
                ),
                score=route_score,
                evidence=[primary_route, *response_modes],
            )
        )
    else:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "route_classification",
                    "pass",
                    "route_classified",
                    f"Selected {primary_route} with {', '.join(response_modes)} available as downstream modes.",
                ),
                score=route_score,
                evidence=[primary_route, *response_modes],
            )
        )

    if expected_lane == "source_only" and handoff_lane != "source_only":
        reason = "low_context_story_not_downgraded" if weak_source_fragment else "manual_reference_not_downgraded"
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "guardrail_application",
                    "fail",
                    reason,
                    "The probe should have stayed upstream, but the guardrail did not hold.",
                ),
                evidence=[handoff_lane, handoff_reason],
            )
        )
    else:
        guardrail_detail = (
            "The source-only guardrail held as expected."
            if expected_lane == "source_only"
            else "No upstream-only downgrade was required for this probe."
        )
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "guardrail_application",
                    "pass",
                    "guardrail_held",
                    guardrail_detail,
                ),
                evidence=[handoff_lane, handoff_reason],
            )
        )

    mismatch_reason = "handoff_lane_mismatch"
    if expected_lane != "persona_candidate" and handoff_lane == "persona_candidate":
        mismatch_reason = "persona_overpromotion"
    elif expected_lane == "post_candidate" and handoff_lane != "post_candidate":
        mismatch_reason = "post_underpromotion"
    elif expected_lane == "route_to_pm" and handoff_lane != "route_to_pm":
        mismatch_reason = "pm_underpromotion"

    if exact_match:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "handoff_decision",
                    "pass",
                    "handoff_match",
                    f"Expected {expected_lane} and the classifier returned {handoff_lane}.",
                ),
                evidence=[expected_lane, handoff_lane, handoff_reason],
            )
        )
    else:
        stage_results.append(
            _extend_stage(
                _handoff_stage_result(
                    "handoff_decision",
                    "fail",
                    mismatch_reason,
                    f"Expected {expected_lane} but the classifier returned {handoff_lane}.",
                ),
                evidence=[expected_lane, handoff_lane, handoff_reason],
            )
        )

    return {
        "expected_handoff_lane": expected_lane,
        "actual_handoff_lane": handoff_lane,
        "exact_match": exact_match,
        "primary_route": primary_route,
        "response_modes": response_modes,
        "route_reason": route_reason,
        "route_score": route_score,
        "lane_hint": lane_id,
        "target_file": target_file,
        "assessment": assessment,
        "handoff_reason": handoff_reason,
        "secondary_consumers": secondary_consumers,
        "manual_reference_source": manual_reference_source,
        "weak_source_fragment": weak_source_fragment,
        "stage_results": stage_results,
        "sample_run": {
            "topic": probe["title"],
            "audience": expected_lane,
            "generation_strategy": "source_handoff_matrix",
            "llm_request_count": 0,
            "platform": probe.get("platform"),
            "source_type": asset["source_type"],
            "structural_fallbacks": [] if exact_match else ["handoff_mismatch"],
            "top_warnings": [handoff_reason] if handoff_reason else [],
            "stage_results": stage_results,
            "top_option_preview": segment,
            "signal_snapshot": {
                "source_channel": asset["source_channel"],
                "source_class": asset["source_class"],
                "unit_kind": "long_form_segment",
                "response_modes": response_modes,
                "topic_tags": [probe.get("topic") or ""],
                "core_claim": segment,
                "supporting_claims": [str(probe.get("title") or "")],
                "why_it_matters": route_reason,
                "role_alignment": str(assessment.get("experience_summary") or ""),
                "expected_handoff_lane": expected_lane,
                "actual_handoff_lane": handoff_lane,
                "primary_route": primary_route,
                "lane_hint": lane_id,
                "handoff_reason": handoff_reason,
                "target_file": target_file,
                "secondary_consumers": secondary_consumers,
            },
        },
    }


def _build_social_probe_signal(probe: dict[str, str]) -> dict[str, Any]:
    return normalize_saved_signal(
        {
            "id": f"lab-article::{probe['title']}",
            "ingest_mode": "harvested",
            "capture_method": "harvested",
            "source_platform": probe["platform"],
            "source_type": "article",
            "source_url": probe["url"],
            "author": probe["author"],
            "title": probe["title"],
            "summary": probe["raw_text"],
            "headline_candidates": [probe["title"]],
            "priority_lane": "current-role",
            "source_metadata": {"extraction_method": "lab_article_probe"},
            "trust_notes": ["lab_article_probe"],
            "topic_tags": [probe["topic"]],
        },
        raw_text=probe["raw_text"],
    )


def _audit_rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((count / total) * 100, 1)


def _bucket_counts(values: list[str], *, empty_label: str = "unknown") -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or empty_label)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _summary_quality_flags(asset: dict[str, Any]) -> list[str]:
    existing = [str(item) for item in (asset.get("quality_flags") or []) if str(item).strip()]
    if existing:
        return existing
    flags: list[str] = []
    summary = str(asset.get("summary") or "").strip()
    structured_summary = str(asset.get("structured_summary") or "").strip()
    if not summary or len(summary.split()) < 7 or "http" in summary.lower() or "<00:" in summary:
        flags.append("summary_needs_cleanup")
    if not structured_summary:
        flags.append("structured_summary_missing")
    if not (asset.get("lessons_learned") or []):
        flags.append("lessons_missing")
    if not (asset.get("key_anecdotes") or []):
        flags.append("anecdotes_missing")
    if not (asset.get("reusable_quotes") or []):
        flags.append("quotes_missing")
    return flags


def _load_live_source_payloads() -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    source_assets_payload: dict[str, Any] | None = None
    long_form_routes_payload: dict[str, Any] | None = None
    source = "empty"

    try:
        persisted_snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
            persisted_only=True,
            include_workspace_files=False,
            include_doc_entries=False,
        )
    except Exception:
        persisted_snapshot = {}

    if isinstance(persisted_snapshot, dict):
        source_assets_payload = persisted_snapshot.get("source_assets") if isinstance(persisted_snapshot.get("source_assets"), dict) else None
        long_form_routes_payload = persisted_snapshot.get("long_form_routes") if isinstance(persisted_snapshot.get("long_form_routes"), dict) else None
        if source_assets_payload or long_form_routes_payload:
            source = "persisted_snapshot"

    try:
        runtime_source_assets = build_source_asset_inventory(
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
            repo_root=WORKSPACE_ROOT,
        )
    except Exception:
        runtime_source_assets = None

    if runtime_source_assets and (runtime_source_assets.get("items") or []):
        source_assets_payload = runtime_source_assets
        source = "runtime_corpus"

    try:
        runtime_routes = long_form_signal_service.build_long_form_route_summary(
            repo_root=WORKSPACE_ROOT,
            source_assets=source_assets_payload,
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
            max_assets=24,
            max_segments_per_asset=2,
        )
    except Exception:
        runtime_routes = None

    if runtime_routes and (runtime_routes.get("candidates") or runtime_routes.get("assets_considered")):
        long_form_routes_payload = runtime_routes
        source = "runtime_corpus"

    return source_assets_payload, long_form_routes_payload, source


def _build_live_source_handoff_audit(*, limit_candidates: int = 12, limit_assets: int = 10) -> dict[str, Any]:
    source_assets_payload, long_form_routes_payload, source = _load_live_source_payloads()
    assets = list((source_assets_payload or {}).get("items") or [])
    candidates = list((long_form_routes_payload or {}).get("candidates") or [])

    asset_count = len(assets)
    candidate_count = len(candidates)
    channel_counts = dict(((source_assets_payload or {}).get("counts") or {}).get("by_channel") or {})
    handoff_lane_counts = dict((long_form_routes_payload or {}).get("handoff_lane_counts") or {})
    primary_route_counts = dict((long_form_routes_payload or {}).get("primary_route_counts") or {})
    target_file_counts = _bucket_counts([str(item.get("target_file") or "unknown") for item in candidates])
    summary_origin_counts = _bucket_counts([str(item.get("summary_origin") or "unknown") for item in assets])
    quality_flags = [_summary_quality_flags(asset) for asset in assets]
    issue_counts = _bucket_counts([flag for flags in quality_flags for flag in flags], empty_label="none")

    summary_ready = sum(1 for asset in assets if str(asset.get("summary") or "").strip())
    structured_summary_ready = sum(1 for asset in assets if str(asset.get("structured_summary") or "").strip())
    lessons_ready = sum(1 for asset in assets if asset.get("lessons_learned"))
    anecdotes_ready = sum(1 for asset in assets if asset.get("key_anecdotes"))
    quotes_ready = sum(1 for asset in assets if asset.get("reusable_quotes"))
    noisy_summary_count = sum(1 for flags in quality_flags if "summary_needs_cleanup" in flags)
    package_ready_count = sum(
        1
        for asset in assets
        if str(asset.get("structured_summary") or "").strip()
        and any(asset.get(key) for key in ("lessons_learned", "key_anecdotes", "reusable_quotes"))
    )

    candidate_samples: list[dict[str, Any]] = []
    for candidate in candidates[:limit_candidates]:
        title = str(candidate.get("title") or "Untitled candidate")
        segment = str(candidate.get("segment") or "").strip()
        candidate_samples.append(
            {
                "topic": title,
                "audience": "live_source_sample",
                "generation_strategy": "source_handoff_live_sample",
                "llm_request_count": 0,
                "platform": candidate.get("source_channel"),
                "source_type": "long_form_segment",
                "structural_fallbacks": [],
                "top_warnings": [str(candidate.get("handoff_reason") or "")] if str(candidate.get("handoff_reason") or "").strip() else [],
                "stage_results": [],
                "top_option_preview": segment or title,
                "signal_snapshot": {
                    "source_channel": candidate.get("source_channel"),
                    "source_class": "long_form_media",
                    "unit_kind": "live_source_sample",
                    "response_modes": candidate.get("response_modes") or [],
                    "topic_tags": [str(candidate.get("lane_hint") or "")],
                    "core_claim": segment,
                    "supporting_claims": [title],
                    "why_it_matters": str(candidate.get("route_reason") or ""),
                    "role_alignment": str(candidate.get("belief_summary") or ""),
                    "actual_handoff_lane": str(candidate.get("handoff_lane") or ""),
                    "primary_route": str(candidate.get("primary_route") or ""),
                    "lane_hint": str(candidate.get("lane_hint") or ""),
                    "handoff_reason": str(candidate.get("handoff_reason") or ""),
                    "target_file": str(candidate.get("target_file") or ""),
                    "secondary_consumers": candidate.get("secondary_consumers") or [],
                    "source_path": str(candidate.get("source_path") or ""),
                    "source_url": str(candidate.get("source_url") or ""),
                },
            }
        )

    asset_samples: list[dict[str, Any]] = []
    for asset in assets[:limit_assets]:
        asset_samples.append(
            {
                "title": str(asset.get("title") or "Untitled asset"),
                "source_channel": str(asset.get("source_channel") or ""),
                "source_type": str(asset.get("source_type") or ""),
                "source_path": str(asset.get("source_path") or ""),
                "source_url": str(asset.get("source_url") or ""),
                "summary": str(asset.get("summary") or ""),
                "summary_origin": str(asset.get("summary_origin") or "unknown"),
                "structured_summary": str(asset.get("structured_summary") or ""),
                "lessons_learned": [str(item) for item in (asset.get("lessons_learned") or []) if str(item).strip()],
                "key_anecdotes": [str(item) for item in (asset.get("key_anecdotes") or []) if str(item).strip()],
                "reusable_quotes": [str(item) for item in (asset.get("reusable_quotes") or []) if str(item).strip()],
                "open_questions": [str(item) for item in (asset.get("open_questions") or []) if str(item).strip()],
                "quality_flags": _summary_quality_flags(asset),
                "word_count": asset.get("word_count"),
                "clean_word_count": asset.get("clean_word_count"),
                "sentence_count": asset.get("sentence_count"),
            }
        )

    top_issues = [
        {
            "id": issue,
            "label": issue.replace("_", " "),
            "count": count,
        }
        for issue, count in list(issue_counts.items())[:6]
        if issue != "none"
    ]

    return {
        "source": source,
        "generated_at": _now_iso(),
        "asset_count": asset_count,
        "candidate_count": candidate_count,
        "segments_total": int((long_form_routes_payload or {}).get("segments_total") or candidate_count),
        "quality_metrics": {
            "summary_coverage_rate": _audit_rate(summary_ready, asset_count),
            "structured_summary_rate": _audit_rate(structured_summary_ready, asset_count),
            "lesson_coverage_rate": _audit_rate(lessons_ready, asset_count),
            "anecdote_coverage_rate": _audit_rate(anecdotes_ready, asset_count),
            "quote_coverage_rate": _audit_rate(quotes_ready, asset_count),
            "noisy_summary_rate": _audit_rate(noisy_summary_count, asset_count),
            "package_readiness_rate": _audit_rate(package_ready_count, asset_count),
        },
        "slice_counts": {
            "handoff_lane_counts": handoff_lane_counts,
            "primary_route_counts": primary_route_counts,
            "channel_counts": channel_counts,
            "target_file_counts": target_file_counts,
            "summary_origin_counts": summary_origin_counts,
            "issue_counts": issue_counts,
        },
        "top_issues": top_issues,
        "candidate_samples": candidate_samples,
        "asset_samples": asset_samples,
    }


def _build_live_source_handoff_samples(limit: int = 5) -> list[dict[str, Any]]:
    return (_build_live_source_handoff_audit(limit_candidates=limit).get("candidate_samples") or [])[:limit]


def _round_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)


def _average(values: list[float]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return _round_score(sum(filtered) / len(filtered))


def _ratio_score(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return _round_score((numerator / denominator) * 10.0)


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        results.append(cleaned)
    return results


def _extend_stage(
    stage_result: dict[str, Any],
    *,
    score: float | None = None,
    evidence: list[str] | None = None,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    stage_result["score"] = _round_score(score)
    stage_result["evidence"] = [str(item) for item in (evidence or []) if str(item).strip()]
    stage_result["missing_fields"] = [str(item) for item in (missing_fields or []) if str(item).strip()]
    return stage_result


def _build_social_probe_stages(
    *,
    signal: dict[str, Any],
    lane_rows: list[dict[str, Any]],
    missing_lanes: list[str],
) -> list[dict[str, Any]]:
    total_lanes = max(len(lane_rows), 1)
    contexts = [row.get("context_snapshot") or {} for row in lane_rows]
    evaluations = [row.get("evaluation") or {} for row in lane_rows]
    article_packets = [row.get("article_understanding") or {} for row in lane_rows]
    retrieval_packets = [row.get("persona_retrieval") or {} for row in lane_rows]
    perspective_packets = [row.get("johnnie_perspective") or {} for row in lane_rows]
    brief_packets = [row.get("reaction_brief") or {} for row in lane_rows]
    response_type_packets = [row.get("response_type_packet") or {} for row in lane_rows]
    composition_packets = [row.get("composition_traces") or {} for row in lane_rows]
    stage_packets = [row.get("stage_evaluation") or {} for row in lane_rows]

    source_channel = str(signal.get("source_channel") or "")
    source_class = str(signal.get("source_class") or "")
    unit_kind = str(signal.get("unit_kind") or "")
    response_modes = [str(item) for item in (signal.get("response_modes") or []) if str(item).strip()]
    standout_lines = [str(item) for item in (signal.get("standout_lines") or []) if str(item).strip()]
    supporting_claims = [str(item) for item in (signal.get("supporting_claims") or []) if str(item).strip()]
    topic_tags = [str(item) for item in (signal.get("topic_tags") or []) if str(item).strip()]
    why_it_matters = str(signal.get("why_it_matters") or "").strip()
    role_alignment = str(signal.get("role_alignment") or "").strip()

    beliefs = _unique_non_empty([row.get("belief_used") or "" for row in lane_rows])
    experience_anchors = _unique_non_empty([row.get("experience_anchor") or "" for row in lane_rows])
    stances = _unique_non_empty([row.get("stance") or "" for row in lane_rows])
    takeaway_strategies = _unique_non_empty([row.get("source_takeaway_strategy") or "" for row in lane_rows])
    technique_bundles = [tuple(row.get("techniques") or []) for row in lane_rows if row.get("techniques")]
    article_stances = _unique_non_empty([str(packet.get("article_stance") or "") for packet in article_packets])
    article_world_positions = _unique_non_empty([str(packet.get("article_world_position") or "") for packet in article_packets])
    world_contexts = _unique_non_empty([str(packet.get("world_context") or "") for packet in article_packets])
    world_stakes = _unique_non_empty([str(packet.get("world_stakes") or "") for packet in article_packets])
    audiences_impacted = _unique_non_empty(
        [str(item) for packet in article_packets for item in (packet.get("audience_impacted") or []) if str(item).strip()]
    )
    source_expression_packets = _unique_non_empty(
        [str(packet.get("source_expression") or "") for packet in article_packets]
    )
    retrieval_top_candidate_counts = [len(packet.get("top_candidates") or []) for packet in retrieval_packets]
    retrieval_diversities = [float(packet.get("retrieval_diversity_score") or 0.0) for packet in retrieval_packets]
    retrieval_claim_counts = [len(packet.get("relevant_claims") or []) for packet in retrieval_packets]
    retrieval_story_counts = [len(packet.get("relevant_stories") or []) for packet in retrieval_packets]
    retrieval_initiative_counts = [len(packet.get("relevant_initiatives") or []) for packet in retrieval_packets]
    retrieval_delta_counts = [len(packet.get("relevant_deltas") or []) for packet in retrieval_packets]
    perspective_agree = _unique_non_empty([str(packet.get("agree_with") or "") for packet in perspective_packets])
    perspective_pushback = _unique_non_empty([str(packet.get("pushback") or "") for packet in perspective_packets])
    perspective_lived = _unique_non_empty([str(packet.get("lived_addition") or "") for packet in perspective_packets])
    perspective_reactions = _unique_non_empty([str(packet.get("personal_reaction") or "") for packet in perspective_packets])
    perspective_what_matters = _unique_non_empty([str(packet.get("what_matters_most") or "") for packet in perspective_packets])
    brief_article_views = _unique_non_empty([str(packet.get("article_view") or "") for packet in brief_packets])
    brief_johnnie_views = _unique_non_empty([str(packet.get("johnnie_view") or "") for packet in brief_packets])
    brief_tensions = _unique_non_empty([str(packet.get("tension") or "") for packet in brief_packets])
    brief_content_angles = _unique_non_empty([str(packet.get("content_angle") or "") for packet in brief_packets])
    response_types = _unique_non_empty([str(packet.get("response_type") or "") for packet in response_type_packets])
    response_type_confidences = [float(packet.get("type_confidence") or 0.0) for packet in response_type_packets]
    humor_packets = [packet.get("humor_safety") or {} for packet in response_type_packets]
    composition_comment_traces = [packet.get("comment") or {} for packet in composition_packets]
    composition_repost_traces = [packet.get("repost") or {} for packet in composition_packets]
    template_families = _unique_non_empty(
        [str(trace.get("template_family") or "") for trace in [*composition_comment_traces, *composition_repost_traces]]
    )
    response_type_selected_humor = sum(1 for packet in response_type_packets if str(packet.get("response_type") or "") == "humor")

    any_generic_warning = any(
        "copy still contains generic language" in (row.get("top_warnings") or [])
        or "copy still contains abstract meta phrasing" in (row.get("top_warnings") or [])
        for row in lane_rows
    )
    any_role_safety_issue = any(str(row.get("role_safety") or "safe") != "safe" for row in lane_rows)
    any_takeaway_missing = any(not str(row.get("source_takeaway") or "").strip() for row in lane_rows)
    any_belief_missing = any(not str(row.get("belief_used") or "").strip() for row in lane_rows)
    any_experience_missing = any(not str(row.get("experience_anchor") or "").strip() for row in lane_rows)
    any_technique_missing = any(not (row.get("techniques") or []) for row in lane_rows)

    comment_passes = sum(1 for row in lane_rows if row.get("comment_status") == "pass")
    repost_passes = sum(1 for row in lane_rows if row.get("repost_status") == "pass")

    expression_structures = _unique_non_empty(
        [str(((row.get("expression_assessment") or {}).get("source_structure")) or "") for row in lane_rows]
    )
    lane_scores = [float((row.get("evaluation") or {}).get("lane_distinctiveness") or 0.0) for row in lane_rows]
    voice_scores = [float((row.get("evaluation") or {}).get("voice_match") or 0.0) for row in lane_rows]
    benchmark_scores = [float((row.get("evaluation") or {}).get("benchmark_score") or 0.0) for row in lane_rows]
    article_understanding_scores = [float((row.get("stage_evaluation") or {}).get("article_understanding_score") or 0.0) for row in lane_rows]
    world_context_scores = [float((row.get("stage_evaluation") or {}).get("world_context_score") or 0.0) for row in lane_rows]
    article_stance_scores = [float((row.get("stage_evaluation") or {}).get("article_stance_score") or 0.0) for row in lane_rows]
    persona_retrieval_scores = [float((row.get("stage_evaluation") or {}).get("persona_retrieval_score") or 0.0) for row in lane_rows]
    belief_relevance_scores = [float((row.get("stage_evaluation") or {}).get("belief_relevance_score") or 0.0) for row in lane_rows]
    experience_relevance_scores = [float((row.get("stage_evaluation") or {}).get("experience_relevance_score") or 0.0) for row in lane_rows]
    johnnie_perspective_scores = [float((row.get("stage_evaluation") or {}).get("johnnie_perspective_score") or 0.0) for row in lane_rows]
    reaction_brief_scores = [float((row.get("stage_evaluation") or {}).get("reaction_brief_score") or 0.0) for row in lane_rows]
    template_composition_scores = [float((row.get("stage_evaluation") or {}).get("template_composition_score") or 0.0) for row in lane_rows]
    response_type_scores = [float((row.get("stage_evaluation") or {}).get("response_type_score") or 0.0) for row in lane_rows]
    humor_safety_scores = [float((row.get("stage_evaluation") or {}).get("humor_safety_score") or 0.0) for row in lane_rows]

    stages: list[dict[str, Any]] = []

    signal_score = _ratio_score(
        sum(
            1
            for item in [signal.get("raw_text"), signal.get("title"), signal.get("summary"), signal.get("core_claim")]
            if str(item or "").strip()
        ),
        4,
    )
    stages.append(
        _extend_stage(
            _social_stage_result(
                "signal_intake",
                "pass" if signal.get("core_claim") else "fail",
                "article_signal_ready" if signal.get("core_claim") else "article_signal_missing_claims",
                (
                    "The article has enough raw signal to normalize into a working source object."
                    if signal.get("core_claim")
                    else "The article normalized, but the core claim is still missing."
                ),
            ),
            score=signal_score,
            evidence=[
                f"title={signal.get('title')}",
                f"author={signal.get('author')}",
                f"platform={source_channel}",
            ],
            missing_fields=[name for name, value in [("raw_text", signal.get("raw_text")), ("core_claim", signal.get("core_claim"))] if not str(value or "").strip()],
        )
    )

    contract_missing = [
        name
        for name, value in [
            ("source_channel", source_channel),
            ("source_class", source_class),
            ("unit_kind", unit_kind),
            ("response_modes", ",".join(response_modes)),
        ]
        if not str(value or "").strip()
    ]
    stages.append(
        _extend_stage(
            _social_stage_result(
                "source_contract",
                "pass" if not contract_missing else "warn",
                "source_contract_ready" if not contract_missing else "source_contract_incomplete",
                (
                    f"Classified this article as {source_channel or 'unknown'} / {source_class or 'unknown'} / {unit_kind or 'unknown'}."
                    if not contract_missing
                    else "The source contract is incomplete, so downstream routing is relying on partial metadata."
                ),
            ),
            score=_ratio_score(4 - len(contract_missing), 4),
            evidence=[
                f"channel={source_channel or 'missing'}",
                f"class={source_class or 'missing'}",
                f"unit={unit_kind or 'missing'}",
                f"modes={', '.join(response_modes) or 'missing'}",
            ],
            missing_fields=contract_missing,
        )
    )

    claim_missing_fields = []
    if not signal.get("core_claim"):
        claim_missing_fields.append("core_claim")
    if not standout_lines:
        claim_missing_fields.append("standout_lines")
    if not supporting_claims:
        claim_missing_fields.append("supporting_claims")
    stages.append(
        _extend_stage(
            _social_stage_result(
                "claim_extraction",
                "pass" if not claim_missing_fields else "warn",
                "claim_packet_ready" if not claim_missing_fields else "supporting_signal_thin",
                (
                    "The article has a usable core claim plus enough support for downstream rewriting."
                    if not claim_missing_fields
                    else "Claim extraction worked, but the support packet is still thin."
                ),
            ),
            score=_ratio_score(3 - len(claim_missing_fields), 3),
            evidence=[
                f"core_claim={signal.get('core_claim') or 'missing'}",
                f"standout_lines={len(standout_lines)}",
                f"supporting_claims={len(supporting_claims)}",
            ],
            missing_fields=claim_missing_fields,
        )
    )

    world_missing_fields = []
    if not world_contexts:
        world_missing_fields.append("world_context")
    if not world_stakes:
        world_missing_fields.append("world_stakes")
    if not article_world_positions and not role_alignment:
        world_missing_fields.append("article_world_position")
    if not audiences_impacted:
        world_missing_fields.append("audience_impacted")
    world_status = "pass" if not world_missing_fields else "warn" if world_contexts or world_stakes or topic_tags else "missing"
    world_reason = (
        "world_model_ready"
        if world_status == "pass"
        else "world_model_thin"
        if world_status == "warn"
        else "world_model_missing"
    )
    world_detail = (
        "The system has enough world-level context to explain why this article matters beyond its raw text."
        if world_status == "pass"
        else "The system has topic tags, but world/stakes modeling is still thin."
        if world_status == "warn"
        else "The system is not explicitly modeling why this article matters in the world yet."
    )
    stages.append(
        _extend_stage(
            _social_stage_result("world_understanding", world_status, world_reason, world_detail),
            score=_average(world_context_scores) or _ratio_score(sum(1 for value in [world_contexts, world_stakes, article_world_positions, audiences_impacted] if value), 4),
            evidence=[
                f"topic_tags={', '.join(topic_tags) or 'missing'}",
                f"world_context={world_contexts[0] if world_contexts else why_it_matters or 'missing'}",
                f"world_stakes={world_stakes[0] if world_stakes else 'missing'}",
                f"world_position={article_world_positions[0] if article_world_positions else role_alignment or 'missing'}",
            ],
            missing_fields=world_missing_fields,
        )
    )

    article_stance_missing_fields = []
    if not article_stances:
        article_stance_missing_fields.append("article_stance")
    if not any(float(packet.get("article_stance_confidence") or 0.0) > 0.0 for packet in article_packets):
        article_stance_missing_fields.append("article_stance_confidence")
    if not article_world_positions:
        article_stance_missing_fields.append("article_world_position")
    article_stance_confidence = _average([float(packet.get("article_stance_confidence") or 0.0) for packet in article_packets])
    article_stance_status = (
        "fail"
        if not article_stances
        else "warn"
        if article_stance_confidence is None or article_stance_confidence < 7.0 or article_stance_missing_fields
        else "pass"
    )
    stages.append(
        _extend_stage(
            _social_stage_result(
                "article_stance",
                article_stance_status,
                "article_stance_missing"
                if article_stance_status == "fail"
                else "article_stance_confidence_low"
                if article_stance_status == "warn"
                else "article_stance_ready",
                (
                    "The system is now carrying a first-class article stance packet, but the stance confidence or world positioning is still thin."
                    if article_stance_status == "warn"
                    else "The system modeled the article's own stance before drafting."
                    if article_stance_status == "pass"
                    else "The system did not return a usable article stance packet."
                ),
            ),
            score=_average(article_stance_scores) or _ratio_score(3 - len(article_stance_missing_fields), 3),
            evidence=[
                f"article_stances={'; '.join(article_stances) or 'missing'}",
                f"avg_confidence={article_stance_confidence if article_stance_confidence is not None else 'missing'}",
                f"world_position={article_world_positions[0] if article_world_positions else 'missing'}",
            ],
            missing_fields=article_stance_missing_fields,
        )
    )

    source_expression_missing = not any(expression_structures) and not any(source_expression_packets)
    stages.append(
        _extend_stage(
            _social_stage_result(
                "source_expression",
                "pass" if not source_expression_missing else "warn",
                "source_expression_ready" if not source_expression_missing else "source_expression_missing",
                (
                    "The system captured article expression structure and is tracking it during rewrite."
                    if not source_expression_missing
                    else "The system is not carrying forward enough article-expression structure."
                ),
            ),
            score=_average(
                [float(((row.get("expression_assessment") or {}).get("source_expression_quality")) or 0.0) for row in lane_rows]
            ),
            evidence=[
                f"structures={', '.join(expression_structures or source_expression_packets) or 'missing'}",
                f"strategies={', '.join(takeaway_strategies) or 'missing'}",
            ],
            missing_fields=["source_expression_structure"] if source_expression_missing else [],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "lane_routing",
                "fail" if missing_lanes else "pass",
                "lane_matrix_incomplete" if missing_lanes else "lane_matrix_complete",
                (
                    f"Missing lane variants: {', '.join(missing_lanes)}."
                    if missing_lanes
                    else "All target lanes returned variants for this article signal."
                ),
            ),
            score=_ratio_score(total_lanes - len(missing_lanes), total_lanes),
            evidence=[f"lanes_returned={total_lanes - len(missing_lanes)}/{total_lanes}"],
            missing_fields=[f"lane:{value}" for value in missing_lanes],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "persona_truth",
                "pass" if beliefs or experience_anchors else "fail",
                "persona_truth_ready" if beliefs or experience_anchors else "persona_truth_missing",
                (
                    "The system loaded persona truth artifacts before drafting."
                    if beliefs or experience_anchors
                    else "No belief or experience anchors were returned from persona truth."
                ),
            ),
            score=_ratio_score(sum(1 for value in [beliefs, experience_anchors] if value), 2),
            evidence=[
                f"beliefs={len(beliefs)}",
                f"experience_anchors={len(experience_anchors)}",
            ],
            missing_fields=["beliefs", "experience_anchors"] if not (beliefs or experience_anchors) else [],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "persona_retrieval",
                "fail"
                if not any(retrieval_top_candidate_counts)
                else "warn"
                if (_average(retrieval_diversities) or 0.0) < 6.5 or sum(1 for values in [retrieval_claim_counts, retrieval_story_counts, retrieval_initiative_counts, retrieval_delta_counts] if sum(values) > 0) < 2
                else "pass",
                "persona_retrieval_missing"
                if not any(retrieval_top_candidate_counts)
                else "retrieval_diversity_thin"
                if (_average(retrieval_diversities) or 0.0) < 6.5
                else "persona_retrieval_ready",
                (
                    "The system returned ranked persona candidates, but the retrieval set is still thin or not diverse enough yet."
                    if any(retrieval_top_candidate_counts)
                    and ((_average(retrieval_diversities) or 0.0) < 6.5 or sum(1 for values in [retrieval_claim_counts, retrieval_story_counts, retrieval_initiative_counts, retrieval_delta_counts] if sum(values) > 0) < 2)
                    else "The system retrieved ranked article-specific persona artifacts before drafting."
                    if any(retrieval_top_candidate_counts)
                    else "The system did not return ranked article-specific persona artifacts."
                ),
            ),
            evidence=[
                f"top_candidates={sum(retrieval_top_candidate_counts)}",
                f"claims={sum(retrieval_claim_counts)} stories={sum(retrieval_story_counts)} initiatives={sum(retrieval_initiative_counts)} deltas={sum(retrieval_delta_counts)}",
                f"avg_retrieval_diversity={_average(retrieval_diversities) if retrieval_diversities else 'missing'}",
            ],
            score=_average(persona_retrieval_scores) or _ratio_score(sum(1 for count in retrieval_top_candidate_counts if count > 0), total_lanes),
            missing_fields=[
                field
                for field, counts in {
                    "top_candidates": retrieval_top_candidate_counts,
                    "relevant_claims": retrieval_claim_counts,
                    "relevant_stories": retrieval_story_counts,
                    "relevant_initiatives": retrieval_initiative_counts,
                    "relevant_deltas": retrieval_delta_counts,
                }.items()
                if not any(counts)
            ],
        )
    )

    belief_overused = len(beliefs) < 3
    stages.append(
        _extend_stage(
            _social_stage_result(
                "belief_selection",
                "fail" if any_belief_missing else "warn" if belief_overused else "pass",
                "belief_missing" if any_belief_missing else "belief_overused" if belief_overused else "belief_selection_ready",
                (
                    "Each lane returned a belief frame, but the belief set is still too narrow across the matrix."
                    if belief_overused and not any_belief_missing
                    else "Each lane returned a usable belief frame."
                    if not any_belief_missing
                    else "At least one lane returned no belief frame."
                ),
            ),
            score=_average(belief_relevance_scores) or _ratio_score(len(beliefs), len(SOCIAL_LANE_MATRIX)),
            evidence=[f"beliefs={'; '.join(beliefs) or 'missing'}"],
            missing_fields=["belief_used"] if any_belief_missing else [],
        )
    )

    experience_overused = len(experience_anchors) < 3
    stages.append(
        _extend_stage(
            _social_stage_result(
                "experience_selection",
                "fail" if any_experience_missing else "warn" if experience_overused else "pass",
                "experience_anchor_missing" if any_experience_missing else "experience_anchor_overused" if experience_overused else "experience_selection_ready",
                (
                    "Each lane returned an experience anchor, but the experience set is still too narrow across the matrix."
                    if experience_overused and not any_experience_missing
                    else "Each lane returned a usable experience anchor."
                    if not any_experience_missing
                    else "At least one lane returned no experience anchor."
                ),
            ),
            score=_average(experience_relevance_scores) or _ratio_score(len(experience_anchors), len(SOCIAL_LANE_MATRIX)),
            evidence=[f"experience_anchors={'; '.join(experience_anchors) or 'missing'}"],
            missing_fields=["experience_anchor"] if any_experience_missing else [],
        )
    )

    johnnie_missing_fields = []
    if not perspective_reactions:
        johnnie_missing_fields.append("personal_reaction")
    if not perspective_agree:
        johnnie_missing_fields.append("agree_with")
    if not perspective_pushback:
        johnnie_missing_fields.append("pushback")
    if not perspective_lived:
        johnnie_missing_fields.append("lived_addition")
    stages.append(
        _extend_stage(
            _social_stage_result(
                "johnnie_perspective",
                "fail"
                if not perspective_reactions
                else "warn"
                if johnnie_missing_fields
                else "pass",
                "johnnie_reaction_missing"
                if not perspective_reactions
                else "lived_reaction_missing"
                if johnnie_missing_fields
                else "johnnie_perspective_ready",
                (
                    "The system modeled a Johnnie perspective packet, but one or more reaction slices are still thin."
                    if perspective_reactions and johnnie_missing_fields
                    else "The system modeled what Johnnie agrees with, pushes back on, and adds from lived experience."
                    if perspective_reactions
                    else "The system did not return a usable Johnnie perspective packet."
                ),
            ),
            evidence=[
                f"stances={', '.join(stances) or 'missing'}",
                f"agree={len(perspective_agree)} pushback={len(perspective_pushback)} lived={len(perspective_lived)}",
                f"what_matters={perspective_what_matters[0] if perspective_what_matters else 'missing'}",
            ],
            score=_average(johnnie_perspective_scores) or _ratio_score(4 - len(johnnie_missing_fields), 4),
            missing_fields=johnnie_missing_fields,
        )
    )

    stance_status = "fail" if not stances else "warn" if len(stances) < 2 else "pass"
    stages.append(
        _extend_stage(
            _social_stage_result(
                "stance_selection",
                stance_status,
                "stance_missing" if not stances else "stance_diversity_thin" if len(stances) < 2 else "stance_selection_ready",
                (
                    "The matrix returned stance coverage, but not enough stance diversity."
                    if stance_status == "warn"
                    else "The matrix returned usable stance coverage."
                    if stance_status == "pass"
                    else "No usable stance selection was returned."
                ),
            ),
            score=_ratio_score(len(stances), 4),
            evidence=[f"stances={', '.join(stances) or 'missing'}"],
            missing_fields=["stance"] if not stances else [],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "reaction_brief",
                "fail"
                if not (brief_article_views or brief_johnnie_views or brief_tensions or brief_content_angles)
                else "warn"
                if not (brief_article_views and brief_johnnie_views and brief_tensions and brief_content_angles)
                else "pass",
                "reaction_brief_missing"
                if not (brief_article_views or brief_johnnie_views or brief_tensions or brief_content_angles)
                else "reaction_brief_partial"
                if not (brief_article_views and brief_johnnie_views and brief_tensions and brief_content_angles)
                else "reaction_brief_ready",
                (
                    "The system returned a reaction brief, but one or more synthesis slices are still missing."
                    if (brief_article_views or brief_johnnie_views or brief_tensions or brief_content_angles)
                    and not (brief_article_views and brief_johnnie_views and brief_tensions and brief_content_angles)
                    else "The system materialized article view, Johnnie view, tension, and content angle before drafting."
                    if (brief_article_views and brief_johnnie_views and brief_tensions and brief_content_angles)
                    else "The system did not return a usable reaction brief packet."
                ),
            ),
            score=_average(reaction_brief_scores) or _ratio_score(
                sum(1 for value in [brief_article_views, brief_johnnie_views, brief_tensions, brief_content_angles] if value),
                4,
            ),
            evidence=[
                f"article_view={brief_article_views[0] if brief_article_views else 'missing'}",
                f"johnnie_view={brief_johnnie_views[0] if brief_johnnie_views else 'missing'}",
                f"tension={brief_tensions[0] if brief_tensions else 'missing'}",
                f"content_angle={', '.join(brief_content_angles) or 'missing'}",
            ],
            missing_fields=[
                field
                for field, value in {
                    "article_view": brief_article_views,
                    "johnnie_view": brief_johnnie_views,
                    "tension": brief_tensions,
                    "content_angle": brief_content_angles,
                }.items()
                if not value
            ],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "source_takeaway",
                "warn" if any_takeaway_missing else "pass",
                "source_takeaway_missing" if any_takeaway_missing else "source_takeaway_ready",
                (
                    "The system is rewriting the source into a usable takeaway before drafting."
                    if not any_takeaway_missing
                    else "At least one lane is missing a usable rewritten source takeaway."
                ),
            ),
            score=_ratio_score(sum(1 for row in lane_rows if row.get("source_takeaway")), total_lanes),
            evidence=[
                f"takeaway_strategies={', '.join(takeaway_strategies) or 'missing'}",
                f"takeaway_examples={'; '.join(_unique_non_empty([row.get('source_takeaway') or '' for row in lane_rows])[:2]) or 'missing'}",
            ],
            missing_fields=["source_takeaway"] if any_takeaway_missing else [],
        )
    )

    technique_diversity = len(_unique_non_empty([", ".join(bundle) for bundle in technique_bundles]))
    stages.append(
        _extend_stage(
            _social_stage_result(
                "technique_selection",
                "fail" if any_technique_missing else "warn" if technique_diversity < 3 else "pass",
                "technique_bundle_empty" if any_technique_missing else "technique_overused" if technique_diversity < 3 else "technique_selection_ready",
                (
                    "Technique bundles are present, but the matrix is still reusing too few combinations."
                    if technique_diversity < 3 and not any_technique_missing
                    else "Each lane returned a technique bundle."
                    if not any_technique_missing
                    else "At least one lane returned no technique bundle."
                ),
            ),
            score=_ratio_score(technique_diversity, len(SOCIAL_LANE_MATRIX)),
            evidence=[f"technique_bundle_variants={technique_diversity}"],
            missing_fields=["techniques"] if any_technique_missing else [],
        )
    )

    response_type_status = (
        "fail"
        if not response_types
        else "warn"
        if len(response_types) < 2 or (_average(response_type_confidences) or 0.0) < 7.0
        else "pass"
    )
    stages.append(
        _extend_stage(
            _social_stage_result(
                "response_type_selection",
                response_type_status,
                "response_type_missing"
                if not response_types
                else "response_type_diversity_thin"
                if len(response_types) < 2
                else "response_type_confidence_low"
                if (_average(response_type_confidences) or 0.0) < 7.0
                else "response_type_ready",
                (
                    "The system returned response types, but the matrix is still collapsing into too few type choices."
                    if response_type_status == "warn"
                    else "The system selected a first-class response type before drafting."
                    if response_type_status == "pass"
                    else "The system did not return a response type packet."
                ),
            ),
            score=_average(response_type_scores) or _ratio_score(len(response_types), 4),
            evidence=[
                f"response_types={', '.join(response_types) or 'missing'}",
                f"avg_type_confidence={_average(response_type_confidences) if response_type_confidences else 'missing'}",
            ],
            missing_fields=["response_type"] if not response_types else [],
        )
    )

    comment_stage = _extend_stage(
        _summarize_response_stage(
            stage_id="comment_draft",
            response_key="comment",
            lane_rows=lane_rows,
            pass_reason="comment_matrix_clean",
            pass_detail="All target-lane comments cleared the current response checks.",
        ),
        score=_ratio_score(comment_passes, total_lanes),
        evidence=[f"comment_passes={comment_passes}/{total_lanes}"],
    )
    stages.append(comment_stage)

    repost_stage = _extend_stage(
        _summarize_response_stage(
            stage_id="repost_draft",
            response_key="repost",
            lane_rows=lane_rows,
            pass_reason="repost_matrix_clean",
            pass_detail="All target-lane reposts cleared the current response checks.",
        ),
        score=_ratio_score(repost_passes, total_lanes),
        evidence=[f"repost_passes={repost_passes}/{total_lanes}"],
    )
    stages.append(repost_stage)

    stages.append(
        _extend_stage(
            _social_stage_result(
                "template_composition",
                "fail"
                if not (composition_comment_traces or composition_repost_traces)
                else "warn"
                if not template_families
                else "pass",
                "template_trace_missing"
                if not (composition_comment_traces or composition_repost_traces)
                else "template_family_missing"
                if not template_families
                else "template_trace_ready",
                (
                    "Template traces exist, but one or more composition families are still missing."
                    if (composition_comment_traces or composition_repost_traces) and not template_families
                    else "Lab can now trace the selected composition path at the part level."
                    if template_families
                    else "The system did not return composition traces for comment and repost rendering."
                ),
            ),
            evidence=[
                f"template_families={', '.join(template_families) or 'missing'}",
                f"comment_parts={', '.join(_unique_non_empty([', '.join(trace.get('selected_parts') or []) for trace in composition_comment_traces])) or 'missing'}",
                f"repost_parts={', '.join(_unique_non_empty([', '.join(trace.get('selected_parts') or []) for trace in composition_repost_traces])) or 'missing'}",
            ],
            score=_average(template_composition_scores) or _ratio_score(
                sum(1 for trace in [*composition_comment_traces, *composition_repost_traces] if trace),
                max(total_lanes * 2, 1),
            ),
            missing_fields=[
                field
                for field, value in {
                    "composition_parts": any(trace.get("selected_parts") for trace in [*composition_comment_traces, *composition_repost_traces]),
                    "template_family": template_families,
                    "selected_close_family": any(str(trace.get("selected_close_family") or "").strip() for trace in [*composition_comment_traces, *composition_repost_traces]),
                }.items()
                if not value
            ],
        )
    )

    stages.append(
        _extend_stage(
            _social_stage_result(
                "voice_normalization",
                "warn" if any_generic_warning else "pass",
                "voice_cleanup_detected_issues" if any_generic_warning else "voice_normalization_clean",
                (
                    "Voice cleanup ran, but generic or abstract phrasing still leaked into at least one lane."
                    if any_generic_warning
                    else "Voice normalization removed the currently blocked generic and abstract phrasing patterns."
                ),
            ),
            score=_average(voice_scores),
            evidence=[f"avg_voice_match={_average(voice_scores) or 'missing'}"],
        )
    )

    specificity_stage = _extend_stage(
        _summarize_matrix_stage(
            stage_id="lane_specificity",
            lane_rows=lane_rows,
            reason_keys=list(_SOCIAL_SPECIFICITY_WARNINGS.values()),
            pass_reason="lane_specificity_clean",
            pass_detail="The lane matrix stayed distinct across AI, tech, admissions, leadership, and entrepreneur outputs.",
        ),
        score=_average(lane_scores),
        evidence=[f"avg_lane_distinctiveness={_average(lane_scores) or 'missing'}"],
    )
    stages.append(specificity_stage)

    quality_stage = _extend_stage(
        _summarize_matrix_stage(
            stage_id="response_quality",
            lane_rows=lane_rows,
            reason_keys=list(_SOCIAL_QUALITY_WARNINGS.values()),
            pass_reason="response_quality_clean",
            pass_detail="Comments and reposts cleared the current genericity and confidence checks.",
        ),
        score=_average(benchmark_scores),
        evidence=[
            f"avg_benchmark={_average(benchmark_scores) or 'missing'}",
            f"min_benchmark={_round_score(min(benchmark_scores)) if benchmark_scores else 'missing'}",
        ],
    )
    stages.append(quality_stage)

    safety_stage = _extend_stage(
        _social_stage_result(
            "safety",
            "fail" if any_role_safety_issue else "pass",
            "role_safety_flagged" if any_role_safety_issue else "role_safe",
            (
                "Role-safety warnings appeared in at least one lane."
                if any_role_safety_issue
                else "The article response matrix stayed role-safe across all target lanes."
            ),
        ),
        score=10.0 if not any_role_safety_issue else 4.0,
        evidence=[f"unsafe_lanes={sum(1 for row in lane_rows if str(row.get('role_safety') or 'safe') != 'safe')}"],
    )
    stages.append(safety_stage)

    humor_missing = any(not packet for packet in humor_packets)
    unsafe_humor_selected = any(
        str(packet.get("response_type") or "") == "humor" and not bool((packet.get("humor_safety") or {}).get("humor_allowed"))
        for packet in response_type_packets
    )
    humor_boundaries_present = all(str(packet.get("humor_boundary") or "").strip() for packet in humor_packets if packet)
    stages.append(
        _extend_stage(
            _social_stage_result(
                "humor_safety",
                "fail"
                if unsafe_humor_selected
                else "warn"
                if humor_missing or not humor_boundaries_present
                else "pass",
                "unsafe_humor_selected"
                if unsafe_humor_selected
                else "humor_safety_missing"
                if humor_missing
                else "humor_boundary_missing"
                if not humor_boundaries_present
                else "humor_safety_ready",
                (
                    "Humor gating exists, but the safety packet or boundary guidance is still incomplete."
                    if humor_missing or not humor_boundaries_present
                    else "Humor is either safely blocked or safely allowed with an explicit boundary."
                ),
            ),
            score=_average(humor_safety_scores) or 8.5,
            evidence=[
                f"humor_selected={response_type_selected_humor}",
                f"humor_allowed={sum(1 for packet in humor_packets if bool(packet.get('humor_allowed')))}",
                f"humor_blocked={sum(1 for packet in humor_packets if packet and not bool(packet.get('humor_allowed')))}",
            ],
            missing_fields=[
                field
                for field, value in {
                    "humor_safety": not humor_missing,
                    "humor_boundary": humor_boundaries_present,
                }.items()
                if not value
            ],
        )
    )

    return stages


def _response_status_for_variant(*, lane_label: str, variant: dict[str, Any], response_key: str) -> dict[str, str]:
    response_text = str(variant.get(response_key) or "").strip()
    evaluation = variant.get("evaluation") or {}
    warnings = [str(item) for item in (evaluation.get("warnings") or [])]
    overall = float(evaluation.get("overall") or 0.0)
    benchmark_score = float(evaluation.get("benchmark_score") or 0.0)
    response_label = "comment" if response_key == "comment" else "repost"

    if not response_text:
        return {
            "status": "fail",
            "reason": f"{response_label}_draft_missing",
            "detail": f"{lane_label} did not return a usable {response_label} draft.",
        }
    if any(item.startswith("role safety is ") for item in warnings):
        return {
            "status": "fail",
            "reason": "role_safety_flagged",
            "detail": f"{lane_label} {response_label} triggered a role-safety warning: {warnings[0]}",
        }
    if "copy still contains generic language" in warnings:
        return {
            "status": "warn",
            "reason": f"{response_label}_contains_generic_language",
            "detail": f"{lane_label} {response_label} still contains generic language.",
        }
    if "copy still contains abstract meta phrasing" in warnings:
        return {
            "status": "warn",
            "reason": "abstract_meta_phrasing_detected",
            "detail": f"{lane_label} {response_label} still contains abstract meta phrasing.",
        }
    if "variant needs review before high-confidence use" in warnings or overall < 6.8:
        return {
            "status": "warn",
            "reason": f"{response_label}_variant_needs_review",
            "detail": f"{lane_label} {response_label} scored {round(overall, 1)} and still needs review.",
        }
    if benchmark_score < TARGET_SOCIAL_BENCHMARK_FLOOR:
        return {
            "status": "warn",
            "reason": "benchmark_below_target",
            "detail": (
                f"{lane_label} {response_label} cleared baseline checks but benchmarked at "
                f"{round(benchmark_score, 1)} / {TARGET_SOCIAL_BENCHMARK_FLOOR}."
            ),
        }
    return {
        "status": "pass",
        "reason": f"{response_label}_ready",
        "detail": f"{lane_label} {response_label} cleared the current lane-quality checks.",
    }


def _summarize_matrix_stage(
    *,
    stage_id: str,
    lane_rows: list[dict[str, Any]],
    reason_keys: list[str],
    pass_reason: str,
    pass_detail: str,
) -> dict[str, Any]:
    matching: list[tuple[str, str]] = []
    for row in lane_rows:
        for warning in row.get("top_warnings") or []:
            mapped = _SOCIAL_SPECIFICITY_WARNINGS.get(warning) or _SOCIAL_QUALITY_WARNINGS.get(warning)
            if mapped in reason_keys:
                matching.append((mapped, row["label"]))
    if matching:
        reason = matching[0][0]
        lanes = ", ".join(sorted({label for _, label in matching}))
        return _social_stage_result(stage_id, "warn", reason, f"Triggered in lane(s): {lanes}.")
    return _social_stage_result(stage_id, "pass", pass_reason, pass_detail)


def _summarize_response_stage(
    *,
    stage_id: str,
    response_key: str,
    lane_rows: list[dict[str, Any]],
    pass_reason: str,
    pass_detail: str,
) -> dict[str, Any]:
    statuses = [row[f"{response_key}_status"] for row in lane_rows]
    if any(status == "fail" for status in statuses):
        failing = next(row for row in lane_rows if row[f"{response_key}_status"] == "fail")
        return _social_stage_result(stage_id, "fail", failing[f"{response_key}_reason"], failing[f"{response_key}_detail"])
    if any(status == "warn" for status in statuses):
        warning = next(row for row in lane_rows if row[f"{response_key}_status"] == "warn")
        return _social_stage_result(stage_id, "warn", warning[f"{response_key}_reason"], warning[f"{response_key}_detail"])
    return _social_stage_result(stage_id, "pass", pass_reason, pass_detail)


def _default_experiment_record() -> dict[str, Any]:
    default_stage_health = [
        {
            **stage,
            "counts": {"pass": 0, "warn": 0, "fail": 0},
            "top_failure_reasons": [],
        }
        for stage in STAGE_CATALOG
    ]
    return {
        "id": EXPERIMENT_ID,
        "title": "Content Fallback Observatory",
        "belongs_to_workspace": "linkedin-content-os",
        "surface": "lab.buildLogs",
        "status": "not_run",
        "hypothesis": "Content quality will improve once staged and provider fallbacks are visible and held below 5 percent.",
        "goal": {
            "metric": "structural_fallback_rate",
            "target_lte": TARGET_FALLBACK_RATE,
            "unit": "percent",
        },
        "target_lane": {"provider": TARGET_PROVIDER, "model": TARGET_MODEL},
        "stage_catalog": STAGE_CATALOG,
        "loop": [
            {"id": "observe", "label": "Observe", "status": "ready"},
            {"id": "tune", "label": "Tune", "status": "ready"},
            {"id": "verify", "label": "Verify", "status": "waiting"},
            {"id": "ship", "label": "Ship", "status": "waiting"},
            {"id": "postmortem", "label": "Postmortem", "status": "waiting"},
        ],
        "current": {
            "summary": "No experiment run recorded yet.",
            "probe_count": len(CONTENT_PROBES),
            "structural_fallback_rate": None,
            "legacy_fallback_rate": None,
            "provider_fallback_rate": None,
            "weak_output_rate": None,
            "metric_cards": [
                _metric_card("structural_fallback_rate", "Structural Fallback", None, "#34d399"),
                _metric_card("legacy_fallback_rate", "Legacy Fallback", None, "#f59e0b"),
                _metric_card("provider_fallback_rate", "Provider Failover", None, "#38bdf8"),
                _metric_card("weak_output_rate", "Weak Output", None, "#a78bfa"),
            ],
            "stage_breakdown": {},
            "stage_health": default_stage_health,
            "top_failure_modes": [],
        },
        "sample_runs": [],
        "history": [],
        "next_action": "Run the experiment from Lab to collect live fallback telemetry.",
        "ship_target": "LinkedIn OS",
    }


def _default_social_experiment_record() -> dict[str, Any]:
    default_stage_health = [
        {
            **stage,
            "counts": {"pass": 0, "warn": 0, "fail": 0, "missing": 0},
            "top_failure_reasons": [],
        }
        for stage in SOCIAL_STAGE_CATALOG
    ]
    return {
        "id": SOCIAL_EXPERIMENT_ID,
        "title": "Article Response Matrix",
        "belongs_to_workspace": "linkedin-content-os",
        "surface": "lab.buildLogs",
        "status": "not_run",
        "hypothesis": (
            "Comments and reposts should clear across AI, tech, admissions, leadership, and entrepreneur lanes "
            "for the same article signal before the response system ships back to LinkedIn OS."
        ),
        "goal": {
            "metric": "benchmark_gap",
            "target_lte": TARGET_SOCIAL_FAILURE_RATE,
            "unit": "points",
        },
        "coverage": {
            "lanes": [{"id": item["id"], "label": item["label"]} for item in SOCIAL_LANE_MATRIX],
            "response_modes": ["comment", "repost"],
            "source_probes": len(ARTICLE_RESPONSE_PROBES),
        },
        "stage_catalog": SOCIAL_STAGE_CATALOG,
        "loop": [
            {"id": "observe", "label": "Observe", "status": "ready"},
            {"id": "tune", "label": "Tune", "status": "ready"},
            {"id": "verify", "label": "Verify", "status": "waiting"},
            {"id": "ship", "label": "Ship", "status": "waiting"},
            {"id": "postmortem", "label": "Postmortem", "status": "waiting"},
        ],
        "current": {
            "summary": "No article response matrix run recorded yet.",
            "probe_count": len(ARTICLE_RESPONSE_PROBES),
            "structural_fallback_rate": None,
            "legacy_fallback_rate": 0.0,
            "provider_fallback_rate": 0.0,
            "weak_output_rate": None,
            "metric_cards": [
                _metric_card("benchmark_score_avg", "Benchmark Avg", None, "#34d399"),
                _metric_card("benchmark_score_min", "Benchmark Floor", None, "#f59e0b"),
                _metric_card("response_failure_rate", "Response Failure", None, "#38bdf8"),
                _metric_card("missing_stage_rate", "Missing Stage", None, "#a78bfa"),
                _metric_card("lane_coverage_rate", "Lane Coverage", None, "#14b8a6"),
                _metric_card("article_understanding_avg", "Article Understanding", None, "#22c55e"),
                _metric_card("persona_retrieval_avg", "Persona Retrieval", None, "#60a5fa"),
                _metric_card("johnnie_perspective_avg", "Johnnie Perspective", None, "#f97316"),
                _metric_card("reaction_brief_avg", "Reaction Brief", None, "#f43f5e"),
                _metric_card("template_composition_avg", "Template Composition", None, "#c084fc"),
                _metric_card("ship_readiness_avg", "Ship Readiness", None, "#14b8a6"),
                _metric_card("blocked_rows_rate", "Blocked Rows", None, "#ef4444"),
                _metric_card("lived_addition_rate", "Lived Addition", None, "#facc15"),
            ],
            "stage_breakdown": {},
            "stage_health": default_stage_health,
            "top_failure_modes": [],
        },
        "sample_runs": [],
        "history": [],
        "next_action": "Run the article response matrix from Lab to inspect comments and reposts across all target lanes.",
        "ship_target": "LinkedIn OS",
    }


def _default_source_handoff_experiment_record() -> dict[str, Any]:
    default_stage_health = [
        {
            **stage,
            "counts": {"pass": 0, "warn": 0, "fail": 0, "missing": 0},
            "top_failure_reasons": [],
        }
        for stage in HANDOFF_STAGE_CATALOG
    ]
    return {
        "id": SOURCE_HANDOFF_EXPERIMENT_ID,
        "title": "Source Handoff Matrix",
        "belongs_to_workspace": "brain",
        "surface": "lab.buildLogs",
        "status": "not_run",
        "hypothesis": (
            "Long-form source segments should land in the right product lane "
            "before Brain, Persona, Posting, or PM starts consuming them."
        ),
        "goal": {
            "metric": "handoff_mismatch_rate",
            "target_lte": TARGET_HANDOFF_MISMATCH_RATE,
            "unit": "percent",
        },
        "coverage": {
            "lanes": [
                {"id": "source_only", "label": "Source only"},
                {"id": "brief_only", "label": "Brief only"},
                {"id": "post_candidate", "label": "Post candidate"},
                {"id": "persona_candidate", "label": "Persona candidate"},
                {"id": "route_to_pm", "label": "Route to PM"},
            ],
            "response_modes": ["post_seed", "belief_evidence", "comment", "repost"],
            "source_probes": len(SOURCE_HANDOFF_PROBES),
        },
        "stage_catalog": HANDOFF_STAGE_CATALOG,
        "loop": [
            {"id": "observe", "label": "Observe", "status": "ready"},
            {"id": "tune", "label": "Tune", "status": "ready"},
            {"id": "verify", "label": "Verify", "status": "waiting"},
            {"id": "ship", "label": "Ship", "status": "waiting"},
            {"id": "postmortem", "label": "Postmortem", "status": "waiting"},
        ],
        "current": {
            "summary": "No source handoff matrix run recorded yet.",
            "probe_count": len(SOURCE_HANDOFF_PROBES),
            "structural_fallback_rate": None,
            "legacy_fallback_rate": 0.0,
            "provider_fallback_rate": 0.0,
            "weak_output_rate": None,
            "metric_cards": [
                _metric_card("exact_match_rate", "Exact Match", None, "#34d399"),
                _metric_card("handoff_mismatch_rate", "Mismatch", None, "#ef4444"),
                _metric_card("persona_false_positive_rate", "Persona Overpush", None, "#f97316"),
                _metric_card("persona_false_negative_rate", "Persona Miss", None, "#f59e0b"),
                _metric_card("post_false_negative_rate", "Post Miss", None, "#38bdf8"),
                _metric_card("pm_alignment_rate", "PM Alignment", None, "#a78bfa"),
                _metric_card("source_guardrail_success_rate", "Source Guardrails", None, "#14b8a6"),
            ],
            "stage_breakdown": {},
            "stage_health": default_stage_health,
            "top_failure_modes": [],
        },
        "sample_runs": [],
        "live_samples": [],
        "live_audit": {
            "source": "empty",
            "generated_at": None,
            "asset_count": 0,
            "candidate_count": 0,
            "segments_total": 0,
            "quality_metrics": {
                "summary_coverage_rate": 0.0,
                "structured_summary_rate": 0.0,
                "lesson_coverage_rate": 0.0,
                "anecdote_coverage_rate": 0.0,
                "quote_coverage_rate": 0.0,
                "noisy_summary_rate": 0.0,
                "package_readiness_rate": 0.0,
            },
            "slice_counts": {
                "handoff_lane_counts": {},
                "primary_route_counts": {},
                "channel_counts": {},
                "target_file_counts": {},
                "summary_origin_counts": {},
                "issue_counts": {},
            },
            "top_issues": [],
            "candidate_samples": [],
            "asset_samples": [],
        },
        "history": [],
        "next_action": "Run the source handoff matrix to calibrate what should stay in source intelligence versus Persona, Posting, Briefs, and PM.",
        "ship_target": "Brain",
    }


async def run_content_fallback_experiment() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    stage_counts = {
        "legacy_generation_fallback": 0,
        "recovered_missing_planned_options": 0,
        "critic_used_rough_options": 0,
        "provider_failover": 0,
        "probe_errors": 0,
    }
    weak_output_count = 0
    target_lane_success_count = 0

    with _lab_provider_lane():
        for probe in CONTENT_PROBES:
            try:
                req = content_generation.ContentGenerationRequest(
                    user_id="lab-experiment",
                    topic=probe["topic"],
                    content_type="linkedin_post",
                    category=probe["category"],
                    tone=probe["tone"],
                    audience=probe["audience"],
                )
                response = await content_generation.run_content_generation(req)
                diagnostics = response.diagnostics or {}
                structural_fallbacks = _structural_fallbacks_for_probe(diagnostics)
                if _probe_held_on_target_provider(diagnostics.get("llm_provider_trace") or []):
                    target_lane_success_count += 1
                for item in structural_fallbacks:
                    stage_counts[item] += 1
                top_warnings = _top_taste_warnings(diagnostics)
                stage_results = _build_stage_results(diagnostics, top_warnings)
                if top_warnings:
                    weak_output_count += 1
                results.append(
                    {
                        "topic": probe["topic"],
                        "audience": probe["audience"],
                        "generation_strategy": diagnostics.get("generation_strategy"),
                        "grounding_mode": diagnostics.get("grounding_mode"),
                        "llm_request_count": diagnostics.get("llm_request_count"),
                        "structural_fallbacks": structural_fallbacks,
                        "fallback_trace": diagnostics.get("fallback_trace") or {},
                        "provider_trace": diagnostics.get("llm_provider_trace") or [],
                        "top_warnings": top_warnings,
                        "stage_results": stage_results,
                        "top_option_preview": (response.options or [""])[0][:340],
                    }
                )
            except Exception as exc:
                stage_counts["probe_errors"] += 1
                weak_output_count += 1
                stage_results = [
                    _stage_result("grounding", "fail", "probe_error", "The probe failed before stage results could be completed."),
                    _stage_result("planner", "fail", "probe_error", "The probe failed before planning diagnostics were returned."),
                    _stage_result("writer", "fail", "probe_error", "The probe failed before writer diagnostics were returned."),
                    _stage_result("critic", "fail", "probe_error", "The probe failed before critic diagnostics were returned."),
                    _stage_result("recovery", "fail", "probe_error", "The probe failed before recovery diagnostics were returned."),
                    _stage_result("provider_router", "fail", "probe_error", str(exc)[:220]),
                    _stage_result("editorial_finish", "fail", "probe_error", "The probe failed before editorial diagnostics were returned."),
                    _stage_result("legacy_escape", "warn", "probe_error", "The probe errored before the escape path could be classified."),
                ]
                results.append(
                    {
                        "topic": probe["topic"],
                        "audience": probe["audience"],
                        "generation_strategy": "probe_error",
                        "grounding_mode": None,
                        "llm_request_count": None,
                        "structural_fallbacks": ["probe_error"],
                        "fallback_trace": {
                            "events": [
                                {
                                    "stage": "probe",
                                    "reason": "experiment_probe_failed",
                                    "action": "captured_error",
                                }
                            ]
                        },
                        "provider_trace": [],
                        "top_warnings": [str(exc)[:220]],
                        "stage_results": stage_results,
                        "top_option_preview": "",
                    }
                )

    probe_count = max(len(results), 1)
    structural_fallback_count = sum(1 for item in results if item["structural_fallbacks"])
    legacy_count = sum(1 for item in results if "legacy_generation_fallback" in item["structural_fallbacks"])
    provider_count = sum(1 for item in results if "provider_failover" in item["structural_fallbacks"])
    structural_fallback_rate = round((structural_fallback_count / probe_count) * 100, 1)
    legacy_rate = round((legacy_count / probe_count) * 100, 1)
    provider_rate = round((provider_count / probe_count) * 100, 1)
    weak_output_rate = round((weak_output_count / probe_count) * 100, 1)
    target_lane_success_rate = round((target_lane_success_count / probe_count) * 100, 1)
    passing = structural_fallback_rate <= TARGET_FALLBACK_RATE
    run_started_at = _now_iso()
    stage_health = _build_stage_health(results)

    run = {
        "run_id": f"{EXPERIMENT_ID}:{run_started_at}",
        "started_at": run_started_at,
        "probe_count": probe_count,
        "structural_fallback_rate": structural_fallback_rate,
        "legacy_fallback_rate": legacy_rate,
        "provider_fallback_rate": provider_rate,
        "weak_output_rate": weak_output_rate,
        "target_lane_success_rate": target_lane_success_rate,
        "stage_breakdown": stage_counts,
        "stage_health": stage_health,
        "top_failure_modes": [
            key for key, value in sorted(stage_counts.items(), key=lambda item: item[1], reverse=True) if value > 0
        ][:4],
        "sample_runs": results,
        "status": "passing" if passing else "investigating",
        "next_action": (
            "Ship the improvement back into the owning workspace and write the postmortem."
            if passing
            else "Tune the stage with the highest fallback count, then rerun the experiment."
        ),
    }

    record = _EXPERIMENT_CACHE.get(EXPERIMENT_ID) or _default_experiment_record()
    history = [run, *(record.get("history") or [])][:MAX_HISTORY]
    record.update(
        {
            "status": run["status"],
            "current": {
                "summary": f"Structural fallback rate is {structural_fallback_rate}% across {probe_count} probes.",
                "probe_count": probe_count,
                "structural_fallback_rate": structural_fallback_rate,
                "legacy_fallback_rate": legacy_rate,
                "provider_fallback_rate": provider_rate,
                "weak_output_rate": weak_output_rate,
                "target_lane_success_rate": target_lane_success_rate,
                "metric_cards": [
                    _metric_card("structural_fallback_rate", "Structural Fallback", structural_fallback_rate, "#34d399"),
                    _metric_card("legacy_fallback_rate", "Legacy Fallback", legacy_rate, "#f59e0b"),
                    _metric_card("provider_fallback_rate", "Provider Failover", provider_rate, "#38bdf8"),
                    _metric_card("weak_output_rate", "Weak Output", weak_output_rate, "#a78bfa"),
                ],
                "stage_breakdown": stage_counts,
                "stage_health": stage_health,
                "top_failure_modes": run["top_failure_modes"],
            },
            "sample_runs": results,
            "history": history,
            "last_run_at": run_started_at,
            "next_action": run["next_action"],
        }
    )
    record["loop"] = [
        {"id": "observe", "label": "Observe", "status": "done"},
        {"id": "tune", "label": "Tune", "status": "active" if not passing else "done"},
        {"id": "verify", "label": "Verify", "status": "active" if not passing else "done"},
        {"id": "ship", "label": "Ship", "status": "ready" if passing else "waiting"},
        {"id": "postmortem", "label": "Postmortem", "status": "ready" if passing else "waiting"},
    ]
    _EXPERIMENT_CACHE[EXPERIMENT_ID] = record
    return record


async def run_social_response_matrix_experiment() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    stage_counts = {stage["id"]: 0 for stage in SOCIAL_STAGE_CATALOG}
    comment_non_pass_count = 0
    repost_non_pass_count = 0
    response_non_pass_count = 0
    coverage_hits = 0
    benchmark_scores: list[float] = []

    for probe in ARTICLE_RESPONSE_PROBES:
        try:
            signal = _build_social_probe_signal(probe)
            variants = build_variants(signal)
            lane_rows: list[dict[str, Any]] = []
            missing_lanes: list[str] = []

            for lane in SOCIAL_LANE_MATRIX:
                lane_id = lane["id"]
                label = lane["label"]
                variant = variants.get(lane_id)
                if not variant:
                    missing_lanes.append(label)
                    lane_rows.append(
                        {
                            "lane_id": lane_id,
                            "label": label,
                            "comment_status": "fail",
                            "comment_reason": "comment_draft_missing",
                            "comment_detail": f"{label} lane variant was not returned.",
                            "comment_preview": "",
                            "repost_status": "fail",
                            "repost_reason": "repost_draft_missing",
                            "repost_detail": f"{label} lane variant was not returned.",
                            "repost_preview": "",
                            "top_warnings": ["missing_lane_variant"],
                            "evaluation_overall": None,
                            "benchmark_score": 0.0,
                            "role_safety": "unknown",
                            "belief_used": "",
                            "belief_summary": "",
                            "experience_anchor": "",
                            "experience_summary": "",
                            "stance": "",
                            "agreement_level": "",
                            "source_takeaway": "",
                            "source_takeaway_origin": "",
                            "source_takeaway_strategy": "",
                            "techniques": [],
                            "technique_reason": "",
                            "response_type": "",
                            "article_understanding": {},
                            "persona_retrieval": {},
                            "johnnie_perspective": {},
                            "reaction_brief": {},
                            "response_type_packet": {},
                            "composition_traces": {},
                            "stage_evaluation": {},
                            "evaluation": {},
                            "expression_assessment": {},
                            "context_snapshot": {},
                        }
                    )
                    comment_non_pass_count += 1
                    repost_non_pass_count += 1
                    response_non_pass_count += 2
                    continue

                coverage_hits += 1
                comment_status = _response_status_for_variant(lane_label=label, variant=variant, response_key="comment")
                repost_status = _response_status_for_variant(lane_label=label, variant=variant, response_key="repost")
                if comment_status["status"] != "pass":
                    comment_non_pass_count += 1
                    response_non_pass_count += 1
                if repost_status["status"] != "pass":
                    repost_non_pass_count += 1
                    response_non_pass_count += 1
                benchmark_score = float((variant.get("evaluation") or {}).get("benchmark_score") or 0.0)
                benchmark_scores.append(benchmark_score)

                lane_rows.append(
                    {
                        "lane_id": lane_id,
                        "label": label,
                        "comment_status": comment_status["status"],
                        "comment_reason": comment_status["reason"],
                        "comment_detail": comment_status["detail"],
                        "comment_preview": str(variant.get("comment") or "")[:240],
                        "repost_status": repost_status["status"],
                        "repost_reason": repost_status["reason"],
                        "repost_detail": repost_status["detail"],
                        "repost_preview": str(variant.get("repost") or "")[:240],
                        "top_warnings": [str(item) for item in ((variant.get("evaluation") or {}).get("warnings") or [])[:4]],
                        "evaluation_overall": (variant.get("evaluation") or {}).get("overall"),
                        "benchmark_score": benchmark_score,
                        "role_safety": str(variant.get("role_safety") or "safe"),
                        "belief_used": str(variant.get("belief_used") or ""),
                        "belief_summary": str(variant.get("belief_summary") or ""),
                        "experience_anchor": str(variant.get("experience_anchor") or ""),
                        "experience_summary": str(variant.get("experience_summary") or ""),
                        "stance": str(variant.get("stance") or ""),
                        "agreement_level": str(variant.get("agreement_level") or ""),
                        "source_takeaway": str(((variant.get("context_snapshot") or {}).get("source_takeaway")) or ""),
                        "source_takeaway_origin": str(((variant.get("context_snapshot") or {}).get("source_takeaway_origin")) or ""),
                        "source_takeaway_strategy": str(((variant.get("context_snapshot") or {}).get("source_takeaway_strategy")) or ""),
                        "techniques": [str(item) for item in (variant.get("techniques") or []) if str(item).strip()],
                        "technique_reason": str(variant.get("technique_reason") or ""),
                        "response_type": str(((variant.get("response_type_packet") or {}).get("response_type")) or ""),
                        "article_understanding": dict(variant.get("article_understanding") or {}),
                        "persona_retrieval": dict(variant.get("persona_retrieval") or {}),
                        "johnnie_perspective": dict(variant.get("johnnie_perspective") or {}),
                        "reaction_brief": dict(variant.get("reaction_brief") or {}),
                        "response_type_packet": dict(variant.get("response_type_packet") or {}),
                        "composition_traces": dict(variant.get("composition_traces") or {}),
                        "stage_evaluation": dict(variant.get("stage_evaluation") or {}),
                        "evaluation": dict(variant.get("evaluation") or {}),
                        "expression_assessment": dict(variant.get("expression_assessment") or {}),
                        "context_snapshot": dict(variant.get("context_snapshot") or {}),
                    }
                )

            stage_results = _build_social_probe_stages(signal=signal, lane_rows=lane_rows, missing_lanes=missing_lanes)

            for stage in stage_results:
                if stage["status"] != "pass":
                    stage_counts[stage["id"]] = stage_counts.get(stage["id"], 0) + 1

            matrix_flags = [item["reason"] for item in stage_results if item["status"] != "pass"]
            results.append(
                {
                    "topic": probe["title"],
                    "audience": "article matrix",
                    "generation_strategy": "comment_repost_matrix",
                    "llm_request_count": 0,
                    "platform": probe["platform"],
                    "source_type": "article",
                    "structural_fallbacks": matrix_flags,
                    "top_warnings": list(
                        dict.fromkeys(
                            warning
                            for row in lane_rows
                            for warning in (row.get("top_warnings") or [])
                        )
                    )[:6],
                    "stage_results": stage_results,
                    "top_option_preview": probe["raw_text"][:340],
                    "signal_snapshot": {
                        "source_channel": signal.get("source_channel"),
                        "source_class": signal.get("source_class"),
                        "unit_kind": signal.get("unit_kind"),
                        "response_modes": signal.get("response_modes") or [],
                        "topic_tags": signal.get("topic_tags") or [],
                        "core_claim": signal.get("core_claim"),
                        "supporting_claims": signal.get("supporting_claims") or [],
                        "why_it_matters": signal.get("why_it_matters"),
                        "role_alignment": signal.get("role_alignment"),
                    },
                    "matrix_rows": lane_rows,
                }
            )
        except Exception as exc:
            stage_counts["signal_intake"] = stage_counts.get("signal_intake", 0) + 1
            results.append(
                {
                    "topic": probe["title"],
                    "audience": "article matrix",
                    "generation_strategy": "probe_error",
                    "llm_request_count": 0,
                    "platform": probe["platform"],
                    "source_type": "article",
                    "structural_fallbacks": ["probe_error"],
                    "top_warnings": [str(exc)[:220]],
                    "top_option_preview": "",
                    "signal_snapshot": {},
                    "matrix_rows": [],
                    "stage_results": [
                        _extend_stage(_social_stage_result("signal_intake", "fail", "probe_error", str(exc)[:220]), missing_fields=["probe"]),
                        _extend_stage(_social_stage_result("source_contract", "missing", "probe_error", "The probe failed before source contract classification completed."), missing_fields=["source_contract"]),
                        _extend_stage(_social_stage_result("claim_extraction", "missing", "probe_error", "The probe failed before claim extraction completed."), missing_fields=["core_claim"]),
                        _extend_stage(_social_stage_result("world_understanding", "missing", "probe_error", "The probe failed before world understanding completed."), missing_fields=["world_model"]),
                        _extend_stage(_social_stage_result("article_stance", "missing", "probe_error", "The probe failed before article stance modeling completed."), missing_fields=["article_stance"]),
                        _extend_stage(_social_stage_result("source_expression", "missing", "probe_error", "The probe failed before source expression analysis completed."), missing_fields=["source_expression"]),
                        _extend_stage(_social_stage_result("lane_routing", "fail", "probe_error", "The probe failed before lane routing completed.")),
                        _extend_stage(_social_stage_result("persona_truth", "missing", "probe_error", "The probe failed before persona truth loading completed."), missing_fields=["persona_truth"]),
                        _extend_stage(_social_stage_result("persona_retrieval", "missing", "probe_error", "The probe failed before persona retrieval completed."), missing_fields=["persona_retrieval"]),
                        _extend_stage(_social_stage_result("belief_selection", "missing", "probe_error", "The probe failed before belief selection completed."), missing_fields=["belief_used"]),
                        _extend_stage(_social_stage_result("experience_selection", "missing", "probe_error", "The probe failed before experience selection completed."), missing_fields=["experience_anchor"]),
                        _extend_stage(_social_stage_result("johnnie_perspective", "missing", "probe_error", "The probe failed before Johnnie perspective modeling completed."), missing_fields=["johnnie_perspective"]),
                        _extend_stage(_social_stage_result("stance_selection", "missing", "probe_error", "The probe failed before stance selection completed."), missing_fields=["stance"]),
                        _extend_stage(_social_stage_result("reaction_brief", "missing", "probe_error", "The probe failed before reaction brief synthesis completed."), missing_fields=["reaction_brief"]),
                        _extend_stage(_social_stage_result("source_takeaway", "missing", "probe_error", "The probe failed before source takeaway selection completed."), missing_fields=["source_takeaway"]),
                        _extend_stage(_social_stage_result("technique_selection", "missing", "probe_error", "The probe failed before technique selection completed."), missing_fields=["techniques"]),
                        _extend_stage(_social_stage_result("response_type_selection", "missing", "probe_error", "The probe failed before response type selection completed."), missing_fields=["response_type"]),
                        _extend_stage(_social_stage_result("comment_draft", "fail", "probe_error", "The probe failed before comment drafting completed.")),
                        _extend_stage(_social_stage_result("repost_draft", "fail", "probe_error", "The probe failed before repost drafting completed.")),
                        _extend_stage(_social_stage_result("template_composition", "missing", "probe_error", "The probe failed before template composition could be inspected."), missing_fields=["template_trace"]),
                        _extend_stage(_social_stage_result("voice_normalization", "missing", "probe_error", "The probe failed before voice normalization checks completed."), missing_fields=["voice_cleanup"]),
                        _extend_stage(_social_stage_result("lane_specificity", "fail", "probe_error", "The probe failed before specificity checks completed.")),
                        _extend_stage(_social_stage_result("response_quality", "fail", "probe_error", "The probe failed before quality checks completed.")),
                        _extend_stage(_social_stage_result("safety", "fail", "probe_error", "The probe failed before safety checks completed.")),
                        _extend_stage(_social_stage_result("humor_safety", "missing", "probe_error", "The probe failed before humor safety checks completed."), missing_fields=["humor_safety"]),
                    ],
                }
            )

    probe_count = max(len(results), 1)
    total_comment_slots = len(ARTICLE_RESPONSE_PROBES) * len(SOCIAL_LANE_MATRIX)
    total_repost_slots = total_comment_slots
    total_response_slots = total_comment_slots + total_repost_slots
    article_non_pass_count = sum(
        1 for item in results if any(stage.get("status") != "pass" for stage in item.get("stage_results") or [])
    )
    response_failure_rate = round((response_non_pass_count / max(total_response_slots, 1)) * 100, 1)
    comment_failure_rate = round((comment_non_pass_count / max(total_comment_slots, 1)) * 100, 1)
    repost_failure_rate = round((repost_non_pass_count / max(total_repost_slots, 1)) * 100, 1)
    article_failure_rate = round((article_non_pass_count / probe_count) * 100, 1)
    lane_coverage_rate = round((coverage_hits / max(len(ARTICLE_RESPONSE_PROBES) * len(SOCIAL_LANE_MATRIX), 1)) * 100, 1)
    benchmark_score_avg = round(sum(benchmark_scores) / max(len(benchmark_scores), 1), 1)
    benchmark_score_min = round(min(benchmark_scores) if benchmark_scores else 0.0, 1)
    benchmark_gap = round(max(TARGET_SOCIAL_BENCHMARK_SCORE - benchmark_score_avg, 0.0), 1)
    total_stage_slots = max(probe_count * len(SOCIAL_STAGE_CATALOG), 1)
    missing_stage_count = sum(1 for item in results for stage in (item.get("stage_results") or []) if stage.get("status") == "missing")
    missing_stage_rate = round((missing_stage_count / total_stage_slots) * 100, 1)
    all_lane_rows = [row for item in results for row in (item.get("matrix_rows") or [])]
    total_lane_rows = max(len(all_lane_rows), 1)
    article_understanding_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("article_understanding_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    persona_retrieval_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("persona_retrieval_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    johnnie_perspective_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("johnnie_perspective_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    article_stance_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("article_stance_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    source_expression_avg = round(
        sum(float(((row.get("expression_assessment") or {}).get("source_expression_quality")) or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    belief_relevance_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("belief_relevance_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    experience_relevance_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("experience_relevance_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    reaction_brief_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("reaction_brief_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    template_composition_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("template_composition_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    ship_readiness_avg = round(
        sum(float((row.get("stage_evaluation") or {}).get("ship_readiness_score") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    blocked_rows_rate = round(
        (
            sum(
                1
                for row in all_lane_rows
                if str((row.get("stage_evaluation") or {}).get("shipping_decision") or "") == "blocked_by_missing_stage"
            )
            / total_lane_rows
        )
        * 100,
        1,
    )
    lived_addition_rate = round(
        (
            sum(1 for row in all_lane_rows if str(((row.get("johnnie_perspective") or {}).get("lived_addition")) or "").strip())
            / total_lane_rows
        )
        * 100,
        1,
    )
    voice_match_avg = round(
        sum(float((row.get("evaluation") or {}).get("voice_match") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    expression_quality_avg = round(
        sum(float((row.get("evaluation") or {}).get("expression_quality") or 0.0) for row in all_lane_rows)
        / total_lane_rows,
        1,
    )
    passing = (
        response_failure_rate <= TARGET_SOCIAL_FAILURE_RATE
        and article_failure_rate <= TARGET_SOCIAL_FAILURE_RATE
        and benchmark_score_avg >= TARGET_SOCIAL_BENCHMARK_SCORE
        and benchmark_score_min >= TARGET_SOCIAL_BENCHMARK_FLOOR
    )
    run_started_at = _now_iso()
    stage_health = _build_social_stage_health(results)

    run = {
        "run_id": f"{SOCIAL_EXPERIMENT_ID}:{run_started_at}",
        "started_at": run_started_at,
        "probe_count": probe_count,
        "response_failure_rate": response_failure_rate,
        "comment_failure_rate": comment_failure_rate,
        "repost_failure_rate": repost_failure_rate,
        "article_failure_rate": article_failure_rate,
        "lane_coverage_rate": lane_coverage_rate,
        "missing_stage_rate": missing_stage_rate,
        "benchmark_score_avg": benchmark_score_avg,
        "benchmark_score_min": benchmark_score_min,
        "benchmark_gap": benchmark_gap,
        "stage_breakdown": stage_counts,
        "stage_health": stage_health,
        "top_failure_modes": [
            key for key, value in sorted(stage_counts.items(), key=lambda item: item[1], reverse=True) if value > 0
        ][:4],
        "sample_runs": results,
        "status": "passing" if passing else "investigating",
        "next_action": (
            "Ship the response-matrix improvement back into the owning workspace and write the postmortem."
            if passing
            else "Tune the non-pass lane or response stage, then rerun the article response matrix."
        ),
    }

    record = _EXPERIMENT_CACHE.get(SOCIAL_EXPERIMENT_ID) or _default_social_experiment_record()
    history = [run, *(record.get("history") or [])][:MAX_HISTORY]
    record.update(
        {
            "status": run["status"],
            "current": {
                "summary": (
                    f"Article response failure rate is {response_failure_rate}% across "
                    f"{probe_count} article probes and {total_response_slots} lane-response checks. "
                    f"Ship readiness is averaging {ship_readiness_avg} with {blocked_rows_rate}% of rows still blocked by missing synthesis."
                ),
                "probe_count": probe_count,
                "structural_fallback_rate": response_failure_rate,
                "legacy_fallback_rate": 0.0,
                "provider_fallback_rate": 0.0,
                "weak_output_rate": article_failure_rate,
                "response_failure_rate": response_failure_rate,
                "comment_failure_rate": comment_failure_rate,
                "repost_failure_rate": repost_failure_rate,
                "article_failure_rate": article_failure_rate,
                "lane_coverage_rate": lane_coverage_rate,
                "missing_stage_rate": missing_stage_rate,
                "benchmark_score_avg": benchmark_score_avg,
                "benchmark_score_min": benchmark_score_min,
                "benchmark_gap": benchmark_gap,
                "metric_cards": [
                    _metric_card("benchmark_score_avg", "Benchmark Avg", benchmark_score_avg, "#34d399"),
                    _metric_card("benchmark_score_min", "Benchmark Floor", benchmark_score_min, "#f59e0b"),
                    _metric_card("response_failure_rate", "Response Failure", response_failure_rate, "#38bdf8"),
                    _metric_card("missing_stage_rate", "Missing Stage", missing_stage_rate, "#a78bfa"),
                    _metric_card("lane_coverage_rate", "Lane Coverage", lane_coverage_rate, "#14b8a6"),
                    _metric_card("article_understanding_avg", "Article Understanding", article_understanding_avg, "#22c55e"),
                    _metric_card("article_stance_avg", "Article Stance", article_stance_avg, "#10b981"),
                    _metric_card("source_expression_avg", "Source Expression", source_expression_avg, "#0ea5e9"),
                    _metric_card("persona_retrieval_avg", "Persona Retrieval", persona_retrieval_avg, "#60a5fa"),
                    _metric_card("belief_relevance_avg", "Belief Relevance", belief_relevance_avg, "#3b82f6"),
                    _metric_card("experience_relevance_avg", "Experience Relevance", experience_relevance_avg, "#6366f1"),
                    _metric_card("johnnie_perspective_avg", "Johnnie Perspective", johnnie_perspective_avg, "#f97316"),
                    _metric_card("reaction_brief_avg", "Reaction Brief", reaction_brief_avg, "#f43f5e"),
                    _metric_card("template_composition_avg", "Template Composition", template_composition_avg, "#c084fc"),
                    _metric_card("voice_match_avg", "Voice Match", voice_match_avg, "#fb7185"),
                    _metric_card("expression_quality_avg", "Expression Quality", expression_quality_avg, "#f59e0b"),
                    _metric_card("ship_readiness_avg", "Ship Readiness", ship_readiness_avg, "#14b8a6"),
                    _metric_card("blocked_rows_rate", "Blocked Rows", blocked_rows_rate, "#ef4444"),
                    _metric_card("lived_addition_rate", "Lived Addition", lived_addition_rate, "#facc15"),
                ],
                "stage_breakdown": stage_counts,
                "stage_health": stage_health,
                "top_failure_modes": run["top_failure_modes"],
            },
            "sample_runs": results,
            "history": history,
            "last_run_at": run_started_at,
            "next_action": run["next_action"],
        }
    )
    record["loop"] = [
        {"id": "observe", "label": "Observe", "status": "done"},
        {"id": "tune", "label": "Tune", "status": "active" if not passing else "done"},
        {"id": "verify", "label": "Verify", "status": "active" if not passing else "done"},
        {"id": "ship", "label": "Ship", "status": "ready" if passing else "waiting"},
        {"id": "postmortem", "label": "Postmortem", "status": "ready" if passing else "waiting"},
    ]
    _EXPERIMENT_CACHE[SOCIAL_EXPERIMENT_ID] = record
    return record


async def run_source_handoff_matrix_experiment() -> dict[str, Any]:
    evaluations = [_evaluate_source_handoff_probe(probe) for probe in SOURCE_HANDOFF_PROBES]
    results = [item["sample_run"] for item in evaluations]
    live_audit = _build_live_source_handoff_audit()
    live_samples = live_audit.get("candidate_samples") or []
    probe_count = max(len(results), 1)
    mismatches = [item for item in evaluations if not item["exact_match"]]
    exact_match_count = probe_count - len(mismatches)
    mismatch_rate = round((len(mismatches) / probe_count) * 100, 1)
    exact_match_rate = round((exact_match_count / probe_count) * 100, 1)
    persona_false_positive_rate = round(
        (
            sum(
                1
                for item in evaluations
                if item["actual_handoff_lane"] == "persona_candidate" and item["expected_handoff_lane"] != "persona_candidate"
            )
            / probe_count
        )
        * 100,
        1,
    )
    persona_false_negative_rate = round(
        (
            sum(
                1
                for item in evaluations
                if item["expected_handoff_lane"] == "persona_candidate" and item["actual_handoff_lane"] != "persona_candidate"
            )
            / probe_count
        )
        * 100,
        1,
    )
    post_false_negative_rate = round(
        (
            sum(
                1
                for item in evaluations
                if item["expected_handoff_lane"] == "post_candidate" and item["actual_handoff_lane"] != "post_candidate"
            )
            / probe_count
        )
        * 100,
        1,
    )
    pm_alignment_rate = round(
        (
            sum(
                1
                for item in evaluations
                if item["expected_handoff_lane"] == "route_to_pm" and item["actual_handoff_lane"] == "route_to_pm"
            )
            / max(sum(1 for item in evaluations if item["expected_handoff_lane"] == "route_to_pm"), 1)
        )
        * 100,
        1,
    )
    source_guardrail_success_rate = round(
        (
            sum(
                1
                for item in evaluations
                if item["expected_handoff_lane"] == "source_only" and item["actual_handoff_lane"] == "source_only"
            )
            / max(sum(1 for item in evaluations if item["expected_handoff_lane"] == "source_only"), 1)
        )
        * 100,
        1,
    )

    stage_counts = {stage["id"]: 0 for stage in HANDOFF_STAGE_CATALOG}
    for item in results:
        for stage in item.get("stage_results") or []:
            if stage.get("status") != "pass":
                stage_counts[str(stage["id"])] = stage_counts.get(str(stage["id"]), 0) + 1

    stage_health = _build_handoff_stage_health(results)
    passing = mismatch_rate <= TARGET_HANDOFF_MISMATCH_RATE
    run_started_at = _now_iso()
    top_failure_modes = [
        key for key, value in sorted(stage_counts.items(), key=lambda item: item[1], reverse=True) if value > 0
    ][:4]

    run = {
        "run_id": f"{SOURCE_HANDOFF_EXPERIMENT_ID}:{run_started_at}",
        "started_at": run_started_at,
        "probe_count": probe_count,
        "structural_fallback_rate": mismatch_rate,
        "legacy_fallback_rate": 0.0,
        "provider_fallback_rate": 0.0,
        "weak_output_rate": persona_false_negative_rate,
        "exact_match_rate": exact_match_rate,
        "handoff_mismatch_rate": mismatch_rate,
        "persona_false_positive_rate": persona_false_positive_rate,
        "persona_false_negative_rate": persona_false_negative_rate,
        "post_false_negative_rate": post_false_negative_rate,
        "pm_alignment_rate": pm_alignment_rate,
        "source_guardrail_success_rate": source_guardrail_success_rate,
        "stage_breakdown": stage_counts,
        "stage_health": stage_health,
        "top_failure_modes": top_failure_modes,
        "sample_runs": results,
        "status": "passing" if passing else "investigating",
        "next_action": (
            "Ship the tuned handoff policy back into Brain and write the postmortem."
            if passing
            else "Tune the handoff thresholds or exemplars, then rerun the source handoff matrix."
        ),
    }

    record = _EXPERIMENT_CACHE.get(SOURCE_HANDOFF_EXPERIMENT_ID) or _default_source_handoff_experiment_record()
    history = [run, *(record.get("history") or [])][:MAX_HISTORY]
    record.update(
        {
            "status": run["status"],
            "current": {
                "summary": (
                    f"Handoff exact-match rate is {exact_match_rate}% across {probe_count} labeled source probes. "
                    f"Mismatch rate is {mismatch_rate}%, with source guardrails holding at {source_guardrail_success_rate}%."
                ),
                "probe_count": probe_count,
                "structural_fallback_rate": mismatch_rate,
                "legacy_fallback_rate": 0.0,
                "provider_fallback_rate": 0.0,
                "weak_output_rate": persona_false_negative_rate,
                "metric_cards": [
                    _metric_card("exact_match_rate", "Exact Match", exact_match_rate, "#34d399"),
                    _metric_card("handoff_mismatch_rate", "Mismatch", mismatch_rate, "#ef4444"),
                    _metric_card("persona_false_positive_rate", "Persona Overpush", persona_false_positive_rate, "#f97316"),
                    _metric_card("persona_false_negative_rate", "Persona Miss", persona_false_negative_rate, "#f59e0b"),
                    _metric_card("post_false_negative_rate", "Post Miss", post_false_negative_rate, "#38bdf8"),
                    _metric_card("pm_alignment_rate", "PM Alignment", pm_alignment_rate, "#a78bfa"),
                    _metric_card("source_guardrail_success_rate", "Source Guardrails", source_guardrail_success_rate, "#14b8a6"),
                ],
                "stage_breakdown": stage_counts,
                "stage_health": stage_health,
                "top_failure_modes": top_failure_modes,
            },
            "sample_runs": results,
            "live_samples": live_samples,
            "live_audit": live_audit,
            "history": history,
            "last_run_at": run_started_at,
            "next_action": run["next_action"],
        }
    )
    record["loop"] = [
        {"id": "observe", "label": "Observe", "status": "done"},
        {"id": "tune", "label": "Tune", "status": "active" if not passing else "done"},
        {"id": "verify", "label": "Verify", "status": "active" if not passing else "done"},
        {"id": "ship", "label": "Ship", "status": "ready" if passing else "waiting"},
        {"id": "postmortem", "label": "Postmortem", "status": "ready" if passing else "waiting"},
    ]
    _EXPERIMENT_CACHE[SOURCE_HANDOFF_EXPERIMENT_ID] = record
    return record


async def run_lab_experiment(experiment_id: str) -> dict[str, Any]:
    if experiment_id == EXPERIMENT_ID:
        return await run_content_fallback_experiment()
    if experiment_id == SOCIAL_EXPERIMENT_ID:
        return await run_social_response_matrix_experiment()
    if experiment_id == SOURCE_HANDOFF_EXPERIMENT_ID:
        return await run_source_handoff_matrix_experiment()
    raise KeyError(experiment_id)


def list_lab_experiments() -> list[dict[str, Any]]:
    return [
        _EXPERIMENT_CACHE.get(EXPERIMENT_ID) or _default_experiment_record(),
        _EXPERIMENT_CACHE.get(SOCIAL_EXPERIMENT_ID) or _default_social_experiment_record(),
        _EXPERIMENT_CACHE.get(SOURCE_HANDOFF_EXPERIMENT_ID) or _default_source_handoff_experiment_record(),
    ]


def get_lab_experiment(experiment_id: str) -> dict[str, Any] | None:
    if experiment_id == EXPERIMENT_ID:
        return _EXPERIMENT_CACHE.get(EXPERIMENT_ID) or _default_experiment_record()
    if experiment_id == SOCIAL_EXPERIMENT_ID:
        return _EXPERIMENT_CACHE.get(SOCIAL_EXPERIMENT_ID) or _default_social_experiment_record()
    if experiment_id == SOURCE_HANDOFF_EXPERIMENT_ID:
        return _EXPERIMENT_CACHE.get(SOURCE_HANDOFF_EXPERIMENT_ID) or _default_source_handoff_experiment_record()
    return None
