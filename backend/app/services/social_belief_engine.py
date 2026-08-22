from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.services.persona_promotion_service import (
    TARGET_CLAIMS,
    TARGET_INITIATIVES,
    TARGET_STORIES,
    build_committed_persona_overlay,
)
from app.services.persona_bundle_writer import (
    preferred_promotion_title,
    resolve_persona_bundle_read_path,
)

STANCE_IDS = [
    "reinforce",
    "nuance",
    "counter",
    "translate",
    "personal-anchor",
    "systemize",
]

_EXPLICIT_CAREER_EXIT_PATTERNS = (
    re.compile(
        r"\b(?:i am|i['’]m)\s+(?:now\s+)?(?:pivoting|transitioning|moving)\s+"
        r"(?:out of education|into tech(?:nology)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i am|i['’]m)\s+(?:leaving|stepping away from|moving on from|done with|getting out of)\s+"
        r"(?:education|my current role|my job)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:i am|i['’]m)\s+(?:quitting|resigning)\b", re.IGNORECASE),
    re.compile(r"\b(?:today is|this is)\s+my last day\b", re.IGNORECASE),
    re.compile(r"\b(?:i am|i['’]m)\s+(?:ready for|starting)\s+(?:my\s+)?next chapter\b", re.IGNORECASE),
    re.compile(
        r"\b(?:i am|i['’]m)\s+(?:open to|looking for|searching for|seeking|applying for)\s+"
        r"(?:a\s+)?(?:new\s+)?(?:tech(?:nology)?\s+)?(?:role|roles|opportunit(?:y|ies))\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:i am|i['’]m|my profile is)\s+(?:now\s+)?open to work\b", re.IGNORECASE),
)
_CAREER_DIRECTION_REVIEW_PATTERNS = (
    re.compile(r"\bpivot(?:ing)?\s+(?:out of education|into tech(?:nology)?)\b", re.IGNORECASE),
    re.compile(r"\bcareer (?:change|transition)\b", re.IGNORECASE),
    re.compile(r"\bjob search\b", re.IGNORECASE),
    re.compile(r"\bnext chapter\b", re.IGNORECASE),
    re.compile(r"\btechnology opportunities\b", re.IGNORECASE),
)
_EMPLOYER_REFERENCE_PATTERNS = (
    re.compile(r"\b[\w&.'’-]+(?:\s+[\w&.'’-]+){0,3}\s+academy\b", re.IGNORECASE),
    re.compile(r"\bcurrent employer\b", re.IGNORECASE),
    re.compile(r"\bmy employer\b", re.IGNORECASE),
    re.compile(r"\bmy current (?:job|role)\b", re.IGNORECASE),
)
_EMPLOYER_DISENGAGEMENT_TERMS = (
    "does not support",
    "doesn't support",
    "doesn’t support",
    "refuses to",
    "toxic",
    "fed up",
    "underappreciated",
    "holding me back",
    "holds me back",
    "does not care",
    "doesn't care",
    "doesn’t care",
    "trying to escape",
    "cannot wait to leave",
    "can't wait to leave",
    "can’t wait to leave",
)

FALLBACK_PERSONA_TRUTH = {
    "claims": [
        {
            "claim": "the owner combines operational leadership with hands-on technology building.",
            "type": "positioning",
            "evidence": "Public-safe fallback positioning only; replace it with reviewed private persona evidence.",
            "usage_rule": "Use only as broad framing. Never infer an employer, credential, identity trait, metric, or personal story.",
        },
        {
            "claim": "the owner treats AI implementation as an operating practice, not a claim of expertise.",
            "type": "positioning",
            "evidence": "Public-safe fallback positioning only; replace it with reviewed private persona evidence.",
            "usage_rule": "Frame as learning through implementation and require concrete evidence before publication.",
        },
    ],
    "stories": [],
    "initiatives": [
        {
            "title": "AI Clone / Brain System",
            "status": "active",
            "purpose": "build a durable system for restart-safe memory, evidence capture, persona development, and content assistance.",
            "value": "",
            "proof": "",
        },
    ],
}


def normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def ensure_period(text: str) -> str:
    text = normalize_inline_text(text)
    if not text:
        return ""
    return text if text.endswith((".", "!", "?")) else f"{text}."


def clean_sentence(value: str | None) -> str:
    if not value:
        return ""
    text = normalize_inline_text(value)
    if not text:
        return ""
    return text[:-1] if text.endswith(".") else text


def sentence_case(text: str) -> str:
    normalized = normalize_inline_text(text)
    if not normalized:
        return ""
    return normalized[0].upper() + normalized[1:]


def _narrativize_fragment(text: str) -> str:
    cleaned = clean_sentence(text)
    lowered = cleaned.lower()
    for prefix in ("build ", "solve ", "strengthen ", "create ", "turn "):
        if lowered.startswith(prefix):
            return f"The work is to {lowered}"
    return sentence_case(cleaned)


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


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2]
    return text


def _parse_claims_table(text: str) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    lines = _strip_frontmatter(text).splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4 or cells[0].lower() == "claim":
            continue
        claims.append(
            {
                "claim": cells[0],
                "type": cells[1],
                "evidence": cells[2],
                "usage_rule": cells[3],
            }
        )
    return claims


def _parse_markdown_sections(text: str) -> dict[str, list[str]]:
    current_title = ""
    sections: dict[str, list[str]] = {}
    for line in _strip_frontmatter(text).splitlines():
        if line.startswith("## "):
            current_title = line.replace("## ", "", 1).strip()
            sections[current_title] = []
            continue
        if current_title:
            sections[current_title].append(line.rstrip())
    return sections


def _parse_story_bank(text: str) -> list[dict[str, str]]:
    stories: list[dict[str, str]] = []
    sections = _parse_markdown_sections(text)
    for title, lines in sections.items():
        story = {"title": title, "story_type": "", "use_when": "", "core_point": ""}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- Story type:"):
                story["story_type"] = stripped.replace("- Story type:", "", 1).strip()
            elif stripped.startswith("- Use when:"):
                story["use_when"] = stripped.replace("- Use when:", "", 1).strip()
            elif stripped.startswith("- Core point:"):
                story["core_point"] = stripped.replace("- Core point:", "", 1).strip()
        stories.append(story)
    return stories


def _parse_initiatives(text: str) -> list[dict[str, str]]:
    initiatives: list[dict[str, str]] = []
    sections = _parse_markdown_sections(text)
    for title, lines in sections.items():
        if title == "Promoted Evidence":
            continue
        initiative = {"title": title, "status": "", "purpose": "", "value": "", "proof": ""}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- Status:"):
                initiative["status"] = stripped.replace("- Status:", "", 1).strip()
            elif stripped.startswith("- Purpose:"):
                initiative["purpose"] = stripped.replace("- Purpose:", "", 1).strip()
            elif stripped.startswith("- Value to persona:"):
                initiative["value"] = stripped.replace("- Value to persona:", "", 1).strip()
            elif stripped.startswith("- Brand value:"):
                initiative["value"] = stripped.replace("- Brand value:", "", 1).strip()
            elif stripped.startswith("- Public-facing proof:"):
                initiative["proof"] = stripped.replace("- Public-facing proof:", "", 1).strip()
        initiatives.append(initiative)
    return initiatives


def _claim_type_for_promotion(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized == "framework":
        return "philosophical"
    if normalized == "anecdote":
        return "identity"
    if normalized == "stat":
        return "factual"
    if normalized == "phrase_candidate":
        return "positioning"
    return "philosophical"


def _merge_promoted_claims(base_claims: list[dict[str, str]], promoted_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = list(base_claims)
    seen = {normalize_inline_text(entry.get("claim")).lower() for entry in rows if normalize_inline_text(entry.get("claim"))}
    for item in promoted_items:
        claim = ensure_period(str(item.get("content") or ""))
        if not claim:
            continue
        key = normalize_inline_text(claim).lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "claim": claim,
                "type": _claim_type_for_promotion(str(item.get("kind") or "")),
                "evidence": ensure_period(str(item.get("evidence") or item.get("trait") or "")),
                "usage_rule": "Promoted from Brain review and committed to the canonical runtime overlay.",
            }
        )
    return rows


def _merge_promoted_stories(base_stories: list[dict[str, str]], promoted_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = list(base_stories)
    seen = {normalize_inline_text(entry.get("title")).lower() for entry in rows if normalize_inline_text(entry.get("title"))}
    for item in promoted_items:
        core_point = ensure_period(str(item.get("content") or ""))
        if not core_point:
            continue
        title = preferred_promotion_title(item)
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "title": title,
                "story_type": humanize_promotion_kind(str(item.get("kind") or "")),
                "use_when": ensure_period(str(item.get("owner_response_excerpt") or item.get("evidence") or "")),
                "core_point": core_point,
            }
        )
    return rows


def _merge_promoted_initiatives(base_initiatives: list[dict[str, str]], promoted_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = list(base_initiatives)
    seen = {normalize_inline_text(entry.get("title")).lower() for entry in rows if normalize_inline_text(entry.get("title"))}
    for item in promoted_items:
        purpose = ensure_period(str(item.get("content") or ""))
        if not purpose:
            continue
        title = preferred_promotion_title(item)
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "title": title,
                "status": "active",
                "purpose": purpose,
                "value": ensure_period(str(item.get("owner_response_excerpt") or "")),
                "proof": ensure_period(str(item.get("evidence") or "")),
            }
        )
    return rows


def humanize_promotion_kind(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized == "talking_point":
        return "Talking point"
    if normalized == "framework":
        return "Framework"
    if normalized == "anecdote":
        return "Anecdote"
    if normalized == "phrase_candidate":
        return "Reusable phrase"
    if normalized == "stat":
        return "Proof point"
    return "Promoted item"


@lru_cache(maxsize=1)
def load_persona_truth() -> dict[str, list[dict[str, str]]]:
    claims_path = resolve_persona_bundle_read_path("identity/claims.md")
    story_bank_path = resolve_persona_bundle_read_path("history/story_bank.md")
    initiatives_path = resolve_persona_bundle_read_path("history/initiatives.md")
    if not (claims_path.exists() and story_bank_path.exists() and initiatives_path.exists()):
        truth = {
            "claims": list(FALLBACK_PERSONA_TRUTH["claims"]),
            "stories": list(FALLBACK_PERSONA_TRUTH["stories"]),
            "initiatives": list(FALLBACK_PERSONA_TRUTH["initiatives"]),
        }
    else:
        truth = {
            "claims": _parse_claims_table(claims_path.read_text(encoding="utf-8")),
            "stories": _parse_story_bank(story_bank_path.read_text(encoding="utf-8")),
            "initiatives": _parse_initiatives(initiatives_path.read_text(encoding="utf-8")),
        }

    overlay = build_committed_persona_overlay()
    promoted = overlay.get("by_target_file") if isinstance(overlay, dict) else {}
    truth["claims"] = _merge_promoted_claims(truth["claims"], promoted.get(TARGET_CLAIMS, []) if isinstance(promoted, dict) else [])
    truth["stories"] = _merge_promoted_stories(truth["stories"], promoted.get(TARGET_STORIES, []) if isinstance(promoted, dict) else [])
    truth["initiatives"] = _merge_promoted_initiatives(
        truth["initiatives"],
        promoted.get(TARGET_INITIATIVES, []) if isinstance(promoted, dict) else [],
    )
    return truth


def _find_claim(claims: list[dict[str, str]], phrase: str) -> dict[str, str]:
    lowered = phrase.lower()
    for claim in claims:
        if lowered in claim["claim"].lower():
            return claim
    return {"claim": "", "type": "", "evidence": "", "usage_rule": ""}


def _find_claim_by_terms(claims: list[dict[str, str]], terms: tuple[str, ...]) -> dict[str, str]:
    for claim in claims:
        searchable = " ".join(str(claim.get(key) or "") for key in ("claim", "type", "evidence", "usage_rule")).lower()
        if any(term in searchable for term in terms):
            return claim
    return claims[0] if claims else {"claim": "", "type": "", "evidence": "", "usage_rule": ""}


def _find_story(stories: list[dict[str, str]], title: str) -> dict[str, str]:
    lowered = title.lower()
    for story in stories:
        if lowered in story["title"].lower():
            return story
    return {"title": "", "story_type": "", "use_when": "", "core_point": ""}


def _find_initiative(initiatives: list[dict[str, str]], title: str) -> dict[str, str]:
    lowered = title.lower()
    for initiative in initiatives:
        if lowered in initiative["title"].lower():
            return initiative
    return {"title": "", "status": "", "purpose": "", "value": "", "proof": ""}


def _find_story_by_terms(stories: list[dict[str, str]], terms: tuple[str, ...]) -> dict[str, str]:
    for story in stories:
        searchable = " ".join(str(story.get(key) or "") for key in ("title", "story_type", "use_when", "core_point")).lower()
        if any(term in searchable for term in terms):
            return story
    return stories[0] if stories else {"title": "", "story_type": "", "use_when": "", "core_point": ""}


def _find_initiative_by_terms(
    initiatives: list[dict[str, str]],
    terms: tuple[str, ...],
) -> dict[str, str]:
    for initiative in initiatives:
        searchable = " ".join(
            str(initiative.get(key) or "")
            for key in ("title", "purpose", "value", "proof")
        ).lower()
        if any(term in searchable for term in terms):
            return initiative
    return initiatives[0] if initiatives else {"title": "", "status": "", "purpose": "", "value": "", "proof": ""}


def _infer_profile(signal: dict[str, Any]) -> dict[str, bool]:
    text = " ".join(
        [
            normalize_inline_text(signal.get("title")),
            normalize_inline_text(signal.get("summary")),
            normalize_inline_text(signal.get("core_claim")),
            " ".join(signal.get("supporting_claims") or []),
            normalize_inline_text(signal.get("raw_text"))[:2000],
        ]
    ).lower()
    return {
        "is_ai": contains_any(text, [" ai ", "ai ", "agent", "model", "prompt", "automation", "llm", "chatgpt", "claude"]),
        "is_education": contains_any(text, ["education", "higher ed", "student", "admissions", "enrollment", "school", "college"]),
        "is_admissions": contains_any(text, ["admissions", "prospect", "student journey", "enrollment", "follow-up"]),
        "is_ops": contains_any(text, ["workflow", "handoff", "ownership", "process", "project", "execution", "operations", "cadence"]),
        "is_leadership": contains_any(text, ["leadership", "leader", "team", "manager", "culture", "accountability"]),
        "is_referral": contains_any(text, ["referral", "consultant", "partner", "family trust", "handoff", "trusted source"]),
        "is_therapy": contains_any(text, ["therapy", "therapist", "clinical", "mental health", "healing", "nervous system", "attuned"]),
        "is_story": contains_any(text, ["i learned", "my experience", "story", "lesson", "personally", "authenticity", "style"]),
        "is_hype": contains_any(text, ["replace", "obsolete", "everyone", "nobody", "never", "always", "all of", "the future is"]),
        "is_relationship": contains_any(text, ["trust", "relationship", "family", "community", "human connection", "dialogue"]),
    }


def _belief_summary(text: str) -> str:
    cleaned = clean_sentence(text)
    lowered = cleaned.lower()
    if lowered.startswith("owner values "):
        return cleaned[len("the owner values ") :]
    if lowered.startswith("owner is "):
        return cleaned[len("the owner is ") :]
    if lowered.startswith("owner "):
        return cleaned[len("the owner ") :]
    return cleaned


def _initiative_summary(initiative: dict[str, str]) -> str:
    for key in ("value", "purpose", "proof"):
        sentence = ensure_period(_narrativize_fragment(initiative.get(key, "")))
        if sentence:
            return sentence
    return ""


def _choose_belief(signal: dict[str, Any], lane_id: str, profile: dict[str, bool], truth: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    claims = truth["claims"]
    leadership = _find_claim_by_terms(claims, ("leadership", "people", "culture", "team"))
    ai_practice = _find_claim_by_terms(claims, ("ai implementation", "ai practitioner", "technology building", "automation"))
    intersection = _find_claim_by_terms(claims, ("education", "technology", "entrepreneur", "operator"))
    support = _find_claim_by_terms(claims, ("support", "trust", "family", "student", "relationship"))
    operator = _find_claim_by_terms(claims, ("operation", "system", "workflow", "implementation", "migration"))

    if lane_id in {"program-leadership", "ops-pm"} or (profile["is_ops"] and lane_id in {"current-role", "program-leadership", "ops-pm", "entrepreneurship"}):
        claim = leadership if leadership["claim"] else operator
        return {
            "belief_used": claim["claim"],
            "belief_summary": _belief_summary(claim["claim"]) or "people, process, and culture are the real levers",
        }
    if lane_id == "ai" or (profile["is_ai"] and lane_id in {"ai", "ops-pm", "entrepreneurship", "program-leadership"}):
        claim = ai_practice if ai_practice["claim"] else intersection
        return {
            "belief_used": claim["claim"],
            "belief_summary": _belief_summary(claim["claim"]) or "being an AI practitioner matters more than passively watching the hype",
        }
    if lane_id in {"therapy", "referral"} or profile["is_referral"] or profile["is_therapy"] or profile["is_relationship"]:
        claim = support if support["claim"] else leadership
        return {
            "belief_used": claim["claim"],
            "belief_summary": _belief_summary(claim["claim"]) or "support has to work for real people, not just sound good on paper",
        }
    if lane_id == "entrepreneurship":
        claim = intersection if intersection["claim"] else operator
        return {
            "belief_used": claim["claim"],
            "belief_summary": _belief_summary(claim["claim"]) or "the work gets stronger when systems, story, and execution reinforce each other",
        }
    claim = leadership if leadership["claim"] else intersection
    return {
        "belief_used": claim["claim"],
        "belief_summary": _belief_summary(claim["claim"]) or "the work only matters once it changes real outcomes",
    }


def _choose_experience(signal: dict[str, Any], lane_id: str, profile: dict[str, bool], truth: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    stories = truth["stories"]
    initiatives = truth["initiatives"]

    if lane_id in {"admissions", "enrollment-management", "current-role", "referral", "therapy"} or profile["is_admissions"] or profile["is_referral"] or profile["is_therapy"]:
        initiative = _find_initiative_by_terms(
            initiatives,
            ("admission", "enrollment", "education", "family", "referral", "relationship"),
        )
        story = _find_story_by_terms(
            stories,
            ("admission", "enrollment", "education", "family", "referral", "relationship", "community"),
        )
        return {
            "experience_anchor": initiative["title"] or story["title"],
            "experience_summary": _initiative_summary(initiative) or ensure_period(story.get("core_point")),
        }
    if lane_id in {"program-leadership", "ops-pm"} or profile["is_ops"] or profile["is_leadership"]:
        selected = _find_story_by_terms(
            stories,
            ("operation", "process", "workflow", "practice", "team", "leadership", "tool"),
        )
        return {
            "experience_anchor": selected["title"],
            "experience_summary": ensure_period(sentence_case(selected.get("core_point"))),
        }
    if lane_id == "personal-story" or profile["is_story"]:
        selected = _find_story_by_terms(
            stories,
            ("personal", "identity", "authentic", "origin", "lesson", "growth"),
        )
        return {
            "experience_anchor": selected["title"],
            "experience_summary": ensure_period(sentence_case(selected.get("core_point"))),
        }
    if lane_id == "entrepreneurship":
        selected = _find_initiative_by_terms(
            initiatives,
            ("founder", "venture", "business", "product", "entrepreneur", "customer"),
        )
        return {
            "experience_anchor": selected["title"],
            "experience_summary": _initiative_summary(selected),
        }
    if lane_id == "ai" or profile["is_ai"]:
        initiative = _find_initiative(initiatives, "AI Clone / Brain System")
        return {
            "experience_anchor": initiative["title"],
            "experience_summary": _initiative_summary(initiative),
        }
    initiative = _find_initiative(initiatives, "Public Thought Leadership")
    return {
        "experience_anchor": initiative["title"],
        "experience_summary": _initiative_summary(initiative),
    }


def _infer_role_safety(signal: dict[str, Any], lane_id: str, profile: dict[str, bool]) -> str:
    text = " ".join(
        [
            normalize_inline_text(signal.get("title")),
            normalize_inline_text(signal.get("summary")),
            normalize_inline_text(signal.get("core_claim")),
            normalize_inline_text(signal.get("raw_text"))[:1200],
        ]
    ).lower()
    if any(pattern.search(text) for pattern in _EXPLICIT_CAREER_EXIT_PATTERNS):
        return "blocked"
    employer_specific = any(pattern.search(text) for pattern in _EMPLOYER_REFERENCE_PATTERNS)
    if employer_specific and any(term in text for term in _EMPLOYER_DISENGAGEMENT_TERMS):
        return "blocked"
    if any(pattern.search(text) for pattern in _CAREER_DIRECTION_REVIEW_PATTERNS):
        return "review"
    if employer_specific:
        return "review"
    if contains_any(text, ["election", "politics", "president", "government", "lawsuit", "sue", "court"]):
        return "review"
    if lane_id == "therapy" and contains_any(text, ["diagnosis", "medication", "treatment plan", "suicide", "trauma"]):
        return "review"
    if lane_id == "current-role" and contains_any(text, ["layoff", "fired", "termination", "confidential"]):
        return "review"
    if profile["is_hype"] and lane_id in {"current-role", "program-leadership", "referral", "therapy"}:
        return "review"
    return "safe"


def _choose_stance(
    signal: dict[str, Any],
    lane_id: str,
    profile: dict[str, bool],
    role_safety: str,
    article_understanding: dict[str, Any] | None = None,
    persona_retrieval: dict[str, Any] | None = None,
) -> str:
    article_understanding = article_understanding or {}
    persona_retrieval = persona_retrieval or {}
    text = " ".join(
        [
            normalize_inline_text(signal.get("title")),
            normalize_inline_text(signal.get("summary")),
            normalize_inline_text(signal.get("core_claim")),
            " ".join(signal.get("supporting_claims") or []),
        ]
    ).lower()
    article_kind = normalize_inline_text(article_understanding.get("article_kind")).lower()
    article_stance = normalize_inline_text(article_understanding.get("article_stance")).lower()
    world_domains = {str(item).lower() for item in (article_understanding.get("world_domains") or []) if str(item).strip()}
    selected_experience = persona_retrieval.get("selected_experience") or {}
    has_lived_anchor = bool(normalize_inline_text(selected_experience.get("text") or selected_experience.get("title")))

    if lane_id == "personal-story":
        stance = "personal-anchor"
    elif lane_id == "admissions":
        stance = "personal-anchor" if has_lived_anchor and (article_kind == "news" or {"education", "admissions"} & world_domains) else "translate"
    elif lane_id in {"current-role", "enrollment-management", "therapy", "referral"}:
        stance = "personal-anchor" if has_lived_anchor and article_kind == "news" else "translate"
    elif lane_id == "ops-pm":
        if article_kind in {"warning", "operator_lesson"} or "ops" in world_domains:
            stance = "systemize"
        elif article_kind == "news":
            stance = "translate"
        else:
            stance = "nuance"
    elif lane_id == "program-leadership":
        if has_lived_anchor and (article_kind == "news" or "leadership" in world_domains):
            stance = "personal-anchor"
        elif article_stance in {"warn", "advocate"} or profile["is_leadership"]:
            stance = "systemize"
        else:
            stance = "nuance"
    elif lane_id == "entrepreneurship":
        if article_kind == "trend":
            stance = "counter"
        elif article_stance in {"speculate", "advocate"}:
            stance = "nuance"
        else:
            stance = "systemize"
    elif lane_id == "ai":
        if article_stance in {"speculate", "advocate"} or profile["is_hype"]:
            stance = "nuance"
        elif article_kind == "news" and {"education", "admissions"} & world_domains:
            stance = "translate"
        else:
            stance = "counter" if contains_any(text, ["replace", "obsolete", "future is", "everyone", "nobody"]) else "nuance"
    elif lane_id in {"program-leadership", "ops-pm", "entrepreneurship"}:
        stance = "systemize"
    elif lane_id in {"admissions", "current-role", "enrollment-management", "therapy", "referral"}:
        stance = "translate"
    else:
        stance = "reinforce"

    if contains_any(text, ["but", "however", "missing piece", "left out", "not enough"]) and stance not in {"personal-anchor", "systemize"}:
        stance = "nuance"
    if profile["is_hype"] and lane_id in {"ai", "ops-pm", "entrepreneurship"}:
        stance = "counter"
    if role_safety != "safe" and stance == "counter":
        stance = "nuance"
    return stance if stance in STANCE_IDS else "reinforce"


def _agreement_level(stance: str) -> str:
    if stance == "counter":
        return "low"
    if stance in {"nuance", "systemize"}:
        return "medium"
    return "high"


def _belief_relation(stance: str) -> str:
    if stance == "counter":
        return "disagreement"
    if stance == "translate":
        return "translation"
    if stance == "personal-anchor":
        return "experience_match"
    if stance == "nuance":
        return "qualified_agreement"
    if stance == "systemize":
        return "system_translation"
    return "agreement"


def _build_stance_language(stance: str, belief_summary: str, experience_summary: str) -> dict[str, str]:
    belief_line = ""
    if belief_summary:
        cleaned_belief = clean_sentence(belief_summary)
        if cleaned_belief.lower().startswith(("a ", "an ")):
            belief_line = ensure_period(f"For me, it keeps coming back to being {cleaned_belief}")
        else:
            belief_line = ensure_period(f"For me, it keeps coming back to {cleaned_belief}")

    if stance == "reinforce":
        return {
            "stance_comment_open": "This tracks for me.",
            "stance_repost_open": "This is directionally right.",
            "bridge_line": belief_line,
        }
    if stance == "nuance":
        return {
            "stance_comment_open": "I agree with the direction, but I think the missing piece is what happens in practice.",
            "stance_repost_open": "I agree with the core point, but I would push the framing a little further.",
            "bridge_line": belief_line,
        }
    if stance == "counter":
        return {
            "stance_comment_open": "I think the bigger issue sits a little deeper than that.",
            "stance_repost_open": "I would frame this a little differently.",
            "bridge_line": belief_line,
        }
    if stance == "translate":
        return {
            "stance_comment_open": "I keep translating this into the real work on the ground.",
            "stance_repost_open": "This changes once it touches the real work.",
            "bridge_line": ensure_period(experience_summary),
        }
    if stance == "personal-anchor":
        return {
            "stance_comment_open": "I have seen some version of this up close.",
            "stance_repost_open": "This feels familiar for a reason.",
            "bridge_line": ensure_period(experience_summary),
        }
    if stance == "systemize":
        return {
            "stance_comment_open": "The useful move is turning this from an idea into a system.",
            "stance_repost_open": "The idea is only useful once it becomes process.",
            "bridge_line": belief_line,
        }
    return {
        "stance_comment_open": "",
        "stance_repost_open": "",
        "bridge_line": "",
    }


class SocialBeliefEngine:
    """Rule-based first pass for stance and experience anchoring."""

    def assess_signal(
        self,
        signal: dict[str, Any],
        lane_id: str,
        article_understanding: dict[str, Any] | None = None,
        persona_retrieval: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        truth = load_persona_truth()
        profile = _infer_profile(signal)
        belief = _choose_belief(signal, lane_id, profile, truth)
        experience = _choose_experience(signal, lane_id, profile, truth)
        role_safety = _infer_role_safety(signal, lane_id, profile)
        stance = _choose_stance(
            signal,
            lane_id,
            profile,
            role_safety,
            article_understanding=article_understanding,
            persona_retrieval=persona_retrieval,
        )
        language = _build_stance_language(
            stance,
            belief.get("belief_summary", ""),
            experience.get("experience_summary", ""),
        )
        return {
            "stance": stance,
            "agreement_level": _agreement_level(stance),
            "belief_relation": _belief_relation(stance),
            "belief_used": belief.get("belief_used", ""),
            "belief_summary": belief.get("belief_summary", ""),
            "experience_anchor": experience.get("experience_anchor", ""),
            "experience_summary": experience.get("experience_summary", ""),
            "role_safety": role_safety,
            "stance_comment_open": language["stance_comment_open"],
            "stance_repost_open": language["stance_repost_open"],
            "bridge_line": language["bridge_line"],
        }


social_belief_engine = SocialBeliefEngine()
