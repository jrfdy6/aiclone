from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.services.embedders import embed_text, embed_texts
from app.services.persona_bundle_writer import resolve_persona_bundle_root
from app.services.persona_promotion_service import build_committed_persona_overlay
from app.services.retrieval import get_combined_weights

_METRIC_TEXT_RE = re.compile(r"\b\d+(?:\.\d+)?(?:x|%|k|m|b)?\b", re.IGNORECASE)


TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_CLAIMS = "identity/claims.md"
TARGET_BIO = "identity/bio_facts.md"
TARGET_PHILOSOPHY = "identity/philosophy.md"
TARGET_COMMUNICATION = "identity/audience_communication.md"
TARGET_DECISION_PRINCIPLES = "identity/decision_principles.md"
TARGET_GUARDRAILS = "prompts/content_guardrails.md"
TARGET_CONTENT_EXAMPLES = "prompts/content_examples.md"
TARGET_OUTREACH = "prompts/outreach_playbook.md"
TARGET_PILLARS = "prompts/content_pillars.md"
TARGET_CHANNELS = "prompts/channel_playbooks.md"
TARGET_RESUME = "history/resume.md"
TARGET_TIMELINE = "history/timeline.md"
TARGET_INITIATIVES = "history/initiatives.md"
TARGET_WINS = "history/wins.md"
TARGET_STORIES = "history/story_bank.md"
GENERIC_PROMOTION_LABELS = {
    "anecdote",
    "claim",
    "framework",
    "phrase candidate",
    "proof point",
    "promoted item",
    "stat",
    "talking point",
}

TAG_BY_TARGET = {
    TARGET_VOICE: "VOICE_PATTERNS",
    TARGET_CLAIMS: "BIO_FACTS",
    TARGET_BIO: "BIO_FACTS",
    TARGET_PHILOSOPHY: "PHILOSOPHY",
    TARGET_COMMUNICATION: "VOICE_PATTERNS",
    TARGET_DECISION_PRINCIPLES: "PHILOSOPHY",
    TARGET_GUARDRAILS: "PHILOSOPHY",
    TARGET_CONTENT_EXAMPLES: "LINKEDIN_EXAMPLES",
    TARGET_OUTREACH: "VOICE_PATTERNS",
    TARGET_PILLARS: "PHILOSOPHY",
    TARGET_CHANNELS: "VOICE_PATTERNS",
    TARGET_RESUME: "EXPERIENCES",
    TARGET_TIMELINE: "EXPERIENCES",
    TARGET_INITIATIVES: "VENTURES",
    TARGET_WINS: "EXPERIENCES",
    TARGET_STORIES: "EXPERIENCES",
}

CORE_TARGETS = {
    TARGET_VOICE,
    TARGET_CLAIMS,
    TARGET_PHILOSOPHY,
    TARGET_COMMUNICATION,
    TARGET_DECISION_PRINCIPLES,
    TARGET_GUARDRAILS,
    TARGET_OUTREACH,
    TARGET_PILLARS,
    TARGET_CHANNELS,
}
EXAMPLE_TARGETS = {
    TARGET_CONTENT_EXAMPLES,
}
PROOF_TARGETS = {
    TARGET_INITIATIVES,
    TARGET_WINS,
}
STORY_TARGETS = {
    TARGET_STORIES,
    TARGET_RESUME,
    TARGET_TIMELINE,
}
AMBIENT_TARGETS = {
    TARGET_BIO,
}

DOMAIN_KEYWORDS = {
    "ai_systems": {"agent", "agents", "ai", "automation", "brain", "ops", "orchestration", "planner", "prompt", "prompting", "routing", "system", "systems"},
    "operator_workflows": {"cadence", "clarity", "documentation", "handoff", "handoffs", "operating", "process", "processes", "workflow", "workflows"},
    "leadership": {"adoption", "coach", "coaching", "culture", "leadership", "manager", "managers", "stakeholder", "stakeholders", "team", "teams"},
    "education_admissions": {"admissions", "enrollment", "family", "families", "fordham", "fusion", "howard", "msw", "referral", "school", "schools", "student", "students"},
    "neurodivergent_advocacy": {"learning", "neurodivergent"},
    "fashion_identity": {"closet", "confidence", "fashion", "outfit", "style", "wardrobe"},
    "content_strategy": {"audience", "content", "linkedin", "messaging", "narrative", "outreach", "post", "posts", "voice"},
    "systems_operations": {"migration", "portfolio", "portfolios", "revenue", "salesforce", "technical", "zoom"},
}
AUDIOENCE_BY_DOMAIN = {
    "ai_systems": {"tech_ai", "entrepreneurs"},
    "operator_workflows": {"tech_ai", "leadership", "entrepreneurs"},
    "leadership": {"leadership"},
    "education_admissions": {"education_admissions"},
    "neurodivergent_advocacy": {"education_admissions", "neurodivergent"},
    "fashion_identity": {"fashion"},
    "content_strategy": {"general", "entrepreneurs"},
    "systems_operations": {"leadership", "tech_ai"},
}


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def _normalize_inline(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace("\xa0", " ").split()).strip()


def _clean_line(text: str | None) -> str:
    normalized = _normalize_inline(text)
    if normalized.endswith("."):
        return normalized[:-1]
    return normalized


def _meaningful_title(value: str | None) -> str:
    normalized = _normalize_inline(value)
    if normalized.lower() in GENERIC_PROMOTION_LABELS:
        return ""
    return normalized


def _is_metric_led_text(text: str | None) -> bool:
    normalized = _normalize_inline(text).lower()
    if not normalized:
        return False
    if _METRIC_TEXT_RE.search(normalized):
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


def _include_overlay_item(rel_path: str, item: dict[str, Any]) -> bool:
    if rel_path != TARGET_INITIATIVES:
        return True
    purpose = _normalize_inline(str(item.get("canon_purpose") or item.get("artifact_summary") or ""))
    value = _normalize_inline(
        str(
            item.get("canon_value")
            or item.get("leverage_signal")
            or item.get("capability_signal")
            or item.get("positioning_signal")
            or ""
        )
    )
    proof = _normalize_inline(str(item.get("canon_proof") or item.get("proof_signal") or item.get("evidence") or ""))
    artifact_kind = _normalize_inline(str(item.get("artifact_kind") or ""))
    artifact_ref = _normalize_inline(str(item.get("artifact_ref") or ""))
    gate_decision = _normalize_inline(str(item.get("gate_decision") or ""))
    if gate_decision and gate_decision != "allow":
        return False
    if not purpose or not value or not proof:
        return False
    if artifact_kind == "metric_or_proof_point" and not artifact_ref:
        return False
    if purpose.lower() == proof.lower() and _is_metric_led_text(purpose):
        return False
    return True


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


def _item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _normalized_chunk_key(item: dict[str, Any]) -> str:
    return " ".join(str(item.get("chunk") or "").split()).strip().lower()


def _infer_memory_role(rel_path: str) -> str:
    if rel_path in CORE_TARGETS:
        return "core"
    if rel_path in EXAMPLE_TARGETS:
        return "example"
    if rel_path in PROOF_TARGETS:
        return "proof"
    if rel_path in STORY_TARGETS:
        return "story"
    if rel_path in AMBIENT_TARGETS:
        return "ambient"
    return "ambient"


def _infer_domain_tags(rel_path: str, chunk: str) -> list[str]:
    normalized_chunk = " ".join((chunk or "").lower().split())
    tags: set[str] = set()
    if rel_path in CORE_TARGETS:
        tags.add("identity_core")
    for domain_tag, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in normalized_chunk for keyword in keywords):
            tags.add(domain_tag)
    if rel_path == TARGET_STORIES:
        tags.add("lived_experience")
    if rel_path in {TARGET_INITIATIVES, TARGET_WINS}:
        tags.add("public_proof")
    return sorted(tags)


def _infer_audience_tags(domain_tags: list[str]) -> list[str]:
    tags: set[str] = set()
    for domain_tag in domain_tags:
        tags.update(AUDIOENCE_BY_DOMAIN.get(domain_tag, set()))
    if not tags:
        tags.add("general")
    return sorted(tags)


def _infer_proof_kind(rel_path: str) -> str:
    if rel_path == TARGET_CONTENT_EXAMPLES:
        return "style_example"
    if rel_path == TARGET_INITIATIVES:
        return "initiative"
    if rel_path == TARGET_WINS:
        return "win"
    if rel_path == TARGET_STORIES:
        return "story"
    if rel_path == TARGET_CLAIMS:
        return "claim"
    if rel_path == TARGET_VOICE:
        return "voice_pattern"
    if rel_path in {TARGET_PHILOSOPHY, TARGET_DECISION_PRINCIPLES, TARGET_GUARDRAILS, TARGET_PILLARS}:
        return "guiding_rule"
    return "support"


def _infer_proof_strength(rel_path: str, chunk: str, *, artifact_backed: bool) -> str:
    normalized_chunk = " ".join((chunk or "").lower().split())
    if rel_path in PROOF_TARGETS and artifact_backed:
        return "strong"
    if rel_path == TARGET_CLAIMS and "evidence:" in normalized_chunk:
        return "medium"
    if rel_path in STORY_TARGETS:
        return "medium"
    if rel_path in CORE_TARGETS:
        return "none"
    return "weak"


def _infer_artifact_backed(rel_path: str, chunk: str) -> bool:
    normalized_chunk = " ".join((chunk or "").lower().split())
    if rel_path in {TARGET_INITIATIVES, TARGET_WINS}:
        return True
    return any(token in normalized_chunk for token in {"proof:", "public-facing proof:", "$", "%", "launched", "migration", "shipped"})


def _infer_usage_modes(memory_role: str) -> list[str]:
    if memory_role == "core":
        return ["always_on", "topic_anchor"]
    if memory_role == "proof":
        return ["proof_anchor", "topic_anchor"]
    if memory_role == "story":
        return ["story_anchor", "optional_support"]
    if memory_role == "example":
        return ["style_reference"]
    return ["support"]


def _build_chunk_metadata(
    *,
    rel_path: str,
    persona_tag: str,
    chunk: str,
    source_kind: str,
    source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_backed = _infer_artifact_backed(rel_path, chunk)
    domain_tags = _infer_domain_tags(rel_path, chunk)
    metadata: dict[str, Any] = {
        "source": source,
        "source_kind": source_kind,
        "file_name": rel_path,
        "persona_tag": persona_tag,
        "bundle_path": rel_path,
        "memory_role": _infer_memory_role(rel_path),
        "domain_tags": domain_tags,
        "audience_tags": _infer_audience_tags(domain_tags),
        "proof_kind": _infer_proof_kind(rel_path),
        "proof_strength": _infer_proof_strength(rel_path, chunk, artifact_backed=artifact_backed),
        "artifact_backed": artifact_backed,
        "usage_modes": _infer_usage_modes(_infer_memory_role(rel_path)),
    }
    if extra:
        metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata


def _build_chunk_record(
    *,
    source_id: str,
    rel_path: str,
    chunk_index: int,
    chunk: str,
    persona_tag: str,
    source_kind: str,
    source: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_file_id": rel_path,
        "chunk_index": chunk_index,
        "chunk": chunk,
        "persona_tag": persona_tag,
        "metadata": _build_chunk_metadata(
            rel_path=rel_path,
            persona_tag=persona_tag,
            chunk=chunk,
            source_kind=source_kind,
            source=source,
            extra=extra_metadata,
        ),
    }


def _claim_tag(claim_type: str) -> str:
    normalized = _normalize_inline(claim_type).lower()
    if normalized == "philosophical":
        return "PHILOSOPHY"
    if normalized == "positioning":
        return "VENTURES"
    return "BIO_FACTS"


def _iter_claim_chunks(text: str, rel_path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4 or cells[0].lower() == "claim":
            continue
        claim, claim_type, evidence, usage_rule = cells
        chunk = _normalize_inline(f"{claim} Evidence: {evidence} Usage: {usage_rule}")
        if not chunk:
            continue
        items.append(
            _build_chunk_record(
                source_id=f"bundle:{rel_path}:{idx}",
                rel_path=rel_path,
                chunk_index=idx,
                chunk=chunk,
                persona_tag=_claim_tag(claim_type),
                source_kind="canonical_bundle",
                source="canonical persona bundle",
                extra_metadata={"claim_type": _normalize_inline(claim_type).lower()},
            )
        )
    return items


def _iter_story_chunks(text: str, rel_path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    title = ""
    story_type = ""
    use_when = ""
    core_point = ""
    idx = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if title and core_point:
                chunk = _normalize_inline(
                    f"{title}. {core_point} Story type: {story_type} Use when: {use_when}"
                )
                items.append(
                    _build_chunk_record(
                        source_id=f"bundle:{rel_path}:{idx}",
                        rel_path=rel_path,
                        chunk_index=idx,
                        chunk=chunk,
                        persona_tag="EXPERIENCES",
                        source_kind="canonical_bundle",
                        source="canonical persona bundle",
                        extra_metadata={"story_kind": story_type or "general"},
                    )
                )
                idx += 1
            title = line.replace("## ", "", 1).strip()
            story_type = ""
            use_when = ""
            core_point = ""
            continue
        if line.startswith("- Story type:"):
            story_type = _clean_line(line.replace("- Story type:", "", 1))
        elif line.startswith("- Use when:"):
            use_when = _clean_line(line.replace("- Use when:", "", 1))
        elif line.startswith("- Core point:"):
            core_point = _clean_line(line.replace("- Core point:", "", 1))
    if title and core_point:
        chunk = _normalize_inline(f"{title}. {core_point} Story type: {story_type} Use when: {use_when}")
        items.append(
            _build_chunk_record(
                source_id=f"bundle:{rel_path}:{idx}",
                rel_path=rel_path,
                chunk_index=idx,
                chunk=chunk,
                persona_tag="EXPERIENCES",
                source_kind="canonical_bundle",
                source="canonical persona bundle",
                extra_metadata={"story_kind": story_type or "general"},
            )
        )
    return items


def _iter_initiative_chunks(text: str, rel_path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    title = ""
    purpose = ""
    value = ""
    proof = ""
    use_when = ""
    idx = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if title and purpose:
                chunk = _normalize_inline(f"{title}. {purpose} Value: {value} Proof: {proof} Use when: {use_when}")
                items.append(
                    _build_chunk_record(
                        source_id=f"bundle:{rel_path}:{idx}",
                        rel_path=rel_path,
                        chunk_index=idx,
                        chunk=chunk,
                        persona_tag="VENTURES",
                        source_kind="canonical_bundle",
                        source="canonical persona bundle",
                    )
                )
                idx += 1
            title = line.replace("## ", "", 1).strip()
            purpose = ""
            value = ""
            proof = ""
            use_when = ""
            continue
        if line.startswith("- Purpose:"):
            purpose = _clean_line(line.replace("- Purpose:", "", 1))
        elif line.startswith("- Value to persona:"):
            value = _clean_line(line.replace("- Value to persona:", "", 1))
        elif line.startswith("- Public-facing proof:"):
            proof = _clean_line(line.replace("- Public-facing proof:", "", 1))
        elif line.startswith("- Use when:"):
            use_when = _clean_line(line.replace("- Use when:", "", 1))
    if title and purpose:
        chunk = _normalize_inline(f"{title}. {purpose} Value: {value} Proof: {proof} Use when: {use_when}")
        items.append(
            _build_chunk_record(
                source_id=f"bundle:{rel_path}:{idx}",
                rel_path=rel_path,
                chunk_index=idx,
                chunk=chunk,
                persona_tag="VENTURES",
                source_kind="canonical_bundle",
                source="canonical persona bundle",
            )
        )
    return items


def _iter_section_chunks(text: str, rel_path: str) -> list[dict[str, Any]]:
    tag = TAG_BY_TARGET.get(rel_path, "PHILOSOPHY")
    items: list[dict[str, Any]] = []
    section_title = ""
    idx = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            section_title = line.replace("## ", "", 1).strip()
            continue
        if not line.startswith("- "):
            continue
        bullet = _normalize_inline(line.replace("- ", "", 1))
        if not bullet or bullet == "-":
            continue
        chunk = bullet if not section_title else f"{section_title}: {bullet}"
        items.append(
            _build_chunk_record(
                source_id=f"bundle:{rel_path}:{idx}",
                rel_path=rel_path,
                chunk_index=idx,
                chunk=chunk,
                persona_tag=tag,
                source_kind="canonical_bundle",
                source="canonical persona bundle",
            )
        )
        idx += 1
    return items


def load_bundle_persona_chunks() -> list[dict[str, Any]]:
    bundle_root = resolve_persona_bundle_root()
    if not bundle_root.exists():
        print(
            f"[bundle_context] root_missing path={bundle_root}",
            flush=True,
        )
        return []

    rel_paths = [
        TARGET_VOICE,
        TARGET_CLAIMS,
        TARGET_BIO,
        TARGET_PHILOSOPHY,
        TARGET_COMMUNICATION,
        TARGET_DECISION_PRINCIPLES,
        TARGET_GUARDRAILS,
        TARGET_CONTENT_EXAMPLES,
        TARGET_OUTREACH,
        TARGET_PILLARS,
        TARGET_CHANNELS,
        TARGET_RESUME,
        TARGET_TIMELINE,
        TARGET_INITIATIVES,
        TARGET_WINS,
        TARGET_STORIES,
    ]
    chunks: list[dict[str, Any]] = []
    for rel_path in rel_paths:
        text = _read_text(bundle_root / rel_path)
        if not text:
            continue
        if rel_path == TARGET_CLAIMS:
            chunks.extend(_iter_claim_chunks(text, rel_path))
        elif rel_path == TARGET_STORIES:
            chunks.extend(_iter_story_chunks(text, rel_path))
        elif rel_path == TARGET_INITIATIVES:
            chunks.extend(_iter_initiative_chunks(text, rel_path))
        else:
            chunks.extend(_iter_section_chunks(text, rel_path))
    if not chunks:
        manifest_exists = (bundle_root / "manifest.json").exists()
        file_count = sum(1 for _ in bundle_root.rglob("*") if _.is_file())
        print(
            f"[bundle_context] root={bundle_root} manifest={manifest_exists} file_count={file_count} parsed_chunks=0",
            flush=True,
        )
    return chunks


def load_committed_overlay_chunks() -> list[dict[str, Any]]:
    try:
        overlay = build_committed_persona_overlay()
    except Exception:
        return []
    if not isinstance(overlay, dict):
        return []
    by_target_file = overlay.get("by_target_file")
    if not isinstance(by_target_file, dict):
        return []

    chunks: list[dict[str, Any]] = []
    for rel_path, items in by_target_file.items():
        if not isinstance(items, list):
            continue
        tag = TAG_BY_TARGET.get(rel_path, "PHILOSOPHY")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if not _include_overlay_item(rel_path, item):
                continue
            if rel_path == TARGET_INITIATIVES:
                title = _meaningful_title(str(item.get("label") or "")) or _meaningful_title(str(item.get("artifact_summary") or ""))
                purpose = _normalize_inline(
                    str(item.get("canon_purpose") or item.get("artifact_summary") or item.get("content") or "")
                )
                value = _normalize_inline(
                    str(
                        item.get("canon_value")
                        or item.get("leverage_signal")
                        or item.get("capability_signal")
                        or item.get("positioning_signal")
                        or ""
                    )
                )
                proof = _normalize_inline(
                    str(item.get("canon_proof") or item.get("proof_signal") or item.get("artifact_summary") or item.get("evidence") or "")
                )
                parts = [part for part in (title, purpose) if part]
                content = ". ".join(parts)
                if value:
                    content = _normalize_inline(f"{content} Value: {value}")
                if proof:
                    content = _normalize_inline(f"{content} Proof: {proof}")
                evidence = proof
            else:
                content = _normalize_inline(str(item.get("content") or ""))
                evidence = _normalize_inline(str(item.get("evidence") or ""))
            if not content:
                continue
            chunk = content if not evidence else f"{content} Evidence: {evidence}"
            chunks.append(
                _build_chunk_record(
                    source_id=f"overlay:{rel_path}:{idx}",
                    rel_path=rel_path,
                    chunk_index=idx,
                    chunk=chunk,
                    persona_tag=tag,
                    source_kind="committed_overlay",
                    source="committed persona overlay",
                    extra_metadata={
                        "artifact_backed": bool(item.get("artifact_summary") or item.get("canon_proof") or item.get("proof_signal")),
                        "proof_strength": str(item.get("proof_strength") or "").lower() or None,
                    },
                )
            )
    return chunks


def retrieve_bundle_persona_chunks(
    *,
    query_text: str | None = None,
    query_embedding: list[float] | None = None,
    category: str = "value",
    channel: str = "linkedin_post",
    top_k: int = 7,
) -> list[dict[str, Any]]:
    overlay_chunks = load_committed_overlay_chunks()
    bundle_chunks = load_bundle_persona_chunks()
    items = overlay_chunks + bundle_chunks
    print(
        f"[bundle_context] overlay={len(overlay_chunks)} bundle={len(bundle_chunks)} total={len(items)}",
        flush=True,
    )
    if not items:
        return []

    if query_embedding is None:
        query_embedding = embed_text(query_text or "")
    if not query_embedding:
        return []

    chunk_texts = [item.get("chunk", "") for item in items]
    embeddings = np.array(embed_texts(chunk_texts), dtype=np.float32)
    query_vector = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
    similarities = cosine_similarity(query_vector, embeddings)[0]

    weights = get_combined_weights(category, channel)
    max_multiplier = 1.8
    diversity_penalty = 0.05
    item_tags = [item.get("persona_tag", "UNTAGGED") for item in items]
    base_scores = []
    for sim, tag in zip(similarities, item_tags):
        multiplier = min(weights.get(tag, 1.0), max_multiplier)
        base_scores.append((sim * multiplier, tag))

    indexed_scores = sorted(enumerate(base_scores), key=lambda entry: entry[1][0], reverse=True)
    final_scores = [0.0] * len(base_scores)
    tag_seen_count: dict[str, int] = {}
    for original_idx, (score, tag) in indexed_scores:
        penalty = tag_seen_count.get(tag, 0) * diversity_penalty
        final_scores[original_idx] = score * (1 - penalty)
        tag_seen_count[tag] = tag_seen_count.get(tag, 0) + 1

    ranked = sorted(
        zip(items, final_scores, similarities),
        key=lambda entry: entry[1],
        reverse=True,
    )

    hydrated_ranked: list[dict[str, Any]] = []
    for item, weighted_score, raw_score in ranked:
        hydrated = dict(item)
        hydrated["similarity_score"] = float(raw_score)
        hydrated["weighted_score"] = float(weighted_score)
        hydrated_ranked.append(hydrated)

    grouped: dict[str, list[dict[str, Any]]] = {
        "core": [],
        "proof": [],
        "story": [],
        "ambient": [],
    }
    for item in hydrated_ranked:
        memory_role = str(_item_metadata(item).get("memory_role") or "ambient")
        grouped.setdefault(memory_role, []).append(item)

    role_targets = {
        "core": min(len(grouped.get("core", [])), max(2, min(4, top_k // 2))),
        "proof": min(len(grouped.get("proof", [])), max(2, min(4, top_k // 2))),
        "story": min(len(grouped.get("story", [])), 1 if top_k < 6 else 2),
        "ambient": min(len(grouped.get("ambient", [])), 1),
    }

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(items: list[dict[str, Any]], *, limit: int | None = None) -> None:
        for entry in items:
            key = _normalized_chunk_key(entry)
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(entry)
            if len(results) >= top_k:
                return
            if limit is not None and sum(1 for item in results if item in items) >= limit:
                return

    for role in ("core", "proof", "story", "ambient"):
        target = role_targets.get(role, 0)
        if target > 0:
            add(grouped.get(role, []), limit=target)
        if len(results) >= top_k:
            return results[:top_k]

    add(hydrated_ranked)
    print(
        f"[bundle_context] returned={len(results)} top_k={top_k}",
        flush=True,
    )
    return results
