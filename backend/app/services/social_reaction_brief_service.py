from __future__ import annotations

from typing import Any


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


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


class SocialReactionBriefService:
    def build(
        self,
        *,
        lane_id: str,
        article_understanding: dict[str, Any],
        persona_retrieval: dict[str, Any],
        johnnie_perspective: dict[str, Any],
    ) -> dict[str, Any]:
        article_view = _ensure_period(article_understanding.get("article_view"))
        johnnie_view = _ensure_period(johnnie_perspective.get("personal_reaction"))
        tension = _ensure_period(
            johnnie_perspective.get("pushback")
            or johnnie_perspective.get("what_matters_most")
            or article_understanding.get("world_stakes")
        )
        lived_addition = _normalize_inline_text(johnnie_perspective.get("lived_addition"))
        if lived_addition:
            content_angle = "lived_translation"
        elif _normalize_inline_text(johnnie_perspective.get("pushback")):
            content_angle = "qualified_disagreement"
        elif _normalize_inline_text(johnnie_perspective.get("agree_with")) and _normalize_inline_text(johnnie_perspective.get("pushback")):
            content_angle = "agreement_with_missing_piece"
        else:
            content_angle = "agreement_plus_extension"

        evidence_to_use = []
        for candidate in [
            *(persona_retrieval.get("relevant_claims") or [])[:1],
            *(persona_retrieval.get("relevant_stories") or [])[:1],
            *(persona_retrieval.get("relevant_initiatives") or [])[:1],
            *(persona_retrieval.get("relevant_deltas") or [])[:1],
        ]:
            text = _ensure_period(_strip_packet_metadata(candidate.get("summary_text") or candidate.get("text")))
            if text and text not in evidence_to_use:
                evidence_to_use.append(text)

        do_not_overstate = "Do not overstate confidence, motives, or certainty beyond the article and the retrieved persona evidence."
        if article_understanding.get("article_kind") == "news":
            do_not_overstate = "Do not overstate motives or outcomes beyond what the article and live operating evidence support."

        opening_intent = "lead_with_agreement"
        if content_angle == "qualified_disagreement":
            opening_intent = "lead_with_pushback"
        elif content_angle == "lived_translation":
            opening_intent = "lead_with_lived_anchor"

        return {
            "article_view": article_view,
            "johnnie_view": johnnie_view,
            "tension": tension,
            "content_angle": content_angle,
            "evidence_to_use": evidence_to_use[:3],
            "stance_rationale": _ensure_period(johnnie_perspective.get("stance_rationale")),
            "takeaway_to_preserve": _ensure_period(article_understanding.get("thesis")),
            "technique_guidance": [
                value
                for value in [
                    "specificity-injection",
                    "relatability-anchor" if lived_addition else "",
                    "contrarian-reframe" if content_angle == "qualified_disagreement" else "",
                ]
                if value
            ],
            "audience_posture": _normalize_inline_text(johnnie_perspective.get("audience_posture")),
            "role_posture": _normalize_inline_text(johnnie_perspective.get("role_posture")),
            "do_not_overstate": do_not_overstate,
            "bridge_intent": "use_lived_addition" if lived_addition else "connect_belief_to_world_signal",
            "priority_signal": _ensure_period(johnnie_perspective.get("what_matters_most") or article_understanding.get("world_stakes")),
            "brief_confidence": 8.1,
            "selection_rationale": _ensure_period(
                f"The brief combines the article view, the Johnnie-side reaction, and the lane={lane_id} posture into one drafting packet."
            ),
            "draft_guidance": {
                "opening_intent": opening_intent,
                "main_turn": content_angle,
                "supporting_proof": evidence_to_use[0] if evidence_to_use else "",
                "optional_story": lived_addition,
                "close_intent": "return_to_real_world_stakes",
            },
            "evidence": [
                f"content_angle={content_angle}",
                f"evidence_count={len(evidence_to_use)}",
            ],
            "missing_fields": [
                key
                for key, value in {
                    "article_view": article_view,
                    "johnnie_view": johnnie_view,
                    "tension": tension,
                    "content_angle": content_angle,
                }.items()
                if not _normalize_inline_text(str(value))
            ],
        }


social_reaction_brief_service = SocialReactionBriefService()
