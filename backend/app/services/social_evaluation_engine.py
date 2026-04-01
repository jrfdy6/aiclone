from __future__ import annotations

from typing import Any

from app.services.social_expression_engine import analyze_expression


GENERIC_PHRASES = [
    "this is important",
    "in today's world",
    "leverage",
    "game changer",
    "synergy",
    "more than ever",
]

ABSTRACT_META_PHRASES = [
    "abstract commentary",
    "community-facing execution",
    "live operating role",
]

VOICE_MARKERS = [
    "that part matters",
    "this tracks for me",
    "i keep",
    "people get this wrong",
    "they're not wrong, but",
    "thats incomplete",
    "that's incomplete",
    "that's not really the issue",
    "that's the real shift",
    "compression",
    "the hard way",
    "real work",
    "the real gap",
    "the real leak",
    "this reads like",
    "the leadership move",
    "builder lesson",
    "the frontline",
    "repeated questions",
    "i can't rock with it",
    "that dog will not hunt",
    "show me the artifact",
    "you feel me",
    "you heard me",
    "real talk",
    "can i be honest",
    "people, process, and culture",
    "if it is not useful, it is just another tab",
    "if it's not useful, it's just another tab",
    "if you cannot rely on the output, you cannot really build with it",
    "automate friction, not judgment",
    "function is not the same thing as value",
    "partial functionality can hide a real system failure",
    "that is a story. where is the artifact",
    "that's a story. where's the artifact",
    "this is not really a system",
    "i have seen some version of this up close",
    "this feels familiar for a reason",
    "it reads one way from a distance and another way from inside the work",
    "it sounds one way from a distance and another way from inside the work",
    "the visible backlog is not the real system",
    "the underlying operating system is where the break usually lives",
    "the signal usually appears at the edge of the work first",
    "leadership matters in whether that gets translated into standards",
]

SIGNATURE_OPENERS = [
    "look,",
    "real talk:",
    "can i be honest?",
    "here's the thing",
    "i have seen some version of this up close.",
    "this feels familiar for a reason.",
]

CONTRAST_MARKERS = [
    "but",
    "instead",
    "one thing",
    "one layer lower",
    "the real leak",
    "the real issue",
    "the real test",
    "the useful move",
    "the bigger challenge",
    "the deeper problem",
    "the issue usually shows up",
    "the pattern only matters once",
    "the pattern only counts once",
    "the idea is not enough",
    "not the finish line",
    "stops too early",
    "show me the artifact",
    "that dog will not hunt",
    "that's not how it works in real life",
    "that is not how it works in real life",
    "here's where the frame loses me",
    "here's where it loses me",
    "the frame loses me",
    "not really a system",
    "one way from a distance and another way from inside the work",
    "the visible backlog is not the real system",
    "the underlying operating system is where the break usually lives",
]

LANE_MARKERS = {
    "admissions": ["admissions", "family", "prospect", "student journey", "follow-up"],
    "entrepreneurship": ["builder", "system", "distribution", "execution", "compound"],
    "current-role": ["current role", "students", "families", "staff", "real work"],
    "program-leadership": ["leadership", "team", "shared process", "leaders", "execution"],
    "enrollment-management": ["enrollment", "conversion", "journey", "follow-through", "drop-off"],
    "ai": ["ai", "model", "prompt", "judgment", "output"],
    "ops-pm": ["ownership", "handoff", "workflow", "cadence", "process"],
    "therapy": ["human", "attuned", "support", "emotional", "held"],
    "referral": ["referral", "partner", "handoff", "trust", "confidence"],
    "personal-story": ["i", "lived", "hard way", "familiar", "seen up close"],
}


def normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _warm_then_sharp(text: str) -> bool:
    lowered = text.lower()
    warm_markers = [
        "i understand",
        "that's an interesting perspective",
        "directionally yes",
        "i see why",
        "the signal is there",
        "they're not wrong",
        "i have seen some version of this up close",
        "this feels familiar for a reason",
    ]
    sharp_markers = [
        "here's where",
        "i can't rock with it",
        "it loses me",
        "that's not really the issue",
        "that's incomplete",
        "that dog will not hunt",
        "show me the artifact",
        "but that's not how it works in real life",
        "the visible backlog is not the real system",
        "the underlying operating system is where the break usually lives",
    ]
    return any(marker in lowered for marker in warm_markers) and any(marker in lowered for marker in sharp_markers)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_score(value: float) -> float:
    return round(value, 1)


class SocialEvaluationEngine:
    """Lightweight rule-based evaluator for observability and debugging."""

    def evaluate_variant(
        self,
        *,
        lane_id: str,
        signal: dict[str, Any],
        belief: dict[str, str],
        technique: dict[str, Any],
        expression: dict[str, Any] | None,
        comment: str,
        repost: str,
        short_comment: str,
        article_understanding: dict[str, Any] | None = None,
        persona_retrieval: dict[str, Any] | None = None,
        johnnie_perspective: dict[str, Any] | None = None,
        reaction_brief: dict[str, Any] | None = None,
        composition_traces: dict[str, Any] | None = None,
        response_type_packet: dict[str, Any] | None = None,
        stage_evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        article_understanding = article_understanding or {}
        persona_retrieval = persona_retrieval or {}
        johnnie_perspective = johnnie_perspective or {}
        reaction_brief = reaction_brief or {}
        composition_traces = composition_traces or {}
        response_type_packet = response_type_packet or {}
        stage_evaluation = stage_evaluation or {}
        combined = " ".join([comment, repost, short_comment]).lower()
        warnings: list[str] = []
        genericity_penalty = 0.0
        comment_expression = analyze_expression(comment)
        repost_expression = analyze_expression(repost)
        short_expression = analyze_expression(short_comment)
        direct_expression_quality = max(
            float(comment_expression.get("overall") or 0.0),
            float(repost_expression.get("overall") or 0.0),
            float(short_expression.get("overall") or 0.0),
        )

        markers = LANE_MARKERS.get(lane_id, [])
        lane_hits = sum(1 for marker in markers if marker in combined)
        lane_distinctiveness = 5.5 + min(lane_hits, 3) * 1.2
        if lane_hits == 0:
            lane_distinctiveness -= 1.5
            warnings.append("lane markers are light")

        belief_clarity = 5.5
        if belief.get("belief_summary"):
            belief_clarity += 1.8
        if belief.get("stance") in {"nuance", "counter", "systemize", "personal-anchor"}:
            belief_clarity += 0.8
        if belief.get("agreement_level") == "low":
            belief_clarity += 0.2

        experience_strength = 4.8
        experience_summary = normalize_inline_text(belief.get("experience_summary"))
        if experience_summary:
            experience_strength += 2.0
        if experience_summary and experience_summary.lower() in combined:
            experience_strength += 0.8
        if belief.get("stance") == "personal-anchor":
            experience_strength += 0.8
        elif lane_id in {"current-role", "referral", "therapy"} and experience_summary:
            experience_strength += 0.5
        if not experience_summary:
            warnings.append("experience anchor is thin")

        voice_match = 5.8
        voice_hits = sum(1 for phrase in VOICE_MARKERS if phrase in combined)
        if voice_hits:
            voice_match += min(voice_hits, 4) * 0.45
        if any(opener in comment.lower() for opener in SIGNATURE_OPENERS):
            voice_match += 0.4
        if any(phrase in comment.lower() for phrase in ["the real gap", "the real leak", "the leadership move", "builder lesson"]):
            voice_match += 0.5
        if _warm_then_sharp(combined):
            voice_match += 0.9
        if any(
            phrase in combined
            for phrase in [
                "show me the artifact",
                "that dog will not hunt",
                "i can't rock with it",
                "if it is not useful, it is just another tab",
                "if it's not useful, it's just another tab",
            ]
        ):
            voice_match += 0.8
        if len(comment.split()) < 22 or len(comment.split()) > 90:
            voice_match -= 0.6
        if contains_any(combined, GENERIC_PHRASES):
            voice_match -= 1.2
            warnings.append("copy still contains generic language")
        if contains_any(combined, ABSTRACT_META_PHRASES):
            voice_match -= 1.1
            genericity_penalty += 1.1
            warnings.append("copy still contains abstract meta phrasing")
        if belief.get("stance") in {"nuance", "counter", "systemize"} and not contains_any(combined, CONTRAST_MARKERS):
            genericity_penalty += 0.6
            warnings.append("stance contrast is light")

        role_safety_value = normalize_inline_text(belief.get("role_safety")) or "safe"
        role_safety_score = {"safe": 9.2, "review": 6.4, "risky": 3.8}.get(role_safety_value, 6.0)
        if role_safety_value != "safe":
            warnings.append(f"role safety is {role_safety_value}")

        expression_quality = 6.0
        source_expression_quality = None
        output_expression_quality = None
        expression_delta = None
        source_structure = None
        output_structure = None
        structure_preserved = None
        if expression:
            source_expression_quality = float(expression.get("source_expression_quality") or 0.0)
            output_expression_quality = float(expression.get("output_expression_quality") or 0.0)
            expression_delta = float(expression.get("expression_delta") or 0.0)
            source_structure = normalize_inline_text(expression.get("source_structure")) or None
            output_structure = normalize_inline_text(expression.get("output_structure")) or None
            structure_preserved = bool(expression.get("structure_preserved"))
            expression_quality = output_expression_quality if output_expression_quality else expression_quality
            if expression_delta < 0:
                expression_quality += expression_delta
            if expression_delta < -0.5:
                warnings.append("rewrite weakened source expression")
            if source_structure and source_structure not in {"none", "plain"} and structure_preserved is False:
                warnings.append("rewrite lost source structure")
            if float(expression.get("overlap_ratio") or 0.0) > 0.92:
                warnings.append("rewrite remains too close to source")
        expression_quality = max(expression_quality, direct_expression_quality)

        if contains_any(combined, GENERIC_PHRASES):
            genericity_penalty += 1.5
        if not technique.get("techniques"):
            genericity_penalty += 1.0
            warnings.append("technique bundle is empty")
        if not signal.get("standout_lines"):
            genericity_penalty += 0.6

        article_understanding_score = float(stage_evaluation.get("article_understanding_score") or 0.0)
        persona_retrieval_score = float(stage_evaluation.get("persona_retrieval_score") or 0.0)
        johnnie_perspective_score = float(stage_evaluation.get("johnnie_perspective_score") or 0.0)
        reaction_brief_score = float(stage_evaluation.get("reaction_brief_score") or 0.0)
        template_composition_score = float(stage_evaluation.get("template_composition_score") or 0.0)
        response_type_score = float(stage_evaluation.get("response_type_score") or 0.0)

        critical_missing_fields = [str(item) for item in (stage_evaluation.get("critical_missing_fields") or [])]
        if critical_missing_fields:
            warnings.append("critical synthesis stage missing")
            genericity_penalty += 1.2
        if not normalize_inline_text(article_understanding.get("article_stance")):
            warnings.append("article stance is missing")
            genericity_penalty += 0.5
        if not (persona_retrieval.get("relevant_claims") or persona_retrieval.get("top_candidates")):
            warnings.append("persona retrieval is thin")
            genericity_penalty += 0.6
        if not normalize_inline_text(johnnie_perspective.get("personal_reaction")):
            warnings.append("johnnie perspective is thin")
            genericity_penalty += 0.6
        if not normalize_inline_text(reaction_brief.get("content_angle")):
            warnings.append("reaction brief is thin")
            genericity_penalty += 0.6
        if not composition_traces.get("comment") or not composition_traces.get("repost"):
            warnings.append("template composition trace is thin")
            genericity_penalty += 0.4

        overall = (
            lane_distinctiveness
            + belief_clarity
            + experience_strength
            + voice_match
            + expression_quality
            + role_safety_score
            - genericity_penalty
        ) / 6.0

        if lane_distinctiveness < 6.2:
            warnings.append("lane differentiation may be weak")
        if belief_clarity < 6.5:
            warnings.append("belief framing may be too implicit")
        if response_type_packet.get("response_type") == "personal_story" and not normalize_inline_text(johnnie_perspective.get("lived_addition")):
            warnings.append("personal story type lacks lived proof")
        if response_type_packet.get("response_type") == "contrarian" and not normalize_inline_text(johnnie_perspective.get("pushback")):
            warnings.append("contrarian type lacks pushback")
        if response_type_packet.get("response_type") == "humor" and not bool((response_type_packet.get("humor_safety") or {}).get("humor_allowed")):
            warnings.append("humor type is not safely eligible")
        if overall < 6.8:
            warnings.append("variant needs review before high-confidence use")

        synthesis_truth = (
            article_understanding_score
            + persona_retrieval_score
            + johnnie_perspective_score
            + reaction_brief_score
            + template_composition_score
            + response_type_score
        ) / 6.0 if stage_evaluation else 0.0
        voice_truth = (
            voice_match
            + float(stage_evaluation.get("belief_relevance_score") or 0.0)
            + float(stage_evaluation.get("experience_relevance_score") or 0.0)
            + johnnie_perspective_score
        ) / 4.0 if stage_evaluation else voice_match

        benchmark_score = (
            overall * 0.35
            + lane_distinctiveness * 0.15
            + belief_clarity * 0.15
            + voice_match * 0.10
            + direct_expression_quality * 0.15
            + role_safety_score * 0.10
        )
        if stage_evaluation:
            benchmark_score = benchmark_score * 0.7 + synthesis_truth * 0.2 + voice_truth * 0.1
        if not warnings:
            benchmark_score += 1.3
        if comment_expression.get("overall", 0.0) >= 7.0 and repost_expression.get("overall", 0.0) >= 7.0:
            benchmark_score += 0.4
        if lane_distinctiveness >= 7.5 and belief_clarity >= 7.3:
            benchmark_score += 0.3
        if critical_missing_fields:
            benchmark_score = min(benchmark_score, 8.2)
        benchmark_score = round_score(clamp(benchmark_score, 1.0, 10.0))

        return {
            "lane_distinctiveness": round_score(clamp(lane_distinctiveness, 1.0, 10.0)),
            "belief_clarity": round_score(clamp(belief_clarity, 1.0, 10.0)),
            "experience_anchor_strength": round_score(clamp(experience_strength, 1.0, 10.0)),
            "voice_match": round_score(clamp(voice_match, 1.0, 10.0)),
            "expression_quality": round_score(clamp(expression_quality, 1.0, 10.0)),
            "comment_expression_quality": round_score(clamp(float(comment_expression.get("overall") or 0.0), 0.0, 10.0)),
            "repost_expression_quality": round_score(clamp(float(repost_expression.get("overall") or 0.0), 0.0, 10.0)),
            "short_expression_quality": round_score(clamp(float(short_expression.get("overall") or 0.0), 0.0, 10.0)),
            "role_safety_score": round_score(clamp(role_safety_score, 1.0, 10.0)),
            "genericity_penalty": round_score(clamp(genericity_penalty, 0.0, 10.0)),
            "source_expression_quality": round_score(clamp(source_expression_quality or 0.0, 0.0, 10.0)),
            "output_expression_quality": round_score(clamp(output_expression_quality or 0.0, 0.0, 10.0)),
            "expression_delta": round_score(clamp(expression_delta or 0.0, -10.0, 10.0)),
            "source_structure": source_structure,
            "output_structure": output_structure,
            "structure_preserved": structure_preserved,
            "article_understanding_score": round_score(clamp(article_understanding_score, 0.0, 10.0)),
            "persona_retrieval_score": round_score(clamp(persona_retrieval_score, 0.0, 10.0)),
            "johnnie_perspective_score": round_score(clamp(johnnie_perspective_score, 0.0, 10.0)),
            "reaction_brief_score": round_score(clamp(reaction_brief_score, 0.0, 10.0)),
            "template_composition_score": round_score(clamp(template_composition_score, 0.0, 10.0)),
            "response_type_score": round_score(clamp(response_type_score, 0.0, 10.0)),
            "voice_truth_score": round_score(clamp(voice_truth, 0.0, 10.0)),
            "synthesis_truth_score": round_score(clamp(synthesis_truth, 0.0, 10.0)),
            "ship_readiness_score": round_score(clamp(float(stage_evaluation.get("ship_readiness_score") or 0.0), 0.0, 10.0)),
            "shipping_decision": stage_evaluation.get("shipping_decision"),
            "critical_missing_fields": critical_missing_fields,
            "overall": round_score(clamp(overall, 1.0, 10.0)),
            "benchmark_score": benchmark_score,
            "warnings": warnings[:6],
        }


social_evaluation_engine = SocialEvaluationEngine()
