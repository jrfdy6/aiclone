from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.embedders import embed_text
from app.services.persona_bundle_context_service import (
    load_bundle_persona_chunks,
    retrieve_bundle_persona_chunks,
)
from app.services.retrieval import retrieve_similar, retrieve_weighted
from app.services.workspace_snapshot_store import get_snapshot_payload


LEGACY_PERSONA_SOURCES = (
    "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
    "JOHNNIE_FIELDS_PERSONA.md",
)
CANONICAL_EXAMPLE_BUNDLE_PATHS = {
    "prompts/content_examples.md",
    "prompts/taste_examples.md",
}
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
AUDIENCE_DOMAIN_PRIORITY = {
    "tech_ai": {"ai_systems", "operator_workflows", "content_strategy", "identity_core"},
    "leadership": {"leadership", "systems_operations", "operator_workflows", "identity_core"},
    "education_admissions": {"education_admissions", "neurodivergent_advocacy", "identity_core"},
    "fashion": {"fashion_identity", "content_strategy", "identity_core"},
    "neurodivergent": {"neurodivergent_advocacy", "education_admissions", "identity_core"},
    "entrepreneurs": {"ai_systems", "content_strategy", "operator_workflows", "identity_core"},
}
GENERIC_PROOF_LABELS = {
    "anecdote",
    "claim",
    "framework",
    "phrase candidate",
    "proof point",
    "promoted item",
    "stat",
    "talking point",
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
    primary_claims: list[str]
    proof_packets: list[str]
    story_beats: list[str]
    disallowed_moves: list[str]
    persona_context_summary: str | None
    content_reservoir_chunks: list[dict[str, Any]] = field(default_factory=list)


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


def _domain_compatibility_score(item: dict[str, Any], *, topic: str, audience: str) -> int:
    metadata = _item_metadata(item)
    primary_text, use_when_text = _split_use_when_text(str(item.get("chunk") or ""))
    focus_terms = _focus_terms(topic, audience)
    focus_score = (_chunk_focus_score(primary_text, focus_terms, topic) * 2) + _chunk_focus_score(use_when_text, focus_terms, topic)
    domain_tags = {str(tag) for tag in metadata.get("domain_tags", []) if tag}
    audience_tags = {str(tag) for tag in metadata.get("audience_tags", []) if tag}
    allowed_domains = AUDIENCE_DOMAIN_PRIORITY.get(audience, set())
    score = focus_score

    if audience in audience_tags:
        score += 2
    if domain_tags & allowed_domains:
        score += 3
    if _passes_audience_anchor_gate(primary_text, audience):
        score += 3
    if bool(metadata.get("artifact_backed")):
        score += 1
    if str(metadata.get("proof_strength") or "").lower() in {"strong", "medium"}:
        score += 1
    return score


def _support_chunk_allowed(item: dict[str, Any], *, topic: str, audience: str) -> bool:
    metadata = _item_metadata(item)
    memory_role = str(metadata.get("memory_role") or "")
    if memory_role == "core":
        return True

    primary_text, _ = _split_use_when_text(str(item.get("chunk") or ""))
    compatibility_score = _domain_compatibility_score(item, topic=topic, audience=audience)
    domain_tags = {str(tag) for tag in metadata.get("domain_tags", []) if tag}
    allowed_domains = AUDIENCE_DOMAIN_PRIORITY.get(audience, set())
    has_allowed_domain = bool(domain_tags & allowed_domains)
    passes_anchor_gate = _passes_audience_anchor_gate(primary_text, audience)
    artifact_backed = bool(metadata.get("artifact_backed"))
    proof_strength = str(metadata.get("proof_strength") or "").lower()

    if audience == "tech_ai":
        if memory_role == "proof":
            return compatibility_score >= 6 and (passes_anchor_gate or has_allowed_domain) and (artifact_backed or proof_strength in {"strong", "medium"})
        if memory_role == "story":
            return compatibility_score >= 7 and passes_anchor_gate and (has_allowed_domain or compatibility_score >= 9)
        if memory_role == "ambient":
            return compatibility_score >= 8 and passes_anchor_gate and has_allowed_domain
        return compatibility_score >= 6 and (passes_anchor_gate or has_allowed_domain)

    if memory_role == "proof":
        return compatibility_score >= 4
    if memory_role == "story":
        return compatibility_score >= 3
    if memory_role == "ambient":
        return compatibility_score >= 3
    return compatibility_score >= 3


def filter_persona_chunks_for_domain(
    persona_chunks: list[dict[str, Any]],
    *,
    topic: str,
    audience: str,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in persona_chunks:
        if _support_chunk_allowed(item, topic=topic, audience=audience):
            filtered.append(item)
    return filtered


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


def _load_content_reservoir_payload() -> dict[str, Any] | None:
    payload = get_snapshot_payload("linkedin-content-os", "content_reservoir")
    if isinstance(payload, dict):
        return payload
    try:
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
            include_workspace_files=False,
            include_doc_entries=False,
        )
    except Exception:
        return None
    payload = snapshot.get("content_reservoir") if isinstance(snapshot, dict) else None
    return payload if isinstance(payload, dict) else None


def _hydrate_content_reservoir_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    hydrated_metadata = metadata if isinstance(metadata, dict) else {}
    return {
        "source_id": item.get("reservoir_id") or item.get("asset_id"),
        "source_file_id": item.get("asset_id"),
        "chunk_index": None,
        "chunk": str(item.get("chunk") or item.get("text") or ""),
        "similarity_score": float(item.get("content_priority") or 0.0),
        "weighted_score": float(item.get("content_priority") or 0.0),
        "persona_tag": str(item.get("persona_tag") or hydrated_metadata.get("persona_tag") or "PHILOSOPHY"),
        "metadata": hydrated_metadata,
    }


def _content_reservoir_lane_bonus(lane: str) -> int:
    return {
        "canon_bridge": 8,
        "proof_point": 6,
        "story_bank": 5,
        "voice_guidance": 4,
        "post_seed": 3,
    }.get(lane, 0)


def retrieve_content_reservoir_chunks(
    *,
    topic: str,
    audience: str,
    category: str,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    payload = _load_content_reservoir_payload()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []

    focus_terms = _focus_terms(topic, audience)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        hydrated = _hydrate_content_reservoir_item(raw_item)
        chunk = str(hydrated.get("chunk") or "")
        if not chunk:
            continue
        primary_text, use_when_text = _split_use_when_text(chunk)
        focus_score = (_chunk_focus_score(primary_text, focus_terms, topic) * 3) + _chunk_focus_score(use_when_text, focus_terms, topic)
        compatibility_score = _domain_compatibility_score(hydrated, topic=topic, audience=audience)
        metadata = _item_metadata(hydrated)
        memory_role = str(metadata.get("memory_role") or "")
        reservoir_lane = str(raw_item.get("reservoir_lane") or metadata.get("content_reservoir_lane") or "")
        score = int(raw_item.get("score") or 0)
        priority = int(raw_item.get("content_priority") or 0)

        composite = priority + (focus_score * 5) + (compatibility_score * 4) + _content_reservoir_lane_bonus(reservoir_lane)
        if category == "personal" and memory_role == "story":
            composite += 6
        if category == "value" and memory_role == "proof":
            composite += 4
        if category == "sales" and reservoir_lane in {"proof_point", "post_seed"}:
            composite += 3

        if composite <= 0:
            continue
        ranked.append((composite, score, hydrated))

    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, item in sorted(ranked, key=lambda entry: (entry[0], entry[1]), reverse=True):
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        curated.append(item)
        if len(curated) >= top_k:
            break
    return curated


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


def retrieve_bundle_example_chunks(
    *,
    topic: str,
    audience: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    focus_terms = _focus_terms(topic, audience)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in load_bundle_persona_chunks():
        metadata = _item_metadata(item)
        bundle_path = str(metadata.get("bundle_path") or "")
        if bundle_path not in CANONICAL_EXAMPLE_BUNDLE_PATHS:
            continue
        primary_text, use_when_text = _split_use_when_text(str(item.get("chunk") or ""))
        score = (_chunk_focus_score(primary_text, focus_terms, topic) * 2) + _chunk_focus_score(use_when_text, focus_terms, topic)
        if score <= 0:
            continue
        normalized = primary_text.lower()
        if normalized.startswith("good examples:"):
            score += 3
        elif normalized.startswith("taste anchors:"):
            score += 4
        elif normalized.startswith("avoid patterns:"):
            score += 1
        ranked.append((score, _hydrate_bundle_chunk(item)))

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


def _dedupe_texts(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = " ".join((item or "").split()).strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def _split_sentences(text: str) -> list[str]:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return []
    return [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", normalized) if segment.strip()]


def _looks_like_heading_sentence(sentence: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", (sentence or "").lower())
    if not tokens or len(tokens) > 6:
        return False
    verbs = {
        "am",
        "are",
        "be",
        "become",
        "becomes",
        "build",
        "builds",
        "can",
        "did",
        "do",
        "does",
        "fail",
        "fails",
        "had",
        "has",
        "have",
        "is",
        "keep",
        "keeps",
        "made",
        "make",
        "makes",
        "move",
        "moves",
        "read",
        "reads",
        "should",
        "treats",
        "turn",
        "turns",
        "use",
        "uses",
        "value",
        "values",
        "was",
        "were",
        "will",
    }
    return not any(token in verbs for token in tokens)


def _extract_label_from_chunk(chunk: str) -> str:
    primary_text, _ = _split_use_when_text(chunk)
    cleaned = primary_text.replace("Public-facing proof:", " ").replace("Proof:", " ").replace("Evidence:", " ")
    sentences = _split_sentences(cleaned)
    if not sentences:
        return cleaned.strip(" .")
    first_sentence = sentences[0].strip(" .")
    if first_sentence.lower() in GENERIC_PROOF_LABELS:
        if len(sentences) >= 2:
            return sentences[1].strip(" .")
        return ""
    return first_sentence


def _extract_claim_text_from_chunk(chunk: str) -> str:
    primary_text, _ = _split_use_when_text(chunk)
    cleaned = re.split(r"\b(?:Value|Proof|Evidence|Public-facing proof):", primary_text, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r"^(?:Guardrails|Wins?|Core Tone|Sentence Rhythm|Strategic Framing Preferences|Recognition And Heat|Signature Openers|Signature Pivots|Anti-Patterns):\s*", "", cleaned, flags=re.IGNORECASE)
    sentences = _split_sentences(cleaned)
    if not sentences:
        return ""
    if sentences[0].strip(" .").lower() in GENERIC_PROOF_LABELS:
        return sentences[1].strip(" .") + "." if len(sentences) >= 2 else ""
    if len(sentences) >= 2 and _looks_like_heading_sentence(sentences[0]):
        return sentences[1].strip(" .") + "."
    if len(sentences) >= 2 and len(sentences[0].split()) <= 8:
        return f"{sentences[0].strip(' .')}. {sentences[1].strip(' .')}."
    return sentences[0].strip(" .") + "."


def _is_metric_led_claim(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip().lower()
    if not normalized:
        return False
    if re.search(r"\b\d", normalized):
        return True
    return any(
        phrase in normalized
        for phrase in (
            "% more likely",
            "x more likely",
            "trust ai outputs",
            "trust ai output",
            "5.2x",
            "65%",
        )
    )


def _claim_candidate_score(
    item: dict[str, Any],
    text: str,
    *,
    source_priority: int,
    focus_terms: set[str],
    topic: str,
    audience: str,
) -> int:
    metadata = _item_metadata(item)
    memory_role = str(metadata.get("memory_role") or "ambient")
    claim_type = str(metadata.get("claim_type") or "").lower()
    score = source_priority
    if memory_role == "core":
        score += 8
    elif memory_role == "proof":
        score += 6
    elif memory_role == "story":
        score += 2
    if claim_type:
        score += 5
        if claim_type in {"contrarian", "operational", "philosophical", "positioning"}:
            score += 2
    if not _is_metric_led_claim(text):
        score += 7
    else:
        score -= 4
    normalized = text.lower()
    focus_score = _chunk_focus_score(text, focus_terms, topic)
    score += focus_score * 3
    audience_domains = AUDIENCE_DOMAIN_PRIORITY.get(audience, set())
    domain_tags = {str(tag) for tag in metadata.get("domain_tags", []) if tag}
    if domain_tags & audience_domains:
        score += 4
    operator_terms = ("agent", "prompt", "workflow", "clarity", "operator", "system", "orchestration", "brain", "ops", "planner", "routing")
    if any(term in normalized for term in operator_terms):
        score += 3
    if audience == "tech_ai":
        if any(term in normalized for term in operator_terms):
            score += 4
        else:
            score -= 8
        if "leadership" in normalized and not any(term in normalized for term in operator_terms):
            score -= 4
        if "people, process, and culture" in normalized and not any(term in normalized for term in operator_terms):
            score -= 5
    if bool(metadata.get("artifact_backed")) and str(metadata.get("proof_strength") or "").lower() in {"strong", "medium"}:
        score += 2
    if 6 <= len(text.split()) <= 28:
        score += 1
    return score


def _extract_primary_claims(
    *,
    core_topic_chunks: list[dict[str, Any]],
    topic_anchor_chunks: list[dict[str, Any]],
    proof_anchor_chunks: list[dict[str, Any]],
    grounding_mode: str,
    topic: str = "",
    audience: str = "general",
) -> list[str]:
    ranked: list[tuple[int, str]] = []
    focus_terms = _focus_terms(topic, audience)
    ordered_groups = [(core_topic_chunks, 16), (topic_anchor_chunks, 10)]
    if grounding_mode == "proof_ready":
        ordered_groups.append((proof_anchor_chunks, 6))
    else:
        ordered_groups.append((proof_anchor_chunks, 5))
    for source_chunks, source_priority in ordered_groups:
        for item in source_chunks:
            text = _extract_claim_text_from_chunk(str(item.get("chunk") or ""))
            if not text:
                continue
            ranked.append(
                (
                    _claim_candidate_score(
                        item,
                        text,
                        source_priority=source_priority,
                        focus_terms=focus_terms,
                        topic=topic,
                        audience=audience,
                    ),
                    text,
                )
            )
    candidates: list[str] = []
    for _, text in sorted(ranked, key=lambda entry: entry[0], reverse=True):
        candidates.append(text)
    return _dedupe_texts(candidates, limit=3)


def _proof_packet_evidence_text(packet: str) -> str:
    parts = (packet or "").split("->", 1)
    text = parts[1].strip() if len(parts) == 2 else (packet or "").strip()
    text, _ = _split_use_when_text(text)
    return text.strip()


def _build_persona_context_summary(
    *,
    primary_claims: list[str],
    proof_packets: list[str],
    persona_chunks: list[dict[str, Any]],
    topic: str,
) -> str | None:
    if primary_claims:
        summary = primary_claims[0]
        if proof_packets:
            proof_text = _proof_packet_evidence_text(proof_packets[0]).strip()
            if proof_text and proof_text.lower() != summary.strip().lower():
                summary = f"{summary} Proof: {proof_text}"
        return summary[:220]
    return summarize_persona_context(persona_chunks, topic)


def _extract_proof_packets(proof_anchor_chunks: list[dict[str, Any]]) -> list[str]:
    packets: list[str] = []
    for item in proof_anchor_chunks:
        chunk = str(item.get("chunk") or "")
        label = _extract_label_from_chunk(chunk)
        proof_segments: list[str] = []
        for marker in ("Public-facing proof:", "Proof:", "Evidence:"):
            if marker.lower() in chunk.lower():
                split_parts = re.split(marker, chunk, maxsplit=1, flags=re.IGNORECASE)
                if len(split_parts) == 2:
                    proof_text, _ = _split_use_when_text(split_parts[1])
                    proof_segments.extend(_split_sentences(proof_text))
        if not proof_segments:
            proof_segments = [
                sentence
                for sentence in _split_sentences(chunk)
                if _proof_signal_score(sentence) > 0 or bool(re.search(r"\b\d[\d.,x%$m]*\b", sentence))
            ]
        if not proof_segments:
            continue
        proof_text = proof_segments[0].strip(" .") + "."
        if not label or label.lower() == proof_segments[0].strip(" .").lower():
            packets.append(proof_text)
            continue
        packets.append(f"{label} -> {proof_text}")
    return _dedupe_texts(packets, limit=4)


def _extract_story_beats(story_anchor_chunks: list[dict[str, Any]]) -> list[str]:
    beats: list[str] = []
    for item in story_anchor_chunks:
        primary_text, _ = _split_use_when_text(str(item.get("chunk") or ""))
        sentences = _split_sentences(primary_text)
        if sentences:
            beats.append(sentences[0].strip(" .") + ".")
    return _dedupe_texts(beats, limit=3)


def _merge_unique_chunks(*groups: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = _normalized_chunk_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def _build_disallowed_moves(*, audience: str, grounding_mode: str) -> list[str]:
    moves = [
        "Do not invent outcomes, causal claims, or cleaner metrics than the approved proof actually states.",
        "Do not borrow names, employers, systems, or projects that are not present in the approved claims, proof packets, or story beats.",
    ]
    if audience == "tech_ai":
        moves.extend(
            [
                "Do not drift into generic leadership, admissions, school-process, or community anecdotes for AI/operator posts.",
                "Do not use generic AI filler like seamless integration, unlock potential, efficiency skyrocketed, or game changer.",
            ]
        )
    if grounding_mode == "principle_only":
        moves.append("Do not use named metrics, case studies, employers, or systems unless they appear directly in the approved primary claims.")
    return moves


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
    audience: str,
) -> tuple[str, str]:
    strong_or_medium_proof = [
        item
        for item in proof_anchor_chunks
        if str(_item_metadata(item).get("proof_strength") or "").lower() in {"strong", "medium"}
        or bool(_item_metadata(item).get("artifact_backed"))
    ]
    if strong_or_medium_proof:
        return ("proof_ready", "Artifact-backed proof is available, so the post can lead with real evidence.")
    story_supported = [
        item
        for item in story_anchor_chunks
        if _proof_signal_score(str(item.get("chunk") or "")) > 0 or audience != "tech_ai"
    ]
    if story_supported:
        return ("story_supported", "Relevant lived experience exists, but proof is weaker than the story support.")
    if audience == "tech_ai":
        return ("principle_only", "No AI/operator proof survived the domain gate, so the post should stay principle-led.")
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
        modes.extend(["contrarian_reframe", "operator_lesson"])
        if grounding_mode == "proof_ready" or proof_anchor_chunks:
            modes.append("warning")
        else:
            modes.append("agree_and_extend")
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
    source_mode: str = "persona_only",
) -> ContentGenerationContext:
    del tone

    normalized_source_mode = " ".join((source_mode or "persona_only").lower().split())
    if normalized_source_mode not in {"persona_only", "selected_source", "recent_signals"}:
        normalized_source_mode = "persona_only"
    context_text = " ".join((context or "").split()).strip()
    context_for_query = context_text[:280]

    persona_query_parts = ["persona voice style", topic, category, audience, "content writing"]
    if context_for_query:
        persona_query_parts.append(context_for_query)
    persona_query = " ".join(part for part in persona_query_parts if part).strip()
    persona_embedding = embed_text(persona_query)
    canonical_bundle_chunks = filter_persona_chunks_for_domain(
        [_hydrate_bundle_chunk(item) for item in load_bundle_persona_chunks()],
        topic=topic,
        audience=audience,
    )

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
    content_reservoir_chunks: list[dict[str, Any]] = []
    retrieved_persona_chunks = []
    if normalized_source_mode == "recent_signals":
        content_reservoir_chunks = retrieve_content_reservoir_chunks(
            topic=topic,
            audience=audience,
            category=category,
            top_k=8,
        )
        if content_reservoir_chunks:
            retrieved_persona_chunks = content_reservoir_chunks
        else:
            retrieved_persona_chunks = retrieve_weighted(
                user_id=user_id,
                query_embedding=persona_embedding,
                category=category,
                channel=content_type,
                top_k=8,
            )
    elif normalized_source_mode == "selected_source":
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
    persona_chunks = filter_persona_chunks_for_domain(
        persona_chunks,
        topic=topic,
        audience=audience,
    )
    core_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "core"]
    proof_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "proof"]
    story_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "story"]
    ambient_chunks = [item for item in persona_chunks if str(_item_metadata(item).get("memory_role") or "") == "ambient"]

    topic_anchor_chunks = select_topic_anchor_chunks(
        persona_chunks,
        topic=topic,
        audience=audience,
        limit=4,
    )
    core_topic_chunks = select_topic_anchor_chunks(
        core_chunks,
        topic=topic,
        audience=audience,
        limit=3,
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
    canonical_core_topic_chunks = select_topic_anchor_chunks(
        [item for item in canonical_bundle_chunks if str(_item_metadata(item).get("memory_role") or "") == "core"],
        topic=topic,
        audience=audience,
        limit=3,
    )
    core_topic_chunks = _merge_unique_chunks(canonical_core_topic_chunks, core_topic_chunks, limit=4)
    canonical_proof_anchor_chunks = select_proof_anchor_chunks(
        [
            item
            for item in canonical_bundle_chunks
            if str(_item_metadata(item).get("memory_role") or "") in {"core", "proof"}
        ],
        topic=topic,
        audience=audience,
        limit=4,
    )
    proof_anchor_chunks = _merge_unique_chunks(canonical_proof_anchor_chunks, proof_anchor_chunks, limit=4)
    print(
        "[content_context] "
        f"bundle={len(bundle_persona_chunks)} "
        f"legacy={len(legacy_support_chunks)} "
        f"reservoir={len(content_reservoir_chunks)} "
        f"retrieved={len(retrieved_persona_chunks)} "
        f"curated={len(persona_chunks)} "
        f"core={len(core_chunks)} "
        f"proof={len(proof_chunks)} "
        f"story={len(story_chunks)} "
        f"topic={len(topic_anchor_chunks)} "
        f"proof_anchors={len(proof_anchor_chunks)} "
        f"story_anchors={len(story_anchor_chunks)}",
        flush=True,
    )

    examples_query = f"high performing content example {content_type} {category} {topic}"
    examples_embedding = embed_text(examples_query)
    bundle_example_chunks = retrieve_bundle_example_chunks(
        topic=topic,
        audience=audience,
        limit=2,
    )
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
    if bundle_example_chunks:
        merged_examples: list[dict[str, Any]] = []
        seen_example_keys: set[str] = set()
        for item in bundle_example_chunks + example_chunks:
            key = _normalized_chunk_key(item)
            if not key or key in seen_example_keys:
                continue
            seen_example_keys.add(key)
            merged_examples.append(item)
            if len(merged_examples) >= 3:
                break
        example_chunks = merged_examples

    grounding_mode, grounding_reason = score_grounding_confidence(
        proof_anchor_chunks=proof_anchor_chunks,
        story_anchor_chunks=story_anchor_chunks,
        audience=audience,
    )
    framing_modes = recommend_framing_modes(
        topic=topic,
        audience=audience,
        category=category,
        grounding_mode=grounding_mode,
        proof_anchor_chunks=proof_anchor_chunks,
        story_anchor_chunks=story_anchor_chunks,
    )
    primary_claims = _extract_primary_claims(
        core_topic_chunks=core_topic_chunks,
        topic_anchor_chunks=topic_anchor_chunks,
        proof_anchor_chunks=proof_anchor_chunks,
        grounding_mode=grounding_mode,
        topic=topic,
        audience=audience,
    )
    proof_packets = _extract_proof_packets(proof_anchor_chunks)
    story_beats = _extract_story_beats(story_anchor_chunks)
    disallowed_moves = _build_disallowed_moves(
        audience=audience,
        grounding_mode=grounding_mode,
    )

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
        primary_claims=primary_claims,
        proof_packets=proof_packets,
        story_beats=story_beats,
        disallowed_moves=disallowed_moves,
        persona_context_summary=_build_persona_context_summary(
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            persona_chunks=persona_chunks,
            topic=topic,
        ),
        content_reservoir_chunks=content_reservoir_chunks,
    )
