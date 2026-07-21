from __future__ import annotations

from typing import Any


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _round_score(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 1)


class SocialStageEvaluationService:
    def evaluate_variant(
        self,
        *,
        article_understanding: dict[str, Any] | None,
        persona_retrieval: dict[str, Any] | None,
        johnnie_perspective: dict[str, Any] | None,
        reaction_brief: dict[str, Any] | None,
        composition_traces: dict[str, Any] | None,
        response_type_packet: dict[str, Any] | None,
    ) -> dict[str, Any]:
        article_understanding = article_understanding or {}
        persona_retrieval = persona_retrieval or {}
        johnnie_perspective = johnnie_perspective or {}
        reaction_brief = reaction_brief or {}
        composition_traces = composition_traces or {}
        response_type_packet = response_type_packet or {}

        article_understanding_score = 4.5
        if _normalize_inline_text(article_understanding.get("thesis")):
            article_understanding_score += 1.7
        if _normalize_inline_text(article_understanding.get("world_context")):
            article_understanding_score += 1.5
        if _normalize_inline_text(article_understanding.get("article_stance")):
            article_understanding_score += 1.3

        world_context_score = 4.5
        if _normalize_inline_text(article_understanding.get("world_stakes")):
            world_context_score += 2.0
        if article_understanding.get("audience_impacted"):
            world_context_score += 1.3
        if _normalize_inline_text(article_understanding.get("article_world_position")):
            world_context_score += 1.0

        article_stance_score = 3.5 + (2.8 if _normalize_inline_text(article_understanding.get("article_stance")) else 0.0)
        article_stance_score += 1.2 if float(article_understanding.get("article_stance_confidence") or 0.0) >= 7.0 else 0.0
        if _normalize_inline_text(article_understanding.get("article_stance_reason")):
            article_stance_score += 0.8
        if _normalize_inline_text(article_understanding.get("article_stance_counterweight")):
            article_stance_score += 0.6
        if article_understanding.get("article_stance_evidence"):
            article_stance_score += 0.4
        if _normalize_inline_text(article_understanding.get("source_expression_family")) not in {"", "plain", "none"}:
            article_stance_score += 0.3

        persona_retrieval_score = 4.0
        if persona_retrieval.get("relevant_claims"):
            persona_retrieval_score += 1.8
        if persona_retrieval.get("relevant_stories"):
            persona_retrieval_score += 1.5
        if persona_retrieval.get("relevant_initiatives"):
            persona_retrieval_score += 1.2
        persona_retrieval_score += min(float(persona_retrieval.get("retrieval_diversity_score") or 0.0) * 0.15, 1.5)

        selected_belief = persona_retrieval.get("selected_belief") or {}
        belief_relevance_score = 3.5
        if _normalize_inline_text(selected_belief.get("text")):
            belief_relevance_score += 2.0
        belief_relevance_score += min(float(selected_belief.get("selection_fit_score") or 0.0) / 6.0, 2.8)
        belief_relevance_score += min(float(selected_belief.get("reference_alignment_score") or 0.0) * 0.35, 0.8)
        if _normalize_inline_text(selected_belief.get("claim_type")) in {"operational", "contrarian", "mission", "philosophical"}:
            belief_relevance_score += 0.6
        elif _normalize_inline_text(selected_belief.get("claim_type")) in {"positioning", "factual"}:
            belief_relevance_score -= 0.4
        selected_experience = persona_retrieval.get("selected_experience") or {}
        experience_relevance_score = 3.5
        if _normalize_inline_text(selected_experience.get("text")):
            experience_relevance_score += 2.0
        experience_relevance_score += min(float(selected_experience.get("selection_fit_score") or 0.0) / 8.0, 2.4)
        if bool(selected_experience.get("artifact_backed")):
            experience_relevance_score += 0.6
        proof_strength = _normalize_inline_text(selected_experience.get("proof_strength"))
        if proof_strength == "strong":
            experience_relevance_score += 0.5
        elif proof_strength == "medium":
            experience_relevance_score += 0.2
        candidate_type = _normalize_inline_text(selected_experience.get("candidate_type"))
        if candidate_type in {"story", "initiative", "delta"}:
            experience_relevance_score += 0.4
        elif candidate_type == "claim":
            experience_relevance_score -= 0.5

        johnnie_perspective_score = 4.0
        if _normalize_inline_text(johnnie_perspective.get("agree_with")):
            johnnie_perspective_score += 1.5
        if _normalize_inline_text(johnnie_perspective.get("pushback")):
            johnnie_perspective_score += 1.3
        if _normalize_inline_text(johnnie_perspective.get("lived_addition")):
            johnnie_perspective_score += 1.3
        if _normalize_inline_text(johnnie_perspective.get("what_matters_most")):
            johnnie_perspective_score += 1.1

        reaction_brief_score = 4.0
        for field in ("article_view", "johnnie_view", "tension", "content_angle"):
            if _normalize_inline_text(str(reaction_brief.get(field) or "")):
                reaction_brief_score += 1.0
        if reaction_brief.get("evidence_to_use"):
            reaction_brief_score += 0.8

        template_composition_score = 4.0
        if composition_traces.get("comment"):
            template_composition_score += 2.0
        if composition_traces.get("repost"):
            template_composition_score += 2.0
        if (composition_traces.get("comment") or {}).get("selected_parts"):
            template_composition_score += 1.0
        if (composition_traces.get("repost") or {}).get("selected_parts"):
            template_composition_score += 1.0

        response_type_score = 4.0
        if _normalize_inline_text(response_type_packet.get("response_type")):
            response_type_score += 2.5
        if response_type_packet.get("eligible_types"):
            response_type_score += 1.0
        if float(response_type_packet.get("type_confidence") or 0.0) >= 7.0:
            response_type_score += 1.0

        humor_safety = response_type_packet.get("humor_safety") or {}
        humor_safety_score = 8.5 if not humor_safety else 6.0 + (2.0 if "humor_allowed" in humor_safety else 0.0)

        missing_fields = []
        for field, value in {
            "article_stance": article_understanding.get("article_stance"),
            "persona_retrieval": persona_retrieval.get("top_candidates"),
            "johnnie_perspective": johnnie_perspective.get("personal_reaction"),
            "reaction_brief": reaction_brief.get("content_angle"),
            "template_composition": composition_traces.get("comment") or composition_traces.get("repost"),
            "response_type": response_type_packet.get("response_type"),
        }.items():
            if not value:
                missing_fields.append(field)

        critical_missing = {
            "article_stance",
            "persona_retrieval",
            "johnnie_perspective",
            "reaction_brief",
            "template_composition",
        } & set(missing_fields)

        ship_readiness_score = _round_score(
            (
                article_understanding_score
                + persona_retrieval_score
                + johnnie_perspective_score
                + reaction_brief_score
                + template_composition_score
                + response_type_score
            )
            / 6.0
        )

        if critical_missing:
            shipping_decision = "blocked_by_missing_stage"
        elif ship_readiness_score >= 8.6:
            shipping_decision = "ship"
        elif ship_readiness_score >= 7.0:
            shipping_decision = "needs_review"
        else:
            shipping_decision = "hold"

        warnings = []
        if critical_missing:
            warnings.append("critical upstream stages are still missing")
        if float(persona_retrieval.get("retrieval_diversity_score") or 0.0) < 6.5:
            warnings.append("persona retrieval diversity is still thin")
        if _normalize_inline_text(selected_belief.get("text")) and float(selected_belief.get("selection_fit_score") or 0.0) < 15.0:
            warnings.append("belief relevance is still thin")
        if _normalize_inline_text(selected_experience.get("text")) and float(selected_experience.get("selection_fit_score") or 0.0) < 15.0:
            warnings.append("experience relevance is still thin")
        if not _normalize_inline_text(johnnie_perspective.get("lived_addition")):
            warnings.append("lived addition is still thin")

        return {
            "article_understanding_score": _round_score(article_understanding_score),
            "world_context_score": _round_score(world_context_score),
            "article_stance_score": _round_score(article_stance_score),
            "persona_retrieval_score": _round_score(persona_retrieval_score),
            "belief_relevance_score": _round_score(belief_relevance_score),
            "experience_relevance_score": _round_score(experience_relevance_score),
            "johnnie_perspective_score": _round_score(johnnie_perspective_score),
            "reaction_brief_score": _round_score(reaction_brief_score),
            "template_composition_score": _round_score(template_composition_score),
            "response_type_score": _round_score(response_type_score),
            "humor_safety_score": _round_score(humor_safety_score),
            "ship_readiness_score": ship_readiness_score,
            "shipping_decision": shipping_decision,
            "warnings": warnings[:6],
            "missing_fields": sorted(missing_fields),
            "critical_missing_fields": sorted(critical_missing),
        }


social_stage_evaluation_service = SocialStageEvaluationService()
