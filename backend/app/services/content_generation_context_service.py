from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.embedders import embed_text
from app.services.persona_bundle_context_service import retrieve_bundle_persona_chunks
from app.services.retrieval import retrieve_similar, retrieve_weighted


LEGACY_PERSONA_SOURCES = (
    "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
    "JOHNNIE_FIELDS_PERSONA.md",
)
LEGACY_EXAMPLE_TAGS = ["LINKEDIN_EXAMPLES"]
PROMPT_SECTION_CORE = "CORE CANON"
PROMPT_SECTION_SUPPORT = "SUPPORTING CANON"
PROMPT_SECTION_LEGACY = "LEGACY SUPPORT"
PROMPT_SECTION_RETRIEVAL = "RETRIEVAL SUPPORT"
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


@dataclass
class ContentGenerationContext:
    persona_chunks: list[dict[str, Any]]
    example_chunks: list[dict[str, Any]]
    core_chunks: list[dict[str, Any]]
    proof_chunks: list[dict[str, Any]]
    story_chunks: list[dict[str, Any]]
    ambient_chunks: list[dict[str, Any]]
    topic_anchor_chunks: list[dict[str, Any]]
    proof_anchor_chunks: list[dict[str, Any]]
    story_anchor_chunks: list[dict[str, Any]]
    grounding_mode: str
    grounding_reason: str
    framing_modes: list[str]
    persona_context_summary: str | None


def _item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _normalized_chunk_key(item: dict[str, Any]) -> str:
    return " ".join(str(item.get("chunk") or "").split()).strip().lower()


def _source_name(item: dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    return str(metadata.get("file_name") or metadata.get("source") or "")


def _with_prompt_section(item: dict[str, Any], section: str) -> dict[str, Any]:
    hydrated = dict(item)
    metadata = dict(_item_metadata(item))
    metadata["prompt_section"] = section
    hydrated["metadata"] = metadata
    return hydrated


def _append_unique(
    destination: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
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


def _passes_audience_anchor_gate(chunk: str, audience: str) -> bool:
    required_terms = STRICT_AUDIENCE_ANCHOR_TERMS.get(audience)
    if not required_terms:
        return True
    normalized_chunk = " ".join((chunk or "").lower().split())
    return any(term in normalized_chunk for term in required_terms)


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


def _infer_support_memory_role(item: dict[str, Any]) -> str:
    metadata = _item_metadata(item)
    memory_role = str(metadata.get("memory_role") or "").strip().lower()
    if memory_role in {"core", "proof", "story", "example", "ambient"}:
        return memory_role
    tag = str(item.get("persona_tag") or metadata.get("persona_tag") or "").upper()
    if tag == "LINKEDIN_EXAMPLES":
        return "example"
    if tag in {"EXPERIENCES", "VENTURES"}:
        return "story"
    return "ambient"


def _infer_support_usage_modes(memory_role: str) -> list[str]:
    if memory_role == "core":
        return ["always_on", "topic_anchor"]
    if memory_role == "proof":
        return ["proof_anchor", "topic_anchor"]
    if memory_role == "story":
        return ["story_anchor", "optional_support"]
    if memory_role == "example":
        return ["style_reference"]
    return ["support"]


def _hydrate_support_chunk(item: dict[str, Any], *, source_lane: str) -> dict[str, Any]:
    hydrated = dict(item)
    metadata = dict(_item_metadata(item))
    memory_role = _infer_support_memory_role(item)
    metadata.setdefault("memory_role", memory_role)
    metadata.setdefault("usage_modes", _infer_support_usage_modes(memory_role))
    metadata.setdefault("source_lane", source_lane)
    metadata.setdefault("proof_strength", "weak")
    metadata.setdefault("artifact_backed", False)
    hydrated["metadata"] = metadata
    return hydrated


def _hydrate_bundle_chunk(item: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(item)
    metadata = dict(_item_metadata(item))
    metadata.setdefault("source_lane", "canonical_bundle")
    hydrated["metadata"] = metadata
    return hydrated


def curate_persona_prompt_chunks(
    *,
    bundle_chunks: list[dict[str, Any]],
    legacy_support_chunks: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
    top_k: int = 9,
) -> list[dict[str, Any]]:
    hydrated_bundle_chunks = [_hydrate_bundle_chunk(item) for item in bundle_chunks]
    hydrated_legacy_chunks = [_hydrate_support_chunk(item, source_lane="legacy_support") for item in legacy_support_chunks]
    hydrated_retrieved_chunks = [_hydrate_support_chunk(item, source_lane="retrieval_support") for item in retrieved_chunks]

    core_chunks = [
        item for item in hydrated_bundle_chunks if str(_item_metadata(item).get("memory_role") or "") == "core"
    ]
    proof_chunks = [
        item for item in hydrated_bundle_chunks if str(_item_metadata(item).get("memory_role") or "") == "proof"
    ]
    story_chunks = [
        item
        for item in (hydrated_bundle_chunks + hydrated_legacy_chunks)
        if str(_item_metadata(item).get("memory_role") or "") == "story"
    ]
    ambient_bundle_chunks = [
        item
        for item in hydrated_bundle_chunks
        if str(_item_metadata(item).get("memory_role") or "") == "ambient"
    ]
    legacy_chunks = [
        item
        for item in hydrated_legacy_chunks
        if _source_name(item) in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]
    retrieval_support_chunks = [
        item
        for item in hydrated_retrieved_chunks
        if _source_name(item) not in LEGACY_PERSONA_SOURCES and item.get("persona_tag") != "LINKEDIN_EXAMPLES"
    ]

    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    _append_unique(curated, core_chunks, limit=min(top_k, 4), seen=seen, section=PROMPT_SECTION_CORE)
    _append_unique(curated, proof_chunks, limit=min(top_k, 7), seen=seen, section=PROMPT_SECTION_SUPPORT)
    _append_unique(curated, story_chunks, limit=min(top_k, 8), seen=seen, section=PROMPT_SECTION_SUPPORT)
    _append_unique(curated, ambient_bundle_chunks, limit=min(top_k, 9), seen=seen, section=PROMPT_SECTION_SUPPORT)
    _append_unique(curated, legacy_chunks, limit=min(top_k, 9), seen=seen, section=PROMPT_SECTION_LEGACY)
    _append_unique(curated, retrieval_support_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_RETRIEVAL)
    return curated[:top_k]


def retrieve_legacy_support_chunks(
    *,
    user_id: str,
    query_embedding: list[float],
    top_k: int = 6,
) -> list[dict[str, Any]]:
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
    query_embedding: list[float],
    content_type: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
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
    example_chunks: list[dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in example_chunks:
        primary_text, _ = _split_use_when_text(str(item.get("chunk") or ""))
        score = _chunk_focus_score(primary_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        ranked.append((score, item))

    curated: list[dict[str, Any]] = []
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


def summarize_persona_context(persona_chunks: list[dict[str, Any]], topic: str) -> str | None:
    normalized_topic = " ".join((topic or "").lower().split())
    if normalized_topic:
        for item in persona_chunks:
            chunk = str(item.get("chunk") or "")
            if normalized_topic in chunk.lower():
                return chunk[:200]
    for preferred_section in (PROMPT_SECTION_CORE, PROMPT_SECTION_SUPPORT, PROMPT_SECTION_LEGACY, PROMPT_SECTION_RETRIEVAL):
        for item in persona_chunks:
            if _item_metadata(item).get("prompt_section") == preferred_section:
                return str(item.get("chunk") or "")[:200]
    return None


def select_topic_anchor_chunks(
    persona_chunks: list[dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    role_priority = {
        "core": 4,
        "proof": 3,
        "story": 2,
        "ambient": 1,
    }
    for item in persona_chunks:
        chunk = str(item.get("chunk") or "")
        primary_text, use_when_text = _split_use_when_text(chunk)
        focus_score = (_chunk_focus_score(primary_text, focus_terms, topic) * 3) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if focus_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        priority = role_priority.get(str(_item_metadata(item).get("memory_role") or "ambient"), 0)
        ranked.append((focus_score, priority, item))

    curated: list[dict[str, Any]] = []
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
    persona_chunks: list[dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    story_candidates: list[tuple[int, int, dict[str, Any]]] = []
    for item in persona_chunks:
        memory_role = str(_item_metadata(item).get("memory_role") or "")
        if memory_role != "story":
            continue
        primary_text, use_when_text = _split_use_when_text(str(item.get("chunk") or ""))
        score = (_chunk_focus_score(primary_text, focus_terms, topic) * 2) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        proof_bonus = 1 if _proof_signal_score(primary_text) > 0 else 0
        story_candidates.append((score, proof_bonus, item))

    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, item in sorted(story_candidates, key=lambda entry: (entry[0], entry[1]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= limit:
            break
    return curated


def select_proof_anchor_chunks(
    persona_chunks: list[dict[str, Any]],
    *,
    topic: str,
    audience: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: list[tuple[int, int, int, dict[str, Any]]] = []
    minimum_focus = 2 if audience == "tech_ai" else 1
    for item in persona_chunks:
        metadata = _item_metadata(item)
        memory_role = str(metadata.get("memory_role") or "")
        if memory_role not in {"core", "proof"}:
            continue
        chunk = str(item.get("chunk") or "")
        primary_text, _ = _split_use_when_text(chunk)
        focus_score = _chunk_focus_score(primary_text, focus_terms, topic)
        proof_score = _proof_signal_score(primary_text)
        proof_strength = str(metadata.get("proof_strength") or "").lower()
        artifact_backed = bool(metadata.get("artifact_backed"))
        if proof_strength == "strong":
            proof_score += 4
        elif proof_strength == "medium":
            proof_score += 2
        if artifact_backed:
            proof_score += 3
        if focus_score <= 0 and proof_score <= 0:
            continue
        if not _passes_audience_anchor_gate(primary_text, audience):
            continue
        if proof_score > 0 and focus_score < minimum_focus:
            continue
        role_priority = 4 if memory_role == "proof" else 3
        ranked.append((focus_score * 4 + proof_score, proof_score, role_priority, item))

    curated: list[dict[str, Any]] = []
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


def score_grounding_confidence(
    *,
    proof_anchor_chunks: list[dict[str, Any]],
    story_anchor_chunks: list[dict[str, Any]],
) -> tuple[str, str]:
    strong_or_medium_proof = [
        item
        for item in proof_anchor_chunks
        if str(_item_metadata(item).get("proof_strength") or "").lower() in {"strong", "medium"}
        or bool(_item_metadata(item).get("artifact_backed"))
    ]
    if strong_or_medium_proof:
        return ("proof_ready", "Artifact-backed proof is available, so the post can lead with real evidence.")
    if story_anchor_chunks:
        return ("story_supported", "Relevant lived experience exists, but proof is weaker than the story support.")
    return ("principle_only", "No strong proof or story support was found, so the post should stay principle-led.")


def recommend_framing_modes(
    *,
    topic: str,
    audience: str,
    category: str,
    grounding_mode: str,
    proof_anchor_chunks: list[dict[str, Any]],
    story_anchor_chunks: list[dict[str, Any]],
) -> list[str]:
    modes: list[str] = []
    normalized_topic = " ".join((topic or "").lower().split())

    if audience == "tech_ai":
        modes.extend(["operator_lesson", "contrarian_reframe", "agree_and_extend"])
    elif audience == "leadership":
        modes.extend(["warning", "agree_and_extend", "reframe"])
    else:
        modes.extend(["reframe", "agree_and_extend", "operator_lesson"])

    if grounding_mode == "proof_ready" or proof_anchor_chunks:
        modes.append("drama_tension")
    if story_anchor_chunks:
        modes.append("story_with_payoff")
    if category == "personal":
        modes.insert(0, "story_with_payoff")
    if category == "sales":
        modes.insert(0, "recognition")
    if any(token in normalized_topic for token in {"thanks", "recognition", "shout-out", "celebrate"}):
        modes.insert(0, "recognition")
    if grounding_mode == "principle_only":
        modes.append("warning")

    unique_modes: list[str] = []
    seen: set[str] = set()
    for mode in modes:
        if mode in seen:
            continue
        seen.add(mode)
        unique_modes.append(mode)
    return unique_modes[:4]


def build_content_generation_context(
    *,
    user_id: str,
    topic: str,
    context: str | None,
    content_type: str,
    category: str,
    tone: str,
    audience: str,
) -> ContentGenerationContext:
    del context, tone

    persona_query = f"persona voice style {topic} {category} content writing"
    persona_embedding = embed_text(persona_query)

    bundle_persona_chunks = retrieve_bundle_persona_chunks(
        query_text=persona_query,
        query_embedding=persona_embedding,
        category=category,
        channel=content_type,
        top_k=10,
    )
    legacy_support_chunks = retrieve_legacy_support_chunks(
        user_id=user_id,
        query_embedding=persona_embedding,
        top_k=6,
    )
    retrieved_persona_chunks = retrieve_weighted(
        user_id=user_id,
        query_embedding=persona_embedding,
        category=category,
        channel=content_type,
        top_k=8,
    )
    persona_chunks = curate_persona_prompt_chunks(
        bundle_chunks=bundle_persona_chunks,
        legacy_support_chunks=legacy_support_chunks,
        retrieved_chunks=retrieved_persona_chunks,
        top_k=9,
    )

    topic_anchor_chunks = select_topic_anchor_chunks(
        persona_chunks,
        topic=topic,
        audience=audience,
        limit=4,
    )
    story_anchor_chunks = select_eligible_story_chunks(
        persona_chunks,
        topic=topic,
        audience=audience,
        limit=3,
    )
    proof_anchor_chunks = select_proof_anchor_chunks(
        persona_chunks,
        topic=topic,
        audience=audience,
        limit=4,
    )

    examples_query = f"high performing content example {content_type} {category} {topic}"
    examples_embedding = embed_text(examples_query)
    example_chunks = retrieve_curated_example_chunks(
        user_id=user_id,
        query_embedding=examples_embedding,
        content_type=content_type,
        top_k=3,
    )
    example_chunks = filter_example_chunks_by_topic(
        example_chunks,
        topic=topic,
        audience=audience,
        limit=3,
    )

    grounding_mode, grounding_reason = score_grounding_confidence(
        proof_anchor_chunks=proof_anchor_chunks,
        story_anchor_chunks=story_anchor_chunks,
    )
    framing_modes = recommend_framing_modes(
        topic=topic,
        audience=audience,
        category=category,
        grounding_mode=grounding_mode,
        proof_anchor_chunks=proof_anchor_chunks,
        story_anchor_chunks=story_anchor_chunks,
    )

    core_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "core"]
    proof_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "proof"]
    story_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "story"]
    ambient_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "ambient"]

    return ContentGenerationContext(
        persona_chunks=persona_chunks,
        example_chunks=example_chunks,
        core_chunks=core_chunks,
        proof_chunks=proof_chunks,
        story_chunks=story_chunks,
        ambient_chunks=ambient_chunks,
        topic_anchor_chunks=topic_anchor_chunks,
        proof_anchor_chunks=proof_anchor_chunks,
        story_anchor_chunks=story_anchor_chunks,
        grounding_mode=grounding_mode,
        grounding_reason=grounding_reason,
        framing_modes=framing_modes,
        persona_context_summary=summarize_persona_context(persona_chunks, topic),
    )
