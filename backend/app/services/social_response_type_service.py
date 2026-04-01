from __future__ import annotations

from typing import Any


TYPE_IDS = ("agree", "contrarian", "personal_story", "humor")


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _ensure_period(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


class SocialResponseTypeService:
    def select(
        self,
        *,
        signal: dict[str, Any],
        lane_id: str,
        article_understanding: dict[str, Any],
        johnnie_perspective: dict[str, Any],
        reaction_brief: dict[str, Any],
    ) -> dict[str, Any]:
        manual_override = _normalize_inline_text(
            signal.get("response_type")
            or (signal.get("source_metadata") or {}).get("response_type")
            or (signal.get("source_metadata") or {}).get("response_type_override")
        ).lower().replace("-", "_").replace(" ", "_")
        if manual_override not in TYPE_IDS:
            manual_override = ""

        article_kind = _normalize_inline_text(article_understanding.get("article_kind")).lower()
        article_stance = _normalize_inline_text(article_understanding.get("article_stance")).lower()
        world_domains = {str(item).strip().lower() for item in (article_understanding.get("world_domains") or []) if str(item).strip()}
        role_safety = _normalize_inline_text(signal.get("risk_level") or johnnie_perspective.get("role_safety") or "safe").lower()
        lived_addition = _normalize_inline_text(johnnie_perspective.get("lived_addition"))
        pushback = _normalize_inline_text(johnnie_perspective.get("pushback"))
        agree_with = _normalize_inline_text(johnnie_perspective.get("agree_with"))
        stance = _normalize_inline_text(johnnie_perspective.get("stance")).lower()

        blocked_types: dict[str, str] = {}
        eligible_types: list[str] = []

        if agree_with:
            eligible_types.append("agree")
        else:
            blocked_types["agree"] = "agreement anchor missing"

        if pushback:
            eligible_types.append("contrarian")
        else:
            blocked_types["contrarian"] = "pushback rationale missing"

        if lived_addition or lane_id == "personal-story":
            eligible_types.append("personal_story")
        else:
            blocked_types["personal_story"] = "lived evidence missing"

        humor_allowed = role_safety == "safe" and article_kind in {"analysis", "operator_lesson"} and not _normalize_inline_text(
            article_understanding.get("primary_domain")
        ) in {"therapy", "admissions"}
        if humor_allowed:
            eligible_types.append("humor")
        else:
            blocked_types["humor"] = "stakes too high or humor target unclear"

        selected_type = "agree"
        if manual_override:
            selected_type = manual_override if manual_override in eligible_types else "agree"
        elif lane_id == "personal-story":
            selected_type = "personal_story"
        elif lane_id in {"admissions", "current-role", "enrollment-management"} and lived_addition and (article_kind == "news" or {"education", "admissions"} & world_domains):
            selected_type = "personal_story"
        elif lane_id == "program-leadership" and lived_addition and ("leadership" in world_domains or article_kind in {"warning", "news"}):
            selected_type = "personal_story"
        elif lane_id == "ai" and pushback and article_kind in {"analysis", "trend", "operator_lesson"}:
            selected_type = "contrarian"
        elif lane_id == "entrepreneurship" and pushback and article_kind in {"trend", "analysis"}:
            selected_type = "contrarian"
        elif lane_id == "ops-pm" and stance in {"systemize", "counter"} and article_kind in {"warning", "operator_lesson"}:
            selected_type = "contrarian"
        elif lived_addition and reaction_brief.get("content_angle") == "lived_translation" and lane_id in {
            "admissions",
            "current-role",
            "enrollment-management",
            "program-leadership",
            "therapy",
            "referral",
            "personal-story",
        }:
            selected_type = "personal_story"
        elif stance in {"translate", "reinforce"} and agree_with:
            selected_type = "agree"
        elif pushback and article_stance in {"advocate", "speculate"}:
            selected_type = "contrarian"
        else:
            selected_type = "agree"

        if selected_type not in eligible_types:
            for fallback_type in ("personal_story", "contrarian", "agree"):
                if fallback_type in eligible_types:
                    selected_type = fallback_type
                    break
            else:
                selected_type = "agree"

        type_selection_reason = "Agreement is the default because the article and worldview align enough for reinforcement plus extension."
        if selected_type == "contrarian":
            type_selection_reason = "Contrarian won because the lane has real pushback and the article framing needs a sharper redirect."
        elif selected_type == "personal_story":
            type_selection_reason = "Personal story won because the lane has lived evidence that should carry the response instead of abstract commentary."
        elif selected_type == "humor":
            type_selection_reason = "Humor won because the stakes are low enough and the packet still has a safe tension target."

        comment_open_override = ""
        repost_open_override = ""
        bridge_override = ""
        if selected_type == "contrarian":
            comment_open_override = "I would push this a little further."
            repost_open_override = "The framing is close, but I would take it one layer lower."
            bridge_override = _ensure_period(pushback)
        elif selected_type == "personal_story":
            comment_open_override = "I have lived some version of this."
            repost_open_override = "This feels familiar for a reason."
            bridge_override = _ensure_period(lived_addition)
        elif selected_type == "humor":
            comment_open_override = "This would be funny if teams did not keep making the same mistake."
            repost_open_override = "There is a version of this that would be funny if it were not so operationally expensive."

        humor_safety = {
            "humor_allowed": humor_allowed,
            "humor_risk_level": "low" if humor_allowed else "high",
            "humor_reason": "Low-stakes analysis pattern" if humor_allowed else blocked_types.get("humor", ""),
            "humor_target": "the recurring pattern" if humor_allowed else "",
            "humor_boundary": "Do not punch down or trivialize real harm.",
            "humor_failure_risk": "tone break" if humor_allowed else "trust erosion",
        }

        return {
            "response_type": selected_type,
            "type_family": selected_type,
            "type_confidence": 8.4 if selected_type != "humor" else 6.8,
            "type_selection_reason": _ensure_period(type_selection_reason),
            "eligible_types": eligible_types,
            "rejected_types": sorted([type_id for type_id in TYPE_IDS if type_id != selected_type and type_id in blocked_types]),
            "selection_evidence": [
                f"lane={lane_id}",
                f"article_kind={article_kind or 'missing'}",
                f"article_stance={article_stance or 'missing'}",
                f"content_angle={reaction_brief.get('content_angle') or 'missing'}",
                f"has_pushback={bool(pushback)}",
                f"has_lived_addition={bool(lived_addition)}",
            ],
            "manual_override": manual_override,
            "manual_override_source": "signal.metadata" if manual_override else "",
            "blocked_types": blocked_types,
            "comment_open_override": comment_open_override,
            "repost_open_override": repost_open_override,
            "bridge_override": bridge_override,
            "humor_safety": humor_safety,
            "missing_fields": [] if selected_type else ["response_type"],
        }


social_response_type_service = SocialResponseTypeService()
