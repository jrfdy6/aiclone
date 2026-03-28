from __future__ import annotations

from typing import Any


GENERIC_PHRASES = [
    "this is important",
    "in today's world",
    "leverage",
    "game changer",
    "synergy",
    "more than ever",
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
        comment: str,
        repost: str,
        short_comment: str,
    ) -> dict[str, Any]:
        combined = " ".join([comment, repost, short_comment]).lower()
        warnings: list[str] = []

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

        voice_match = 6.0
        if any(phrase in combined for phrase in ["the hard way", "real work", "that part matters", "i keep", "this tracks for me"]):
            voice_match += 1.2
        if len(comment.split()) < 22 or len(comment.split()) > 90:
            voice_match -= 0.6
        if contains_any(combined, GENERIC_PHRASES):
            voice_match -= 1.2
            warnings.append("copy still contains generic language")

        role_safety_value = normalize_inline_text(belief.get("role_safety")) or "safe"
        role_safety_score = {"safe": 9.2, "review": 6.4, "risky": 3.8}.get(role_safety_value, 6.0)
        if role_safety_value != "safe":
            warnings.append(f"role safety is {role_safety_value}")

        genericity_penalty = 0.0
        if contains_any(combined, GENERIC_PHRASES):
            genericity_penalty += 1.5
        if not technique.get("techniques"):
            genericity_penalty += 1.0
            warnings.append("technique bundle is empty")
        if not signal.get("standout_lines"):
            genericity_penalty += 0.6

        overall = (
            lane_distinctiveness
            + belief_clarity
            + experience_strength
            + voice_match
            + role_safety_score
            - genericity_penalty
        ) / 5.0

        if lane_distinctiveness < 6.2:
            warnings.append("lane differentiation may be weak")
        if belief_clarity < 6.5:
            warnings.append("belief framing may be too implicit")
        if overall < 6.8:
            warnings.append("variant needs review before high-confidence use")

        return {
            "lane_distinctiveness": round_score(clamp(lane_distinctiveness, 1.0, 10.0)),
            "belief_clarity": round_score(clamp(belief_clarity, 1.0, 10.0)),
            "experience_anchor_strength": round_score(clamp(experience_strength, 1.0, 10.0)),
            "voice_match": round_score(clamp(voice_match, 1.0, 10.0)),
            "role_safety_score": round_score(clamp(role_safety_score, 1.0, 10.0)),
            "genericity_penalty": round_score(clamp(genericity_penalty, 0.0, 10.0)),
            "overall": round_score(clamp(overall, 1.0, 10.0)),
            "warnings": warnings[:4],
        }


social_evaluation_engine = SocialEvaluationEngine()
