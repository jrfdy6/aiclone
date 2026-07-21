from __future__ import annotations

import re
from typing import Any

from app.services.persona_bundle_context_service import load_bundle_persona_chunks, load_committed_overlay_chunks


_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "over",
    "under",
    "they",
    "them",
    "their",
    "have",
    "has",
    "had",
    "more",
    "than",
    "what",
    "when",
    "where",
    "which",
    "about",
    "after",
    "before",
    "because",
    "while",
    "would",
    "could",
    "should",
}

_WORLD_TO_PERSONA_TAGS = {
    "ai": {"ai_systems", "operator_workflows", "content_strategy"},
    "education": {"education_admissions", "leadership"},
    "admissions": {"education_admissions", "neurodivergent_advocacy"},
    "leadership": {"leadership", "operator_workflows", "systems_operations"},
    "entrepreneurship": {"content_strategy", "public_proof", "ai_systems"},
    "ops": {"operator_workflows", "systems_operations", "leadership"},
}

_LANE_DOMAIN_PREFERENCES = {
    "ai": {"ai_systems", "operator_workflows", "content_strategy"},
    "ops-pm": {"operator_workflows", "systems_operations", "leadership"},
    "admissions": {"education_admissions", "neurodivergent_advocacy", "leadership"},
    "program-leadership": {"leadership", "operator_workflows", "systems_operations"},
    "entrepreneurship": {"content_strategy", "public_proof", "ai_systems", "fashion_identity"},
    "current-role": {"education_admissions", "leadership", "operator_workflows"},
    "enrollment-management": {"education_admissions", "operator_workflows", "leadership"},
    "therapy": {"neurodivergent_advocacy", "education_admissions", "leadership"},
    "referral": {"education_admissions", "leadership", "content_strategy"},
    "personal-story": {"lived_experience", "identity_core", "fashion_identity"},
}

_LANE_AUDIENCE_PREFERENCES = {
    "ai": {"tech_ai", "entrepreneurs"},
    "ops-pm": {"tech_ai", "leadership"},
    "admissions": {"education_admissions"},
    "program-leadership": {"leadership"},
    "entrepreneurship": {"entrepreneurs", "general"},
    "current-role": {"education_admissions", "leadership"},
    "enrollment-management": {"education_admissions"},
    "therapy": {"education_admissions", "neurodivergent"},
    "referral": {"education_admissions", "general"},
    "personal-story": {"general"},
}

_LANE_KEYWORDS = {
    "ai": {"ai", "agent", "automation", "model", "prompt", "routing", "system", "systems"},
    "ops-pm": {"accountability", "cadence", "delivery", "execution", "handoff", "ownership", "process", "workflow"},
    "admissions": {"admissions", "enrollment", "family", "families", "school", "student", "students", "trust"},
    "program-leadership": {"adoption", "coach", "coaching", "culture", "leadership", "manager", "team", "teams"},
    "entrepreneurship": {"builder", "business", "distribution", "founder", "market", "product", "story", "venture"},
    "current-role": {"family", "market", "referral", "relationship", "school", "students", "trust"},
    "enrollment-management": {"enrollment", "family", "journey", "messaging", "student", "students", "trust"},
    "therapy": {"attuned", "care", "clinical", "healing", "human", "therapy", "trust"},
    "referral": {"family", "handoff", "partner", "referral", "relationship", "trust"},
    "personal-story": {"authenticity", "lesson", "lived", "personally", "story", "style"},
}

_BELIEF_TYPE_PREFERENCES = {
    "ai": ("claim", "initiative", "delta"),
    "ops-pm": ("claim", "initiative", "delta"),
    "admissions": ("claim", "delta", "initiative"),
    "program-leadership": ("claim", "initiative", "delta"),
    "entrepreneurship": ("claim", "initiative", "delta"),
    "current-role": ("claim", "initiative", "delta"),
    "enrollment-management": ("claim", "initiative", "delta"),
    "therapy": ("claim", "story", "delta"),
    "referral": ("claim", "story", "delta"),
    "personal-story": ("story", "claim", "delta"),
}

_EXPERIENCE_TYPE_PREFERENCES = {
    "ai": ("initiative", "story", "delta"),
    "ops-pm": ("story", "initiative", "delta"),
    "admissions": ("initiative", "story", "delta"),
    "program-leadership": ("story", "initiative", "delta"),
    "entrepreneurship": ("initiative", "story", "delta"),
    "current-role": ("initiative", "story", "delta"),
    "enrollment-management": ("initiative", "story", "delta"),
    "therapy": ("story", "initiative", "delta"),
    "referral": ("story", "initiative", "delta"),
    "personal-story": ("story", "initiative", "delta"),
}


def _normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _ensure_period(value: str | None) -> str:
    normalized = _normalize_inline_text(value)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


def _keyword_terms(text: str, *, limit: int = 18) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower()):
        if token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        results.append(token)
        if len(results) >= limit:
            break
    return results


def _candidate_type(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    memory_role = str(metadata.get("memory_role") or "")
    bundle_path = str(metadata.get("bundle_path") or "")
    source_kind = str(item.get("source_kind") or metadata.get("source_kind") or "")
    if source_kind == "committed_overlay":
        return "delta"
    if memory_role == "story" or bundle_path.endswith("story_bank.md"):
        return "story"
    if bundle_path.endswith("initiatives.md") or bundle_path.endswith("wins.md") or memory_role == "proof":
        return "initiative"
    return "claim"


def _title_for_candidate(item: dict[str, Any]) -> str:
    chunk = _normalize_inline_text(item.get("chunk"))
    if not chunk:
        return ""
    first = chunk.split(".")[0].strip()
    if len(first) <= 90:
        return first
    return chunk[:90].strip()


def _candidate_summary_text(text: str, candidate_type: str, title: str) -> str:
    normalized = _normalize_inline_text(text)
    if not normalized:
        return ""
    compact = re.split(r"(?:\bValue:|\bProof:|\bUse when:|\bStatus:|\bPurpose:|\bStory type:)", normalized, maxsplit=1, flags=re.IGNORECASE)[0]
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
    cleaned: list[str] = []
    title_key = _normalize_inline_text(title).lower()
    for sentence in sentences:
        normalized_sentence = _normalize_inline_text(sentence)
        if not normalized_sentence:
            continue
        if title_key and normalized_sentence.lower() == title_key:
            continue
        cleaned.append(normalized_sentence)
    if candidate_type in {"initiative", "story"} and cleaned:
        return _ensure_period(" ".join(cleaned[:2]))
    return _ensure_period(compact)


def _lane_query_context(lane_id: str) -> str:
    prompts = {
        "ai": "ai systems operator judgment workflow design evaluation",
        "ops-pm": "workflow handoff accountability clarity delivery execution ownership",
        "admissions": "admissions enrollment trust family student journey school context",
        "program-leadership": "leadership team adoption coaching standards accountability",
        "entrepreneurship": "builder founder market distribution product ownership narrative",
        "current-role": "live operator trust relationship referrals families outcomes",
        "enrollment-management": "enrollment journey follow-up messaging conversion trust",
        "therapy": "attunement care trust human support neurodivergent context",
        "referral": "referral handoff trust partner relationship credibility",
        "personal-story": "lived lesson authenticity identity story personal proof",
    }
    return prompts.get(lane_id, "")


def _normalized_set(values: list[Any] | None) -> set[str]:
    return {str(value).strip().lower() for value in values or [] if str(value).strip()}


def _keyword_bonus(text: str, keywords: set[str]) -> float:
    lowered = text.lower()
    matches = 0
    for keyword in keywords:
        if keyword in lowered:
            matches += 1
    return min(matches * 0.45, 2.2)


def _external_reference_terms(candidates: list[dict[str, Any]]) -> set[str]:
    text = " ".join(
        _normalize_inline_text(candidate.get("text") or candidate.get("summary_text"))
        for candidate in candidates[:3]
    ).strip()
    return set(_keyword_terms(text, limit=24))


def _external_reference_domains(candidates: list[dict[str, Any]]) -> set[str]:
    tags: set[str] = set()
    for candidate in candidates[:4]:
        tags.update(_normalized_set(candidate.get("domain_tags")))
    return tags


def _belief_claim_type_bonus(
    claim_type: str,
    *,
    lane_id: str,
    article_understanding: dict[str, Any],
    text: str,
) -> float:
    normalized = _normalize_inline_text(claim_type).lower()
    if not normalized:
        return 0.0
    article_kind = _normalize_inline_text(article_understanding.get("article_kind")).lower()
    article_stance = _normalize_inline_text(article_understanding.get("article_stance")).lower()
    world_domains = {str(item).strip().lower() for item in (article_understanding.get("world_domains") or []) if str(item).strip()}
    lowered = text.lower()

    if normalized == "operational":
        if lane_id in {"ops-pm", "program-leadership", "ai", "current-role", "enrollment-management"}:
            return 1.9
        if any(domain in world_domains for domain in {"ai", "leadership", "education", "admissions"}):
            return 1.2
        return 0.7
    if normalized == "contrarian":
        if lane_id in {"ai", "entrepreneurship"} or article_kind in {"trend", "analysis"} or article_stance in {"advocate", "speculate", "warn"}:
            return 1.7
        return 0.6
    if normalized == "mission":
        if lane_id in {"admissions", "current-role", "enrollment-management", "therapy", "referral"}:
            return 1.9
        if any(domain in world_domains for domain in {"education", "admissions"}):
            return 1.6
        return 0.6
    if normalized == "philosophical":
        return 1.2
    if normalized == "identity":
        if lane_id in {"therapy", "referral", "personal-story", "admissions"} or any(token in lowered for token in ("neurodivergent", "students", "families", "trust")):
            return 0.9
        return -0.2
    if normalized == "positioning":
        if lane_id == "entrepreneurship":
            return 0.4
        if any(token in lowered for token in ("ai practitioner", "operator")) and lane_id in {"ai", "ops-pm"}:
            return 0.3
        return -0.9
    if normalized == "factual":
        if lane_id in {"ops-pm", "program-leadership", "current-role"} and any(token in lowered for token in ("salesforce", "migration", "revenue")):
            return 0.7
        return -0.8
    return 0.0


def _article_text(article_understanding: dict[str, Any]) -> str:
    return " ".join(
        [
            _normalize_inline_text(article_understanding.get("thesis")),
            _normalize_inline_text(article_understanding.get("world_context")),
            _normalize_inline_text(article_understanding.get("world_stakes")),
            " ".join(str(item) for item in (article_understanding.get("world_domains") or [])),
            " ".join(str(item) for item in (article_understanding.get("audience_impacted") or [])),
        ]
    ).lower()


def _seed_window_bonus(
    *,
    title: str,
    text: str,
    lane_id: str,
    candidate_type: str,
    memory_role: str,
    article_understanding: dict[str, Any],
) -> float:
    lowered = f"{title} {text}".lower()
    article_text = _article_text(article_understanding)
    score = 0.0

    if lane_id == "entrepreneurship" and any(
        token in article_text for token in ("distribution", "product", "market", "moat", "customer", "trust", "behavior")
    ):
        if any(
            token in lowered
            for token in (
                "easy outfit",
                "valuable enough to change behavior",
                "change user behavior",
                "metadata and validation",
                "product reality",
            )
        ):
            score += 4.2
        if any(
            token in lowered
            for token in (
                "cheap models",
                "ai constraint breakthrough",
                "function is not the same thing as value",
            )
        ):
            score += 2.3
        if "ai clone / brain system" in lowered and candidate_type == "initiative":
            score -= 1.5

    if lane_id == "ai" and any(
        token in article_text for token in ("judgment", "evaluation", "constraint", "schema", "reliability", "competence")
    ):
        if any(
            token in lowered
            for token in (
                "cheap models",
                "ai constraint breakthrough",
                "instruction-layer",
                "schema",
                "validation",
                "if you cannot rely on the output",
            )
        ):
            score += 3.4
        if "ai clone / brain system" in lowered and memory_role == "proof":
            score -= 1.2

    return score


def _generic_belief_penalty(
    text: str,
    *,
    lane_id: str,
    claim_type: str,
    article_understanding: dict[str, Any],
) -> float:
    lowered = text.lower()
    world_domains = {str(item).strip().lower() for item in (article_understanding.get("world_domains") or []) if str(item).strip()}
    penalty = 0.0

    if "intersection of education, ai systems, entrepreneurship, and style" in lowered and lane_id != "entrepreneurship":
        penalty += 2.6
    if "director of admissions" in lowered and lane_id not in {"admissions", "current-role", "enrollment-management"}:
        penalty += 1.6
    if any(token in lowered for token in ("34m in annual revenue", "salesforce migration", "$1m salesforce migration")) and lane_id not in {"ops-pm", "program-leadership", "current-role"}:
        penalty += 1.4
    if "neurodivergent professional" in lowered and lane_id not in {"therapy", "referral", "admissions", "personal-story", "current-role"}:
        penalty += 0.8
    if _normalize_inline_text(claim_type).lower() == "positioning" and world_domains and not any(
        token in lowered for token in ("trust", "education", "adoption", "workflow", "ai", "leadership", "students", "families")
    ):
        penalty += 1.0
    return penalty


def _external_alignment_bonus(
    item: dict[str, Any],
    *,
    external_reference_candidates: list[dict[str, Any]],
) -> float:
    if not external_reference_candidates:
        return 0.0
    candidate_tags = _normalized_set(item.get("domain_tags"))
    reference_domains = _external_reference_domains(external_reference_candidates)
    reference_terms = _external_reference_terms(external_reference_candidates)
    text = _normalize_inline_text(item.get("text"))
    score = len(candidate_tags & reference_domains) * 0.7
    score += _keyword_bonus(text, reference_terms) * 0.6
    return min(score, 2.4)


def _belief_alignment_bonus(text: str, belief_text: str | None) -> float:
    normalized_belief = _normalize_inline_text(belief_text)
    if not normalized_belief:
        return 0.0
    belief_terms = set(_keyword_terms(normalized_belief, limit=16))
    if not belief_terms:
        return 0.0
    return min(_keyword_bonus(text, belief_terms) * 0.8, 2.0)


def _experience_article_fit_bonus(
    text: str,
    *,
    lane_id: str,
    article_understanding: dict[str, Any],
) -> float:
    lowered = text.lower()
    article_text = " ".join(
        [
            _normalize_inline_text(article_understanding.get("thesis")),
            _normalize_inline_text(article_understanding.get("world_context")),
            _normalize_inline_text(article_understanding.get("world_stakes")),
            " ".join(str(item) for item in (article_understanding.get("world_domains") or [])),
            " ".join(str(item) for item in (article_understanding.get("audience_impacted") or [])),
        ]
    ).lower()

    score = 0.0
    if any(token in article_text for token in ("dashboard", "reporting", "visibility", "referral", "outreach", "meetings", "priorities")):
        if any(token in lowered for token in ("dashboard", "visibility", "reporting", "fusion academy", "market development", "coffee and convo", "referral")):
            score += 3.0
    if any(token in article_text for token in ("family", "families", "student", "students", "education", "admissions", "trust", "school")):
        if any(token in lowered for token in ("fusion academy", "coffee and convo", "market development", "family", "families", "student", "students", "trust")):
            score += 3.0
    if any(token in article_text for token in ("team", "leadership", "manager", "coaching", "participation", "culture", "adoption")):
        if any(token in lowered for token in ("best practices", "team participation", "warm then sharp", "leadership", "visibility")):
            score += 2.8
    if any(token in article_text for token in ("product", "distribution", "moat", "style", "outfit", "validation", "metadata", "consumer")):
        if any(
            token in lowered
            for token in (
                "easy outfit",
                "metadata",
                "validation",
                "style",
                "outfit",
                "cheap models",
                "easy outfit build and adoption lesson",
                "valuable enough to change behavior",
            )
        ):
            score += 3.1
    if any(token in article_text for token in ("ai", "agent", "model", "prompt", "workflow", "retrieval", "json", "automation", "system")):
        if any(
            token in lowered
            for token in (
                "ai clone",
                "cheap models",
                "validation",
                "retrieval",
                "json",
                "metadata",
                "operating system",
                "ai constraint breakthrough",
                "if you cannot rely on the output",
            )
        ):
            score += 2.8
    if any(token in article_text for token in ("family", "families", "student", "students", "education", "trust", "school", "faculty")):
        if any(token in lowered for token in ("admissions family clarity shift", "education changed", "translation")):
            score += 2.9
    if any(token in article_text for token in ("team", "repeat", "process", "handoff", "workflow", "execution", "leadership", "change")):
        if any(token in lowered for token in ("partial functionality hides failure", "quiet inefficiency cleanup", "speaking truth in the room")):
            score += 2.7

    if lane_id == "entrepreneurship" and any(token in article_text for token in ("distribution", "product", "market", "moat", "customer", "startup")):
        if any(
            token in lowered
            for token in (
                "easy outfit",
                "cheap models",
                "market development",
                "product",
                "easy outfit build and adoption lesson",
                "valuable enough to change behavior",
            )
        ):
            score += 1.4
    if lane_id == "ai" and any(token in lowered for token in ("ai clone", "cheap models", "validation", "retrieval", "json")):
        score += 1.2
    if lane_id == "ai" and any(token in lowered for token in ("ai constraint breakthrough", "if you cannot rely on the output", "fail to constrain")):
        score += 1.8
    if lane_id in {"admissions", "current-role", "enrollment-management"} and any(token in lowered for token in ("fusion academy", "coffee and convo", "market development")):
        score += 1.4
    return min(score, 4.4)


def _generic_experience_penalty(
    text: str,
    *,
    lane_id: str,
    article_understanding: dict[str, Any],
) -> float:
    lowered = text.lower()
    article_text = " ".join(
        [
            _normalize_inline_text(article_understanding.get("thesis")),
            _normalize_inline_text(article_understanding.get("world_context")),
            _normalize_inline_text(article_understanding.get("world_stakes")),
            " ".join(str(item) for item in (article_understanding.get("world_domains") or [])),
        ]
    ).lower()
    penalty = 0.0

    if "ai clone / brain system" in lowered and lane_id != "ai" and not any(
        token in article_text for token in ("ai", "agent", "workflow", "prompt", "model", "system", "automation", "retrieval")
    ):
        penalty += 2.1
    if "coffee and convo" in lowered and lane_id not in {"admissions", "current-role", "enrollment-management", "referral", "therapy"}:
        penalty += 1.4
    if "best practices initiative" in lowered and not any(
        token in article_text for token in ("team", "coaching", "adoption", "leadership", "performance", "culture")
    ):
        penalty += 1.2
    if "fusion academy market development" in lowered and lane_id not in {"admissions", "current-role", "enrollment-management", "referral"}:
        penalty += 1.0
    return penalty


def _type_bonus(candidate_type: str, preferences: tuple[str, ...]) -> float:
    if candidate_type not in preferences:
        return -1.2
    index = preferences.index(candidate_type)
    return 2.8 - (index * 1.1)


def _world_tags(article_understanding: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for domain in article_understanding.get("world_domains") or []:
        tags.update(_WORLD_TO_PERSONA_TAGS.get(str(domain).lower(), set()))
    return tags


def _selection_score(
    item: dict[str, Any],
    *,
    lane_id: str,
    article_understanding: dict[str, Any],
    target_kind: str,
    external_reference_candidates: list[dict[str, Any]] | None = None,
    selected_belief_text: str | None = None,
) -> float:
    lane_domain_preferences = _LANE_DOMAIN_PREFERENCES.get(lane_id, set())
    lane_audience_preferences = _LANE_AUDIENCE_PREFERENCES.get(lane_id, {"general"})
    lane_keywords = _LANE_KEYWORDS.get(lane_id, set())
    candidate_tags = _normalized_set(item.get("domain_tags"))
    candidate_audiences = _normalized_set(item.get("audience_tags"))
    candidate_type = str(item.get("candidate_type") or "")
    claim_type = str(item.get("claim_type") or "")
    memory_role = str(item.get("memory_role") or "")
    proof_strength = str(item.get("proof_strength") or "")
    text = _normalize_inline_text(item.get("text"))
    title = _normalize_inline_text(item.get("title"))
    lowered = f"{title} {text}".lower()

    score = float(item.get("score") or 0.0)
    score += len(candidate_tags & lane_domain_preferences) * 2.4
    score += len(candidate_tags & _world_tags(article_understanding)) * 1.3
    score += len(candidate_audiences & lane_audience_preferences) * 1.1
    score += _keyword_bonus(text, lane_keywords)

    is_ai_heavy = any(token in lowered for token in (" ai ", "prompt", "agent", "llm", "automation"))
    if lane_id != "ai" and target_kind == "belief" and is_ai_heavy:
        score -= 2.2

    if target_kind == "belief":
        article_text = _article_text(article_understanding)
        score += _belief_claim_type_bonus(
            claim_type,
            lane_id=lane_id,
            article_understanding=article_understanding,
            text=lowered,
        )
        score += _external_alignment_bonus(
            item,
            external_reference_candidates=external_reference_candidates or [],
        )
        score -= _generic_belief_penalty(
            lowered,
            lane_id=lane_id,
            claim_type=claim_type,
            article_understanding=article_understanding,
        )
        if lane_id == "ops-pm" and any(token in lowered for token in ("visibility changes behavior", "people, process, and culture", "workflow", "handoff", "process")):
            score += 2.7
        if lane_id == "admissions" and any(token in lowered for token in ("equity", "student", "family", "adoption", "access")):
            score += 2.0
        if lane_id in {"admissions", "current-role", "enrollment-management"} and any(
            token in article_text for token in ("change", "adoption", "announce", "repeat the process", "team", "teams", "leaders")
        ) and any(
            token in lowered for token in ("people adopt what makes their life easier", "education changed", "trust", "families", "students")
        ):
            score += 2.3
        if lane_id == "program-leadership" and any(token in lowered for token in ("visibility changes behavior", "people adopt", "people, process, and culture", "leadership")):
            score += 2.1
        if lane_id in {"admissions", "current-role", "enrollment-management", "therapy", "referral"} and any(
            token in lowered for token in ("education changed", "education access", "families", "students", "trust", "honesty", "curiosity")
        ):
            score += 1.9
        if lane_id == "ai" and any(
            token in lowered for token in ("workflow is unclear", "prompting alone", "coherent", "reject inputs", "ai maturity", "ai practitioner")
        ):
            score += 2.0
        if lane_id == "ai" and any(
            token in lowered
            for token in (
                "speed of leverage",
                "changing what competence looks like",
                "if you cannot rely on the output",
                "fail to constrain",
                "automate friction, not judgment",
            )
        ):
            score += 2.2
        if lane_id in {"ops-pm", "program-leadership"} and any(
            token in lowered
            for token in (
                "partial functionality hides the real failure",
                "partial functionality can hide real system failure",
                "friction is often a signal",
            )
        ):
            score += 2.3
        if lane_id in {"admissions", "current-role", "enrollment-management"} and any(
            token in lowered
            for token in (
                "admissions is not just enrollment. it is translation",
                "education changed johnnie's life",
            )
        ):
            score += 2.3
        if lane_id == "entrepreneurship" and any(
            token in article_text for token in ("change", "adoption", "announce", "repeat the process", "team", "teams", "leaders", "process")
        ) and any(
            token in lowered for token in ("people adopt what makes their life easier", "systems become useful by being coherent", "narrative without artifacts")
        ):
            score += 2.6
        if lane_id == "entrepreneurship" and any(
            token in article_text for token in ("change", "adoption", "announce", "repeat the process", "team", "teams", "leaders", "process")
        ) and "systems become useful by being coherent" in lowered:
            score += 1.6
        if lane_id == "entrepreneurship" and any(token in lowered for token in ("narrative", "artifact", "distribution", "builder", "market", "product", "story", "prompting alone", "agent orchestration")):
            score += 1.9
        if lane_id == "entrepreneurship" and any(
            token in lowered
            for token in (
                "function is not the same as value",
                "valuable enough to change behavior",
                "speed of leverage",
                "changing what competence looks like",
            )
        ):
            score += 2.1
        if lane_id == "entrepreneurship" and "workflow is unclear" in lowered:
            score -= 1.5
        if lane_id == "admissions" and "workflow is unclear" in lowered and not any(token in lowered for token in ("student", "family", "equity", "access")):
            score -= 1.0
        if lane_id in {"admissions", "entrepreneurship"} and "workflow is unclear" in lowered and any(
            token in article_text for token in ("change", "adoption", "announce", "repeat the process", "leaders", "teams")
        ) and not any(token in article_text for token in ("ai", "agent", "automation", "model")):
            score -= 2.0
    else:
        score += _experience_article_fit_bonus(
            lowered,
            lane_id=lane_id,
            article_understanding=article_understanding,
        )
        score += _belief_alignment_bonus(
            lowered,
            selected_belief_text,
        )
        score -= _generic_experience_penalty(
            lowered,
            lane_id=lane_id,
            article_understanding=article_understanding,
        )
        if lane_id == "ai" and any(token in lowered for token in ("ai clone", "grounded content generation", "brain system")):
            score += 4.2
        if lane_id in {"admissions", "current-role", "enrollment-management"} and any(token in lowered for token in ("market development", "coffee and convo", "family", "student", "trust")):
            score += 2.4
        if lane_id == "program-leadership" and any(token in lowered for token in ("best practices", "coffee and convo", "visibility", "team")):
            score += 5.0
        if lane_id == "ops-pm" and any(token in lowered for token in ("dashboard", "zoom logging", "best practices", "handoff", "workflow")):
            score += 1.8
        if lane_id == "entrepreneurship" and any(token in lowered for token in ("ai clone", "easy outfit", "acorn", "thought leadership", "market", "builder", "style")):
            score += 2.0

    if target_kind == "belief":
        score += _type_bonus(candidate_type, _BELIEF_TYPE_PREFERENCES.get(lane_id, ("claim", "initiative", "delta")))
        if memory_role == "core":
            score += 1.4
        elif memory_role == "proof":
            score += 0.6
        if candidate_type == "initiative":
            score -= 3.1
        if candidate_type == "story":
            score -= 3.6
    else:
        score += _type_bonus(candidate_type, _EXPERIENCE_TYPE_PREFERENCES.get(lane_id, ("initiative", "story", "delta")))
        if memory_role in {"story", "proof"}:
            score += 1.2
        if memory_role == "story":
            score += 0.8
        if item.get("artifact_backed"):
            score += 0.7
        if proof_strength == "strong":
            score += 0.5
        elif proof_strength == "medium":
            score += 0.2
        if candidate_type == "claim":
            score -= 2.8
    return round(score, 2)


def _rerank_for_target(
    candidates: list[dict[str, Any]],
    *,
    lane_id: str,
    article_understanding: dict[str, Any],
    target_kind: str,
    external_reference_candidates: list[dict[str, Any]] | None = None,
    selected_belief_text: str | None = None,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for item in candidates:
        reference_alignment_score = _external_alignment_bonus(
            item,
            external_reference_candidates=external_reference_candidates or [],
        ) if target_kind == "belief" else 0.0
        score = _selection_score(
            item,
            lane_id=lane_id,
            article_understanding=article_understanding,
            target_kind=target_kind,
            external_reference_candidates=external_reference_candidates,
            selected_belief_text=selected_belief_text,
        )
        decorated.append(
            {
                **item,
                "selection_fit_score": round(score, 1),
                "selection_target": target_kind,
                "reference_alignment_score": round(reference_alignment_score, 1),
            }
        )
    decorated.sort(key=lambda candidate: (float(candidate.get("selection_fit_score") or 0.0), float(candidate.get("score") or 0.0)), reverse=True)
    return decorated


def _first_candidate(candidates: list[dict[str, Any]], allowed_types: tuple[str, ...], *, excluded_title: str = "") -> dict[str, Any]:
    normalized_excluded = _normalize_inline_text(excluded_title).lower()
    for candidate in candidates:
        candidate_type = str(candidate.get("candidate_type") or "")
        title = _normalize_inline_text(candidate.get("title")).lower()
        if candidate_type not in allowed_types:
            continue
        if normalized_excluded and title and title == normalized_excluded:
            continue
        return candidate
    return {}


def _first_candidate_matching_text(
    candidates: list[dict[str, Any]],
    tokens: tuple[str, ...],
    *,
    excluded_title: str = "",
) -> dict[str, Any]:
    normalized_excluded = _normalize_inline_text(excluded_title).lower()
    for candidate in candidates:
        title = _normalize_inline_text(candidate.get("title")).lower()
        text = _normalize_inline_text(candidate.get("text")).lower()
        if normalized_excluded and title and title == normalized_excluded:
            continue
        if any(token in f"{title} {text}" for token in tokens):
            return candidate
    return {}


class SocialPersonaRetrievalService:
    def retrieve(self, signal: dict[str, Any], lane_id: str, article_understanding: dict[str, Any]) -> dict[str, Any]:
        overlay_chunks = load_committed_overlay_chunks()
        bundle_chunks = load_bundle_persona_chunks()
        items = overlay_chunks + bundle_chunks

        query_text = " ".join(
            [
                _normalize_inline_text(article_understanding.get("thesis")),
                _normalize_inline_text(article_understanding.get("world_context")),
                _normalize_inline_text(article_understanding.get("world_stakes")),
                " ".join(str(item) for item in (article_understanding.get("world_domains") or [])),
                " ".join(str(item) for item in (article_understanding.get("audience_impacted") or [])),
                _normalize_inline_text(signal.get("raw_text"))[:1200],
                _lane_query_context(lane_id),
                _normalize_inline_text(lane_id),
            ]
        ).strip()
        query_terms = _keyword_terms(query_text)
        lane_terms = set(_keyword_terms(lane_id.replace("-", " ")))
        domain_terms = {str(item).lower() for item in (article_understanding.get("world_domains") or []) if str(item).strip()}

        ranked: list[dict[str, Any]] = []
        for item in items:
            chunk = _normalize_inline_text(item.get("chunk"))
            if not chunk:
                continue
            lowered = chunk.lower()
            metadata = item.get("metadata") or {}
            candidate_type = _candidate_type(item)
            title = _title_for_candidate(item)
            overlap = sum(1 for term in query_terms if term in lowered)
            domain_tags = {str(tag).lower() for tag in (metadata.get("domain_tags") or []) if str(tag).strip()}
            audience_tags = {str(tag).lower() for tag in (metadata.get("audience_tags") or []) if str(tag).strip()}
            domain_overlap = len(domain_terms & domain_tags)
            lane_overlap = len(lane_terms & domain_tags)
            memory_role = str(metadata.get("memory_role") or "")
            proof_strength = str(metadata.get("proof_strength") or "").lower()
            source_kind = str(item.get("source_kind") or metadata.get("source_kind") or "")
            score = overlap * 1.4
            score += domain_overlap * 2.2
            score += lane_overlap * 1.3
            score += _seed_window_bonus(
                title=title,
                text=chunk,
                lane_id=lane_id,
                candidate_type=candidate_type,
                memory_role=memory_role,
                article_understanding=article_understanding,
            )
            if memory_role == "core":
                score += 1.2
            elif memory_role == "proof":
                score += 1.0
            elif memory_role == "story":
                score += 0.8
            if proof_strength == "strong":
                score += 1.0
            elif proof_strength == "medium":
                score += 0.5
            if source_kind == "committed_overlay":
                score += 0.8
            if score <= 0:
                continue
            ranked.append(
                {
                    "title": title,
                    "text": _ensure_period(chunk),
                    "summary_text": _candidate_summary_text(chunk, candidate_type, title),
                    "score": round(score, 1),
                    "candidate_type": candidate_type,
                    "source_kind": source_kind or "canonical_bundle",
                    "memory_role": memory_role or "ambient",
                    "bundle_path": str(metadata.get("bundle_path") or ""),
                    "domain_tags": list(metadata.get("domain_tags") or []),
                    "audience_tags": list(metadata.get("audience_tags") or []),
                    "artifact_backed": bool(metadata.get("artifact_backed")),
                    "proof_strength": proof_strength or "weak",
                    "claim_type": str(metadata.get("claim_type") or ""),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        external_reference_candidates = [
            item for item in ranked if item["source_kind"] == "external_reference"
        ][:6]
        selection_window = [
            item for item in ranked if item["source_kind"] != "external_reference"
        ][:24]
        experience_window = [
            item for item in ranked if item["source_kind"] != "external_reference"
        ][:40]
        top_candidates = selection_window[:10]
        claims = [item for item in selection_window if item["candidate_type"] == "claim"][:5]
        stories = [item for item in experience_window if item["candidate_type"] == "story"][:5]
        initiatives = [item for item in experience_window if item["candidate_type"] == "initiative"][:5]
        deltas = [item for item in selection_window if item["candidate_type"] == "delta"][:5]

        belief_candidates = _rerank_for_target(
            selection_window,
            lane_id=lane_id,
            article_understanding=article_understanding,
            target_kind="belief",
            external_reference_candidates=external_reference_candidates,
        )
        selected_belief = _first_candidate(
            belief_candidates,
            ("claim", "delta"),
        ) or _first_candidate(
            belief_candidates,
            _BELIEF_TYPE_PREFERENCES.get(lane_id, ("claim", "initiative", "delta")),
        ) or (top_candidates[0] if top_candidates else {})
        selected_belief_text = _normalize_inline_text(
            (selected_belief or {}).get("text")
            or (selected_belief or {}).get("summary_text")
        )
        experience_candidates = _rerank_for_target(
            experience_window,
            lane_id=lane_id,
            article_understanding=article_understanding,
            target_kind="experience",
            selected_belief_text=selected_belief_text,
        )
        selected_experience = _first_candidate(
            experience_candidates,
            _EXPERIENCE_TYPE_PREFERENCES.get(lane_id, ("initiative", "story", "delta")),
            excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
        ) or _first_candidate(
            experience_candidates,
            ("initiative", "story", "delta", "claim"),
        )
        selected_experience_score = float((selected_experience or {}).get("selection_fit_score") or 0.0)
        best_story_experience = _first_candidate(
            experience_candidates,
            ("story",),
            excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
        )
        best_story_score = float((best_story_experience or {}).get("selection_fit_score") or 0.0)
        if lane_id in {"ops-pm", "program-leadership", "therapy", "referral", "personal-story"} and best_story_experience and best_story_score >= 18.0:
            if not selected_experience or (selected_experience_score - best_story_score) <= 12.0:
                selected_experience = best_story_experience
                selected_experience_score = best_story_score
        if lane_id in {"ai", "entrepreneurship", "current-role", "admissions", "enrollment-management"} and best_story_experience and best_story_score >= 17.0:
            if not selected_experience or (selected_experience_score - best_story_score) <= 3.5:
                selected_experience = best_story_experience
                selected_experience_score = best_story_score

        if lane_id == "ai":
            ai_native_experience = _first_candidate_matching_text(
                experience_candidates,
                ("ai clone", "grounded content generation", "brain system"),
                excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
            )
            ai_native_score = float((ai_native_experience or {}).get("selection_fit_score") or 0.0)
            if ai_native_experience and (not selected_experience or (selected_experience_score - ai_native_score) <= 3.5):
                selected_experience = ai_native_experience
                selected_experience_score = ai_native_score
            ai_story_experience = _first_candidate_matching_text(
                experience_candidates,
                ("ai constraint breakthrough", "cheap models", "easy outfit build and adoption lesson", "if you cannot rely on the output"),
                excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
            )
            ai_story_score = float((ai_story_experience or {}).get("selection_fit_score") or 0.0)
            if ai_story_experience and (not selected_experience or (selected_experience_score - ai_story_score) <= 4.0):
                selected_experience = ai_story_experience
                selected_experience_score = ai_story_score

        if lane_id in {"admissions", "current-role", "enrollment-management"}:
            relational_experience = _first_candidate_matching_text(
                experience_candidates,
                ("market development", "coffee and convo", "family", "student", "trust"),
                excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
            )
            relational_score = float((relational_experience or {}).get("selection_fit_score") or 0.0)
            if relational_experience and (not selected_experience or (selected_experience_score - relational_score) <= 4.0):
                selected_experience = relational_experience
        if lane_id == "entrepreneurship":
            article_text = _article_text(article_understanding)
            founder_story_gap = 4.0
            if any(token in article_text for token in ("distribution", "product", "market", "moat", "customer", "trust", "behavior")):
                founder_story_gap = 8.0
            founder_story = _first_candidate_matching_text(
                experience_candidates,
                (
                    "easy outfit build and adoption lesson",
                    "easy outfit",
                    "valuable enough to change behavior",
                    "change user behavior",
                    "metadata and validation",
                    "cheap models",
                ),
                excluded_title=_normalize_inline_text((selected_belief or {}).get("title")),
            )
            founder_story_score = float((founder_story or {}).get("selection_fit_score") or 0.0)
            if founder_story and (not selected_experience or (selected_experience_score - founder_story_score) <= founder_story_gap):
                selected_experience = founder_story
                selected_experience_score = founder_story_score
        unique_types = {item["candidate_type"] for item in top_candidates}
        retrieval_diversity_score = round(min(10.0, 4.0 + len(unique_types) * 1.4), 1)

        evidence = [
            f"query_terms={', '.join(query_terms[:8]) or 'missing'}",
            f"top_types={', '.join(sorted(unique_types)) or 'missing'}",
            f"overlay_hits={sum(1 for item in top_candidates if item['source_kind'] == 'committed_overlay')}",
            f"external_reference_hits={len(external_reference_candidates)}",
            f"selected_belief={_normalize_inline_text((selected_belief or {}).get('title')) or 'missing'}",
            f"selected_experience={_normalize_inline_text((selected_experience or {}).get('title')) or 'missing'}",
        ]
        missing_fields = []
        if not claims:
            missing_fields.append("relevant_claims")
        if not stories:
            missing_fields.append("relevant_stories")
        if not initiatives:
            missing_fields.append("relevant_initiatives")

        return {
            "retrieval_query": query_text,
            "query_terms": query_terms,
            "top_candidates": top_candidates,
            "relevant_claims": claims,
            "relevant_stories": stories,
            "relevant_initiatives": initiatives,
            "relevant_deltas": deltas,
            "selected_belief": selected_belief,
            "selected_experience": selected_experience,
            "belief_candidates": belief_candidates[:6],
            "experience_candidates": experience_candidates[:6],
            "external_reference_candidates": external_reference_candidates,
            "retrieval_diversity_score": retrieval_diversity_score,
            "selection_rationale": _ensure_period(
                "The retrieval packet ranks persona evidence by article overlap first, then reranks selection targets by lane worldview, audience fit, and evidence type."
            ),
            "evidence": evidence,
            "missing_fields": missing_fields,
        }


social_persona_retrieval_service = SocialPersonaRetrievalService()
