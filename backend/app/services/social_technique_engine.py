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


class SocialTechniqueEngine:
    """Selects a small rhetorical technique bundle for each variant."""

    def select_for_variant(self, signal: dict[str, Any], lane_id: str, belief: dict[str, str]) -> dict[str, Any]:
        profile = _infer_profile(signal)
        stance = belief.get("stance", "reinforce")
        techniques: list[str] = []
        emotional_profile: list[str] = []

        if stance == "counter":
            techniques.extend(["contrarian-reframe", "pattern-interrupt", "authority-snap"])
            emotional_profile.extend(["tension", "clarity"])
        elif stance == "nuance":
            techniques.extend(["specificity-injection", "contrarian-reframe"])
            emotional_profile.extend(["clarity", "discernment"])
        elif stance == "translate":
            techniques.extend(["specificity-injection", "relatability-anchor"])
            emotional_profile.extend(["practicality", "clarity"])
        elif stance == "personal-anchor":
            techniques.extend(["story-fragment", "relatability-anchor", "delayed-payoff"])
            emotional_profile.extend(["familiarity", "humanity"])
        elif stance == "systemize":
            techniques.extend(["pattern-interrupt", "specificity-injection", "authority-snap"])
            emotional_profile.extend(["clarity", "authority"])
        else:
            techniques.extend(["specificity-injection", "authority-snap"])
            emotional_profile.extend(["clarity"])

        if lane_id == "ai":
            techniques.append("contrarian-reframe" if stance in {"nuance", "counter"} else "specificity-injection")
            emotional_profile.append("discernment")
        elif lane_id in {"ops-pm", "program-leadership"}:
            techniques.extend(["pattern-interrupt", "authority-snap"])
            emotional_profile.append("structure")
        elif lane_id in {"therapy", "referral"}:
            techniques.extend(["relatability-anchor", "delayed-payoff"])
            emotional_profile.append("trust")
        elif lane_id == "personal-story":
            techniques.extend(["story-fragment", "punchline-close"])
            emotional_profile.append("recognition")
        elif lane_id in {"admissions", "current-role", "enrollment-management"}:
            techniques.extend(["specificity-injection", "relatability-anchor"])
            emotional_profile.append("grounding")
        elif lane_id == "entrepreneurship":
            techniques.extend(["contrarian-reframe", "authority-snap"])
            emotional_profile.append("ambition")

        if profile["is_story"]:
            techniques.append("story-fragment")
        if profile["is_ops"]:
            techniques.append("specificity-injection")
        if profile["is_relationship"]:
            techniques.append("relatability-anchor")
        if profile["is_claim_heavy"]:
            techniques.append("punchline-close")
        if profile["is_ai"] and lane_id == "ai":
            techniques.append("curiosity-gap")

        selected = _dedupe([technique for technique in techniques if technique in TECHNIQUE_IDS])[:3]
        emotions = _dedupe([value for value in emotional_profile if value])[:3]

        reason_parts = [
            f"stance={stance}",
            f"lane={lane_id}",
        ]
        if profile["is_ai"]:
            reason_parts.append("source carries an AI signal")
        if profile["is_ops"]:
            reason_parts.append("source reads operationally")
        if profile["is_relationship"]:
            reason_parts.append("source touches trust/relationship dynamics")
        if profile["is_story"]:
            reason_parts.append("source has a story or identity texture")

        return {
            "techniques": selected,
            "emotional_profile": emotions,
            "reason": "; ".join(reason_parts),
        }


social_technique_engine = SocialTechniqueEngine()
