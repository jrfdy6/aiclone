from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

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
STRONG_STORY_TERMS = (
    " i ",
    " my ",
    " my team ",
    " our team ",
    " my family ",
    " i learned",
    " i remember",
    " my experience",
    " origin story",
)
BOILERPLATE_PREFIXES = (
    "thank you",
    "hello",
    "good morning",
    "good afternoon",
    "welcome",
    "one question is",
    "that's a great question",
)
PROMO_PREFIXES = (
    "my site:",
    "full story",
    "follow ",
    "follow the ",
    "follow on ",
    "subscribe",
    "join my ",
    "sign up",
    "newsletter",
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
DIRECT_REACTION_TERMS = (
    "fail",
    "failing",
    "successful",
    "trust",
    "judgment",
    "bias",
    "hallucinations",
    "workflow clarity",
    "rollout",
    "adoption",
    "leadership",
    "replace",
    "more likely",
)
PM_ROUTE_TERMS = (
    "system",
    "process",
    "workflow",
    "ownership",
    "handoff",
    "execution",
    "queue",
    "dispatch",
    "review",
    "backlog",
    "standup",
    "operational",
)
REACTION_DISCOURAGED_PREFIXES = (
    "the ",
    "that's ",
    "a company ",
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
LOW_CONTEXT_STORY_PATTERNS = (
    r"^remember\b",
    r"\bthat i showed you\b",
    r"\bsystem of record hill\b",
)
HYPE_PATTERNS = (
    r"\b\d+\s+years in the field of ai\b",
    r"\bthat(?:'s| is) an eternity\b",
    r"\bai magic takes over\b",
    r"\bmost transformative technology of our generation\b",
    r"\beveryone thinks\b.*\bwhat if\b",
)
META_GUIDANCE_PATTERNS = (
    r"\bnot safe to treat as\b",
    r"\bstyle-reference-only\b",
    r"\breference-only\b",
    r"\bshould remain style-reference-only\b",
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
NOISY_ASSET_TERMS = (
    "queue test transcript",
    "validation transcript",
    "media background queue",
)
NOISY_SECTION_HEADINGS = ("owner notes", "follow-ups")
TARGET_CLAIMS = "identity/claims.md"
TARGET_VOICE = "identity/VOICE_PATTERNS.md"
TARGET_STORIES = "history/story_bank.md"
URL_PATTERN = re.compile(r"https?://\S+")
INLINE_TIMESTAMP_PATTERN = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
INLINE_CAPTION_TAG_PATTERN = re.compile(r"</?c(?:\.[^>]*)?>")
CUE_TIMECODE_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
WEBVTT_HEADER_PATTERN = re.compile(r"^(?:WEBVTT|Kind:|Language:)\b", flags=re.IGNORECASE)
MUSIC_BRACKET_PATTERN = re.compile(r"\[[^\]]*music[^\]]*\]", flags=re.IGNORECASE)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _collapse_adjacent_repeated_runs(text: str, *, min_run: int = 4, max_run: int = 10) -> str:
    tokens = [token for token in _clean_text(text).split() if token]
    if len(tokens) < min_run * 2:
        return " ".join(tokens)
    changed = True
    while changed:
        changed = False
        upper = min(max_run, len(tokens) // 2)
        for size in range(upper, min_run - 1, -1):
            for start in range(0, len(tokens) - (size * 2) + 1):
                if tokens[start : start + size] == tokens[start + size : start + (size * 2)]:
                    del tokens[start : start + size]
                    changed = True
                    break
            if changed:
                break
    return " ".join(tokens)


def _normalize_transcript_markup(text: str) -> str:
    cleaned = str(text or "")
    if not cleaned:
        return ""
    cleaned = INLINE_TIMESTAMP_PATTERN.sub(" ", cleaned)
    cleaned = INLINE_CAPTION_TAG_PATTERN.sub("", cleaned)
    cleaned = MUSIC_BRACKET_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s*-->\s*", " ", cleaned)
    cleaned = _collapse_adjacent_repeated_runs(cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:!?])(?=\w)", r"\1 ", cleaned)
    return _clean_text(cleaned)


def _normalize_source_document(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
            continue
        if WEBVTT_HEADER_PATTERN.match(stripped) or CUE_TIMECODE_PATTERN.match(stripped):
            continue
        cleaned = _normalize_transcript_markup(stripped)
        if not cleaned:
            continue
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned)
        emitted = False
        for piece in pieces:
            normalized = _clean_text(piece)
            if not normalized:
                continue
            lines.append(normalized)
            emitted = True
        if not emitted:
            lines.append(cleaned)
    return "\n".join(line for line in lines if line is not None).strip()


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
    if WEBVTT_HEADER_PATTERN.match(line) or CUE_TIMECODE_PATTERN.match(line):
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
    line = _normalize_transcript_markup(line)
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
    return meta, _normalize_source_document(_trim_noise_sections(body))


def _asset_has_segmentable_transcript(asset: dict[str, Any], meta: dict[str, Any], body: str) -> bool:
    asset_text = " ".join(
        _clean_text(asset.get(key))
        for key in ("title", "summary", "asset_id", "raw_path", "source_path")
    ).lower()
    if any(term in asset_text for term in NOISY_ASSET_TERMS):
        return False
    source_type = _clean_text(asset.get("source_type") or meta.get("source_type")).lower()
    word_count = asset.get("word_count")
    body_text = _clean_text(body).lower()

    if source_type in {"youtube_transcript", "podcast_transcript"}:
        if isinstance(word_count, (int, float)) and word_count > 0:
            return True
        if body_text.startswith("# source notes") or "transcript capture still pending" in body_text:
            return False

    return bool(body.strip())


def _is_boilerplate(sentence: str, asset_title: str) -> bool:
    cleaned = _clean_text(sentence)
    lowered = f" {cleaned.lower()} "
    if any(lowered.strip().startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
        return True
    if any(lowered.strip().startswith(prefix) for prefix in PROMO_PREFIXES):
        return True
    if "selected from youtube watchlist" in lowered:
        return True
    if "transcript capture still pending" in lowered:
        return True
    if any(term in lowered for term in NOISY_LINE_TERMS):
        return True
    title = _clean_text(asset_title).lower()
    if title and lowered.strip() == title:
        return True
    if len(URL_PATTERN.findall(cleaned)) >= 1:
        return True
    if cleaned.count("@") >= 2:
        return True
    if cleaned.count(":") >= 3 and len(cleaned.split()) <= 35:
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


def _find_context_index(segment: str, sentences: list[str]) -> int | None:
    if not sentences:
        return None
    normalized_segment = _clean_text(segment).lower()
    if not normalized_segment:
        return None
    for index, sentence in enumerate(sentences):
        if _clean_text(sentence).lower() == normalized_segment:
            return index

    segment_terms = set(re.findall(r"[a-z0-9]+", normalized_segment))
    if not segment_terms:
        return None
    best_index: int | None = None
    best_overlap = 0
    for index, sentence in enumerate(sentences):
        sentence_terms = set(re.findall(r"[a-z0-9]+", _clean_text(sentence).lower()))
        overlap = len(segment_terms & sentence_terms)
        if overlap > best_overlap:
            best_overlap = overlap
            best_index = index
    return best_index if best_overlap >= min(4, len(segment_terms)) else None


def _build_segment_context(segment: str, sentences: list[str], *, window: int = 2) -> dict[str, Any]:
    cleaned_segment = _clean_text(segment)
    if not cleaned_segment:
        return {
            "source_context_excerpt": "",
            "source_context_before": [],
            "source_context_after": [],
        }
    index = _find_context_index(cleaned_segment, sentences)
    if index is None:
        return {
            "source_context_excerpt": cleaned_segment,
            "source_context_before": [],
            "source_context_after": [],
        }
    before = [_clean_text(item) for item in sentences[max(0, index - window) : index] if _clean_text(item)]
    after = [_clean_text(item) for item in sentences[index + 1 : index + 1 + window] if _clean_text(item)]
    context_excerpt = " ".join(before + [cleaned_segment] + after).strip()
    return {
        "source_context_excerpt": context_excerpt or cleaned_segment,
        "source_context_before": before,
        "source_context_after": after,
    }


def _extract_segments(asset: dict[str, Any], body: str, max_segments: int) -> list[dict[str, Any]]:
    summary = _clean_text(asset.get("summary"))
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    body_first_candidates = _bullet_lines(body, limit=24) + _candidate_sentences(body, limit=80)
    summary_candidates = [] if body_first_candidates else _candidate_sentences(summary, limit=8)

    for candidate in body_first_candidates + summary_candidates:
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(
            {
                "segment": candidate,
                "context_pool": body_first_candidates if candidate in body_first_candidates else [candidate],
            }
        )

    scored = [
        (
            entry["segment"],
            _score_sentence(str(entry["segment"]), asset),
            entry.get("context_pool") if isinstance(entry.get("context_pool"), list) else [],
        )
        for entry in candidates
        if not _is_boilerplate(str(entry.get("segment") or ""), _clean_text(asset.get("title")))
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    selected: list[dict[str, Any]] = []
    for candidate, metrics, context_pool in scored:
        if metrics[0] < 2:
            continue
        candidate_words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        if any(
            len(candidate_words & set(re.findall(r"[a-z0-9]+", str(existing.get("segment") or "").lower()))) >= min(8, len(candidate_words))
            for existing in selected
        ):
            continue
        selected.append(
            {
                "segment": candidate,
                "metrics": metrics,
                **_build_segment_context(candidate, [str(item) for item in context_pool if _clean_text(item)]),
            }
        )
        if len(selected) >= max_segments:
            break
    return selected


def _lane_hint(text: str) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if any(term in lowered for term in AI_TERMS):
        return "ai"
    if any(term in lowered for term in ADMISSIONS_TERMS):
        return "admissions"
    if any(term in lowered for term in STRONG_STORY_TERMS):
        return "personal-story"
    if any(term in lowered for term in PROCESS_TERMS):
        return "program-leadership"
    return "current-role"


def _choose_target_file(text: str, lane_id: str, assessment: dict[str, str]) -> str:
    lowered = f" {_clean_text(text).lower()} "
    if lane_id == "personal-story" or any(term in lowered for term in (" i learned", " i remember", " my experience", " origin story")):
        return TARGET_STORIES
    if assessment.get("stance") in {"counter", "nuance"} or any(term in lowered for term in CONTRAST_TERMS):
        return TARGET_CLAIMS
    if len(text.split()) <= 18:
        return TARGET_VOICE
    return TARGET_CLAIMS


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


def _route_score(segment: str, assessment: dict[str, str], target_file: str, worldview_score: int) -> int:
    lowered = f" {_clean_text(segment).lower()} "
    words = len(segment.split())
    score = worldview_score
    if 8 <= words <= 24:
        score += 3
    elif 6 <= words <= 30:
        score += 1
    else:
        score -= 2
    if re.search(r"\b\d+\b", lowered):
        score += 1
    if any(term in lowered for term in CONTRAST_TERMS):
        score += 1
    if assessment.get("stance") in {"counter", "nuance"}:
        score += 1
    if target_file == TARGET_STORIES:
        score -= 1
    return score


def _is_comment_ready_segment(segment: str, score: int, target_file: str) -> bool:
    cleaned = _clean_text(segment)
    lowered = f" {cleaned.lower()} "
    words = cleaned.split()
    if target_file == TARGET_STORIES:
        return False
    if not 8 <= len(words) <= 18:
        return False
    if score < 12:
        return False
    if any(cleaned.lower().startswith(prefix) for prefix in REACTION_DISCOURAGED_PREFIXES):
        return False
    if re.search(r"\b\d+\b", cleaned):
        return True
    if any(term in lowered for term in CONTRAST_TERMS):
        return True
    return any(term in lowered for term in DIRECT_REACTION_TERMS)


def _is_repost_ready_segment(segment: str, score: int, target_file: str) -> bool:
    cleaned = _clean_text(segment)
    if not _is_comment_ready_segment(cleaned, score, target_file):
        return False
    if len(cleaned.split()) > 15 or score < 14:
        return False
    lowered = f" {cleaned.lower()} "
    return bool(re.search(r"\b\d+\b", cleaned) or any(term in lowered for term in CONTRAST_TERMS))


def _is_belief_evidence_segment(segment: str, assessment: dict[str, str], target_file: str, route_score: int) -> bool:
    cleaned = _clean_text(segment)
    if not cleaned:
        return False
    lowered = f" {cleaned.lower()} "
    words = len(cleaned.split())
    if cleaned.endswith("?"):
        return False
    if any(re.search(pattern, lowered) for pattern in META_GUIDANCE_PATTERNS):
        return False
    if target_file == TARGET_STORIES:
        return words >= 10 and any(term in lowered for term in STRONG_STORY_TERMS)
    if target_file == TARGET_VOICE:
        return 6 <= words <= 18
    if route_score < 5:
        return False
    if any(term in lowered for term in WORLDVIEW_TERMS):
        return True
    if any(term in lowered for term in PROCESS_TERMS) and _clean_text(assessment.get("belief_summary")):
        return True
    if assessment.get("stance") in {"counter", "nuance"} and words <= 22:
        return True
    return False


def _is_low_context_story_fragment(segment: str, source_context_excerpt: str = "") -> bool:
    cleaned = _clean_text(segment)
    if not cleaned:
        return False
    lowered = f" {cleaned.lower()} "
    context_cleaned = _clean_text(source_context_excerpt)
    if any(re.search(pattern, lowered) for pattern in LOW_CONTEXT_STORY_PATTERNS):
        return True
    demonstrative_hits = sum(lowered.count(token) for token in (" that ", " this ", " these ", " those ", " it "))
    if cleaned.endswith("?") and (demonstrative_hits >= 2 or "showed you" in lowered):
        return True
    if cleaned.endswith("?") and (_clean_text(context_cleaned).lower() in {"", cleaned.lower()}):
        return True
    return False


def _is_manual_reference_source(asset: dict[str, Any]) -> bool:
    channel = _clean_text(asset.get("source_channel")).lower()
    source_type = _clean_text(asset.get("source_type")).lower()
    return channel == "manual" or source_type == "transcript_note"


def _has_lived_proof_context(segment: str, source_context_excerpt: str = "") -> bool:
    lowered = f" {_clean_text(segment).lower()} "
    if any(term in lowered for term in STRONG_STORY_TERMS):
        return True
    context_lowered = f" {_clean_text(source_context_excerpt).lower()} "
    return any(term in context_lowered for term in STRONG_STORY_TERMS)


def _is_high_value_non_lived_segment(segment: str, assessment: dict[str, str], route_score: int) -> bool:
    cleaned = _clean_text(segment)
    if not cleaned:
        return False
    lowered = f" {cleaned.lower()} "
    words = len(cleaned.split())
    if route_score < 14:
        return False
    if words < 9 or words > 34:
        return False
    if not any(term in lowered for term in WORLDVIEW_TERMS + PROCESS_TERMS + CONTRAST_TERMS):
        return False
    return _clean_text(assessment.get("stance")) in {"counter", "nuance", "translate"}


def _classify_routes(
    segment: str,
    assessment: dict[str, str],
    target_file: str,
    worldview_score: int,
    *,
    source_context_excerpt: str = "",
) -> tuple[list[str], str, str, int]:
    score = _route_score(segment, assessment, target_file, worldview_score)
    words = len(segment.split())
    low_context_story = target_file == TARGET_STORIES and _is_low_context_story_fragment(segment, source_context_excerpt)
    belief_candidate = False if low_context_story else _is_belief_evidence_segment(segment, assessment, target_file, score)
    routes = {"post_seed"}
    if belief_candidate:
        routes.add("belief_evidence")

    if low_context_story:
        return (
            ["post_seed"],
            "post_seed",
            "segment depends on missing story context and is safer as source intelligence or a post seed than a canon candidate",
            score,
        )

    if _is_comment_ready_segment(segment, score, target_file):
        routes.add("comment")
    if _is_repost_ready_segment(segment, score, target_file):
        routes.add("repost")

    if "comment" in routes:
        primary = "comment"
        reason = "segment is compact and explicit enough for direct reaction"
    elif belief_candidate and (target_file == TARGET_VOICE or words <= 18 or score >= 8):
        primary = "belief_evidence"
        reason = "segment reads like a durable worldview or language fragment that may be worth canon review"
    else:
        primary = "post_seed"
        reason = "segment is stronger as a post seed or source-intelligence input than a direct canon claim"

    ordered = [mode for mode in ("comment", "repost", "post_seed", "belief_evidence") if mode in routes]
    return ordered, primary, reason, score


def _handoff_lane_for_candidate(
    *,
    segment: str,
    lane_hint: str,
    target_file: str,
    assessment: dict[str, str],
    response_modes: list[str],
    primary_route: str,
    route_reason: str,
    route_score: int,
    weak_source_fragment: bool,
    manual_reference_source: bool,
    lived_proof_context: bool,
    high_value_non_lived: bool,
) -> tuple[str, str, list[str]]:
    lowered = f" {_clean_text(segment).lower()} "
    route_reason_lowered = f" {_clean_text(route_reason).lower()} "

    source_only = weak_source_fragment or (
        manual_reference_source
        and not lived_proof_context
        and not high_value_non_lived
        and " source intelligence " in route_reason_lowered
    )
    if source_only:
        return (
            "source_only",
            "segment depends on missing lived context or strategic reference framing and should stay upstream until stronger proof appears",
            [],
        )

    operational_pressure = any(term in lowered for term in PM_ROUTE_TERMS) or lane_hint == "program-leadership"
    if operational_pressure and route_score >= 15 and _clean_text(assessment.get("stance")) in {"counter", "nuance", "translate"}:
        return (
            "route_to_pm",
            "segment carries operational pressure and should be reviewed for execution routing before it turns into persona or posting work",
            ["brief"],
        )

    if primary_route == "belief_evidence":
        secondary = ["brief"]
        if any(mode in {"comment", "repost", "post_seed"} for mode in response_modes):
            secondary.append("posting")
        return (
            "persona_candidate",
            "segment reads like durable worldview, voice, or identity evidence and should be judged in Persona",
            secondary,
        )

    if primary_route == "post_seed" and any(mode in {"comment", "repost"} for mode in response_modes):
        return (
            "post_candidate",
            "segment is strong enough for public expression and is better treated as posting fuel than canon",
            ["brief"],
        )

    return (
        "brief_only",
        "segment is awareness-worthy for the current cycle but not strong enough yet for persona or public expression",
        ["brief"],
    )


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


def extract_long_form_candidates(
    *,
    repo_root: Path,
    source_assets: dict[str, Any] | None = None,
    transcripts_root: Path | None = None,
    ingestions_root: Path | None = None,
    max_assets: int = 12,
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
        and any(mode in {"belief_evidence", "post_seed"} for mode in (item.get("response_modes") or []))
    ]

    candidates: list[dict[str, Any]] = []
    assets_considered = 0
    skipped_no_segments = 0
    by_channel: dict[str, int] = {}
    assets: list[dict[str, Any]] = []

    for asset in items[:max_assets]:
        assets_considered += 1
        channel = _clean_text(asset.get("source_channel")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1
        meta, body = _read_asset_content(asset, repo_root)
        if not body:
            skipped_no_segments += 1
            continue
        if not _asset_has_segmentable_transcript(asset, meta, body):
            skipped_no_segments += 1
            continue
        segments = _extract_segments(asset, body, max_segments=max_segments_per_asset)
        if not segments:
            skipped_no_segments += 1
            continue

        asset_candidates: list[dict[str, Any]] = []
        for index, segment_payload in enumerate(segments, start=1):
            segment = _clean_text(segment_payload.get("segment"))
            metrics = segment_payload.get("metrics") or (0, 0, 0)
            worldview_score = int(metrics[0])
            lane_id = _lane_hint(segment)
            assessment = social_belief_engine.assess_signal(_build_signal(asset, segment), lane_id)
            target_file = _choose_target_file(segment, lane_id, assessment)
            source_context_excerpt = _clean_text(segment_payload.get("source_context_excerpt"))
            response_modes, primary_route, route_reason, route_score = _classify_routes(
                segment,
                assessment,
                target_file,
                worldview_score,
                source_context_excerpt=source_context_excerpt,
            )
            manual_reference_source = _is_manual_reference_source(asset)
            lived_proof_context = _has_lived_proof_context(segment, source_context_excerpt)
            high_value_non_lived = _is_high_value_non_lived_segment(segment, assessment, route_score)
            if manual_reference_source and "belief_evidence" in response_modes and not lived_proof_context and not high_value_non_lived:
                response_modes = [mode for mode in response_modes if mode != "belief_evidence"]
                if not response_modes:
                    response_modes = ["post_seed"]
                if primary_route == "belief_evidence":
                    primary_route = response_modes[0]
                route_reason = (
                    "segment is strategic source intelligence and should stay a post seed unless lived-proof context or exceptional value is clear"
                )
            weak_source_fragment = target_file == TARGET_STORIES and _is_low_context_story_fragment(segment, source_context_excerpt)
            candidate = {
                "candidate_id": _review_key(asset, segment, target_file),
                "asset_id": _clean_text(asset.get("asset_id")),
                "title": _clean_text(asset.get("title")) or "Untitled asset",
                "source_channel": channel,
                "source_type": _clean_text(asset.get("source_type")),
                "source_url": _clean_text(asset.get("source_url")),
                "source_path": _clean_text(asset.get("source_path")),
                "segment_index": index,
                "segment_total": len(segments),
                "segment": segment,
                "lane_hint": lane_id,
                "target_file": target_file,
                "stance": assessment.get("stance", ""),
                "belief_relation": assessment.get("belief_relation", ""),
                "belief_summary": _clean_text(assessment.get("belief_summary")),
                "experience_summary": _clean_text(assessment.get("experience_summary")),
                "source_context_excerpt": source_context_excerpt,
                "source_context_before": [str(item) for item in (segment_payload.get("source_context_before") or []) if _clean_text(item)],
                "source_context_after": [str(item) for item in (segment_payload.get("source_context_after") or []) if _clean_text(item)],
                "weak_source_fragment": weak_source_fragment,
                "manual_reference_source": manual_reference_source,
                "lived_proof_context": lived_proof_context,
                "high_value_non_lived": high_value_non_lived,
                "response_modes": response_modes,
                "primary_route": primary_route,
                "route_reason": route_reason,
                "worldview_score": worldview_score,
                "route_score": route_score,
                "assessment": assessment,
                "asset": asset,
            }
            handoff_lane, handoff_reason, secondary_consumers = _handoff_lane_for_candidate(
                segment=segment,
                lane_hint=lane_id,
                target_file=target_file,
                assessment=assessment,
                response_modes=response_modes,
                primary_route=primary_route,
                route_reason=route_reason,
                route_score=route_score,
                weak_source_fragment=weak_source_fragment,
                manual_reference_source=manual_reference_source,
                lived_proof_context=lived_proof_context,
                high_value_non_lived=high_value_non_lived,
            )
            candidate["handoff_lane"] = handoff_lane
            candidate["handoff_reason"] = handoff_reason
            candidate["secondary_consumers"] = secondary_consumers
            candidates.append(candidate)
            asset_candidates.append(candidate)

        assets.append(
            {
                "asset_id": _clean_text(asset.get("asset_id")),
                "title": _clean_text(asset.get("title")) or "Untitled asset",
                "source_channel": channel,
                "source_path": _clean_text(asset.get("source_path")),
                "extracted_segments": len(asset_candidates),
                "primary_routes": list(dict.fromkeys(item["primary_route"] for item in asset_candidates)),
                "response_modes": list(dict.fromkeys(mode for item in asset_candidates for mode in item["response_modes"])),
            }
        )

    candidates.sort(key=lambda item: (-int(item["route_score"]), item["title"].lower(), item["segment_index"]))
    route_counts = {mode: 0 for mode in ("comment", "repost", "post_seed", "belief_evidence")}
    primary_route_counts = {mode: 0 for mode in ("comment", "repost", "post_seed", "belief_evidence")}
    handoff_lane_counts = {lane: 0 for lane in ("source_only", "brief_only", "post_candidate", "persona_candidate", "route_to_pm")}
    lane_counts: dict[str, int] = {}
    for candidate in candidates:
        lane = str(candidate["lane_hint"])
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
        primary_route_counts[str(candidate["primary_route"])] += 1
        handoff_lane_counts[str(candidate.get("handoff_lane") or "brief_only")] = handoff_lane_counts.get(str(candidate.get("handoff_lane") or "brief_only"), 0) + 1
        for mode in candidate["response_modes"]:
            route_counts[str(mode)] += 1

    return {
        "assets_considered": assets_considered,
        "considered_asset_ids": [_clean_text(item.get("asset_id")) for item in items[:max_assets] if _clean_text(item.get("asset_id"))],
        "segments_total": len(candidates),
        "skipped_no_segments": skipped_no_segments,
        "route_counts": route_counts,
        "primary_route_counts": primary_route_counts,
        "handoff_lane_counts": handoff_lane_counts,
        "lane_counts": lane_counts,
        "by_channel": by_channel,
        "assets": assets,
        "candidates": candidates,
    }


def build_long_form_route_summary(
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
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets_considered": extracted["assets_considered"],
        "segments_total": extracted["segments_total"],
        "skipped_no_segments": extracted["skipped_no_segments"],
        "route_counts": extracted["route_counts"],
        "primary_route_counts": extracted["primary_route_counts"],
        "handoff_lane_counts": extracted["handoff_lane_counts"],
        "lane_counts": extracted["lane_counts"],
        "by_channel": extracted["by_channel"],
        "assets": extracted["assets"],
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "asset_id": item["asset_id"],
                "title": item["title"],
                "source_channel": item["source_channel"],
                "source_url": item["source_url"],
                "source_path": item["source_path"],
                "segment": item["segment"],
                "lane_hint": item["lane_hint"],
                "target_file": item["target_file"],
                "stance": item["stance"],
                "belief_relation": item.get("belief_relation", ""),
                "belief_summary": item["belief_summary"],
                "source_context_excerpt": item.get("source_context_excerpt", ""),
                "weak_source_fragment": bool(item.get("weak_source_fragment")),
                "response_modes": item["response_modes"],
                "primary_route": item["primary_route"],
                "route_reason": item["route_reason"],
                "route_score": item["route_score"],
                "handoff_lane": item.get("handoff_lane", ""),
                "handoff_reason": item.get("handoff_reason", ""),
                "secondary_consumers": item.get("secondary_consumers") or [],
            }
            for item in extracted["candidates"][:12]
        ],
    }
