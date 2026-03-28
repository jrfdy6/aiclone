from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from app.models import PersonaDeltaCreate
from app.services import persona_delta_service
from app.services.social_belief_engine import social_belief_engine
from app.services.social_source_asset_service import build_source_asset_inventory


CONTRAST_TERMS = (" not ", " but ", " because ", " however ", " instead ", " rather than ")
PROCESS_TERMS = (
    "system",
    "process",
    "workflow",
    "ownership",
    "handoff",
    "execution",
    "team",
    "leadership",
    "training",
    "change management",
    "culture",
    "standard",
)
AI_TERMS = (" ai ", "agent", "model", "prompt", "automation", "llm", "judgment")
ADMISSIONS_TERMS = (" admissions", " enrollment", " prospect", " student journey", " referral", " family trust")
STORY_TERMS = (" i ", " my ", " we ", " our ", " learned", " experience", " story")
BOILERPLATE_PREFIXES = (
    "thank you",
    "hello",
    "good morning",
    "good afternoon",
    "welcome",
    "one question is",
    "that's a great question",
)
TARGET_CLAIMS = "identity/claims.md"
TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_STORIES = "history/story_bank.md"
PERSONA_TARGET = "feeze.core"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def _candidate_sentences(text: str, limit: int = 60) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    normalized = re.sub(r"\s+", " ", cleaned)
    raw_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", normalized)
    sentences: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        candidate = _clean_text(part)
        lowered = candidate.lower()
        if not candidate or lowered in seen:
            continue
        seen.add(lowered)
        sentences.append(candidate)
        if len(sentences) >= limit:
            break
    return sentences


def _bullet_lines(text: str, limit: int = 20) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            candidate = _clean_text(line[2:])
        elif re.match(r"^\d+\.\s+", line):
            candidate = _clean_text(re.sub(r"^\d+\.\s+", "", line))
        else:
            continue
        lowered = candidate.lower()
        if not candidate or lowered in seen:
            continue
        seen.add(lowered)
        items.append(candidate)
        if len(items) >= limit:
            break
    return items


def _read_asset_content(asset: dict[str, Any], repo_root: Path) -> tuple[dict[str, Any], str]:
    rel_path = _clean_text(asset.get("source_path"))
    if not rel_path:
        return {}, ""
    path = repo_root / rel_path
    if not path.exists():
        return {}, ""
    raw = path.read_text(encoding="utf-8")
    return _parse_frontmatter(raw)


def _is_boilerplate(sentence: str, asset_title: str) -> bool:
    lowered = f" {_clean_text(sentence).lower()} "
    if any(lowered.strip().startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
        return True
    title = _clean_text(asset_title).lower()
    if title and lowered.strip() == title:
        return True
    if len(lowered.split()) < 6:
        return True
    return False


def _score_sentence(sentence: str, asset: dict[str, Any]) -> tuple[int, int, int]:
    text = _clean_text(sentence)
    lowered = f" {text.lower()} "
    words = text.split()
    score = 0
    if 8 <= len(words) <= 34:
        score += 3
    elif 6 <= len(words) <= 42:
        score += 1
    else:
        score -= 2
    if any(term in lowered for term in CONTRAST_TERMS):
        score += 3
    if any(term in lowered for term in PROCESS_TERMS):
        score += 2
    if any(term in lowered for term in AI_TERMS):
        score += 2
    if any(term in lowered for term in ADMISSIONS_TERMS):
        score += 2
    if re.search(r"\b\d+\b", text):
        score += 1
    if any(term in lowered for term in STORY_TERMS):
        score += 1
    if _clean_text(asset.get("source_channel")) in {"youtube", "podcast"} and "question" in lowered:
        score -= 1
    if _is_boilerplate(text, _clean_text(asset.get("title"))):
        score -= 4
    return score, len(words), -len(text)


def _extract_segments(asset: dict[str, Any], body: str, max_segments: int) -> list[str]:
    summary = _clean_text(asset.get("summary"))
    candidates: list[str] = []
    seen: set[str] = set()

    for candidate in _bullet_lines(body, limit=24) + _candidate_sentences(summary, limit=8):
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(candidate)

    body_sentences = _candidate_sentences(body, limit=80)
    for candidate in body_sentences:
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(candidate)

    scored = [
        (candidate, _score_sentence(candidate, asset))
        for candidate in candidates
        if not _is_boilerplate(candidate, _clean_text(asset.get("title")))
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    selected: list[str] = []
    for candidate, metrics in scored:
        if metrics[0] < 2:
            continue
        candidate_words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        if any(len(candidate_words & set(re.findall(r"[a-z0-9]+", existing.lower()))) >= min(8, len(candidate_words)) for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_segments:
            break
    return selected


def _lane_hint(text: str) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if any(term in lowered for term in AI_TERMS):
        return "ai"
    if any(term in lowered for term in ADMISSIONS_TERMS):
        return "admissions"
    if any(term in lowered for term in STORY_TERMS):
        return "personal-story"
    if any(term in lowered for term in PROCESS_TERMS):
        return "program-leadership"
    return "current-role"


def _choose_target_file(text: str, lane_id: str, assessment: dict[str, str]) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if lane_id == "personal-story" or any(term in lowered for term in ("i learned", "i remember", "my experience", "origin story")):
        return TARGET_STORIES
    if assessment.get("stance") in {"counter", "nuance"} or any(term in lowered for term in CONTRAST_TERMS):
        return TARGET_CLAIMS
    if len(text.split()) <= 18:
        return TARGET_VOICE
    return TARGET_CLAIMS


def _trait_label(segment: str, target_file: str) -> str:
    text = _clean_text(segment)
    if target_file == TARGET_VOICE and len(text) > 110:
        return f"{text[:107].rstrip()}..."
    if len(text) > 140:
        return f"{text[:137].rstrip()}..."
    return text


def _extract_stats(segment: str, asset: dict[str, Any]) -> list[str]:
    stats: list[str] = []
    title = _clean_text(asset.get("title"))
    if re.search(r"\b\d+\b", title):
        stats.append(title)
    if re.search(r"\b\d+\b", segment):
        stats.append(segment)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in stats:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped[:3]


def _promotion_metadata(segment: str, asset: dict[str, Any], target_file: str, assessment: dict[str, str]) -> dict[str, Any]:
    belief_summary = _clean_text(assessment.get("belief_summary"))
    experience_summary = _clean_text(assessment.get("experience_summary"))
    talking_points = [item for item in [segment, belief_summary, experience_summary] if item]
    phrase_candidates = [segment] if len(segment.split()) <= 20 else []
    frameworks: list[dict[str, str]] = []
    anecdotes: list[dict[str, str]] = []

    if target_file == TARGET_CLAIMS and belief_summary:
        frameworks.append(
            {
                "title": "Belief candidate",
                "takeaway": belief_summary,
                "evidence": segment,
            }
        )
    if target_file == TARGET_STORIES:
        anecdotes.append(
            {
                "title": _clean_text(asset.get("title")) or "Source anecdote",
                "summary": segment,
                "evidence": _clean_text(asset.get("source_url")) or _clean_text(asset.get("source_path")),
            }
        )

    return {
        "talking_points": talking_points[:3],
        "phrase_candidates": phrase_candidates,
        "frameworks": frameworks,
        "anecdotes": anecdotes,
        "stats": _extract_stats(segment, asset),
    }


def _review_key(asset: dict[str, Any], segment: str, target_file: str) -> str:
    source = "|".join(
        [
            _clean_text(asset.get("asset_id")),
            _clean_text(asset.get("source_path")),
            target_file,
            _clean_text(segment).lower(),
        ]
    )
    return f"long-form:{hashlib.sha1(source.encode('utf-8')).hexdigest()[:16]}"


def _build_signal(asset: dict[str, Any], segment: str) -> dict[str, Any]:
    title = _clean_text(asset.get("title"))
    summary = _clean_text(asset.get("summary"))
    return {
        "title": title,
        "summary": summary,
        "core_claim": segment,
        "supporting_claims": [summary] if summary and summary.lower() != segment.lower() else [],
        "source_class": asset.get("source_class"),
        "source_channel": asset.get("source_channel"),
        "source_type": asset.get("source_type"),
        "source_url": asset.get("source_url"),
        "topic_tags": list(asset.get("topics") or []) + list(asset.get("tags") or []),
    }


def _build_notes(asset: dict[str, Any], segment: str, lane_id: str, target_file: str, assessment: dict[str, str]) -> str:
    lines = [
        f"Source asset: {_clean_text(asset.get('title')) or 'Untitled asset'}",
        f"Source channel: {_clean_text(asset.get('source_channel')) or 'unknown'}",
        f"Lane hint: {lane_id}",
        f"Target file: {target_file}",
        "",
        "Candidate segment:",
        segment,
    ]
    belief_summary = _clean_text(assessment.get("belief_summary"))
    experience_summary = _clean_text(assessment.get("experience_summary"))
    if belief_summary:
        lines.extend(["", f"Belief relation: {belief_summary}"])
    if experience_summary:
        lines.extend(["", f"Experience anchor: {experience_summary}"])
    return "\n".join(lines)


def _build_metadata(asset: dict[str, Any], segment: str, lane_id: str, target_file: str, assessment: dict[str, str]) -> dict[str, Any]:
    review_key = _review_key(asset, segment, target_file)
    source_label = _clean_text(asset.get("title")) or _clean_text(asset.get("asset_id")) or "long-form source"
    return {
        "review_key": review_key,
        "review_source": "long_form_media.segment",
        "source_class": _clean_text(asset.get("source_class")) or "long_form_media",
        "response_mode": "belief_evidence",
        "source_asset_id": _clean_text(asset.get("asset_id")),
        "source_channel": _clean_text(asset.get("source_channel")),
        "source_type": _clean_text(asset.get("source_type")),
        "source_url": _clean_text(asset.get("source_url")),
        "source_path": _clean_text(asset.get("source_path")),
        "evidence_source": source_label,
        "lane_hint": lane_id,
        "target_file": target_file,
        "why_showing": f"I am showing this because a segment from {source_label} looks durable enough to affect your worldview, language, or story archive.",
        "review_prompt": f"Decide whether this segment belongs in {target_file}, what you agree or disagree with, and what wording or context should be preserved before it shapes the persona.",
        "segment_excerpt": segment,
        "stance": assessment.get("stance", ""),
        "agreement_level": assessment.get("agreement_level", ""),
        "belief_used": assessment.get("belief_used", ""),
        "belief_summary": assessment.get("belief_summary", ""),
        "experience_anchor": assessment.get("experience_anchor", ""),
        "experience_summary": assessment.get("experience_summary", ""),
        "role_safety": assessment.get("role_safety", ""),
        **_promotion_metadata(segment, asset, target_file, assessment),
    }


class SocialPersonaReviewService:
    def sync_long_form_worldview_reviews(
        self,
        *,
        repo_root: Path,
        source_assets: dict[str, Any] | None = None,
        transcripts_root: Path | None = None,
        ingestions_root: Path | None = None,
        max_assets: int = 4,
        max_segments_per_asset: int = 2,
    ) -> dict[str, Any]:
        inventory = source_assets
        if inventory is None:
            inventory = build_source_asset_inventory(
                transcripts_root=transcripts_root or repo_root / "knowledge" / "aiclone" / "transcripts",
                ingestions_root=ingestions_root or repo_root / "knowledge" / "ingestions",
                repo_root=repo_root,
            )

        items = [
            item
            for item in (inventory.get("items") or [])
            if item.get("source_class") == "long_form_media"
            and "belief_evidence" in (item.get("response_modes") or [])
        ]

        created: list[dict[str, Any]] = []
        skipped_existing = 0
        skipped_no_segments = 0
        assets_considered = 0

        for asset in items[:max_assets]:
            assets_considered += 1
            _, body = _read_asset_content(asset, repo_root)
            if not body:
                skipped_no_segments += 1
                continue
            segments = _extract_segments(asset, body, max_segments=max_segments_per_asset)
            if not segments:
                skipped_no_segments += 1
                continue

            for index, segment in enumerate(segments, start=1):
                lane_id = _lane_hint(segment)
                assessment = social_belief_engine.assess_signal(_build_signal(asset, segment), lane_id)
                target_file = _choose_target_file(segment, lane_id, assessment)
                metadata = _build_metadata(asset, segment, lane_id, target_file, assessment)
                metadata["segment_index"] = index
                metadata["segment_total"] = len(segments)

                if persona_delta_service.get_delta_by_review_key(str(metadata["review_key"])):
                    skipped_existing += 1
                    continue

                payload = PersonaDeltaCreate(
                    persona_target=PERSONA_TARGET,
                    trait=_trait_label(segment, target_file),
                    notes=_build_notes(asset, segment, lane_id, target_file, assessment),
                    metadata=metadata,
                )
                delta = persona_delta_service.create_delta(payload)
                created.append(
                    {
                        "id": delta.id,
                        "trait": delta.trait,
                        "target_file": target_file,
                        "source_asset_id": _clean_text(asset.get("asset_id")),
                        "review_key": metadata["review_key"],
                    }
                )

        return {
            "assets_considered": assets_considered,
            "created_count": len(created),
            "skipped_existing": skipped_existing,
            "skipped_no_segments": skipped_no_segments,
            "created": created,
        }


social_persona_review_service = SocialPersonaReviewService()
