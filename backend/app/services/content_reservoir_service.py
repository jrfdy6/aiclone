from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _bucket_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = _clean_text(value) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _derive_reservoir_lane(fragment: dict[str, Any]) -> tuple[str | None, str]:
    recommendation = _clean_text(fragment.get("promotion_recommendation")) or "source_only"
    primary_type = _clean_text(fragment.get("primary_type")) or "signal"
    score = int(fragment.get("score") or 0)
    likely_handoff_lane = _clean_text(fragment.get("likely_handoff_lane")) or "source_only"
    labels = {str(item).strip() for item in (fragment.get("labels") or []) if str(item).strip()}

    if recommendation == "canon_suggestion":
        return ("canon_bridge", "Strong source fragment already flagged as a canon suggestion.")
    if recommendation == "persona_candidate":
        if primary_type == "anecdote":
            return ("story_bank", "Persona-ready anecdote should stay reusable for future story-led posts.")
        return ("proof_point", "Persona-ready lesson should stay available as source-backed proof.")
    if recommendation == "voice_guidance_only":
        return ("voice_guidance", "Voice guidance should remain available as reusable phrasing and cadence support.")
    if primary_type == "anecdote" and score >= 6:
        return ("story_bank", "High-signal anecdote was held back from persona, but it is still valuable as future story material.")
    if primary_type in {"lesson", "worldview"} and score >= 6 and "operational" not in labels:
        return ("proof_point", "Held-back lesson/worldview fragment should remain available as a reusable content proof point.")
    if primary_type in {"quote", "voice_pattern"} and score >= 6:
        return ("voice_guidance", "Sharp quote or phrase should stay available as voice guidance.")
    if likely_handoff_lane == "post_candidate" and score >= 5:
        return ("post_seed", "Post-ready fragment should remain available as future content fuel.")
    if likely_handoff_lane == "brief_only" and primary_type in {"lesson", "worldview"} and score >= 6:
        return ("post_seed", "Brief-only lesson still deserves storage as future post fuel.")
    return (None, "")


def _lane_priority(lane: str) -> int:
    return {
        "canon_bridge": 10,
        "proof_point": 8,
        "story_bank": 7,
        "voice_guidance": 6,
        "post_seed": 5,
    }.get(lane, 0)


def _memory_role_for_lane(lane: str, primary_type: str) -> str:
    if lane == "story_bank" or primary_type == "anecdote":
        return "story"
    if lane in {"proof_point", "canon_bridge"}:
        return "proof"
    return "ambient"


def _persona_tag_for_lane(lane: str, primary_type: str) -> str:
    if lane == "voice_guidance" or primary_type in {"quote", "voice_pattern"}:
        return "VOICE_PATTERNS"
    if lane == "story_bank" or primary_type == "anecdote":
        return "EXPERIENCES"
    if lane == "post_seed":
        return "VENTURES"
    return "PHILOSOPHY"


def _proof_strength_for_lane(lane: str, score: int) -> str:
    if lane == "canon_bridge" or score >= 9:
        return "strong"
    if lane in {"proof_point", "story_bank"} or score >= 7:
        return "medium"
    return "weak"


def _claim_type(primary_type: str, labels: set[str]) -> str:
    if primary_type == "anecdote":
        return "story"
    if "operational" in labels:
        return "operational"
    if primary_type == "worldview":
        return "positioning"
    if primary_type == "lesson":
        return "philosophical"
    if primary_type in {"quote", "voice_pattern"}:
        return "voice"
    return "support"


def _domain_tags(asset: dict[str, Any], fragment: dict[str, Any]) -> list[str]:
    fields = " ".join(
        [
            _clean_text(fragment.get("text")),
            _clean_text(asset.get("title")),
            _clean_text(asset.get("summary")),
            " ".join(str(item) for item in (asset.get("topics") or [])),
            " ".join(str(item) for item in (asset.get("tags") or [])),
        ]
    ).lower()
    tags: list[str] = []
    if _contains_any(fields, {"ai", "agent", "agents", "automation", "prompt", "prompts", "model", "models", "token", "tokens"}):
        tags.append("ai_systems")
    if _contains_any(fields, {"workflow", "workflows", "handoff", "handoffs", "operator", "operators", "routing", "planner", "system", "systems", "execution", "review"}):
        tags.append("operator_workflows")
    if _contains_any(fields, {"ops", "operations", "automation", "pipeline", "process", "processes", "dispatch", "queue"}):
        tags.append("systems_operations")
    if _contains_any(fields, {"content", "post", "posts", "linkedin", "voice", "brand", "audience", "phrase", "phrasing"}):
        tags.append("content_strategy")
    if _contains_any(fields, {"admissions", "enrollment", "student", "students", "families", "family", "school", "schools"}):
        tags.append("education_admissions")
    if _contains_any(fields, {"trust", "judgment", "voice", "identity", "worldview"}):
        tags.append("identity_core")

    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        ordered.append(tag)
    return ordered


def _audience_tags(domain_tags: list[str]) -> list[str]:
    tags: list[str] = []
    domain_tag_set = set(domain_tags)
    if domain_tag_set & {"ai_systems", "operator_workflows", "systems_operations"}:
        tags.append("tech_ai")
    if "systems_operations" in domain_tag_set:
        tags.append("leadership")
    if "education_admissions" in domain_tag_set:
        tags.append("education_admissions")
    if domain_tag_set & {"ai_systems", "content_strategy"}:
        tags.append("entrepreneurs")
    return tags


def _usage_modes_for_role(memory_role: str) -> list[str]:
    if memory_role == "proof":
        return ["proof_anchor", "topic_anchor"]
    if memory_role == "story":
        return ["story_anchor", "optional_support"]
    return ["support"]


def _use_when_text(lane: str) -> str:
    return {
        "canon_bridge": "you need a durable source-backed claim that may later deserve canon.",
        "proof_point": "you need a source-backed lesson, operating principle, or proof point.",
        "story_bank": "you need a lived scene or story beat that makes the post feel human and specific.",
        "voice_guidance": "you need Johnnie-like phrasing, sharper contrast, or sentence rhythm.",
        "post_seed": "you need a future post seed, angle, or hook without forcing it into persona.",
    }.get(lane, "you need reusable source-backed support.")


def _chunk_text(text: str, lane: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    return f"{cleaned} Use when: {_use_when_text(lane)}"


def _content_priority(lane: str, score: int, source_section: str) -> int:
    section_bonus = {
        "summary": 2,
        "structured_summary": 2,
        "lessons_learned": 4,
        "key_anecdotes": 4,
        "reusable_quotes": 3,
        "clean_document": 1,
    }.get(source_section, 0)
    return (_lane_priority(lane) * 10) + score + section_bonus


def _entry_id(asset_id: str, lane: str, text: str) -> str:
    digest = hashlib.md5(_clean_text(text).lower().encode("utf-8")).hexdigest()[:12]
    return f"{asset_id}:{lane}:{digest}"


def _reservoir_entry(asset: dict[str, Any], fragment: dict[str, Any], lane: str, lane_reason: str) -> dict[str, Any]:
    text = _clean_text(fragment.get("text"))
    primary_type = _clean_text(fragment.get("primary_type")) or "signal"
    source_section = _clean_text(fragment.get("source_section")) or "clean_document"
    captured_at = _clean_text(asset.get("captured_at")) or _clean_text(asset.get("published_at")) or _clean_text(asset.get("updated_at"))
    labels = [str(item).strip() for item in (fragment.get("labels") or []) if str(item).strip()]
    label_set = set(labels)
    score = int(fragment.get("score") or 0)
    domain_tags = _domain_tags(asset, fragment)
    audience_tags = _audience_tags(domain_tags)
    memory_role = _memory_role_for_lane(lane, primary_type)
    persona_tag = _persona_tag_for_lane(lane, primary_type)
    proof_strength = _proof_strength_for_lane(lane, score)
    metadata = {
        "file_name": _clean_text(asset.get("title")) or _clean_text(asset.get("source_path")) or _clean_text(asset.get("asset_id")),
        "file_type": _clean_text(asset.get("source_type")) or "long_form_fragment",
        "source": _clean_text(asset.get("source_path")) or _clean_text(asset.get("source_url")) or _clean_text(asset.get("title")),
        "source_lane": "content_reservoir",
        "memory_role": memory_role,
        "usage_modes": _usage_modes_for_role(memory_role),
        "proof_strength": proof_strength,
        "artifact_backed": True,
        "domain_tags": domain_tags,
        "audience_tags": audience_tags,
        "claim_type": _claim_type(primary_type, label_set),
        "content_reservoir_lane": lane,
        "content_reservoir_reason": lane_reason,
        "promotion_recommendation": _clean_text(fragment.get("promotion_recommendation")) or "source_only",
        "promotion_reason": _clean_text(fragment.get("promotion_reason")),
        "source_section": source_section,
        "source_channel": _clean_text(asset.get("source_channel")),
        "origin": _clean_text(asset.get("origin")),
        "origin_detail": _clean_text(asset.get("origin_detail")),
        "source_url": _clean_text(asset.get("source_url")),
        "source_path": _clean_text(asset.get("source_path")),
        "captured_at": captured_at,
        "summary": _clean_text(asset.get("structured_summary")) or _clean_text(asset.get("summary")),
        "persona_tag": persona_tag,
    }
    return {
        "reservoir_id": _entry_id(_clean_text(asset.get("asset_id")), lane, text),
        "asset_id": _clean_text(asset.get("asset_id")),
        "title": _clean_text(asset.get("title")),
        "source_path": _clean_text(asset.get("source_path")),
        "source_url": _clean_text(asset.get("source_url")),
        "source_channel": _clean_text(asset.get("source_channel")),
        "source_type": _clean_text(asset.get("source_type")),
        "origin": _clean_text(asset.get("origin")),
        "origin_detail": _clean_text(asset.get("origin_detail")),
        "captured_at": captured_at,
        "summary": _clean_text(asset.get("summary")),
        "structured_summary": _clean_text(asset.get("structured_summary")),
        "text": text,
        "chunk": _chunk_text(text, lane),
        "source_section": source_section,
        "primary_type": primary_type,
        "labels": labels,
        "score": score,
        "content_priority": _content_priority(lane, score, source_section),
        "likely_handoff_lane": _clean_text(fragment.get("likely_handoff_lane")) or "source_only",
        "promotion_recommendation": _clean_text(fragment.get("promotion_recommendation")) or "source_only",
        "promotion_reason": _clean_text(fragment.get("promotion_reason")),
        "reservoir_lane": lane,
        "reservoir_reason": lane_reason,
        "persona_tag": persona_tag,
        "metadata": metadata,
    }


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = _clean_text(entry.get("text")).lower()
        if not key:
            continue
        existing = deduped.get(key)
        if existing is None or int(entry.get("content_priority") or 0) > int(existing.get("content_priority") or 0):
            deduped[key] = entry
    return list(deduped.values())


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_content_reservoir_payload(*, source_assets: dict[str, Any] | None, per_asset_limit: int = 12) -> dict[str, Any] | None:
    if not isinstance(source_assets, dict):
        return None
    items = source_assets.get("items")
    if not isinstance(items, list):
        return None

    collected: list[dict[str, Any]] = []
    for asset in items:
        if not isinstance(asset, dict):
            continue
        fragments = asset.get("deep_harvest_fragments") or []
        if not isinstance(fragments, list):
            continue
        explicit_entries: list[dict[str, Any]] = []
        inferred_entries: list[dict[str, Any]] = []
        for fragment in fragments:
            if not isinstance(fragment, dict):
                continue
            lane, lane_reason = _derive_reservoir_lane(fragment)
            if not lane:
                continue
            entry = _reservoir_entry(asset, fragment, lane, lane_reason)
            if entry["promotion_recommendation"] != "source_only":
                explicit_entries.append(entry)
            else:
                inferred_entries.append(entry)
        explicit_entries.sort(key=lambda item: (-int(item.get("content_priority") or 0), str(item.get("text") or "").lower()))
        inferred_entries.sort(key=lambda item: (-int(item.get("content_priority") or 0), str(item.get("text") or "").lower()))
        selected = explicit_entries[:per_asset_limit]
        remaining = max(per_asset_limit - len(selected), 0)
        if remaining:
            selected.extend(inferred_entries[:remaining])
        collected.extend(selected)

    deduped = _dedupe_entries(collected)
    deduped.sort(
        key=lambda item: (
            -int(item.get("content_priority") or 0),
            -int(item.get("score") or 0),
            str(item.get("title") or "").lower(),
            str(item.get("text") or "").lower(),
        )
    )

    counts = {
        "total": len(deduped),
        "by_reservoir_lane": _bucket_counts([str(item.get("reservoir_lane") or "unknown") for item in deduped]),
        "by_primary_type": _bucket_counts([str(item.get("primary_type") or "unknown") for item in deduped]),
        "by_origin": _bucket_counts([str(item.get("origin") or "unknown") for item in deduped]),
        "by_promotion_recommendation": _bucket_counts(
            [str(item.get("promotion_recommendation") or "unknown") for item in deduped]
        ),
        "by_source_section": _bucket_counts([str(item.get("source_section") or "unknown") for item in deduped]),
    }

    return {
        "generated_at": _timestamp_now(),
        "workspace": "linkedin-content-os",
        "items": deduped,
        "counts": counts,
    }
