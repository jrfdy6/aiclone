from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

from app.services import workspace_snapshot_service as workspace_snapshot_module

INLINE_TIMESTAMP_PATTERN = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
INLINE_CAPTION_TAG_PATTERN = re.compile(r"</?c(?:\.[^>]*)?>")
CUE_TIMECODE_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
WEBVTT_HEADER_PATTERN = re.compile(r"^(?:WEBVTT|Kind:|Language:)\b", flags=re.IGNORECASE)
MUSIC_BRACKET_PATTERN = re.compile(r"\[[^\]]*music[^\]]*\]", flags=re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")
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
NOISY_SUMMARY_TERMS = (
    "pending transcript",
    "pending owner review",
    "selected from youtube watchlist",
)
LESSON_HINTS = (
    " matters ",
    " matters more ",
    " because ",
    " should ",
    " need to ",
    " don't ",
    " never ",
    " valuable ",
    " important ",
    " key ",
    " trust ",
    " judgment ",
    " workflow ",
    " system ",
)
ANECDOTE_HINTS = (
    " i ",
    " we ",
    " my ",
    " our ",
    " customer ",
    " client ",
    " my team ",
    " our team ",
    " when ",
    " started ",
    " remember ",
)
QUOTE_HINTS = (
    " matters ",
    " because ",
    " trust ",
    " judgment ",
    " workflow ",
    " customer ",
    " team ",
    " human ",
    " ai ",
)
CONTRAST_TERMS = (" not ", " but ", " because ", " however ", " instead ", " rather than ")
SIGNAL_TERMS = (" ai ", " workflow ", " trust ", " customer ", " team ", " human ", " judgment ", " system ")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")
    return cleaned[:72] or "long_form_source"


def _first_meaningful_line(value: str, *, limit: int = 220) -> str:
    for line in _normalize_source_document(value).splitlines():
        cleaned = _clean_text(line)
        if cleaned and not cleaned.startswith("#"):
            return cleaned[:limit]
    return ""


def _normalize_url(url: str) -> str:
    text = _clean_text(url)
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme:
        return f"https://{text}"
    return text


def _infer_channel(url: str, source_type: str) -> str:
    normalized_type = _clean_text(source_type).lower()
    if normalized_type.startswith("youtube"):
        return "youtube"
    if "podcast" in normalized_type:
        return "podcast"
    host = urlparse(url).netloc.replace("www.", "").lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if any(token in host for token in ("spotify", "apple", "soundcloud", "podcast")):
        return "podcast"
    return "manual"


def _infer_source_type(url: str, source_type: str | None) -> str:
    explicit = _clean_text(source_type)
    if explicit:
        return explicit
    host = urlparse(url).netloc.replace("www.", "").lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube_transcript"
    if any(token in host for token in ("spotify", "apple", "soundcloud", "podcast")):
        return "podcast_transcript"
    return "long_form_media"


def _topic_tags(channel: str) -> tuple[list[str], list[str]]:
    topics = ["transcript"]
    tags = ["brain_ingest", "needs_review"]
    if channel == "youtube":
        topics.extend(["youtube", "video"])
    elif channel == "podcast":
        topics.extend(["podcast", "audio"])
    else:
        topics.append("long_form")
    return topics, tags


def _asset_id(title: str, url: str) -> str:
    source = url or title or "long_form_source"
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    return f"{_slugify(title or url)}_{digest}"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


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
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if WEBVTT_HEADER_PATTERN.match(stripped) or CUE_TIMECODE_PATTERN.match(stripped):
            continue
        cleaned = _normalize_transcript_markup(stripped)
        if not cleaned:
            continue
        for piece in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned):
            normalized = _clean_text(piece)
            lowered = normalized.lower()
            if not normalized or lowered in seen:
                continue
            seen.add(lowered)
            lines.append(normalized)
    return "\n".join(lines).strip()


def _sentence_candidates(text: str, *, limit: int = 120) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_line in _normalize_source_document(text).splitlines():
        candidate = _clean_text(raw_line)
        lowered = candidate.lower()
        if not candidate or lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def _is_noisy_summary(text: str) -> bool:
    lowered = f" {_clean_text(text).lower()} "
    if not lowered.strip():
        return True
    if len(lowered.split()) < 7:
        return True
    if any(term in lowered for term in NOISY_SUMMARY_TERMS):
        return True
    if URL_PATTERN.search(lowered):
        return True
    if "<00:" in text or "<c>" in text:
        return True
    return False


def _score_sentence(sentence: str) -> tuple[int, int]:
    lowered = f" {_clean_text(sentence).lower()} "
    words = sentence.split()
    score = 0
    if 8 <= len(words) <= 28:
        score += 3
    elif 6 <= len(words) <= 36:
        score += 1
    else:
        score -= 2
    if any(term in lowered for term in CONTRAST_TERMS):
        score += 3
    if any(term in lowered for term in SIGNAL_TERMS):
        score += 2
    if re.search(r"\b\d+\b", sentence):
        score += 1
    if any(lowered.strip().startswith(prefix) for prefix in PROMO_PREFIXES):
        score -= 5
    if URL_PATTERN.search(sentence):
        score -= 5
    return score, len(words)


def _dedupe_strings(values: list[str], *, limit: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _top_ranked_sentences(
    sentences: list[str],
    *,
    limit: int,
    predicate: Callable[[str], bool] | None = None,
    minimum_score: int = 0,
    max_words: int = 34,
) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        words = sentence.split()
        if len(words) > max_words:
            continue
        if predicate and not predicate(sentence):
            continue
        score, _ = _score_sentence(sentence)
        if score < minimum_score:
            continue
        ranked.append((score, -index, sentence))
    ranked.sort(reverse=True)
    selected = [sentence for _, _, sentence in ranked[:limit]]
    return _dedupe_strings(selected, limit=limit)


def _derive_summary(summary: str, notes: str, sentences: list[str], title: str) -> tuple[str, str]:
    explicit = _clean_text(summary)
    if explicit:
        return explicit[:420], "provided"

    ranked = _top_ranked_sentences(sentences, limit=2, minimum_score=1)
    if ranked:
        return " ".join(ranked)[:420], "derived_transcript"

    note_line = _first_meaningful_line(notes, limit=420)
    if note_line:
        return note_line, "derived_notes"

    fallback = _first_meaningful_line(title, limit=220) or f"Pending review for {title}."
    return fallback, "fallback_title"


def _extract_lessons(sentences: list[str]) -> list[str]:
    return _top_ranked_sentences(
        sentences,
        limit=4,
        predicate=lambda sentence: any(term in f" {_clean_text(sentence).lower()} " for term in LESSON_HINTS),
        minimum_score=1,
    )


def _extract_anecdotes(sentences: list[str]) -> list[str]:
    return _top_ranked_sentences(
        sentences,
        limit=3,
        predicate=lambda sentence: any(term in f" {_clean_text(sentence).lower()} " for term in ANECDOTE_HINTS),
        minimum_score=0,
        max_words=40,
    )


def _extract_quotes(sentences: list[str]) -> list[str]:
    return _top_ranked_sentences(
        sentences,
        limit=4,
        predicate=lambda sentence: any(term in f" {_clean_text(sentence).lower()} " for term in QUOTE_HINTS),
        minimum_score=2,
        max_words=22,
    )


def _extract_open_questions(notes: str) -> list[str]:
    questions: list[str] = []
    for line in _normalize_source_document(notes).splitlines():
        cleaned = _clean_text(line)
        if cleaned.endswith("?"):
            questions.append(cleaned)
    return _dedupe_strings(questions, limit=4)


def _format_bullets(items: list[str], *, empty: str) -> list[str]:
    values = _dedupe_strings(items, limit=8)
    if not values:
        return [f"- {empty}"]
    return [f"- {item}" for item in values]


def _build_structured_extraction(
    *,
    title: str,
    summary: str,
    notes: str,
    transcript_text: str,
) -> dict[str, Any]:
    clean_transcript = _normalize_source_document(transcript_text)
    clean_notes = _normalize_source_document(notes)
    sentences = _sentence_candidates(clean_transcript or clean_notes or summary)
    derived_summary, summary_origin = _derive_summary(summary, clean_notes, sentences, title)
    lessons = _extract_lessons(sentences)
    anecdotes = _extract_anecdotes(sentences)
    quotes = _extract_quotes(sentences)
    open_questions = _extract_open_questions(clean_notes)
    quality_flags: list[str] = []
    if _is_noisy_summary(derived_summary):
        quality_flags.append("summary_needs_cleanup")
    if not lessons:
        quality_flags.append("lessons_missing")
    if not anecdotes:
        quality_flags.append("anecdotes_missing")
    if not quotes:
        quality_flags.append("quotes_missing")
    if not clean_transcript and not clean_notes:
        quality_flags.append("source_text_missing")
    return {
        "clean_transcript": clean_transcript,
        "clean_notes": clean_notes,
        "summary": derived_summary,
        "summary_origin": summary_origin,
        "structured_summary": derived_summary,
        "lessons_learned": lessons,
        "key_anecdotes": anecdotes,
        "reusable_quotes": quotes,
        "open_questions": open_questions,
        "clean_word_count": len(clean_transcript.split()) if clean_transcript else len(clean_notes.split()),
        "sentence_count": len(sentences),
        "quality_flags": quality_flags,
    }


class BrainLongFormIngestService:
    def register_source(
        self,
        *,
        url: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
        transcript_text: str | None = None,
        source_type: str | None = None,
        author: str | None = None,
        run_refresh: bool = True,
    ) -> dict[str, Any]:
        normalized_url = _normalize_url(url or "")
        normalized_type = _infer_source_type(normalized_url, source_type)
        channel = _infer_channel(normalized_url, normalized_type)
        clean_title = _clean_text(title)
        if not clean_title:
            clean_title = _clean_text(urlparse(normalized_url).path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")) or "Long-form source"

        raw_transcript = (transcript_text or "").strip()
        raw_notes = (notes or "").strip()
        extraction = _build_structured_extraction(
            title=clean_title,
            summary=summary or "",
            notes=raw_notes,
            transcript_text=raw_transcript,
        )
        clean_transcript = extraction["clean_transcript"]
        clean_notes = extraction["clean_notes"]
        clean_summary = extraction["summary"]
        topics, tags = _topic_tags(channel)
        asset_id = _asset_id(clean_title, normalized_url)

        ingestions_root = workspace_snapshot_module._ingestions_root()
        repo_root = workspace_snapshot_module.ROOT
        now = datetime.now(timezone.utc)
        asset_dir = ingestions_root / now.strftime("%Y") / now.strftime("%m") / asset_id
        raw_dir = asset_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        raw_files: list[str] = []
        if normalized_url:
            url_path = raw_dir / "source.url"
            url_path.write_text(normalized_url + "\n", encoding="utf-8")
            raw_files.append(_relative_path(url_path, asset_dir))
        if raw_transcript:
            transcript_path = raw_dir / "transcript.txt"
            transcript_path.write_text(raw_transcript, encoding="utf-8")
            raw_files.append(_relative_path(transcript_path, asset_dir))

        frontmatter = {
            "id": asset_id,
            "title": clean_title,
            "source_type": normalized_type,
            "captured_at": now.isoformat().replace("+00:00", "Z"),
            "workspace_ids": ["brain"],
            "projects": [],
            "topics": topics,
            "tags": tags,
            "source_url": normalized_url or "unknown",
            "author": _clean_text(author) or "unknown",
            "raw_files": raw_files,
            "word_count": len(clean_transcript.split()) if clean_transcript else None,
            "summary": clean_summary or f"Pending transcript or notes for {clean_title}.",
            "summary_origin": extraction["summary_origin"],
            "structured_summary": extraction["structured_summary"],
            "lessons_learned": extraction["lessons_learned"],
            "key_anecdotes": extraction["key_anecdotes"],
            "reusable_quotes": extraction["reusable_quotes"],
            "open_questions": extraction["open_questions"],
            "clean_word_count": extraction["clean_word_count"],
            "sentence_count": extraction["sentence_count"],
            "extraction_quality_flags": extraction["quality_flags"],
        }

        body_lines = [
            "# Structured Extraction",
            "",
            "## Summary",
            clean_summary or f"Pending transcript or notes for {clean_title}.",
            "",
            "## Lessons Learned",
            *_format_bullets(extraction["lessons_learned"], empty="No clear lessons extracted yet."),
            "",
            "## Key Anecdotes",
            *_format_bullets(extraction["key_anecdotes"], empty="No strong anecdote extracted yet."),
            "",
            "## Reusable Quotes",
            *_format_bullets(extraction["reusable_quotes"], empty="No strong quote extracted yet."),
            "",
            "## Open Questions",
            *_format_bullets(
                extraction["open_questions"],
                empty="What build implications matter, what persona implications matter, and what should be emphasized?",
            ),
            "",
            "# Clean Transcript / Document",
            clean_transcript or clean_notes or f"Pending transcript capture for {clean_title}.",
        ]
        normalized_path = asset_dir / "normalized.md"
        normalized_path.write_text(
            f"---\n{yaml.safe_dump(frontmatter, sort_keys=False).strip()}\n---\n\n" + "\n".join(body_lines).strip() + "\n",
            encoding="utf-8",
        )

        routing_status_path = asset_dir / "routing_status.json"
        routing_status_path.write_text(
            json.dumps(
                {
                    "asset_id": asset_id,
                    "status": "pending_segmentation",
                    "source_channel": channel,
                    "source_type": normalized_type,
                    "has_transcript": bool(clean_transcript),
                    "summary_origin": extraction["summary_origin"],
                    "quality_flags": extraction["quality_flags"],
                    "updated_at": now.isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        refreshed = workspace_snapshot_module.workspace_snapshot_service.refresh_persisted_linkedin_os_state() if run_refresh else {}
        return {
            "asset_id": asset_id,
            "title": clean_title,
            "source_url": normalized_url,
            "source_type": normalized_type,
            "source_channel": channel,
            "source_path": _relative_path(normalized_path, repo_root),
            "routing_status_path": _relative_path(routing_status_path, repo_root),
            "has_transcript": bool(clean_transcript),
            "refreshed_snapshots": sorted(refreshed.keys()),
        }


brain_long_form_ingest_service = BrainLongFormIngestService()
