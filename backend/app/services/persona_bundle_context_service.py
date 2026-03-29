from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.services.embedders import embed_text, embed_texts
from app.services.persona_bundle_writer import resolve_persona_bundle_root
from app.services.retrieval import get_combined_weights


TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_CLAIMS = "identity/claims.md"
TARGET_BIO = "identity/bio_facts.md"
TARGET_PHILOSOPHY = "identity/philosophy.md"
TARGET_COMMUNICATION = "identity/audience_communication.md"
TARGET_DECISION_PRINCIPLES = "identity/decision_principles.md"
TARGET_GUARDRAILS = "prompts/content_guardrails.md"
TARGET_OUTREACH = "prompts/outreach_playbook.md"
TARGET_PILLARS = "prompts/content_pillars.md"
TARGET_CHANNELS = "prompts/channel_playbooks.md"
TARGET_RESUME = "history/resume.md"
TARGET_TIMELINE = "history/timeline.md"
TARGET_INITIATIVES = "history/initiatives.md"
TARGET_WINS = "history/wins.md"
TARGET_STORIES = "history/story_bank.md"

TAG_BY_TARGET = {
    TARGET_VOICE: "VOICE_PATTERNS",
    TARGET_CLAIMS: "BIO_FACTS",
    TARGET_BIO: "BIO_FACTS",
    TARGET_PHILOSOPHY: "PHILOSOPHY",
    TARGET_COMMUNICATION: "VOICE_PATTERNS",
    TARGET_DECISION_PRINCIPLES: "PHILOSOPHY",
    TARGET_GUARDRAILS: "PHILOSOPHY",
    TARGET_OUTREACH: "VOICE_PATTERNS",
    TARGET_PILLARS: "PHILOSOPHY",
    TARGET_CHANNELS: "VOICE_PATTERNS",
    TARGET_RESUME: "EXPERIENCES",
    TARGET_TIMELINE: "EXPERIENCES",
    TARGET_INITIATIVES: "VENTURES",
    TARGET_WINS: "EXPERIENCES",
    TARGET_STORIES: "EXPERIENCES",
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


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


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
            {
                "source_id": f"bundle:{rel_path}:{idx}",
                "source_file_id": rel_path,
                "chunk_index": idx,
                "chunk": chunk,
                "persona_tag": _claim_tag(claim_type),
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "file_name": rel_path,
                    "persona_tag": _claim_tag(claim_type),
                    "bundle_path": rel_path,
                },
            }
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
                    {
                        "source_id": f"bundle:{rel_path}:{idx}",
                        "source_file_id": rel_path,
                        "chunk_index": idx,
                        "chunk": chunk,
                        "persona_tag": "EXPERIENCES",
                        "metadata": {
                            "source": "canonical persona bundle",
                            "source_kind": "canonical_bundle",
                            "file_name": rel_path,
                            "persona_tag": "EXPERIENCES",
                            "bundle_path": rel_path,
                        },
                    }
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
            {
                "source_id": f"bundle:{rel_path}:{idx}",
                "source_file_id": rel_path,
                "chunk_index": idx,
                "chunk": chunk,
                "persona_tag": "EXPERIENCES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "file_name": rel_path,
                    "persona_tag": "EXPERIENCES",
                    "bundle_path": rel_path,
                },
            }
        )
    return items


def _iter_initiative_chunks(text: str, rel_path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    title = ""
    purpose = ""
    value = ""
    proof = ""
    idx = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if title and purpose:
                chunk = _normalize_inline(f"{title}. {purpose} Value: {value} Proof: {proof}")
                items.append(
                    {
                        "source_id": f"bundle:{rel_path}:{idx}",
                        "source_file_id": rel_path,
                        "chunk_index": idx,
                        "chunk": chunk,
                        "persona_tag": "VENTURES",
                        "metadata": {
                            "source": "canonical persona bundle",
                            "source_kind": "canonical_bundle",
                            "file_name": rel_path,
                            "persona_tag": "VENTURES",
                            "bundle_path": rel_path,
                        },
                    }
                )
                idx += 1
            title = line.replace("## ", "", 1).strip()
            purpose = ""
            value = ""
            proof = ""
            continue
        if line.startswith("- Purpose:"):
            purpose = _clean_line(line.replace("- Purpose:", "", 1))
        elif line.startswith("- Value to persona:"):
            value = _clean_line(line.replace("- Value to persona:", "", 1))
        elif line.startswith("- Public-facing proof:"):
            proof = _clean_line(line.replace("- Public-facing proof:", "", 1))
    if title and purpose:
        chunk = _normalize_inline(f"{title}. {purpose} Value: {value} Proof: {proof}")
        items.append(
            {
                "source_id": f"bundle:{rel_path}:{idx}",
                "source_file_id": rel_path,
                "chunk_index": idx,
                "chunk": chunk,
                "persona_tag": "VENTURES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "file_name": rel_path,
                    "persona_tag": "VENTURES",
                    "bundle_path": rel_path,
                },
            }
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
            {
                "source_id": f"bundle:{rel_path}:{idx}",
                "source_file_id": rel_path,
                "chunk_index": idx,
                "chunk": chunk,
                "persona_tag": tag,
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "file_name": rel_path,
                    "persona_tag": tag,
                    "bundle_path": rel_path,
                },
            }
        )
        idx += 1
    return items


def load_bundle_persona_chunks() -> list[dict[str, Any]]:
    bundle_root = resolve_persona_bundle_root()
    if not bundle_root.exists():
        return []

    rel_paths = [
        TARGET_VOICE,
        TARGET_CLAIMS,
        TARGET_BIO,
        TARGET_PHILOSOPHY,
        TARGET_COMMUNICATION,
        TARGET_DECISION_PRINCIPLES,
        TARGET_GUARDRAILS,
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
    return chunks


def retrieve_bundle_persona_chunks(
    *,
    query_text: str | None = None,
    query_embedding: list[float] | None = None,
    category: str = "value",
    channel: str = "linkedin_post",
    top_k: int = 7,
) -> list[dict[str, Any]]:
    items = load_bundle_persona_chunks()
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

    results: list[dict[str, Any]] = []
    for item, weighted_score, raw_score in ranked[:top_k]:
        hydrated = dict(item)
        hydrated["similarity_score"] = float(raw_score)
        hydrated["weighted_score"] = float(weighted_score)
        results.append(hydrated)
    return results
