"""
AI-Powered Content Generation Routes

Generates content using:
1. User's persona and style from knowledge base
2. High-performing content examples
3. Topic intelligence data
4. PACER/Chris Do frameworks
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import json
import re

from app.services.embedders import embed_text
from app.services.content_generation_context_service import (
    ContentGenerationContext,
    build_content_generation_context,
)
from app.services.persona_bundle_context_service import retrieve_bundle_persona_chunks
from app.services.retrieval import retrieve_similar, retrieve_weighted

router = APIRouter()

CORE_BUNDLE_PATHS = {
    "identity/claims.md",
    "identity/philosophy.md",
    "identity/decision_principles.md",
    "identity/VOICE_PATTERNS.md",
    "identity/audience_communication.md",
    "prompts/content_guardrails.md",
    "prompts/content_pillars.md",
    "prompts/channel_playbooks.md",
    "prompts/outreach_playbook.md",
}
SUPPORT_BUNDLE_PATHS = {
    "identity/bio_facts.md",
    "history/story_bank.md",
    "history/wins.md",
    "history/timeline.md",
    "history/initiatives.md",
    "history/resume.md",
}
LEGACY_PERSONA_SOURCES = (
    "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
    "JOHNNIE_FIELDS_PERSONA.md",
)
LEGACY_EXAMPLE_TAGS = ["LINKEDIN_EXAMPLES"]
PROMPT_SECTION_ORDER = [
    "CORE CANON",
    "SUPPORTING CANON",
    "LEGACY SUPPORT",
    "RETRIEVAL SUPPORT",
]
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "with",
}
AUDIENCE_FOCUS_TERMS = {
    "tech_ai": {"ai", "agent", "agents", "automation", "operator", "operators", "workflow", "workflows", "prompt", "prompting", "system", "systems", "shipping", "builder", "builders"},
    "leadership": {"leadership", "leaders", "manager", "managers", "team", "teams", "coaching", "culture", "clarity", "decision", "decisions"},
    "education_admissions": {"education", "admissions", "enrollment", "families", "students", "referral", "school", "schools", "trust"},
    "fashion": {"fashion", "style", "closet", "wardrobe", "outfit", "confidence"},
    "neurodivergent": {"neurodivergent", "learning", "students", "families", "support", "fit"},
    "entrepreneurs": {"build", "building", "founder", "founders", "product", "shipping", "market", "customers"},
}
TOPIC_FOCUS_BOOSTS = {
    "workflow clarity": {"workflow", "clarity", "process", "processes", "handoff", "handoffs", "alignment", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
    "agent orchestration": {"agent", "agents", "orchestration", "workflow", "workflows", "automation", "prompting", "handoff", "handoffs", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
}
STRICT_AUDIENCE_ANCHOR_TERMS = {
    "tech_ai": {"ai", "agent", "agents", "automation", "brain", "briefs", "handoff", "handoffs", "operator", "ops", "orchestration", "planner", "prompt", "prompting", "routing", "system", "systems", "workflow", "workflows"},
}
PROOF_KEYWORDS = {
    "built",
    "clarity",
    "evidence",
    "handoff",
    "handoffs",
    "improved",
    "launched",
    "metric",
    "metrics",
    "migration",
    "operator",
    "ops",
    "prompt",
    "prompting",
    "proof",
    "revenue",
    "salesforce",
    "shipped",
    "signal",
    "system",
    "systems",
    "workflow",
}
FRAMING_MODE_GUIDANCE = {
    "contrarian_reframe": "Push against a lazy default belief, then replace it with a sharper operating truth.",
    "agree_and_extend": "Start from agreement, then extend it with a stronger lesson or pattern.",
    "drama_tension": "Use real tension, stakes, or friction from the work without inventing facts.",
    "story_with_payoff": "Use a real eligible story, then land on a clear payoff.",
    "operator_lesson": "Lead through workflow, handoff, prompt, system, or operating-pattern clarity.",
    "recognition": "Center recognition or gratitude when real people or teams are part of the proof.",
    "warning": "Name the failure mode or hidden cost directly and explain why it matters.",
    "reframe": "Take a familiar idea and make the audience see it through a different lens.",
}
GENERIC_SENTENCE_OPENERS = {
    "Are",
    "Big",
    "Can",
    "Clear",
    "Clarity",
    "Good",
    "Here",
    "How",
    "I",
    "If",
    "It",
    "Listen",
    "Look",
    "Most",
    "Read",
    "Real",
    "Teams",
    "That",
    "The",
    "This",
    "Without",
    "Workflow",
    "Write",
    "Yall",
    "You",
    "Your",
}
UNSUPPORTED_EVIDENCE_PLACEHOLDERS = {
    "article",
    "case study",
    "company",
    "course",
    "podcast",
    "school",
    "talk",
    "university",
    "video",
    "webinar",
}


class ContentGenerationRequest(BaseModel):
    user_id: str = Field(..., description="User ID for knowledge base lookup")
    topic: str = Field(..., description="Content topic")
    context: Optional[str] = Field(None, description="Additional context")
    content_type: str = Field("linkedin_post", description="Type: linkedin_post, cold_email, linkedin_dm, instagram_post")
    category: str = Field("value", description="Chris Do category: value, sales, personal")
    pacer_elements: List[str] = Field(default_factory=list, description="PACER elements to include: Problem, Amplify, Credibility, Educate, Request")
    tone: str = Field("expert_direct", description="Tone: expert_direct, inspiring, conversational")
    audience: str = Field("general", description="Target audience: general, education_admissions, tech_ai, fashion, leadership, neurodivergent, entrepreneurs")


class ContentGenerationResponse(BaseModel):
    success: bool
    options: List[str]
    persona_context: Optional[str] = None
    examples_used: List[str] = []


def _normalized_chunk_key(item: Dict[str, Any]) -> str:
    return " ".join(str(item.get("chunk") or "").split()).strip().lower()


def _item_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _source_name(item: Dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    return str(metadata.get("file_name") or metadata.get("source") or "")


def _bundle_path(item: Dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    return str(metadata.get("bundle_path") or item.get("source_file_id") or "")


def _with_prompt_section(item: Dict[str, Any], section: str) -> Dict[str, Any]:
    hydrated = dict(item)
    metadata = dict(_item_metadata(item))
    metadata["prompt_section"] = section
    hydrated["metadata"] = metadata
    return hydrated


def _append_unique(
    destination: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    *,
    limit: int,
    seen: set[str],
    section: str,
) -> None:
    for item in candidates:
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        destination.append(_with_prompt_section(item, section))
        if len(destination) >= limit:
            return


def _collect_prompt_visible_chunks(
    *,
    persona_chunks: List[Dict[str, Any]],
    topic_anchor_chunks: List[Dict[str, Any]],
    eligible_story_chunks: List[Dict[str, Any]],
    proof_anchor_chunks: List[Dict[str, Any]],
    topic: str,
    audience: str,
) -> List[Dict[str, Any]]:
    visible: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(items: List[Dict[str, Any]], *, limit: int | None = None) -> None:
        for item in items:
            key = _normalized_chunk_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            visible.append(item)
            if limit is not None and len(visible) >= limit:
                return

    core_chunks = [
        item
        for item in persona_chunks
        if str(_item_metadata(item).get("prompt_section") or "") == "CORE CANON"
    ]
    add(core_chunks, limit=4)
    add(topic_anchor_chunks)
    add(proof_anchor_chunks)
    add(eligible_story_chunks)

    if len(visible) < 5:
        focus_terms = _focus_terms(topic, audience)
        supporting_chunks = [
            item
            for item in persona_chunks
            if str(_item_metadata(item).get("prompt_section") or "") == "SUPPORTING CANON"
            and _passes_audience_anchor_gate(_split_use_when_text(str(item.get("chunk") or ""))[0], audience)
            and _chunk_focus_score(_split_use_when_text(str(item.get("chunk") or ""))[0], focus_terms, topic) > 0
        ]
        add(supporting_chunks, limit=6)

    return visible


def curate_persona_prompt_chunks(
    *,
    bundle_chunks: List[Dict[str, Any]],
    legacy_support_chunks: List[Dict[str, Any]],
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 9,
) -> List[Dict[str, Any]]:
    core_chunks = [item for item in bundle_chunks if _bundle_path(item) in CORE_BUNDLE_PATHS]
    support_chunks = [item for item in bundle_chunks if _bundle_path(item) in SUPPORT_BUNDLE_PATHS]
    bundle_other_chunks = [
        item
        for item in bundle_chunks
        if _bundle_path(item) not in CORE_BUNDLE_PATHS and _bundle_path(item) not in SUPPORT_BUNDLE_PATHS
    ]
    legacy_chunks = [
        item
        for item in legacy_support_chunks
        if _source_name(item) in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]
    retrieval_support_chunks = [
        item
        for item in retrieved_chunks
        if _source_name(item) not in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    _append_unique(curated, core_chunks, limit=min(top_k, 4), seen=seen, section="CORE CANON")
    _append_unique(curated, support_chunks, limit=min(top_k, 7), seen=seen, section="SUPPORTING CANON")
    _append_unique(curated, legacy_chunks, limit=min(top_k, 9), seen=seen, section="LEGACY SUPPORT")
    _append_unique(curated, bundle_other_chunks, limit=min(top_k, 9), seen=seen, section="SUPPORTING CANON")
    _append_unique(curated, retrieval_support_chunks, limit=top_k, seen=seen, section="RETRIEVAL SUPPORT")
    return curated[:top_k]


def retrieve_legacy_support_chunks(
    *,
    user_id: str,
    query_embedding: List[float],
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    for source_name in LEGACY_PERSONA_SOURCES:
        items = retrieve_similar(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
            source_filter=source_name,
        )
        if items:
            return items
    return []


def retrieve_curated_example_chunks(
    *,
    user_id: str,
    query_embedding: List[float],
    content_type: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    if content_type == "linkedin_post":
        for source_name in LEGACY_PERSONA_SOURCES:
            items = retrieve_similar(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=top_k,
                tag_filter=LEGACY_EXAMPLE_TAGS,
                source_filter=source_name,
            )
            if items:
                return items
    return retrieve_similar(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )


def filter_example_chunks_by_topic(
    example_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, Dict[str, Any]]] = []
    for item in example_chunks:
        primary_text, _ = _split_use_when_text(str(item.get("chunk") or ""))
        score = _chunk_focus_score(primary_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        ranked.append((score, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(ranked, key=lambda entry: entry[0], reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def summarize_persona_context(persona_chunks: List[Dict[str, Any]], topic: str) -> Optional[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    if normalized_topic:
        for item in persona_chunks:
            chunk = str(item.get("chunk") or "")
            if normalized_topic in chunk.lower():
                return chunk[:200]
    for preferred_section in PROMPT_SECTION_ORDER:
        for item in persona_chunks:
            if _item_metadata(item).get("prompt_section") == preferred_section:
                return str(item.get("chunk") or "")[:200]
    return None


def _focus_terms(topic: str, audience: str) -> set[str]:
    normalized_topic = " ".join((topic or "").lower().split())
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_topic)
        if len(token) > 2 and token not in STOPWORDS
    }
    for phrase, boosts in TOPIC_FOCUS_BOOSTS.items():
        if phrase in normalized_topic:
            tokens.update(boosts)
    tokens.update(AUDIENCE_FOCUS_TERMS.get(audience, set()))
    return tokens


def _chunk_focus_score(chunk: str, focus_terms: set[str], topic: str) -> int:
    normalized_chunk = " ".join((chunk or "").lower().split())
    normalized_topic = " ".join((topic or "").lower().split())
    if not normalized_chunk:
        return 0
    score = sum(1 for term in focus_terms if term and term in normalized_chunk)
    if normalized_topic and normalized_topic in normalized_chunk:
        score += 4
    return score


def _split_use_when_text(chunk: str) -> tuple[str, str]:
    normalized_chunk = " ".join((chunk or "").split())
    parts = normalized_chunk.split(" Use when:", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return normalized_chunk, ""


def _render_anchor_chunk(item: Dict[str, Any], *, include_use_when: bool = False) -> str:
    chunk = str(item.get("chunk") or "").strip()
    primary_text, use_when_text = _split_use_when_text(chunk)
    if include_use_when and use_when_text:
        return f"{primary_text} Use when: {use_when_text}"
    return primary_text


def _passes_audience_anchor_gate(chunk: str, audience: str) -> bool:
    required_terms = STRICT_AUDIENCE_ANCHOR_TERMS.get(audience)
    if not required_terms:
        return True
    normalized_chunk = " ".join((chunk or "").lower().split())
    return any(term in normalized_chunk for term in required_terms)


def select_topic_anchor_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, int, Dict[str, Any]]] = []
    section_priority = {
        "CORE CANON": 4,
        "SUPPORTING CANON": 3,
        "LEGACY SUPPORT": 2,
        "RETRIEVAL SUPPORT": 1,
    }
    for item in persona_chunks:
        chunk = str(item.get("chunk") or "")
        primary_text, use_when_text = _split_use_when_text(chunk)
        focus_score = (_chunk_focus_score(primary_text, focus_terms, topic) * 3) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if focus_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        section = str(_item_metadata(item).get("prompt_section") or "RETRIEVAL SUPPORT")
        priority = section_priority.get(section, 0)
        ranked.append((focus_score, priority, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, item in sorted(ranked, key=lambda entry: (entry[0], entry[1]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def select_eligible_story_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    story_candidates: List[tuple[int, Dict[str, Any]]] = []
    for item in persona_chunks:
        tag = str(item.get("persona_tag") or "")
        section = str(_item_metadata(item).get("prompt_section") or "")
        if section == "CORE CANON":
            continue
        if tag not in {"EXPERIENCES", "VENTURES"}:
            continue
        primary_text, use_when_text = _split_use_when_text(str(item.get("chunk") or ""))
        score = (_chunk_focus_score(primary_text, focus_terms, topic) * 2) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        story_candidates.append((score, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(story_candidates, key=lambda entry: entry[0], reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def _proof_signal_score(chunk: str) -> int:
    normalized_chunk = " ".join((chunk or "").lower().split())
    if not normalized_chunk:
        return 0
    score = 0
    if "evidence:" in normalized_chunk:
        score += 4
    if "proof:" in normalized_chunk or "public-facing proof:" in normalized_chunk:
        score += 4
    if re.search(r"\b\d[\d.,x%$m]*\b", normalized_chunk):
        score += 3
    score += sum(1 for term in PROOF_KEYWORDS if term in normalized_chunk)
    return score


def select_proof_anchor_chunks(
    persona_chunks: List[Dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: List[tuple[int, int, int, Dict[str, Any]]] = []
    section_priority = {
        "CORE CANON": 4,
        "SUPPORTING CANON": 3,
        "LEGACY SUPPORT": 2,
        "RETRIEVAL SUPPORT": 1,
    }
    minimum_focus = 2 if audience == "tech_ai" else 1
    for item in persona_chunks:
        chunk = str(item.get("chunk") or "")
        primary_text, _ = _split_use_when_text(chunk)
        focus_score = _chunk_focus_score(primary_text, focus_terms, topic)
        proof_score = _proof_signal_score(primary_text)
        if focus_score <= 0 and proof_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        if proof_score > 0 and focus_score < minimum_focus:
            continue
        section = str(_item_metadata(item).get("prompt_section") or "RETRIEVAL SUPPORT")
        priority = section_priority.get(section, 0)
        ranked.append((focus_score * 4 + proof_score, proof_score, priority, item))

    curated: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, _, item in sorted(ranked, key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def build_topic_focus_guidance(
    *,
    topic: str,
    audience: str,
    eligible_story_chunks: List[Dict[str, Any]],
) -> str:
    lines = [
        f'TOPIC DISCIPLINE: Stay tightly on "{topic}".',
        "Lead with the core claim or operating lesson, not a broad personal recap.",
    ]

    if audience == "tech_ai":
        lines.extend(
            [
                "Stay in the operator / AI systems lane: workflow clarity, prompting, automation, handoffs, and shipped execution.",
                "Do not reach for family, fashion, school, or community stories unless one appears in the eligible story anchors below.",
            ]
        )
    elif audience == "leadership":
        lines.extend(
            [
                "Stay in the leadership lane: clarity, coaching, team temperature, stakeholder influence, and operating cadence.",
                "Do not default to product-building or fashion stories unless the eligible story anchors make that link explicit.",
            ]
        )

    if eligible_story_chunks:
        lines.append("A personal story is optional. If you use one, it must come from the eligible story anchors below and connect to the topic in one sentence.")
    else:
        lines.append("No directly relevant story anchor was found. Do not force an anecdote. Use principle + proof instead.")
    return "\n".join(f"- {line}" for line in lines)


def build_proof_guidance(proof_anchor_chunks: List[Dict[str, Any]]) -> str:
    if proof_anchor_chunks:
        return "\n".join(
            [
                "- Each option must include at least one concrete proof anchor, named system, metric, or evidence phrase from the PROOF ANCHORS section below.",
                "- Prefer proof over abstraction: systems, migrations, shipped surfaces, prompting patterns, handoffs, metrics, or role-grounded evidence.",
                "- Do not make up numbers. If the proof anchor is qualitative, keep it qualitative but concrete.",
                "- Do not translate one metric into another. Keep the original subject and meaning of every proof anchor intact.",
            ]
        )
    return "\n".join(
        [
            "- No strong proof anchor was found. Stay concrete about process, role, and workflow mechanics.",
            "- Do not invent metrics or accomplishments.",
        ]
    )


def get_openai_client():
    """Get OpenAI client for content generation."""
    import openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return openai.OpenAI(api_key=api_key)


def build_content_prompt(
    topic: str,
    context: str,
    content_type: str,
    category: str,
    pacer_elements: List[str],
    tone: str,
    persona_chunks: List[Dict],
    example_chunks: List[Dict],
    audience: str = "general",
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
) -> str:
    """Build the prompt for content generation."""
    topic_anchor_chunks = topic_anchor_chunks or select_topic_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    eligible_story_chunks = eligible_story_chunks or select_eligible_story_chunks(persona_chunks, topic=topic, audience=audience, limit=3)
    proof_anchor_chunks = proof_anchor_chunks or select_proof_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    topic_anchor_text = "\n".join(f"- {_render_anchor_chunk(item)}" for item in topic_anchor_chunks) or "- No topic anchors available."
    eligible_story_text = (
        "\n".join(f"- {_render_anchor_chunk(item, include_use_when=True)}" for item in eligible_story_chunks)
        if eligible_story_chunks
        else "- No directly relevant story anchor found. Do not force one."
    )
    proof_anchor_text = (
        "\n".join(f"- {_render_anchor_chunk(item)}" for item in proof_anchor_chunks)
        if proof_anchor_chunks
        else "- No strong proof anchor found. Stay concrete about process and role."
    )
    topic_focus_guidance = build_topic_focus_guidance(
        topic=topic,
        audience=audience,
        eligible_story_chunks=eligible_story_chunks,
    )
    proof_guidance = build_proof_guidance(proof_anchor_chunks)
    grounding_mode = grounding_mode or ("proof_ready" if proof_anchor_chunks else "principle_only")
    grounding_reason = grounding_reason or (
        "Concrete proof anchors are available, so the post can lead with real evidence."
        if proof_anchor_chunks
        else "No strong proof anchor was found, so the post should stay principle-led."
    )
    approved_framing_modes = framing_modes or ["operator_lesson", "contrarian_reframe", "reframe"]
    framing_modes_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in approved_framing_modes
    )
    primary_claims = primary_claims or []
    proof_packets = proof_packets or []
    story_beats = story_beats or []
    disallowed_moves = disallowed_moves or []
    primary_claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- No primary claims were pre-composed. Stay tightly inside the topic anchors."
    proof_packets_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No approved proof packets. Use principle only."
    story_beats_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No story beat approved for this request."
    disallowed_moves_text = "\n".join(f"- {move}" for move in disallowed_moves) or "- No extra banned moves."
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {term}" for term in approved_reference_terms) or "- No approved named references."
    
    visible_persona_chunks = _collect_prompt_visible_chunks(
        persona_chunks=persona_chunks,
        topic_anchor_chunks=topic_anchor_chunks,
        eligible_story_chunks=eligible_story_chunks,
        proof_anchor_chunks=proof_anchor_chunks,
        topic=topic,
        audience=audience,
    )

    # Group visible chunks by prompt layer so canon stays ahead of support, without flooding the prompt with off-topic history.
    persona_sections: Dict[str, List[str]] = {}
    for c in visible_persona_chunks:
        tag = str(c.get("persona_tag", "GENERAL")).replace("_", " ").title()
        section = str(_item_metadata(c).get("prompt_section") or "RETRIEVAL SUPPORT")
        chunk_text = _render_anchor_chunk(c)
        if not chunk_text:
            continue
        persona_sections.setdefault(section, []).append(f"- [{tag}] {chunk_text}")

    persona_parts = []
    for section in PROMPT_SECTION_ORDER:
        chunks = persona_sections.get(section)
        if chunks:
            persona_parts.append(f"### {section}\n" + "\n".join(chunks))
    persona_text = "\n\n".join(persona_parts)
    
    # Extract example content
    examples_text = "\n---\n".join([c.get("chunk", "")[:500] for c in example_chunks[:3]])
    
    # Anti-AI writing filter
    anti_ai_rules = """
## CRITICAL WRITING RULES - FOLLOW STRICTLY

NEVER use generic LLM patterns such as:
- "In today's world", "In today's fast-paced", "In the realm of"
- "Furthermore", "Moreover", "Additionally", "However"
- "Let's dive into", "Let's explore", "Let's unpack"
- "This is important because", "It's worth noting"
- "At the end of the day", "When it comes to"
- "I'm excited to", "I'm thrilled to", "I'm passionate about"
- "Game-changer", "Leverage", "Synergy", "Paradigm shift"
- Corporate buzzwords and emotionally flat summaries
- Obvious transitional phrases

Emulate human writing style:
- Direct, clear, and confident
- Short sentences when emphasizing key ideas
- Precise and concrete language
- No filler transitions
- Vary sentence length to feel human
- Lead with insight, not recap
- Avoid AI cadence

TONE EXAMPLES TO MATCH:
1. "Leadership isn't about authority. It's about clarity, direction, and decisions made when the room goes quiet."
2. "Most operational problems aren't mysteries. They're patterns. When you track them honestly, solutions become obvious."
3. "I used to dominate conversations. Now I make it my business to be the last person to talk. The result? Better relationships, heavier adoption of my ideas."
4. "Thanksgiving has a funny way of reminding us what actually shapes people. For me, it's always been education and style — two worlds everyone thinks are separate, but they're not."
5. "Style isn't vanity — it's a form of self-belief."
6. "Your outfit tells a story long before you say a word."

CRITICAL STYLE RULES:
- Open with a HOOK that creates tension or reframes a common belief
- Use short, punchy sentences for emphasis
- Break lines for rhythm and visual impact
- Be specific and concrete, not abstract
- End with a question that invites engagement
- NO soft openings like "Thanksgiving isn't just about..." or "For me, it's..."
- NO generic statements like "It's a chance to reflect"
- Lead with INSIGHT, not setup

BEFORE vs AFTER EXAMPLES:

❌ BAD (generic): "Education isn't just about books. It's about identity."
✅ GOOD (specific): "Education isn't only about books; it's identity."

❌ BAD (vague): "I watched my dad teach me that every piece of knowledge is a tool."
✅ GOOD (concrete): "My dad worked as a mechanic, and he taught me that knowledge is a tool."

❌ BAD (abstract): "Knowledge empowers them. It's not just grades; it's confidence, community, and style."
✅ GOOD (specific): "Real learning gives them confidence. It shapes how they show up. It influences how they express themselves."

❌ BAD (wordy): "When I see students wearing their stories, I see the result of real education—an expression of who they are and who they aspire to be."
✅ GOOD (tight): "When students wear their stories—through their choices, their style, their presence—I see the result of education that reaches beyond the classroom."

❌ BAD (generic question): "How do we celebrate not just the learning, but the journeys that shape us?"
✅ GOOD (specific question): "How do we celebrate not only what students learn, but who they become through the process?"

KEY DIFFERENCES:
- Remove "just" and use "only" or cut entirely
- Replace abstract nouns with concrete actions
- Tighten every sentence by 10-20%
- Make questions more specific
- Every word must earn its place

MORE BEFORE/AFTER TIGHTENING:

❌ "I remember those vibrant tablecloths, the way they matched her bold personality."
✅ "Those vibrant tablecloths matched her bold personality."

❌ "It's cozy, yes, but it's also a representation of hard work and resilience."
✅ "Cozy, yes, but also a symbol of hard work and resilience."

❌ "That blend of function and sentiment is what I try to channel in my choices today."
✅ "That blend of function and sentiment is what I aim for today."

❌ "Fashion isn't just about trends; it's about roots and aspirations."
✅ "Fashion isn't just trends; it's roots and aspirations."

❌ "I learned that style is about more than fabric; it's about confidence and clarity."
✅ "I learned that style is more than fabric. It's confidence and clarity."

❌ "This Thanksgiving, let's think beyond the plate. How do we ensure our personal style reflects the stories we want to tell?"
✅ "This Thanksgiving, think beyond the plate: How can your personal style reflect the story you want to tell?"

TIGHTENING RULES:
- Cut "I remember" / "I recall" - just describe directly
- "is about" → cut or use em-dash
- "let's" → direct "you" address
- "How do we" → "How can your"
- Remove unnecessary "that" and "the way"
- "try to" → "aim for" or cut
- Semicolons → periods or colons for clarity
"""

    # Channel-specific examples - USE REAL POSTS FROM PERSONA, not fabricated stories
    channel_examples = {
        "linkedin_post": """
Use the knowledge-base examples below as the primary post references.

Match their rhythm:
- strong hook up top
- short line breaks
- specific names, systems, and stakes
- recognition where it is earned
- a clean close, not a generic recap

VOICE RULES (MANDATORY - VARY these patterns across options):
- CRITICAL: Each option must use a DIFFERENT opener. Never start all 3 with "Yall"
- Casual openers (rotate): "Yall" (1 in 5 max), "Look,", "Real talk:", "Here's the thing...", "Can I be honest?", "Let me tell y'all something."
- Conversational pivots: "Tell you what tho", "Here's what I learned:", "Am I talking to somebody?"
- Engagement hooks (vary): "Say it with me: 🗣️" (rare), "Write that down.", "Read that again.", "Listen to me."
- Recognition: "Big shout-out to...", "Huge thank you to..."
- Punchy closers: "Makes no sense. Period.", "It's real.", "That's the money ball right there."
- Emphasis: "Are you hearing what I'm telling you?", "I'm just being real.", "For real, for real."
- Short, punchy sentences for emphasis
- **Bold** key insight statements
- Tag people with their title/org when that is actually part of the story
- Hashtags grouped at end (5-7 max)
- Use legacy examples for rhythm and specificity, never for copy-paste
""",
        "cold_email": """
EMAIL STYLE RULES (based on this person's voice):

Structure:
- Personal connection in opening
- Short paragraphs, easy to skim
- Reflective tone, not salesy
- One clear CTA
- "Warmly" or similar human closing

Voice markers to include:
- Direct, confident language
- Reference real experiences (Fusion Academy, Coffee & Convo events, neurodivergent students)
- NO corporate jargon
- Authentic, not overly polished

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "linkedin_dm": """
LINKEDIN DM STYLE (based on this person's voice):

Structure:
- Opens casual ("Hey —" or similar)
- Short, under 10 seconds to read
- Personal detail from REAL experiences
- Ends with genuine question
- NO pitch, NO ask for a call

Voice markers:
- Casual but professional
- Can use "Yall" if appropriate
- Reference real work (Fusion Academy, neurodivergent students, Coffee & Convo)
- Feels like a message from a friend

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "instagram_post": """
INSTAGRAM STYLE (based on this person's voice):

Structure:
- Opens with short punchy line
- **Bold** key statements
- Stacked short phrases for rhythm
- Emoji sparingly at end (🙏, 💜, ✨)
- Ends with question or reflection

Voice markers:
- Casual, warm, authentic
- "Yall" acceptable
- Reference real experiences
- Personal but not oversharing

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
"""
    }
    
    channel_example = channel_examples.get(content_type, "")
    
    # Audience-specific guidance with examples
    audience_guidance = {
        "general": """TARGET AUDIENCE: General professional audience
- Write for smart professionals across industries
- Use clear, accessible language
- Focus on universal themes: growth, reflection, connection
- Avoid niche jargon""",

        "education_admissions": """TARGET AUDIENCE: Education & Admissions professionals
- Speak to enrollment managers, admissions counselors, program directors
- Reference: yield optimization, pipeline management, student recruitment, family conversations
- Focus on BUSINESS of education, not teaching/classroom
- You manage teams, hit enrollment targets, work with families

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Education is changing rapidly in today's world."
✅ "Enrollment season taught me something about pipeline management that applies everywhere."

❌ "Students need more support than ever."
✅ "When a family walks into your office unsure if their kid belongs, your first 60 seconds matter more than your brochure."

SPECIFIC STORIES TO DRAW FROM:
- Managing $34M portfolios at 2U
- Launching Fordham MSW, Howard MSW programs
- Salesforce migrations across 3 instances
- Fusion Academy: 1:1 school for neurodivergent students
- The "temperature gauge" approach to team management""",

        "tech_ai": """TARGET AUDIENCE: Tech & AI professionals
- Speak to builders, founders, operators who use AI as a tool
- Reference: shipping, automation, building in public, efficiency
- Focus on practical applications, not hype
- You build things, you ship, you iterate

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "AI is revolutionizing the way we work."
✅ "I shipped an AI clone of myself last week. Here's what broke."

❌ "Technology can help us be more productive."
✅ "Most AI tools promise 10x productivity. Reality: 2x on good days, if you know what to automate."

SPECIFIC STORIES TO DRAW FROM:
- Only use a story if it appears in the eligible story anchors below
- Prefer operator proof: workflow clarity, prompting, automation, handoffs, shipped systems
- Only use institutions, employers, or named projects when they appear directly in the approved proof or story anchors for this request""",

        "fashion": """TARGET AUDIENCE: Fashion & Style enthusiasts
- Use visual, sensory language
- Reference: personal style, wardrobe, self-expression, confidence
- Keep it relatable, not high-fashion exclusive
- Style is identity, not vanity

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Fashion is an important form of self-expression."
✅ "That oversized jacket from my dad, a mechanic, taught me more about style than any magazine."

❌ "What you wear matters."
✅ "Clothes aren't just clothes. They're memories. They're roots."

SPECIFIC STORIES TO DRAW FROM:
- Dad's mechanic jacket worn on cold school mornings
- Fell in love with fashion in a random textile course
- Building Easy Outfit app to solve your own styling problem
- Buying clothes every weekend trying to figure out style""",

        "leadership": """TARGET AUDIENCE: Leaders & Managers
- Speak to people who manage teams and navigate organizational complexity
- Reference: coaching, developing people, driving results, decision-making
- Focus on practical leadership, not theoretical
- You've managed teams, hit targets, built culture

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Leadership is about inspiring others."
✅ "I used to dominate conversations. Now I make it my business to be the last person to talk."

❌ "Good managers support their teams."
✅ "Teams don't perform because they don't have a clear goal or they don't believe in the plan. That's it."

SPECIFIC STORIES TO DRAW FROM:
- Managing teams of 15+ at 2U
- "Temperature gauge" approach: never let the team cool off
- "Process Champion" identity: keeping things documented
- The defer process story: getting buy-in before formally suggesting
- Coaching struggling ACs: taking him to lunch as a peer, not a manager""",

        "neurodivergent": """TARGET AUDIENCE: Neurodivergent community & supporters
- Speak to families, professionals, and neurodivergent individuals
- Reference: different learning styles, finding the right fit, accommodations
- Be authentic: you're neurodivergent yourself
- This isn't just work; it's personal

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Neurodivergent students face unique challenges."
✅ "I'm neurodivergent. This isn't just a job. It's personal."

❌ "We need to support different learning styles."
✅ "When a student finally finds an environment where 'different' is the norm, you see the shift immediately."

SPECIFIC STORIES TO DRAW FROM:
- Being neurodivergent yourself
- Fusion Academy: 1:1 school serving neurodivergent students
- Understanding what it's like to learn differently
- Helping families find the right fit for their kids
- The moment when students feel seen, not just academically""",

        "entrepreneurs": """TARGET AUDIENCE: Entrepreneurs & Founders
- Speak to people building something from scratch
- Reference: shipping, pivoting, customer discovery, building in public
- Focus on action and results, not theory
- You're building Easy Outfit, pivoting into tech

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Entrepreneurship requires persistence and vision."
✅ "I'm building an app to solve my own problem. That's the only validation that matters early on."

❌ "Starting a business is challenging but rewarding."
✅ "I've spent 10+ years in education. Now I'm pivoting into tech. You're witnessing the messy middle."

SPECIFIC STORIES TO DRAW FROM:
- Building Easy Outfit app
- Pivoting from education into tech
- Founded InspireSTL nonprofit out of college
- "I can't be put in a box" identity
- Building in public, sharing the journey"""
    }
    
    audience_context = audience_guidance.get(audience, audience_guidance["general"])
    
    # Category guidance (Chris Do 911) with examples
    category_guidance = {
        "value": """VALUE CONTENT (9 out of 11 posts)
Pure value. Teaching, insights, observations. NO selling. Make them smarter.

PURPOSE: Build authority and trust. Give without asking.

EXAMPLE VALUE HOOKS:
❌ "Here are 5 tips for better leadership."
✅ "Teams don't perform because they don't have a clear goal or they don't believe in the plan. That's it."

❌ "Communication is key in management."
✅ "I used to dominate conversations. Now I make it my business to be the last person to talk. Results: more fruitful exchanges, heavier adoption of my ideas."

❌ "Here's what I learned about enrollment management."
✅ "Enrollment season taught me something: your first 60 seconds with a family matter more than your brochure."

VALUE CONTENT RULES:
- Lead with the insight, not the setup
- Share frameworks, not platitudes
- Use specific numbers and outcomes
- End with reflection or question, NOT a pitch
- NO "DM me" or "link in bio" on value posts""",

        "sales": """SALES CONTENT (1 out of 11 posts)
Sell unabashedly. Direct ask. No apologies.

PURPOSE: Convert attention into action. You've earned the right to ask.

EXAMPLE SALES HOOKS:
❌ "I'm excited to announce my new project."
✅ "I'm building Easy Outfit. It solves a problem I've had for years. Here's how to get early access."

❌ "If you're interested in learning more about my services..."
✅ "I consult on enrollment management and program launches. 10+ years experience. $34M portfolios. If you need help, let's talk."

❌ "I'd love to connect with anyone who might benefit from this."
✅ "Looking for beta testers. DM me if you want in. No pitch deck, just building."

SALES CONTENT RULES:
- State what you're building/offering in the first 2 lines
- Be specific about who it's for
- Clear CTA: DM, comment, link
- No hedging ("might be interested", "could potentially")
- Confidence, not arrogance
- You've given 9 value posts. You've earned this ask.""",

        "personal": """PERSONAL CONTENT (1 out of 11 posts)
Behind-the-scenes. The real you. Struggles included. Vulnerability builds trust.

PURPOSE: Humanize yourself. Let people connect with the person, not just the professional.

EXAMPLE PERSONAL HOOKS:
❌ "I want to share a personal story with you today."
✅ "I can't be put into a box. Son of a mechanic from St. Louis. Fell in love with fashion in a random textile course. 10+ years in education. Now pivoting into tech."

❌ "I've learned a lot on my journey."
✅ "I used to dominate conversations. I'd talk over people. Interrupt. Make sure my point was heard. It made me appear intimidating. And honestly? It hurt my relationships."

❌ "Thanksgiving is a time for gratitude."
✅ "That oversized jacket from my dad, a mechanic, taught me more about style than any magazine. Cozy, yes, but also a symbol of hard work and resilience."

PERSONAL CONTENT RULES:
- Specific details: names, places, objects, moments
- Show the struggle, not just the win
- Vulnerability, not oversharing
- Connect personal story to broader meaning
- End with reflection or question that invites others to share"""
    }
    
    # Channel-specific system prompts - PRESERVE AUTHENTIC VOICE
    channel_prompts = {
        "linkedin_post": """You write LinkedIn posts that sound like THIS SPECIFIC PERSON - casual, warm, punchy.

VOICE PRESERVATION (CRITICAL):
- Keep casual markers: "Yall", "Tell you what tho", "I'm here for it"
- Keep punchy rhythm: short sentences, stacked phrases
- Keep engagement hooks: "Say it with me: 🗣️"
- Keep recognition patterns: "Big shout-out to..."
- DO NOT over-polish or remove casual language
- DO NOT make it sound corporate or generic

Tone:
- confident and direct
- warm and casual (NOT stiff or formal)
- grounded in real experience
- punchy, not verbose

Writing rules:
- lead with insight or hook, not setup
- vary sentence length
- short paragraphs (1-3 sentences)
- use REAL stories from persona data
- end with question or reflection
- hashtags grouped at end

Voice audit:
- Does it sound like the real LinkedIn examples?
- Are casual markers preserved?
- Is the rhythm punchy, not flat?
- Would this person actually post this?""",

        "cold_email": """You write emails that are professional but still sound like THIS PERSON.

VOICE PRESERVATION:
- Keep direct, confident language
- Can include casual warmth
- Reference real experiences from persona
- NO corporate jargon

Tone:
- direct and confident
- warm but professional
- clean and human

Structure:
- strong opening
- short paragraphs
- one clear CTA
- human closing ("Warmly" etc.)

Voice audit:
- Does it sound authentic to this person?
- Is it direct without being cold?""",

        "linkedin_dm": """You write DMs that feel like messages from a friend, not a salesperson.

VOICE PRESERVATION:
- Casual openers OK ("Hey —")
- Can use "Yall" if fits context
- Short and punchy
- Reference real work from persona

Tone:
- casual and warm
- confident, not salesy
- conversational

Rules:
- under 10 seconds to read
- one question or insight
- NO pitch language
- feels personal

Voice audit:
- Would you send this to a friend?
- Is it too formal or stiff?""",

        "instagram_post": """You write Instagram captions that are casual, warm, and authentic.

VOICE PRESERVATION:
- Casual language OK ("Yall" etc.)
- Emojis sparingly (🙏 💜 ✨)
- Punchy rhythm, stacked phrases
- Personal but not oversharing

Tone:
- casual and thoughtful
- warm and authentic
- visually descriptive

Rules:
- short paragraphs, white space
- open with hook
- end with question or reflection
- NO brand voice, NO corporate

Voice audit:
- Does it sound like a real person?
- Is the rhythm natural?"""
    }
    
    channel_prompt = channel_prompts.get(content_type, channel_prompts["linkedin_post"])
    
    # PACER elements
    pacer_guidance = ""
    if pacer_elements:
        pacer_map = {
            "Problem": "Start by identifying a specific problem your audience faces",
            "Amplify": "Amplify the pain - what happens if they don't solve it?",
            "Credibility": "Establish why you're qualified to speak on this",
            "Educate": "Provide actionable value and insights",
            "Request": "End with a clear call-to-action"
        }
        pacer_guidance = "Include these PACER elements:\n" + "\n".join([f"- {p}: {pacer_map.get(p, '')}" for p in pacer_elements])
    
    prompt = f"""{anti_ai_rules}

{channel_prompt}

{channel_example}

---

{audience_context}

---

## PERSONA STACK (core canon first, then support, then legacy):
{persona_text if persona_text else "No persona data available - use a professional, authentic voice."}

## TOPIC ANCHORS (highest priority):
{topic_anchor_text}

## ELIGIBLE STORY / PROOF ANCHORS:
{eligible_story_text}

## PROOF ANCHORS:
{proof_anchor_text}

## EXAMPLES FROM THEIR KNOWLEDGE BASE:
{examples_text if examples_text else "No additional examples available."}

## CONTENT REQUEST:
- **Topic:** {topic}
- **Context:** {context or "General"}
- **Audience:** {audience.replace('_', ' ').title()}
- **Category:** {category.upper()} - {category_guidance.get(category, "")}

CRITICAL: The content MUST be about "{topic}". 
- If the topic is a PERSON'S NAME: The post MUST mention them BY NAME multiple times. Feature them prominently - share what you learned from them, celebrate their work, or tell a story involving them. Do NOT write a generic post that ignores the person.
- If the topic is a concept: The post should explore that concept directly.

IMPORTANT: If Context is provided above (not "General"), you MUST incorporate that specific context into the content. Reference the situation, event, or details mentioned in the context directly.

{pacer_guidance}

## TOPIC DISCIPLINE:
{topic_focus_guidance}

## PROOF DISCIPLINE:
{proof_guidance}

## GROUNDING MODE:
- Current mode: `{grounding_mode}`
- {grounding_reason}
- This mode controls what kind of claim is allowed. Do not upgrade weak support into hard proof.
- `proof_ready`: use named systems, artifacts, and evidence only from TOPIC / PROOF anchors.
- `story_supported`: use at most one eligible story and keep it tied to the operating lesson.
- `principle_only`: do not reach for named projects, employers, metrics, or case studies unless they already appear in the TOPIC anchors.

## APPROVED FRAMING MODES (preserve the legacy rhetorical edge):
{framing_modes_text}

## PRIMARY CLAIMS YOU MAY MAKE:
{primary_claims_text}

## APPROVED PROOF PACKETS:
{proof_packets_text}

## OPTIONAL STORY BEATS:
{story_beats_text}

## ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

## DISALLOWED MOVES:
{disallowed_moves_text}

## NARRATIVE ARC (follow this structure):
1. **HOOK/CONTEXT** - Start with something relatable, surprising, or attention-grabbing. Use voice markers.
2. **OPERATING LESSON** - Build the post around a real lesson, framework, proof point, or experience from the topic anchors.
3. **REFLECTION/CTA** - Tie it back to the audience with insight or a question. End strong.

## INSTRUCTIONS:
1. Write AS this person using their actual experiences and perspectives.
2. Follow the 3-part structure above, but do NOT force a personal story when the topic anchors are principle-led.
3. Ground every option in the topic anchors first. Biography is support, not the main point.
4. Only use a personal anecdote if it appears in the eligible story/proof anchors above.
5. If there is no eligible story anchor, stay with proof, principle, and operating insight.
6. Each option must include at least one concrete proof anchor, named system, or explicit operating signal from the proof anchors above when available.
7. If you use a metric, keep its original subject intact. Never convert a participation, utilization, or revenue metric into a generic productivity or completion-time claim.
8. Be specific and actionable, not generic.
9. Generate 3 different options with varying hooks/angles.
10. Keep the writing vivid. Use tension, agreement, contrast, or drama only when it stays grounded in the approved framing modes above.
11. Use a different approved framing mode for each option so the three drafts do not collapse into one flat shape.
12. Pick one PRIMARY CLAIM per option and stay inside it. Do not merge multiple weak ideas together.
13. If `proof_ready`, each option must use one APPROVED PROOF PACKET faithfully. Keep the original subject and meaning intact.
14. If `principle_only`, do not mention named systems, employers, projects, or metrics unless they already appear in PRIMARY CLAIMS.
15. If a named reference is not in APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES, remove it.

## ANTI-HALLUCINATION RULES (CRITICAL):
- ONLY use anecdotes, stories, and facts that appear in the PERSONA section above
- If you need a personal story, it must come from the ELIGIBLE STORY / PROOF ANCHORS section above
- NEVER invent stories about family members, objects, or experiences not in the persona
- If no relevant anecdote exists, use a general reflection instead of fabricating
- Only reference named ventures, employers, systems, programs, or stories if they appear in the TOPIC / ELIGIBLE STORY / PROOF anchors above
- Do not reach into broad biography memory for extra names just because they are real somewhere else in the persona bundle
- Do not borrow a weakly related story just to make the post feel more personal

## VOICE MARKERS TO USE:
- "Yall" / "Y'all" as casual opener
- "Tell you what tho" as pivot
- "Say it with me: 🗣️" for engagement
- "Big shout-out to..." for recognition
- "Makes no sense. Period." for punchy closer
- "I'm here for it" for endorsement
- "#stayready" "#staytuned" for hashtags

Output only the content. No notes, no explanations.

Generate 3 content options, separated by "---OPTION---":
"""
    
    return prompt


def parse_content_options(raw_content: str) -> List[str]:
    if "---OPTION 1---" in raw_content:
        options = re.split(r"---OPTION \d+---", raw_content)
        return [opt.strip() for opt in options if opt.strip()]
    if "---OPTION---" in raw_content:
        return [opt.strip() for opt in raw_content.split("---OPTION---") if opt.strip()]
    return [raw_content.strip()] if raw_content.strip() else []


def _normalized_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _extract_approved_reference_terms(
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
) -> List[str]:
    sources = primary_claims + proof_packets + story_beats
    approved: List[str] = []
    seen: set[str] = set()
    for text in sources:
        normalized_text = " ".join((text or "").split())
        if not normalized_text:
            continue
        for pattern in (
            r"(?:[A-Z]{2,}|[A-Z][a-z]+)(?:\s*/\s*(?:[A-Z]{2,}|[A-Z][a-z]+))+",
            r"(?:[A-Z]{2,}|[A-Z][a-z]+)(?:\s+(?:[A-Z]{2,}|[A-Z][a-z]+)){0,3}",
        ):
            for match in re.finditer(pattern, normalized_text):
                phrase = " ".join(match.group(0).replace("/", " / ").split()).strip()
                key = phrase.lower()
                if len(key) < 2 or key in seen:
                    continue
                seen.add(key)
                approved.append(phrase)
        for phrase in re.findall(
            r"(explicit handoffs|shared workspace state|proof-aware prompts|routed workspace snapshot|bundle-first content generation|long-form routing|daily briefs|workflow clarity|agent orchestration)",
            normalized_text,
            flags=re.IGNORECASE,
        ):
            normalized_phrase = " ".join(phrase.split()).strip()
            key = normalized_phrase.lower()
            if key in seen:
                continue
            seen.add(key)
            approved.append(normalized_phrase)
    return approved[:12]


def _extract_named_reference_candidates(text: str) -> set[str]:
    candidates: set[str] = set()
    cleaned = re.sub(r"[*_`#]", " ", text or "")
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        tokens = re.findall(r"[A-Za-z][A-Za-z/&+-]*", sentence)
        for index, token in enumerate(tokens):
            if not token:
                continue
            if index == 0 and token in GENERIC_SENTENCE_OPENERS:
                continue
            if token.lower() in STOPWORDS:
                continue
            if re.fullmatch(r"[A-Z]{2,}", token) or re.fullmatch(r"[A-Z][a-z]+", token):
                if len(token) >= 4 or token.isupper():
                    candidates.add(token.lower())
    return candidates


def option_uses_unapproved_reference(
    option: str,
    *,
    approved_reference_terms: List[str],
    audience: str,
) -> bool:
    approved_terms = _normalized_terms(" ".join(approved_reference_terms))
    approved_terms.update(_extract_named_reference_candidates(" ".join(approved_reference_terms)))
    if _extract_named_reference_candidates(option) - approved_terms:
        return True

    if audience == "tech_ai":
        option_text = " ".join((option or "").lower().split())
        for placeholder in UNSUPPORTED_EVIDENCE_PLACEHOLDERS:
            if placeholder in option_text and placeholder not in approved_terms:
                return True
    return False


def option_mentions_approved_proof(option: str, proof_packets: List[str]) -> bool:
    option_terms = _normalized_terms(option)
    if not option_terms or not proof_packets:
        return False
    for packet in proof_packets:
        packet_terms = _normalized_terms(packet)
        if len(option_terms.intersection(packet_terms)) >= 2:
            return True
    return False


def build_proof_enforcement_prompt(
    *,
    topic: str,
    audience: str,
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
) -> str:
    options_text = "\n---OPTION---\n".join(rough_options)
    claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- Stay inside the topic."
    proof_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No proof packets available."
    story_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No approved story beats."
    approved_references = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {reference}" for reference in approved_references) or "- No approved named references."
    framing_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in framing_modes
    ) or "- `operator_lesson`"
    return f"""You are repairing draft posts that are too generic and are not carrying the approved proof strongly enough.

Topic: {topic}
Audience: {audience}

PRIMARY CLAIMS:
{claims_text}

APPROVED PROOF PACKETS:
{proof_text}

OPTIONAL STORY BEATS:
{story_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

APPROVED FRAMING MODES:
{framing_text}

DRAFTS TO REWRITE:
{options_text}

REWRITE RULES:
- Keep 3 options.
- Each option must use one PRIMARY CLAIM.
- Each option must explicitly mention at least one named system, artifact, or evidence phrase from an APPROVED PROOF PACKET.
- Only use named references that appear in the APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES list above.
- Remove unsupported references like videos, schools, employers, or projects that are not explicitly approved above.
- Keep the original proof meaning intact. Do not generalize it into vague productivity language.
- Do not use phrases like seamless, unlock potential, drive results, or everything flows.
- Preserve the person's casual rhythm and punchy style.
- Use different framing modes across the options.

Output only the rewritten options, separated by ---OPTION---.
"""


def build_refinement_prompt(
    *,
    topic: str,
    audience: str,
    persona_chunks: List[Dict[str, Any]],
    rough_options: List[str],
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
) -> str:
    topic_anchor_chunks = topic_anchor_chunks or select_topic_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    eligible_story_chunks = eligible_story_chunks or select_eligible_story_chunks(persona_chunks, topic=topic, audience=audience, limit=3)
    proof_anchor_chunks = proof_anchor_chunks or select_proof_anchor_chunks(persona_chunks, topic=topic, audience=audience, limit=4)
    topic_anchor_text = "\n".join(f"- {_render_anchor_chunk(item)}" for item in topic_anchor_chunks) or "- No topic anchors available."
    eligible_story_text = (
        "\n".join(f"- {_render_anchor_chunk(item, include_use_when=True)}" for item in eligible_story_chunks)
        if eligible_story_chunks
        else "- No directly relevant story anchor found. Do not force one."
    )
    proof_anchor_text = (
        "\n".join(f"- {_render_anchor_chunk(item)}" for item in proof_anchor_chunks)
        if proof_anchor_chunks
        else "- No strong proof anchor found. Stay concrete about process and role."
    )
    grounding_mode = grounding_mode or ("proof_ready" if proof_anchor_chunks else "principle_only")
    grounding_reason = grounding_reason or (
        "Concrete proof anchors are available, so the post can stay specific."
        if proof_anchor_chunks
        else "No strong proof anchor was found, so the post should stay principle-led."
    )
    approved_framing_modes = framing_modes or ["operator_lesson", "contrarian_reframe", "reframe"]
    framing_modes_text = "\n".join(
        f"- `{mode}`: {FRAMING_MODE_GUIDANCE.get(mode, mode.replace('_', ' '))}"
        for mode in approved_framing_modes
    )
    primary_claims = primary_claims or []
    proof_packets = proof_packets or []
    story_beats = story_beats or []
    disallowed_moves = disallowed_moves or []
    primary_claims_text = "\n".join(f"- {claim}" for claim in primary_claims) or "- No pre-composed primary claims."
    proof_packets_text = "\n".join(f"- {packet}" for packet in proof_packets) or "- No approved proof packets."
    story_beats_text = "\n".join(f"- {beat}" for beat in story_beats) or "- No approved story beats."
    disallowed_moves_text = "\n".join(f"- {move}" for move in disallowed_moves) or "- No extra banned moves."
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    approved_reference_text = "\n".join(f"- {term}" for term in approved_reference_terms) or "- No approved named references."
    rough_text = "\n---OPTION---\n".join(rough_options)
    return f"""You are revising drafted posts so they sound sharper, more specific, and more faithful to this person's canon.

Topic: {topic}
Audience: {audience}

TOPIC ANCHORS:
{topic_anchor_text}

ELIGIBLE STORY / PROOF ANCHORS:
{eligible_story_text}

PROOF ANCHORS:
{proof_anchor_text}

GROUNDING MODE:
- `{grounding_mode}`
- {grounding_reason}

APPROVED FRAMING MODES:
{framing_modes_text}

PRIMARY CLAIMS YOU MAY MAKE:
{primary_claims_text}

APPROVED PROOF PACKETS:
{proof_packets_text}

OPTIONAL STORY BEATS:
{story_beats_text}

ONLY THESE NAMED REFERENCES MAY APPEAR:
{approved_reference_text}

DISALLOWED MOVES:
{disallowed_moves_text}

ROUGH OPTIONS TO REWRITE:
{rough_text}

REVISION RULES:
- Keep 3 options.
- Preserve the person's casual voice and punchy rhythm.
- Remove generic filler, motivational fluff, and any language that could apply to anyone.
- Preserve the dramatic, contrarian, agreement, or tension-based framing when it is grounded in the approved framing modes above.
- Ban phrases like "magic happens", "synergy", "game changer", "nice-to-have", "backbone", and "thrive in AI".
- Every option must be grounded in the topic anchors above.
- Only use a personal anecdote if it appears in the eligible story / proof anchors above.
- Each option must include at least one concrete proof anchor, named system, evidence phrase, or metric from the PROOF ANCHORS above when available.
- Never translate one metric into another. If a proof anchor mentions participation, utilization, or revenue, keep that exact subject or omit the number.
- If no eligible story anchor exists, do not force a story. Stay with proof, pattern, and operating insight.
- Replace vague claims with concrete operator language: workflow, handoff, prompt, system, proof, constraint, operating cadence.
- Cut weak setup lines. Start faster.
- Use one PRIMARY CLAIM per option and make it legible in the first lines.
- If `proof_ready`, tie each option to one APPROVED PROOF PACKET and preserve its exact meaning.
- If `principle_only`, remove stray named examples that are not explicitly present in PRIMARY CLAIMS.
- If a named reference is not in the APPROVED PROOF PACKETS, OPTIONAL STORY BEATS, or ONLY THESE NAMED REFERENCES list, remove it.

Output only the rewritten options, separated by ---OPTION---.
"""


def refine_generated_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    content_type: str,
    persona_chunks: List[Dict[str, Any]],
    rough_options: List[str],
    topic_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    eligible_story_chunks: Optional[List[Dict[str, Any]]] = None,
    proof_anchor_chunks: Optional[List[Dict[str, Any]]] = None,
    grounding_mode: Optional[str] = None,
    grounding_reason: Optional[str] = None,
    framing_modes: Optional[List[str]] = None,
    primary_claims: Optional[List[str]] = None,
    proof_packets: Optional[List[str]] = None,
    story_beats: Optional[List[str]] = None,
    disallowed_moves: Optional[List[str]] = None,
) -> List[str]:
    if content_type != "linkedin_post" or not rough_options:
        return rough_options

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a strict editorial pass. Make the writing sharper and more concrete without changing the author's voice.",
            },
            {
                "role": "user",
                "content": build_refinement_prompt(
                    topic=topic,
                    audience=audience,
                    persona_chunks=persona_chunks,
                    rough_options=rough_options,
                    topic_anchor_chunks=topic_anchor_chunks,
                    eligible_story_chunks=eligible_story_chunks,
                    proof_anchor_chunks=proof_anchor_chunks,
                    grounding_mode=grounding_mode,
                    grounding_reason=grounding_reason,
                    framing_modes=framing_modes,
                    primary_claims=primary_claims,
                    proof_packets=proof_packets,
                    story_beats=story_beats,
                    disallowed_moves=disallowed_moves,
                ),
            },
        ],
        temperature=0.35,
        max_tokens=1800,
    )
    refined = parse_content_options(response.choices[0].message.content or "")
    return refined[:3] if refined else rough_options


def enforce_grounding_on_options(
    *,
    client: Any,
    topic: str,
    audience: str,
    content_type: str,
    grounding_mode: str,
    rough_options: List[str],
    primary_claims: List[str],
    proof_packets: List[str],
    story_beats: List[str],
    framing_modes: List[str],
) -> List[str]:
    if content_type != "linkedin_post" or grounding_mode != "proof_ready" or not proof_packets or not rough_options:
        return rough_options
    approved_reference_terms = _extract_approved_reference_terms(primary_claims, proof_packets, story_beats)
    if all(
        option_mentions_approved_proof(option, proof_packets)
        and not option_uses_unapproved_reference(
            option,
            approved_reference_terms=approved_reference_terms,
            audience=audience,
        )
        for option in rough_options
    ):
        return rough_options

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a strict factual editor. Keep the voice, but force the writing to carry the approved proof explicitly.",
            },
            {
                "role": "user",
                "content": build_proof_enforcement_prompt(
                    topic=topic,
                    audience=audience,
                    rough_options=rough_options,
                    primary_claims=primary_claims,
                    proof_packets=proof_packets,
                    story_beats=story_beats,
                    framing_modes=framing_modes,
                ),
            },
        ],
        temperature=0.2,
        max_tokens=1800,
    )
    repaired = parse_content_options(response.choices[0].message.content or "")
    return repaired[:3] if repaired else rough_options

@router.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(req: ContentGenerationRequest):
    """
    Generate AI-powered content using persona and examples from knowledge base.
    """
    try:
        content_context: ContentGenerationContext = build_content_generation_context(
            user_id=req.user_id,
            topic=req.topic,
            context=req.context,
            content_type=req.content_type,
            category=req.category,
            tone=req.tone,
            audience=req.audience,
        )
        persona_chunks = content_context.persona_chunks

        # Log what tags were retrieved for debugging
        if persona_chunks:
            tag_summary = {}
            for chunk in persona_chunks:
                tag = chunk.get("persona_tag", "UNKNOWN")
                tag_summary[tag] = tag_summary.get(tag, 0) + 1
            print(f"[content_gen] Retrieved persona chunks by tag: {tag_summary}", flush=True)
        example_chunks = content_context.example_chunks
        
        # Step 3: Build prompt with all context
        prompt = build_content_prompt(
            topic=req.topic,
            context=req.context or "",
            content_type=req.content_type,
            category=req.category,
            pacer_elements=req.pacer_elements,
            tone=req.tone,
            persona_chunks=persona_chunks,
            example_chunks=example_chunks,
            audience=req.audience,
            topic_anchor_chunks=content_context.topic_anchor_chunks,
            eligible_story_chunks=content_context.story_anchor_chunks,
            proof_anchor_chunks=content_context.proof_anchor_chunks,
            grounding_mode=content_context.grounding_mode,
            grounding_reason=content_context.grounding_reason,
            framing_modes=content_context.framing_modes,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            disallowed_moves=content_context.disallowed_moves,
        )
        
        # Step 4: Generate content with OpenAI
        client = get_openai_client()
        
        system_message = """You are a ghostwriter who perfectly mimics a specific person's voice.

CRITICAL RULES:
1. Use the EXACT voice patterns from the persona data (casual phrases, rhythm, signature expressions)
2. ONLY use stories, anecdotes, and facts EXPLICITLY mentioned in the persona data below
3. NEVER invent or fabricate stories - if no relevant story exists, speak generally about the topic
4. DO NOT make up family stories, childhood memories, or personal details not in the persona
5. Preserve casual markers like "Yall", "Tell you what tho", "Say it with me"
6. Keep punchy rhythm - short sentences, stacked phrases
7. DO NOT over-polish or make it sound generic/corporate
8. Stay focused on the user's TOPIC and CONTEXT - don't drift to unrelated subjects
9. Treat TOPIC ANCHORS as higher priority than generic biography
10. Only use a personal anecdote if it appears in ELIGIBLE STORY / PROOF ANCHORS

ANTI-HALLUCINATION: If you cannot find a relevant real story in the persona data, write value-driven content about the topic WITHOUT inventing personal anecdotes. Generic insights are better than fake stories.

CONTEXTUAL RELEVANCE: Only include personal details when they're relevant to the topic:
- "Son of a mechanic" - ONLY use if topic relates to family, work ethic, blue collar values, or personal background
- "Can't be put in a box" - ONLY use if topic relates to identity, career pivots, or being multifaceted
- Don't shoehorn personal details into unrelated topics (e.g., don't mention mechanic dad in a post about supply chains)
- Each option should feel fresh and directly address the user's topic/context

If the persona uses casual language, USE IT. Do not "clean it up" into formal English."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.68 if req.audience == "tech_ai" else 0.85,
            max_tokens=2000,
        )
        
        # Step 5: Parse and refine options.
        raw_content = response.choices[0].message.content or ""
        options = parse_content_options(raw_content)
        options = refine_generated_options(
            client=client,
            topic=req.topic,
            audience=req.audience,
            content_type=req.content_type,
            persona_chunks=persona_chunks,
            rough_options=options,
            topic_anchor_chunks=content_context.topic_anchor_chunks,
            eligible_story_chunks=content_context.story_anchor_chunks,
            proof_anchor_chunks=content_context.proof_anchor_chunks,
            grounding_mode=content_context.grounding_mode,
            grounding_reason=content_context.grounding_reason,
            framing_modes=content_context.framing_modes,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            disallowed_moves=content_context.disallowed_moves,
        )
        options = enforce_grounding_on_options(
            client=client,
            topic=req.topic,
            audience=req.audience,
            content_type=req.content_type,
            grounding_mode=content_context.grounding_mode,
            rough_options=options,
            primary_claims=content_context.primary_claims,
            proof_packets=content_context.proof_packets,
            story_beats=content_context.story_beats,
            framing_modes=content_context.framing_modes,
        )

        return ContentGenerationResponse(
            success=True,
            options=options[:3],  # Max 3 options
            persona_context=content_context.persona_context_summary,
            examples_used=[c.get("metadata", {}).get("source", "")[:50] for c in example_chunks[:3]]
        )
        
    except Exception as e:
        print(f"Content generation error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


@router.post("/quick-generate")
async def quick_generate(
    topic: str,
    content_type: str = "linkedin_post",
    category: str = "value",
    user_id: str = "default"
):
    """Quick endpoint for simple content generation."""
    req = ContentGenerationRequest(
        user_id=user_id,
        topic=topic,
        content_type=content_type,
        category=category,
    )
    return await generate_content(req)
