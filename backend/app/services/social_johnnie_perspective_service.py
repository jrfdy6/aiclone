from __future__ import annotations

from typing import Any


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _clean_sentence(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized[:-1] if normalized.endswith(".") else normalized


def _ensure_period(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


def _strip_packet_metadata(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    for marker in (" Usage:", " Evidence:", " Proof:", " Public-facing proof:"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0].strip()
    return normalized


def _lane_audience_posture(lane_id: str) -> str:
    mapping = {
        "ai": "builder_operator",
        "ops-pm": "operator_peer",
        "admissions": "frontline_enrollment_peer",
        "enrollment-management": "journey_operator",
        "program-leadership": "team_leadership_peer",
        "entrepreneurship": "builder_founder_peer",
        "therapy": "care_and_attunement_posture",
        "referral": "trust_and_handoff_posture",
        "current-role": "live_role_operator",
        "personal-story": "lived_experience_posture",
    }
    return mapping.get(lane_id, "operator_peer")


def _lane_role_posture(lane_id: str) -> str:
    mapping = {
        "admissions": "trusted_admissions_operator",
        "enrollment-management": "journey_system_operator",
        "program-leadership": "process_and_people_leader",
        "ops-pm": "workflow_owner",
        "ai": "ai_practitioner",
        "entrepreneurship": "builder_operator",
        "therapy": "human-centered_reflector",
        "referral": "trust_bridge_operator",
        "current-role": "live_operating_role",
        "personal-story": "lived_operator",
    }
    return mapping.get(lane_id, "operator")


class SocialJohnniePerspectiveService:
    def build(
        self,
        *,
        signal: dict[str, Any],
        lane_id: str,
        article_understanding: dict[str, Any],
        persona_retrieval: dict[str, Any],
        belief_assessment: dict[str, str],
    ) -> dict[str, Any]:
        thesis = _clean_sentence(article_understanding.get("thesis"))
        world_stakes = _clean_sentence(article_understanding.get("world_stakes"))
        article_kind = _normalize_inline_text(article_understanding.get("article_kind")).lower()
        selected_belief = persona_retrieval.get("selected_belief") or {}
        selected_experience = persona_retrieval.get("selected_experience") or {}

        belief_text = _clean_sentence(
            _strip_packet_metadata(
            selected_belief.get("summary_text")
            or selected_belief.get("text")
            or belief_assessment.get("belief_summary")
            )
        )
        experience_text = _clean_sentence(
            _strip_packet_metadata(
            selected_experience.get("summary_text")
            or selected_experience.get("text")
            or belief_assessment.get("experience_summary")
            )
        )
        stance = _normalize_inline_text(belief_assessment.get("stance")).lower() or "reinforce"
        agreement_level = _normalize_inline_text(belief_assessment.get("agreement_level")).lower() or "high"

        if stance == "counter":
            agree_with = _ensure_period(thesis or world_stakes or "There is still a useful signal here")
            pushback = _ensure_period(
                belief_text
                or "The article is directionally interesting, but the real issue sits one layer lower in the work."
            )
        elif stance in {"nuance", "systemize"}:
            agree_with = _ensure_period(thesis or "The article is pointing at something real")
            pushback = _ensure_period(
                belief_text
                or "The missing piece is usually how that signal turns into process, judgment, and follow-through."
            )
        else:
            agree_with = _ensure_period(thesis or world_stakes or "The article is pointing at a real operating signal")
            pushback = _ensure_period(belief_text) if article_kind in {"warning", "trend"} and belief_text else ""

        lived_addition = _ensure_period(experience_text)
        if not lived_addition and belief_assessment.get("experience_anchor"):
            lived_addition = _ensure_period(
                f"I have seen some version of this through {belief_assessment.get('experience_anchor')}."
            )

        what_matters_most = _ensure_period(world_stakes or article_understanding.get("world_context"))
        skepticism = ""
        if article_kind in {"trend", "analysis"} and stance in {"counter", "nuance"}:
            skepticism = _ensure_period("I would watch for whether the framing is cleaner than the real operating environment.")
        elif article_kind == "news":
            skepticism = _ensure_period("The real downstream effect usually shows up in trust, messaging, and the lived experience after the headline.")

        personal_reaction = _ensure_period(
            " ".join(part for part in [agree_with, pushback or "", lived_addition or ""] if _normalize_inline_text(part))
        )

        evidence = []
        if selected_belief.get("title"):
            evidence.append(f"belief={selected_belief['title']}")
        if selected_experience.get("title"):
            evidence.append(f"experience={selected_experience['title']}")
        if belief_assessment.get("belief_used"):
            evidence.append(f"belief_used={belief_assessment['belief_used']}")

        missing_fields = []
        for key, value in {
            "agree_with": agree_with,
            "what_matters_most": what_matters_most,
            "personal_reaction": personal_reaction,
        }.items():
            if not _normalize_inline_text(str(value)):
                missing_fields.append(key)

        return {
            "agree_with": agree_with,
            "pushback": pushback,
            "lived_addition": lived_addition,
            "what_matters_most": what_matters_most,
            "skepticism": skepticism,
            "personal_reaction": personal_reaction,
            "stance": stance,
            "agreement_level": agreement_level,
            "belief_relation": _normalize_inline_text(belief_assessment.get("belief_relation")),
            "audience_posture": _lane_audience_posture(lane_id),
            "role_posture": _lane_role_posture(lane_id),
            "stance_rationale": _ensure_period(
                f"The lane is {lane_id}, the article reads as {article_kind or 'analysis'}, and the current stance is {stance or 'reinforce'}."
            ),
            "evidence": evidence,
            "missing_fields": missing_fields,
        }


social_johnnie_perspective_service = SocialJohnniePerspectiveService()
