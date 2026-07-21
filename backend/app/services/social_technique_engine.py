from __future__ import annotations

import re
from typing import Any


TECHNIQUE_IDS = [
    "curiosity-gap",
    "contrarian-reframe",
    "pattern-interrupt",
    "tension-escalation",
    "relatability-anchor",
    "specificity-injection",
    "authority-snap",
    "delayed-payoff",
    "story-fragment",
    "punchline-close",
]

_STANCE_TECHNIQUES = {
    "reinforce": ["specificity-injection", "authority-snap", "delayed-payoff"],
    "nuance": ["contrarian-reframe", "specificity-injection", "authority-snap"],
    "counter": ["contrarian-reframe", "pattern-interrupt", "authority-snap"],
    "translate": ["specificity-injection", "relatability-anchor", "delayed-payoff"],
    "personal-anchor": ["story-fragment", "relatability-anchor", "delayed-payoff"],
    "systemize": ["pattern-interrupt", "specificity-injection", "authority-snap"],
}

_LANE_TECHNIQUES = {
    "ai": ["curiosity-gap", "specificity-injection", "contrarian-reframe"],
    "ops-pm": ["pattern-interrupt", "specificity-injection", "authority-snap"],
    "admissions": ["relatability-anchor", "specificity-injection", "delayed-payoff"],
    "program-leadership": ["authority-snap", "pattern-interrupt", "delayed-payoff"],
    "entrepreneurship": ["contrarian-reframe", "curiosity-gap", "punchline-close"],
    "current-role": ["relatability-anchor", "authority-snap", "specificity-injection"],
    "enrollment-management": ["specificity-injection", "relatability-anchor", "delayed-payoff"],
    "therapy": ["relatability-anchor", "story-fragment", "delayed-payoff"],
    "referral": ["relatability-anchor", "delayed-payoff", "authority-snap"],
    "personal-story": ["story-fragment", "relatability-anchor", "punchline-close"],
}

_RESPONSE_TYPE_TECHNIQUES = {
    "agree": ["specificity-injection", "delayed-payoff"],
    "contrarian": ["contrarian-reframe", "authority-snap"],
    "personal_story": ["story-fragment", "relatability-anchor"],
    "humor": ["pattern-interrupt", "punchline-close"],
}

_LANE_EMOTIONS = {
    "ai": ["discernment", "clarity"],
    "ops-pm": ["structure", "clarity"],
    "admissions": ["grounding", "trust"],
    "program-leadership": ["authority", "coaching"],
    "entrepreneurship": ["ambition", "discernment"],
    "current-role": ["credibility", "grounding"],
    "enrollment-management": ["clarity", "trust"],
    "therapy": ["attunement", "humanity"],
    "referral": ["trust", "continuity"],
    "personal-story": ["recognition", "humanity"],
}

_RESPONSE_TYPE_EMOTIONS = {
    "agree": ["clarity"],
    "contrarian": ["tension", "clarity"],
    "personal_story": ["lived_proof", "humanity"],
    "humor": ["wit", "release"],
}


def normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    for needle in needles:
        token = needle.lower()
        if token.isalpha() and len(token) <= 3:
            if re.search(rf"\b{re.escape(token)}\b", lowered):
                return True
            continue
        if token in lowered:
            return True
    return False


def _infer_profile(signal: dict[str, Any]) -> dict[str, bool]:
    text = " ".join(
        [
            normalize_inline_text(signal.get("title")),
            normalize_inline_text(signal.get("summary")),
            normalize_inline_text(signal.get("core_claim")),
            " ".join(signal.get("supporting_claims") or []),
            normalize_inline_text(signal.get("raw_text"))[:1600],
        ]
    ).lower()
    return {
        "is_ai": contains_any(text, ["ai", "agent", "model", "llm", "automation", "prompt"]),
        "is_story": contains_any(text, ["story", "lesson", "experience", "authenticity", "personally", "i learned"]),
        "is_relationship": contains_any(text, ["trust", "referral", "family", "relationship", "community", "human"]),
        "is_ops": contains_any(text, ["workflow", "ownership", "handoff", "process", "project", "execution", "operations"]),
        "is_education": contains_any(text, ["education", "student", "admissions", "enrollment", "school", "college"]),
        "is_claim_heavy": contains_any(text, ["should", "must", "need to", "real issue", "the point is"]),
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _extend_unique(target: list[str], values: list[str], *, limit: int) -> None:
    for value in values:
        normalized = normalize_inline_text(value)
        if not normalized or normalized in target:
            continue
        target.append(normalized)
        if len(target) >= limit:
            return


class SocialTechniqueEngine:
    """Selects a small rhetorical technique bundle for each variant."""

    def select_for_variant(self, signal: dict[str, Any], lane_id: str, belief: dict[str, str]) -> dict[str, Any]:
        profile = _infer_profile(signal)
        stance = belief.get("stance", "reinforce")
        response_type = normalize_inline_text(belief.get("response_type")).lower().replace("-", "_")
        selected: list[str] = []
        emotions: list[str] = []

        _extend_unique(selected, (_LANE_TECHNIQUES.get(lane_id) or [])[:1], limit=3)
        _extend_unique(selected, (_RESPONSE_TYPE_TECHNIQUES.get(response_type) or [])[:1], limit=3)
        _extend_unique(selected, (_STANCE_TECHNIQUES.get(stance) or [])[:2], limit=3)

        if profile["is_story"]:
            _extend_unique(selected, ["story-fragment"], limit=3)
        if profile["is_ops"]:
            _extend_unique(selected, ["specificity-injection"], limit=3)
        if profile["is_relationship"]:
            _extend_unique(selected, ["relatability-anchor"], limit=3)
        if profile["is_claim_heavy"]:
            _extend_unique(selected, ["punchline-close"], limit=3)
        if profile["is_ai"] and lane_id == "ai":
            _extend_unique(selected, ["curiosity-gap"], limit=3)
        _extend_unique(selected, _LANE_TECHNIQUES.get(lane_id) or [], limit=3)
        _extend_unique(selected, _RESPONSE_TYPE_TECHNIQUES.get(response_type) or [], limit=3)
        _extend_unique(selected, _STANCE_TECHNIQUES.get(stance) or [], limit=3)

        _extend_unique(emotions, (_LANE_EMOTIONS.get(lane_id) or [])[:1], limit=3)
        _extend_unique(emotions, (_RESPONSE_TYPE_EMOTIONS.get(response_type) or [])[:1], limit=3)
        if stance == "counter":
            _extend_unique(emotions, ["tension", "clarity"], limit=3)
        elif stance == "nuance":
            _extend_unique(emotions, ["discernment", "clarity"], limit=3)
        elif stance == "personal-anchor":
            _extend_unique(emotions, ["humanity", "familiarity"], limit=3)
        elif stance == "systemize":
            _extend_unique(emotions, ["authority", "structure"], limit=3)
        else:
            _extend_unique(emotions, ["clarity"], limit=3)

        reason_parts = [
            f"stance={stance}",
            f"lane={lane_id}",
        ]
        if response_type:
            reason_parts.append(f"type={response_type}")
        if profile["is_ai"]:
            reason_parts.append("source carries an AI signal")
        if profile["is_ops"]:
            reason_parts.append("source reads operationally")
        if profile["is_relationship"]:
            reason_parts.append("source touches trust/relationship dynamics")
        if profile["is_story"]:
            reason_parts.append("source has a story or identity texture")

        return {"techniques": selected[:3], "emotional_profile": emotions[:3], "reason": "; ".join(reason_parts)}


social_technique_engine = SocialTechniqueEngine()
