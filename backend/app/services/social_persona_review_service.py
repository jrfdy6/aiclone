from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from app.models import PersonaDeltaCreate, PersonaDeltaUpdate
from app.services import persona_delta_service
from app.services.social_long_form_signal_service import TARGET_CLAIMS, TARGET_STORIES, TARGET_VOICE, extract_long_form_candidates


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
EVENT_META_TERMS = (
    "south by",
    "show of hands",
    "closing keynote",
    "give it up",
    "you guys",
    "this presentation",
    "the slide",
    "today we are talking about",
    "years later to talk to you about",
)
WORLDVIEW_TERMS = (
    "trust",
    "culture",
    "resistance to change",
    "operational efficiencies",
    "customer experience",
    "drive revenue",
    "return on investment",
    "roi",
    "bias",
    "transparency",
    "hallucinations",
    "workflow clarity",
    "leadership",
    "rollout",
    "adoption stalled",
    "process and training approach",
    "more likely to be successful",
    "ai pilots",
    "failing",
)
SELF_CREDENTIAL_PATTERNS = (
    r"\bi(?:'ve| have) been working in\b",
    r"\bi am the chief\b",
    r"\bi do have credibility\b",
    r"\bi know what i(?:'m| am) talking about\b",
    r"\bmy book\b",
    r"\bi travel a lot\b",
)
DEFINITION_PATTERNS = (
    r"\bmachine learning is a subset of ai\b",
    r"\bgenerative ai is a subset of machine learning\b",
    r"\buses math and statistical processes\b",
    r"\bmake predictions\b",
)
WEAK_CONTEXT_PATTERNS = (
    r"\bthat element in green\b",
    r"\bquestions when my team is sleeping\b",
    r"\bmy team and i thought\b",
    r"\bwhy does it have to be that way\??$",
    r"\bi(?:'m| am) super proud\b",
    r"\balive in spirit\b",
    r"\bnot very well done\b",
    r"\bchief product officer was presenting\b",
    r"\bshowed me (?:his|her|their) ai dashboard\b",
)
HYPE_PATTERNS = (
    r"\b\d+\s+years in the field of ai\b",
    r"\bthat(?:'s| is) an eternity\b",
    r"\bai magic takes over\b",
    r"\bmost transformative technology of our generation\b",
)
NOISY_LINE_TERMS = (
    "pending owner review",
    "pending routing review",
    "quotes to reuse",
    "open questions",
    "review build implications",
    "review persona implications",
    "validation transcript",
    "media background queue",
)
NOISY_SECTION_HEADINGS = ("owner notes", "follow-ups")
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


def _trim_noise_sections(text: str) -> str:
    if not text:
        return ""
    pattern = re.compile(
        r"^\s*##\s+(?:"
        + "|".join(re.escape(section) for section in NOISY_SECTION_HEADINGS)
        + r")\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return text[: match.start()].strip() if match else text.strip()


def _normalize_source_line(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""
    if line.startswith("#"):
        return ""
    if re.match(r"^- \[[ xX]\]\s+", line):
        return ""
    line = re.sub(r"^\d+\.\s+", "", line)
    line = re.sub(r"^-+\s+", "", line)
    line = re.sub(r"^\*\*[^*]+\*\*:\s*", "", line)
    line = re.sub(r"^(Transcript\s+Host|Host|Speaker\s*\d+|Moderator|Interviewer|Question|Audience):\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^Transcript\s*$", "", line, flags=re.IGNORECASE)
    line = _clean_text(line)
    lowered = line.lower()
    if not line:
        return ""
    if any(term in lowered for term in NOISY_LINE_TERMS):
        return ""
    if lowered.endswith(":") and len(lowered.split()) <= 4:
        return ""
    return line


def _sentence_case(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return ""
    return f"{text[0].upper()}{text[1:]}" if len(text) > 1 else text.upper()


def _ensure_terminal_punctuation(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return ""
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _normalize_worldview_candidate(candidate: str) -> str:
    text = _clean_text(candidate)
    if not text:
        return ""

    text = re.sub(r"^(?:And|But|So|Well)\s+", "", text, flags=re.IGNORECASE)
    text = _clean_text(text)

    patterns: list[tuple[str, Any]] = [
        (
            r"^We're gonna start with leadership and talk a little bit about why (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(match.group(1))),
        ),
        (
            r"^One story from the conversation described a company that (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(f"A company {match.group(1)}")),
        ),
        (
            r"^At [^,]+, where we work to identify and implement (.+)$",
            lambda match: _ensure_terminal_punctuation(_sentence_case(f"The practical work is to identify and implement {match.group(1)}")),
        ),
        (
            r"^Even if I identify a handful of those opportunities, how do I overcome (.+)\?$",
            lambda match: _sentence_case(f"The harder problem is overcoming {match.group(1)}."),
        ),
        (
            r"^If your CEO is using it for prompting and for agents, brainstorming with you, doing cross-team groups with you, you're (.+?) because they're talking about it\.$",
            lambda match: _sentence_case(f"If your CEO is visibly using AI for prompting and agents, you're {match.group(1)}."),
        ),
        (
            r"^The better question would be if we rebuilt (.+), what would that look like\?$",
            lambda match: _sentence_case(f"The better question is what it would look like if we rebuilt {match.group(1)}."),
        ),
    ]

    for pattern, builder in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            text = builder(match)
            break

    return _ensure_terminal_punctuation(_sentence_case(text))


def _candidate_sentences(text: str, limit: int = 60) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = _normalize_source_line(raw_line)
        if not line:
            continue
        normalized = re.sub(r"\s+", " ", line)
        raw_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", normalized)
        for part in raw_parts:
            candidate = _clean_text(part)
            candidate = _normalize_worldview_candidate(candidate)
            lowered = candidate.lower()
            if not candidate or lowered in seen:
                continue
            seen.add(lowered)
            sentences.append(candidate)
            if len(sentences) >= limit:
                return sentences
    return sentences


def _bullet_lines(text: str, limit: int = 20) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            candidate = _normalize_source_line(line[2:])
        elif re.match(r"^\d+\.\s+", line):
            candidate = _normalize_source_line(re.sub(r"^\d+\.\s+", "", line))
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
    meta, body = _parse_frontmatter(raw)
    return meta, _trim_noise_sections(body)


def _is_boilerplate(sentence: str, asset_title: str) -> bool:
    lowered = f" {_clean_text(sentence).lower()} "
    if any(lowered.strip().startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
        return True
    if any(term in lowered for term in NOISY_LINE_TERMS):
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
    if any(term in lowered for term in WORLDVIEW_TERMS):
        score += 2
    if re.search(r"\b\d+\b", text):
        score += 1
    if any(term in lowered for term in STORY_TERMS):
        score += 1
    if _clean_text(asset.get("source_channel")) in {"youtube", "podcast"} and "question" in lowered:
        score -= 1
    if any(term in lowered for term in EVENT_META_TERMS):
        score -= 3
    if any(re.search(pattern, lowered) for pattern in SELF_CREDENTIAL_PATTERNS):
        score -= 4
    if any(re.search(pattern, lowered) for pattern in DEFINITION_PATTERNS):
        score -= 3
    if any(re.search(pattern, lowered) for pattern in WEAK_CONTEXT_PATTERNS):
        score -= 6
    if any(re.search(pattern, lowered) for pattern in HYPE_PATTERNS):
        score -= 5
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
    talking_points = [segment] if segment else []
    phrase_candidates = [segment] if len(segment.split()) <= 20 else []
    frameworks: list[dict[str, str]] = []
    anecdotes: list[dict[str, str]] = []

    if target_file == TARGET_CLAIMS and belief_summary:
        frameworks.append(
            {
                "title": "System hypothesis",
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


def _build_notes(
    asset: dict[str, Any],
    segment: str,
    lane_id: str,
    target_file: str,
    assessment: dict[str, str],
    *,
    primary_route: str = "",
    response_modes: list[str] | None = None,
    source_context_excerpt: str = "",
) -> str:
    lines = [
        f"Source asset: {_clean_text(asset.get('title')) or 'Untitled asset'}",
        f"Source channel: {_clean_text(asset.get('source_channel')) or 'unknown'}",
        f"Lane hint: {lane_id}",
    ]
    if primary_route:
        lines.append(f"Best first move: {primary_route.replace('_', ' ')}")
    if response_modes:
        other_routes = [mode.replace("_", " ") for mode in response_modes if _clean_text(mode) and _clean_text(mode) != _clean_text(primary_route)]
        if other_routes:
            lines.append(f"Other possible routes: {', '.join(other_routes)}")
    lines.extend(
        [
            "",
            "Source segment:",
            segment,
        ]
    )
    if source_context_excerpt and _clean_text(source_context_excerpt).lower() != _clean_text(segment).lower():
        lines.extend(
            [
                "",
                "Surrounding source context:",
                source_context_excerpt,
            ]
        )
    lines.extend(
        [
            "",
            f"Possible canon destination: {target_file}",
        ]
    )
    belief_relation = _clean_text(assessment.get("belief_relation"))
    belief_summary = _clean_text(assessment.get("belief_summary"))
    experience_summary = _clean_text(assessment.get("experience_summary"))
    if belief_relation:
        lines.extend(["", f"System relation: {belief_relation}"])
    if belief_summary:
        lines.extend(["", f"System hypothesis: {belief_summary}"])
    if experience_summary:
        lines.extend(["", f"Possible experience anchor: {experience_summary}"])
    return "\n".join(lines)


def _build_metadata(asset: dict[str, Any], segment: str, lane_id: str, target_file: str, assessment: dict[str, str]) -> dict[str, Any]:
    review_key = _review_key(asset, segment, target_file)
    source_label = _clean_text(asset.get("title")) or _clean_text(asset.get("asset_id")) or "long-form source"
    belief_summary = _clean_text(assessment.get("belief_summary"))
    experience_anchor = _clean_text(assessment.get("experience_anchor"))
    experience_summary = _clean_text(assessment.get("experience_summary"))
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
        "review_stage": "source_first",
        "target_file": target_file,
        "suggested_target_file": target_file,
        "why_showing": f"I am showing this because the system pulled a strong segment from {source_label}. Start with the source itself first. Treat route and canon suggestions as system guesses until you decide what matters.",
        "review_prompt": "What is the source actually saying, what do you think about it, and should it stay source intelligence, become memory, turn into a post seed, or affect canon?",
        "segment_excerpt": segment,
        "source_excerpt_clean": segment,
        "stance": assessment.get("stance", ""),
        "agreement_level": assessment.get("agreement_level", ""),
        "belief_relation": assessment.get("belief_relation", ""),
        "belief_used": assessment.get("belief_used", ""),
        "belief_summary": belief_summary,
        "system_hypothesis": belief_summary,
        "experience_anchor": experience_anchor,
        "experience_summary": experience_summary,
        "system_experience_hypothesis": experience_summary,
        "role_safety": assessment.get("role_safety", ""),
        **_promotion_metadata(segment, asset, target_file, assessment),
    }


def _is_legacy_relation_note(notes: str, belief_summary: str) -> bool:
    note_text = _clean_text(notes)
    summary_text = _clean_text(belief_summary)
    if not note_text or not summary_text:
        return False
    return f"Belief relation: {summary_text}" in note_text and "Belief summary:" not in note_text


def _needs_existing_refresh(
    existing_delta: Any,
    *,
    notes: str,
    metadata: dict[str, Any],
    trait: str,
) -> bool:
    status = _clean_text(getattr(existing_delta, "status", "")).lower() or "draft"
    if status != "draft":
        return False

    existing_metadata = existing_delta.metadata if isinstance(existing_delta.metadata, dict) else {}
    if _clean_text(existing_metadata.get("review_source")) != "long_form_media.segment":
        return False
    if existing_metadata.get("resolution_capture_id") or existing_metadata.get("pending_promotion"):
        return False

    required_fields = (
        "belief_relation",
        "review_prompt",
        "why_showing",
        "primary_route",
        "route_reason",
        "route_score",
        "response_modes",
        "review_stage",
        "suggested_target_file",
        "source_context_excerpt",
        "weak_source_fragment",
    )
    if any(not existing_metadata.get(field) for field in required_fields):
        return True

    refresh_fields = (
        "review_prompt",
        "why_showing",
        "primary_route",
        "route_reason",
        "route_score",
        "response_modes",
        "review_stage",
        "suggested_target_file",
        "system_hypothesis",
        "system_experience_hypothesis",
        "source_context_excerpt",
        "weak_source_fragment",
    )
    if any(existing_metadata.get(field) != metadata.get(field) for field in refresh_fields):
        return True

    existing_notes = existing_delta.notes or ""
    if _clean_text(existing_notes) != _clean_text(notes):
        return True
    if _is_legacy_relation_note(existing_notes, metadata.get("belief_summary", "")):
        return True
    if "Target file:" in existing_notes or "Belief summary:" in existing_notes or "Experience anchor:" in existing_notes:
        return True

    if _clean_text(existing_delta.trait) != _clean_text(trait):
        return True

    return False


class SocialPersonaReviewService:
    def sync_long_form_worldview_reviews(
        self,
        *,
        repo_root: Path,
        source_assets: dict[str, Any] | None = None,
        transcripts_root: Path | None = None,
        ingestions_root: Path | None = None,
        max_assets: int = 12,
        max_segments_per_asset: int = 2,
    ) -> dict[str, Any]:
        extracted = extract_long_form_candidates(
            repo_root=repo_root,
            source_assets=source_assets,
            transcripts_root=transcripts_root,
            ingestions_root=ingestions_root,
            max_assets=max_assets,
            max_segments_per_asset=max_segments_per_asset,
        )
        candidates = [
            item
            for item in extracted.get("candidates") or []
            if _clean_text(item.get("handoff_lane")) == "persona_candidate"
            or (_clean_text(item.get("handoff_lane")) == "" and _clean_text(item.get("primary_route")) == "belief_evidence")
        ]
        inventory_asset_ids: set[str] = {
            _clean_text(item.get("asset_id"))
            for item in ((source_assets or {}).get("items") or [])
            if _clean_text(item.get("asset_id"))
        }

        try:
            existing_deltas = persona_delta_service.list_deltas(limit=400)
        except Exception:
            existing_deltas = []
        existing_review_keys: dict[str, Any] = {}
        for delta in existing_deltas:
            metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
            if _clean_text(metadata.get("review_source")) != "long_form_media.segment":
                continue
            review_key = _clean_text(metadata.get("review_key"))
            if review_key:
                existing_review_keys[review_key] = delta

        created: list[dict[str, Any]] = []
        skipped_existing = 0
        refreshed_existing = 0
        skipped_no_segments = int(extracted.get("skipped_no_segments") or 0)
        resolved_stale = 0
        assets_considered = int(extracted.get("assets_considered") or 0)
        desired_review_keys: set[str] = set()
        considered_asset_ids: set[str] = {
            _clean_text(asset_id) for asset_id in (extracted.get("considered_asset_ids") or []) if _clean_text(asset_id)
        }
        extracted_candidate_routes: dict[str, str] = {
            _clean_text(item.get("candidate_id")): _clean_text(item.get("primary_route"))
            for item in (extracted.get("candidates") or [])
            if _clean_text(item.get("candidate_id"))
        }
        extracted_candidate_handoff_lanes: dict[str, str] = {
            _clean_text(item.get("candidate_id")): _clean_text(item.get("handoff_lane"))
            for item in (extracted.get("candidates") or [])
            if _clean_text(item.get("candidate_id"))
        }
        extracted_asset_ids: set[str] = {
            _clean_text(item.get("asset_id"))
            for item in (extracted.get("assets") or [])
            if _clean_text(item.get("asset_id"))
        }

        for candidate in candidates:
            asset = candidate.get("asset") or {}
            assessment = candidate.get("assessment") or {}
            segment = _clean_text(candidate.get("segment"))
            lane_id = _clean_text(candidate.get("lane_hint")) or "current-role"
            target_file = _clean_text(candidate.get("target_file")) or TARGET_CLAIMS
            review_key = _clean_text(candidate.get("candidate_id"))
            asset_id = _clean_text(candidate.get("asset_id"))
            desired_review_keys.add(review_key)

            metadata = _build_metadata(asset, segment, lane_id, target_file, assessment)
            metadata["review_key"] = review_key
            metadata["segment_index"] = int(candidate.get("segment_index") or 1)
            metadata["segment_total"] = int(candidate.get("segment_total") or 1)
            metadata["response_modes"] = list(candidate.get("response_modes") or [])
            metadata["primary_route"] = _clean_text(candidate.get("primary_route"))
            metadata["route_reason"] = _clean_text(candidate.get("route_reason"))
            metadata["route_score"] = int(candidate.get("route_score") or 0)
            metadata["handoff_lane"] = _clean_text(candidate.get("handoff_lane"))
            metadata["handoff_reason"] = _clean_text(candidate.get("handoff_reason"))
            metadata["secondary_consumers"] = list(candidate.get("secondary_consumers") or [])
            metadata["source_context_excerpt"] = _clean_text(candidate.get("source_context_excerpt"))
            metadata["source_context_before"] = [
                str(item)
                for item in (candidate.get("source_context_before") or [])
                if _clean_text(item)
            ]
            metadata["source_context_after"] = [
                str(item)
                for item in (candidate.get("source_context_after") or [])
                if _clean_text(item)
            ]
            metadata["weak_source_fragment"] = bool(candidate.get("weak_source_fragment"))
            trait = _trait_label(segment, target_file)
            notes = _build_notes(
                asset,
                segment,
                lane_id,
                target_file,
                assessment,
                primary_route=metadata["primary_route"],
                response_modes=metadata["response_modes"],
                source_context_excerpt=metadata["source_context_excerpt"],
            )

            existing_delta = existing_review_keys.get(review_key) or persona_delta_service.get_delta_by_review_key(review_key)
            if existing_delta:
                existing_metadata = existing_delta.metadata if isinstance(existing_delta.metadata, dict) else {}
                existing_review_key = _clean_text(existing_metadata.get("review_key"))
                if existing_review_key and existing_review_key != review_key:
                    skipped_existing += 1
                    continue
            if existing_delta:
                skipped_existing += 1
                if _needs_existing_refresh(existing_delta, notes=notes, metadata=metadata, trait=trait):
                    update = PersonaDeltaUpdate(
                        notes=notes,
                        metadata=metadata,
                    )
                    if persona_delta_service.update_delta(existing_delta.id, update):
                        refreshed_existing += 1
                continue

            payload = PersonaDeltaCreate(
                persona_target=PERSONA_TARGET,
                trait=trait,
                notes=notes,
                metadata=metadata,
            )
            delta = persona_delta_service.create_delta(payload)
            created.append(
                {
                    "id": delta.id,
                    "trait": delta.trait,
                    "target_file": target_file,
                    "source_asset_id": asset_id,
                    "review_key": review_key,
                }
            )

        for review_key, delta in existing_review_keys.items():
            metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
            if review_key in desired_review_keys:
                continue
            source_asset_id = _clean_text(metadata.get("source_asset_id"))
            legacy_primary_route = _clean_text(metadata.get("primary_route"))
            stale_reason = ""
            sync_state = ""
            if legacy_primary_route and legacy_primary_route != "belief_evidence":
                stale_reason = "legacy segment route is no longer canon-eligible and should stay outside the brain review queue"
                sync_state = "stale_route_downgrade"
            elif extracted_candidate_routes.get(review_key) and extracted_candidate_routes.get(review_key) != "belief_evidence":
                stale_reason = "segment no longer qualifies for persona-canon review and should stay outside the brain review queue"
                sync_state = "stale_route_downgrade"
            elif extracted_candidate_handoff_lanes.get(review_key) and extracted_candidate_handoff_lanes.get(review_key) != "persona_candidate":
                stale_reason = "segment no longer qualifies for persona review under the current handoff policy"
                sync_state = "stale_handoff_downgrade"
            elif source_asset_id and source_asset_id not in inventory_asset_ids:
                stale_reason = "source asset no longer present in current long-form inventory"
                sync_state = "stale_source_asset"
            elif source_asset_id in considered_asset_ids or source_asset_id in extracted_asset_ids:
                stale_reason = "segment no longer selected by current worldview extractor"
                sync_state = "stale_segment"
            else:
                continue
            if (delta.status or "draft").strip().lower() != "draft":
                continue
            if metadata.get("resolution_capture_id") or metadata.get("pending_promotion"):
                continue
            update = PersonaDeltaUpdate(
                status="resolved",
                metadata={
                    "sync_state": sync_state,
                    "stale_reason": stale_reason,
                },
            )
            if persona_delta_service.update_delta(delta.id, update):
                resolved_stale += 1

        return {
            "assets_considered": assets_considered,
            "created_count": len(created),
            "skipped_existing": skipped_existing,
            "refreshed_existing": refreshed_existing,
            "skipped_no_segments": skipped_no_segments,
            "resolved_stale": resolved_stale,
            "created": created,
        }


social_persona_review_service = SocialPersonaReviewService()
