from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any

from app.services.embedders import embed_text
from app.services.firestore_client import get_firestore_client
from app.services.content_release_policy_service import (
    build_content_release_policy,
    build_public_safe_primary_claims,
    build_public_safe_proof_packets,
    build_public_safe_story_beats,
    render_policy_approved_primary_claims,
    render_policy_approved_proof_packets,
    render_policy_approved_story_beats,
)
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
SNAPSHOT_STORE_ENV_KEYS = (
    "OPEN_BRAIN_DATABASE_URL",
    "BRAIN_VECTOR_DATABASE_URL",
    "DATABASE_URL",
    "DATABASE_PUBLIC_URL",
)
AUDIENCE_FOCUS_TERMS = {
    "tech_ai": {"ai", "agent", "agents", "automation", "operator", "operators", "workflow", "workflows", "prompt", "prompting", "system", "systems", "shipping", "builder", "builders"},
    "leadership": {"leadership", "leaders", "manager", "managers", "team", "teams", "coaching", "culture", "clarity", "decision", "decisions"},
    "leadership_management": {"leadership", "leaders", "manager", "managers", "team", "teams", "coaching", "culture", "clarity", "decision", "decisions", "people", "behavior", "change", "adoption"},
    "education_admissions": {"education", "admissions", "enrollment", "families", "students", "referral", "school", "schools", "trust"},
    "fashion": {"fashion", "style", "closet", "wardrobe", "outfit", "confidence"},
    "neurodivergent": {"neurodivergent", "learning", "students", "families", "support", "fit"},
    "entrepreneurs": {"build", "building", "founder", "founders", "product", "shipping", "market", "customers"},
}
TOPIC_FOCUS_BOOSTS = {
    "workflow clarity": {"workflow", "clarity", "process", "processes", "handoff", "handoffs", "alignment", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
    "agent orchestration": {"agent", "agents", "orchestration", "workflow", "workflows", "automation", "prompting", "handoff", "handoffs", "operator", "system", "systems", "brain", "ops", "planner", "briefs", "snapshot", "routing"},
    "ai adoption": {"ai", "adoption", "adopt", "useful", "usage", "workflow", "constraints", "constraint", "operator", "operators", "system", "systems", "handoff", "handoffs", "shared", "state", "behavior"},
    "change management": {"change", "management", "leadership", "leaders", "people", "behavior", "adoption", "adopt", "coaching", "clarity", "execution", "priority", "priorities", "dashboard", "team", "teams"},
}
STRICT_AUDIENCE_ANCHOR_TERMS = {
    "tech_ai": {"ai", "agent", "agents", "automation", "brain", "briefs", "handoff", "handoffs", "operator", "ops", "orchestration", "planner", "prompt", "prompting", "routing", "system", "systems", "workflow", "workflows"},
    "leadership_management": {"leadership", "leaders", "people", "behavior", "change", "team", "teams", "coaching", "adoption", "execution", "clarity"},
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
    "leadership_management": {"leadership", "systems_operations", "operator_workflows", "identity_core"},
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
    raw_primary_claims: list[str] = field(default_factory=list)
    public_safe_primary_claims: list[dict[str, Any]] = field(default_factory=list)
    raw_story_beats: list[str] = field(default_factory=list)
    public_safe_story_beats: list[dict[str, Any]] = field(default_factory=list)
    raw_proof_packets: list[str] = field(default_factory=list)
    public_safe_proof_packets: list[dict[str, Any]] = field(default_factory=list)
    content_release_policy: dict[str, Any] = field(default_factory=dict)
    content_reservoir_chunks: list[dict[str, Any]] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)


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


def _append_quota(
    destination: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    quota: int,
    top_k: int,
    seen: set[str],
    section: str,
) -> None:
    if quota <= 0 or len(destination) >= top_k:
        return
    limit = min(top_k, len(destination) + quota)
    _append_unique(destination, candidates, limit=limit, seen=seen, section=section)


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
    original_source_lane = str(metadata.get("source_lane") or "").strip()
    if original_source_lane and original_source_lane != source_lane:
        metadata.setdefault("origin_source_lane", original_source_lane)
    metadata["source_lane"] = source_lane
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


def _retrieval_support_fallback_allowed(item: dict[str, Any], *, topic: str, audience: str) -> bool:
    metadata = _item_metadata(item)
    if str(metadata.get("source_lane") or "") != "retrieval_support":
        return False
    if str(metadata.get("memory_role") or "") not in {"proof", "story"}:
        return False
    compatibility_score = _domain_compatibility_score(item, topic=topic, audience=audience)
    artifact_backed = bool(metadata.get("artifact_backed"))
    proof_strength = str(metadata.get("proof_strength") or "").lower()
    if audience == "tech_ai":
        return compatibility_score >= 4 and (artifact_backed or proof_strength in {"strong", "medium"})
    return compatibility_score >= 3


def _restore_retrieval_support_chunks(
    persona_chunks: list[dict[str, Any]],
    *,
    retrieved_chunks: list[dict[str, Any]],
    topic: str,
    audience: str,
    top_k: int,
) -> list[dict[str, Any]]:
    if any(str(_item_metadata(item).get("source_lane") or "") == "retrieval_support" for item in persona_chunks):
        return persona_chunks

    hydrated_retrieved = [_hydrate_support_chunk(item, source_lane="retrieval_support") for item in retrieved_chunks]
    promoted = [
        item
        for item in hydrated_retrieved
        if _retrieval_support_fallback_allowed(item, topic=topic, audience=audience)
    ][:2]
    if not promoted:
        return persona_chunks

    core_prefix: list[dict[str, Any]] = []
    remainder = list(persona_chunks)
    while remainder and str(_item_metadata(remainder[0]).get("memory_role") or "") == "core":
        core_prefix.append(remainder.pop(0))

    seen: set[str] = set()
    restored: list[dict[str, Any]] = []
    for item in core_prefix + promoted + remainder:
        key = _normalized_chunk_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        restored.append(item)
        if len(restored) >= top_k:
            break
    return restored


def curate_persona_prompt_chunks(
    *,
    bundle_chunks: list[dict[str, Any]],
    legacy_support_chunks: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
    top_k: int = 9,
    prioritize_retrieval: bool = False,
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
    retrieval_priority_chunks = [
        item
        for item in retrieval_support_chunks
        if str(_item_metadata(item).get("memory_role") or "") in {"proof", "story"}
    ]
    retrieval_secondary_chunks = [
        item
        for item in retrieval_support_chunks
        if str(_item_metadata(item).get("memory_role") or "") not in {"proof", "story"}
    ]

    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    _append_quota(curated, core_chunks, quota=min(4, top_k), top_k=top_k, seen=seen, section=PROMPT_SECTION_CORE)
    if prioritize_retrieval:
        _append_quota(curated, retrieval_priority_chunks, quota=2, top_k=top_k, seen=seen, section=PROMPT_SECTION_RETRIEVAL)
        _append_quota(curated, proof_chunks, quota=2, top_k=top_k, seen=seen, section=PROMPT_SECTION_SUPPORT)
        _append_quota(curated, story_chunks, quota=1, top_k=top_k, seen=seen, section=PROMPT_SECTION_SUPPORT)
        _append_unique(curated, retrieval_priority_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_RETRIEVAL)
        _append_unique(curated, retrieval_secondary_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_RETRIEVAL)
        _append_unique(curated, proof_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_SUPPORT)
        _append_unique(curated, story_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_SUPPORT)
        _append_unique(curated, ambient_bundle_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_SUPPORT)
        _append_unique(curated, legacy_chunks, limit=top_k, seen=seen, section=PROMPT_SECTION_LEGACY)
    else:
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


def _load_content_reservoir_payload(*, allow_runtime_rebuild: bool = True) -> dict[str, Any] | None:
    payload = get_snapshot_payload("linkedin-content-os", "content_reservoir")
    if isinstance(payload, dict) and not allow_runtime_rebuild:
        return payload
    if not allow_runtime_rebuild:
        return None
    try:
        from app.services.workspace_snapshot_service import SNAPSHOT_CONTENT_RESERVOIR, _load_snapshot

        refreshed = _load_snapshot(SNAPSHOT_CONTENT_RESERVOIR)
        if isinstance(refreshed, dict):
            return refreshed
    except Exception:
        pass
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


def _load_source_assets_payload(*, allow_runtime_rebuild: bool = True) -> dict[str, Any] | None:
    payload = get_snapshot_payload("linkedin-content-os", "source_assets")
    if isinstance(payload, dict) and not allow_runtime_rebuild:
        return payload
    if not allow_runtime_rebuild:
        return None
    try:
        from app.services.workspace_snapshot_service import SNAPSHOT_SOURCE_ASSETS, _load_snapshot

        refreshed = _load_snapshot(SNAPSHOT_SOURCE_ASSETS)
        if isinstance(refreshed, dict):
            return refreshed
    except Exception:
        pass
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
    payload = snapshot.get("source_assets") if isinstance(snapshot, dict) else None
    return payload if isinstance(payload, dict) else None


def _source_asset_capture_map(*, allow_runtime_rebuild: bool = True) -> dict[str, str]:
    payload = _load_source_assets_payload(allow_runtime_rebuild=allow_runtime_rebuild)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    capture_map: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        asset_id = " ".join(str(item.get("asset_id") or "").split()).strip()
        if not asset_id:
            continue
        normalized_captured_at = ""
        for field in ("captured_at", "published_at", "updated_at"):
            value = " ".join(str(item.get(field) or "").split()).strip()
            if value:
                normalized_captured_at = value
                break
        if normalized_captured_at:
            capture_map[asset_id] = normalized_captured_at
    return capture_map


def _content_reservoir_recency(raw_item: dict[str, Any], hydrated: dict[str, Any], capture_map: dict[str, str]) -> str:
    metadata = _item_metadata(hydrated)
    direct_fields = (
        raw_item.get("captured_at"),
        raw_item.get("published_at"),
        raw_item.get("updated_at"),
        metadata.get("captured_at"),
        metadata.get("published_at"),
        metadata.get("updated_at"),
    )
    for value in direct_fields:
        normalized = " ".join(str(value or "").split()).strip()
        if normalized:
            return normalized
    asset_id = " ".join(str(raw_item.get("asset_id") or hydrated.get("source_file_id") or "").split()).strip()
    return capture_map.get(asset_id, "")


def _hydrate_content_reservoir_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    hydrated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    captured_at = " ".join(str(item.get("captured_at") or hydrated_metadata.get("captured_at") or "").split()).strip()
    if captured_at:
        hydrated_metadata["captured_at"] = captured_at
    return {
        "source_id": item.get("reservoir_id") or item.get("asset_id"),
        "source_file_id": item.get("asset_id"),
        "chunk_index": None,
        "chunk": str(item.get("chunk") or item.get("text") or ""),
        "similarity_score": float(item.get("content_priority") or 0.0),
        "weighted_score": float(item.get("content_priority") or 0.0),
        "persona_tag": str(item.get("persona_tag") or hydrated_metadata.get("persona_tag") or "PHILOSOPHY"),
        "captured_at": captured_at,
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
    strategy: str = "ranked",
    allow_runtime_rebuild: bool = True,
) -> list[dict[str, Any]]:
    payload = _load_content_reservoir_payload(allow_runtime_rebuild=allow_runtime_rebuild)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return []

    focus_terms = _focus_terms(topic, audience)
    recent_mode = " ".join((strategy or "ranked").lower().split()) == "recent"
    capture_map = _source_asset_capture_map(allow_runtime_rebuild=allow_runtime_rebuild)
    ranked: list[tuple[str, int, int, dict[str, Any]]] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        hydrated = _hydrate_content_reservoir_item(raw_item)
        recency = _content_reservoir_recency(raw_item, hydrated, capture_map)
        if recency:
            hydrated["captured_at"] = recency
            hydrated_metadata = _item_metadata(hydrated)
            hydrated_metadata["captured_at"] = recency
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

        if recent_mode:
            if focus_score <= 0 and compatibility_score <= 0 and composite <= 0:
                continue
            ranked.append((recency, composite, score, hydrated))
            continue

        if composite <= 0:
            continue
        ranked.append((recency, composite, score, hydrated))

    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    sort_key = (
        (lambda entry: (entry[0], entry[1], entry[2]))
        if recent_mode
        else (lambda entry: (entry[1], entry[2], entry[0]))
    )
    for _, _, _, item in sorted(ranked, key=sort_key, reverse=True):
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


def _legacy_embedding_store_available() -> bool:
    try:
        return get_firestore_client() is not None
    except Exception:
        return False


def _snapshot_store_configured() -> bool:
    return any(bool(os.getenv(key)) for key in SNAPSHOT_STORE_ENV_KEYS)


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = " ".join(str(value or "").split()).strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _count_chunk_metadata(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    values: list[str] = []
    for item in items:
        metadata = _item_metadata(item)
        raw_value = metadata.get(key)
        if isinstance(raw_value, list):
            values.extend(str(value) for value in raw_value if str(value).strip())
            continue
        values.append(str(raw_value or ""))
    return _count_values(values)


def _rounded_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, 4)


def _serialize_context_chunk(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _item_metadata(item)
    return {
        "chunk": " ".join(str(item.get("chunk") or "").split()).strip()[:500],
        "source_id": str(item.get("source_id") or ""),
        "source_file_id": str(item.get("source_file_id") or ""),
        "persona_tag": str(item.get("persona_tag") or ""),
        "source_kind": str(metadata.get("source_kind") or ""),
        "source_lane": str(metadata.get("source_lane") or ""),
        "source": str(metadata.get("source") or ""),
        "file_name": str(metadata.get("file_name") or ""),
        "bundle_path": str(metadata.get("bundle_path") or ""),
        "memory_role": str(metadata.get("memory_role") or ""),
        "proof_kind": str(metadata.get("proof_kind") or ""),
        "proof_strength": str(metadata.get("proof_strength") or ""),
        "claim_type": str(metadata.get("claim_type") or ""),
        "artifact_backed": bool(metadata.get("artifact_backed")),
        "usage_modes": [str(value) for value in (metadata.get("usage_modes") or []) if str(value).strip()],
        "domain_tags": [str(value) for value in (metadata.get("domain_tags") or []) if str(value).strip()],
        "audience_tags": [str(value) for value in (metadata.get("audience_tags") or []) if str(value).strip()],
        "content_reservoir_lane": str(metadata.get("content_reservoir_lane") or ""),
        "content_reservoir_reason": str(metadata.get("content_reservoir_reason") or ""),
        "captured_at": str(item.get("captured_at") or metadata.get("captured_at") or ""),
        "similarity_score": _rounded_float(item.get("similarity_score")),
        "weighted_score": _rounded_float(item.get("weighted_score")),
    }


def _serialize_chunk_group(items: list[dict[str, Any]], *, limit: int) -> dict[str, Any]:
    return {
        "count": len(items),
        "counts_by_memory_role": _count_chunk_metadata(items, "memory_role"),
        "counts_by_source_kind": _count_chunk_metadata(items, "source_kind"),
        "counts_by_source_lane": _count_chunk_metadata(items, "source_lane"),
        "counts_by_proof_strength": _count_chunk_metadata(items, "proof_strength"),
        "items": [_serialize_context_chunk(item) for item in items[:limit]],
    }


def _snapshot_payload_summary(snapshot_type: str) -> dict[str, Any]:
    payload = get_snapshot_payload("linkedin-content-os", snapshot_type)
    items = payload.get("items") if isinstance(payload, dict) else None
    counts = payload.get("counts") if isinstance(payload, dict) and isinstance(payload.get("counts"), dict) else {}
    available = isinstance(payload, dict)
    return {
        "available": available,
        "status": "available" if available else "missing_persisted_snapshot",
        "generated_at": str((payload or {}).get("generated_at") or ""),
        "item_count": len(items) if isinstance(items, list) else 0,
        "counts": counts,
    }


def _runtime_snapshot_payload_summary(snapshot_type: str) -> dict[str, Any]:
    try:
        if snapshot_type == "source_assets":
            from app.services.workspace_snapshot_service import _build_source_assets_payload

            payload = _build_source_assets_payload()
        elif snapshot_type == "content_reservoir":
            from app.services.content_reservoir_service import build_content_reservoir_payload
            from app.services.workspace_snapshot_service import _build_source_assets_payload

            source_assets_payload = _build_source_assets_payload()
            payload = build_content_reservoir_payload(source_assets=source_assets_payload)
        else:
            payload = None
    except Exception as exc:
        return {
            "available": False,
            "status": "runtime_builder_error",
            "generated_at": "",
            "item_count": 0,
            "counts": {},
            "error": str(exc),
        }

    items = payload.get("items") if isinstance(payload, dict) else None
    counts = payload.get("counts") if isinstance(payload, dict) and isinstance(payload.get("counts"), dict) else {}
    available = isinstance(payload, dict)
    return {
        "available": available,
        "status": "available" if available else "runtime_builder_unavailable",
        "generated_at": str((payload or {}).get("generated_at") or ""),
        "item_count": len(items) if isinstance(items, list) else 0,
        "counts": counts,
    }


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
    cleaned = re.sub(
        r"^(?:Guardrails|Wins?|Core Tone|Sentence Rhythm|Strategic Framing Preferences|Recognition And Heat|Signature Openers|Signature Pivots|Anti-Patterns|Reusable Phrases):\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
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


def _claim_text_is_too_thin(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(tokens) <= 2:
        return True
    verbs = {
        "am",
        "are",
        "be",
        "becomes",
        "build",
        "builds",
        "can",
        "changes",
        "creates",
        "fail",
        "fails",
        "forces",
        "gets",
        "gives",
        "is",
        "keeps",
        "lets",
        "makes",
        "means",
        "moves",
        "reads",
        "requires",
        "scales",
        "should",
        "stays",
        "turns",
        "use",
        "uses",
        "works",
    }
    if len(tokens) < 5 and not any(token in verbs for token in tokens):
        return True
    return False


def _extract_primary_claims(
    *,
    core_topic_chunks: list[dict[str, Any]],
    topic_anchor_chunks: list[dict[str, Any]],
    proof_anchor_chunks: list[dict[str, Any]],
    grounding_mode: str,
    topic: str = "",
    audience: str = "general",
    source_mode: str = "persona_only",
) -> list[str]:
    ranked: list[tuple[int, str]] = []
    focus_terms = _focus_terms(topic, audience)
    if source_mode == "persona_only":
        ordered_groups = [(core_topic_chunks, 16), (topic_anchor_chunks, 10)]
        if grounding_mode == "proof_ready":
            ordered_groups.append((proof_anchor_chunks, 6))
        else:
            ordered_groups.append((proof_anchor_chunks, 5))
    else:
        ordered_groups = [(proof_anchor_chunks, 16), (topic_anchor_chunks, 12), (core_topic_chunks, 8)]
    for source_chunks, source_priority in ordered_groups:
        for item in source_chunks:
            metadata = _item_metadata(item)
            if str(metadata.get("claim_type") or "").lower() == "voice":
                continue
            text = _extract_claim_text_from_chunk(str(item.get("chunk") or ""))
            if not text:
                continue
            if _claim_text_is_instructional(text):
                continue
            if _claim_text_is_too_thin(text):
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


def _claim_text_is_instructional(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered.startswith("keep ") and "grounded in lived experience" in lowered and "credible" in lowered:
        return False
    instructional_starts = (
        "avoid ",
        "do not ",
        "don't ",
        "never ",
        "use ",
        "keep ",
        "start ",
        "end ",
        "lead ",
        "sound like ",
        "let ",
        "tie ",
        "preserve ",
        "prefer ",
        "skip ",
        "write ",
        "return ",
        "replace ",
    )
    if lowered.startswith(instructional_starts):
        return True
    return lowered.startswith(("core tone:", "guardrails:", "anti-patterns:", "avoid patterns:"))


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


def _content_reservoir_snapshot_summary() -> dict[str, Any]:
    return _snapshot_payload_summary("content_reservoir")


def _source_assets_snapshot_summary() -> dict[str, Any]:
    return _snapshot_payload_summary("source_assets")


def _runtime_content_reservoir_snapshot_summary() -> dict[str, Any]:
    return _runtime_snapshot_payload_summary("content_reservoir")


def _runtime_source_assets_snapshot_summary() -> dict[str, Any]:
    return _runtime_snapshot_payload_summary("source_assets")


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
    include_audit: bool = False,
    allow_snapshot_rebuild: bool = True,
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
            strategy="recent",
            allow_runtime_rebuild=allow_snapshot_rebuild,
        )
        retrieved_persona_chunks = content_reservoir_chunks
    elif normalized_source_mode == "selected_source":
        content_reservoir_chunks = retrieve_content_reservoir_chunks(
            topic=topic,
            audience=audience,
            category=category,
            top_k=8,
            strategy="ranked",
            allow_runtime_rebuild=allow_snapshot_rebuild,
        )
        retrieved_persona_chunks = content_reservoir_chunks
    persona_chunks = curate_persona_prompt_chunks(
        bundle_chunks=bundle_persona_chunks,
        legacy_support_chunks=legacy_support_chunks,
        retrieved_chunks=retrieved_persona_chunks,
        top_k=9,
        prioritize_retrieval=normalized_source_mode != "persona_only",
    )
    persona_chunks = filter_persona_chunks_for_domain(
        persona_chunks,
        topic=topic,
        audience=audience,
    )
    if normalized_source_mode != "persona_only":
        persona_chunks = _restore_retrieval_support_chunks(
            persona_chunks,
            retrieved_chunks=retrieved_persona_chunks,
            topic=topic,
            audience=audience,
            top_k=9,
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
    if normalized_source_mode == "persona_only":
        core_topic_chunks = _merge_unique_chunks(canonical_core_topic_chunks, core_topic_chunks, limit=4)
    else:
        core_topic_chunks = _merge_unique_chunks(core_topic_chunks, canonical_core_topic_chunks, limit=4)
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
    if normalized_source_mode == "persona_only":
        proof_anchor_chunks = _merge_unique_chunks(canonical_proof_anchor_chunks, proof_anchor_chunks, limit=4)
    else:
        proof_anchor_chunks = _merge_unique_chunks(proof_anchor_chunks, canonical_proof_anchor_chunks, limit=4)
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
    raw_primary_claims = _extract_primary_claims(
        core_topic_chunks=core_topic_chunks,
        topic_anchor_chunks=topic_anchor_chunks,
        proof_anchor_chunks=proof_anchor_chunks,
        grounding_mode=grounding_mode,
        topic=topic,
        audience=audience,
        source_mode=normalized_source_mode,
    )
    content_release_policy = build_content_release_policy(
        content_type=content_type,
        audience=audience,
    )
    public_safe_primary_claims = build_public_safe_primary_claims(
        raw_primary_claims=raw_primary_claims,
        content_type=content_type,
        topic=topic,
        audience=audience,
    )
    primary_claims = (
        render_policy_approved_primary_claims(
            public_safe_primary_claims=public_safe_primary_claims,
            content_type=content_type,
        )
        if content_type == "linkedin_post"
        else raw_primary_claims
    )
    raw_proof_packets = _extract_proof_packets(proof_anchor_chunks)
    public_safe_proof_packets = build_public_safe_proof_packets(
        proof_anchor_chunks=proof_anchor_chunks,
        raw_proof_packets=raw_proof_packets,
        content_type=content_type,
        topic=topic,
        audience=audience,
    )
    proof_packets = (
        render_policy_approved_proof_packets(
            public_safe_proof_packets=public_safe_proof_packets,
            content_type=content_type,
        )
        if content_type == "linkedin_post"
        else raw_proof_packets
    )
    raw_story_beats = _extract_story_beats(story_anchor_chunks)
    public_safe_story_beats = build_public_safe_story_beats(
        raw_story_beats=raw_story_beats,
        content_type=content_type,
        topic=topic,
        audience=audience,
    )
    story_beats = (
        render_policy_approved_story_beats(
            public_safe_story_beats=public_safe_story_beats,
            content_type=content_type,
        )
        if content_type == "linkedin_post"
        else raw_story_beats
    )
    disallowed_moves = _build_disallowed_moves(
        audience=audience,
        grounding_mode=grounding_mode,
    )
    persona_context_summary = _build_persona_context_summary(
        primary_claims=primary_claims,
        proof_packets=proof_packets,
        persona_chunks=persona_chunks,
        topic=topic,
    )
    audit: dict[str, Any] = {}
    if include_audit:
        legacy_store_available = _legacy_embedding_store_available()
        snapshot_store_configured = _snapshot_store_configured()
        source_assets_summary = _source_assets_snapshot_summary()
        content_reservoir_summary = _content_reservoir_snapshot_summary()
        runtime_source_assets_summary = _runtime_source_assets_snapshot_summary()
        runtime_content_reservoir_summary = _runtime_content_reservoir_snapshot_summary()
        audit = {
            "request": {
                "user_id": user_id,
                "topic": topic,
                "context": context_text,
                "content_type": content_type,
                "category": category,
                "audience": audience,
                "source_mode": normalized_source_mode,
            },
            "queries": {
                "persona_query": persona_query,
                "examples_query": examples_query,
                "context_for_query": context_for_query,
            },
            "snapshot_inputs": {
                "source_assets": source_assets_summary,
                "content_reservoir": content_reservoir_summary,
            },
            "runtime_snapshot_inputs": {
                "source_assets": runtime_source_assets_summary,
                "content_reservoir": runtime_content_reservoir_summary,
            },
            "environment": {
                "snapshot_store_configured": snapshot_store_configured,
                "legacy_embedding_store_available": legacy_store_available,
                "legacy_embedding_store_status": "available" if legacy_store_available else "firestore_unavailable",
            },
            "retrieval": {
                "canonical_bundle_filtered": _serialize_chunk_group(canonical_bundle_chunks, limit=12),
                "bundle_candidates": _serialize_chunk_group(bundle_persona_chunks, limit=10),
                "legacy_support_candidates": _serialize_chunk_group(legacy_support_chunks, limit=6),
                "content_reservoir_candidates": _serialize_chunk_group(content_reservoir_chunks, limit=8),
                "curated_persona_chunks": _serialize_chunk_group(persona_chunks, limit=12),
                "core_chunks": _serialize_chunk_group(core_chunks, limit=8),
                "proof_chunks": _serialize_chunk_group(proof_chunks, limit=8),
                "story_chunks": _serialize_chunk_group(story_chunks, limit=8),
                "ambient_chunks": _serialize_chunk_group(ambient_chunks, limit=8),
                "topic_anchor_chunks": _serialize_chunk_group(topic_anchor_chunks, limit=4),
                "proof_anchor_chunks": _serialize_chunk_group(proof_anchor_chunks, limit=4),
                "story_anchor_chunks": _serialize_chunk_group(story_anchor_chunks, limit=3),
                "example_chunks": _serialize_chunk_group(example_chunks, limit=3),
            },
            "selection": {
                "grounding_mode": grounding_mode,
                "grounding_reason": grounding_reason,
                "framing_modes": framing_modes,
                "raw_primary_claims": raw_primary_claims,
                "primary_claims": primary_claims,
                "public_safe_primary_claims": public_safe_primary_claims,
                "raw_proof_packets": raw_proof_packets,
                "proof_packets": proof_packets,
                "public_safe_proof_packets": public_safe_proof_packets,
                "content_release_policy": content_release_policy,
                "raw_story_beats": raw_story_beats,
                "story_beats": story_beats,
                "public_safe_story_beats": public_safe_story_beats,
                "persona_context_summary": persona_context_summary,
                "disallowed_moves": disallowed_moves,
            },
            "warnings": [
                *([] if legacy_store_available else ["Legacy Firestore retrieval is unavailable in this runtime."]),
                *([] if snapshot_store_configured else ["Open Brain snapshot store is not configured in this runtime."]),
                *(
                    []
                    if source_assets_summary.get("available")
                    else ["Persisted source_assets snapshot is unavailable in this runtime."]
                ),
                *(
                    []
                    if content_reservoir_summary.get("available")
                    else ["Persisted content_reservoir snapshot is unavailable in this runtime."]
                ),
                *(
                    []
                    if runtime_source_assets_summary.get("available")
                    else ["Runtime source_assets builder is unavailable in this runtime."]
                ),
                *(
                    []
                    if runtime_content_reservoir_summary.get("available")
                    else ["Runtime content_reservoir builder is unavailable in this runtime."]
                ),
            ],
        }

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
        persona_context_summary=persona_context_summary,
        raw_primary_claims=raw_primary_claims,
        public_safe_primary_claims=public_safe_primary_claims,
        raw_story_beats=raw_story_beats,
        public_safe_story_beats=public_safe_story_beats,
        raw_proof_packets=raw_proof_packets,
        public_safe_proof_packets=public_safe_proof_packets,
        content_release_policy=content_release_policy,
        content_reservoir_chunks=content_reservoir_chunks,
        audit=audit,
    )
