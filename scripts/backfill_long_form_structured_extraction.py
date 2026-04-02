#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

import yaml

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


def _first_meaningful_line(value: str, *, limit: int = 220) -> str:
    for line in _normalize_source_document(value).splitlines():
        cleaned = _clean_text(line)
        if cleaned and not cleaned.startswith("#"):
            return cleaned[:limit]
    return ""


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


def _build_structured_extraction(*, title: str, summary: str, notes: str, transcript_text: str) -> dict[str, Any]:
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


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def _extract_section(raw: str, heading: str) -> str:
    marker = f"## {heading}"
    start = raw.find(marker)
    if start == -1:
        return ""
    section = raw[start + len(marker) :].lstrip()
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    return section.strip()


def _section_bullets(section: str) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in section.splitlines():
        cleaned = line.strip()
        if not cleaned.startswith("- "):
            continue
        text = _clean_text(cleaned[2:])
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        items.append(text)
    return items


def _choose_summary_seed(meta: dict[str, Any], body: str) -> str:
    summary = _clean_text(meta.get("summary"))
    structured_summary = _clean_text(meta.get("structured_summary"))
    for candidate in (structured_summary, summary):
        if candidate and not _is_noisy_summary(candidate):
            return candidate
    section_summary = _clean_text(_extract_section(body, "Summary"))
    if section_summary and not _is_noisy_summary(section_summary):
        return section_summary
    return ""


def _notes_seed(meta: dict[str, Any], body: str) -> str:
    notes: list[str] = []
    open_questions = [str(item) for item in (meta.get("open_questions") or []) if _clean_text(item)]
    if not open_questions:
        open_questions = _section_bullets(_extract_section(body, "Open Questions"))
    if open_questions:
        notes.append("\n".join(open_questions))
    existing_lessons = [str(item) for item in (meta.get("lessons_learned") or []) if _clean_text(item)]
    if existing_lessons:
        notes.append("\n".join(existing_lessons))
    return "\n".join(part for part in notes if _clean_text(part))


def _transcript_seed(asset_dir: Path, body: str) -> str:
    raw_transcript_path = asset_dir / "raw" / "transcript.txt"
    if raw_transcript_path.exists():
        return raw_transcript_path.read_text(encoding="utf-8")
    clean_document = _extract_section(body, "Clean Transcript / Document")
    if clean_document:
        return clean_document
    return body


def _render_normalized_document(frontmatter: dict[str, Any], extraction: dict[str, Any], title: str) -> str:
    body_lines = [
        "# Structured Extraction",
        "",
        "## Summary",
        extraction["summary"] or f"Pending transcript or notes for {title}.",
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
        extraction["clean_transcript"] or extraction["clean_notes"] or f"Pending transcript capture for {title}.",
    ]
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False).strip()}\n---\n\n" + "\n".join(body_lines).strip() + "\n"


def _backfill_asset(path: Path, *, write: bool) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    title = _clean_text(meta.get("title")) or path.parent.name.replace("_", " ")
    summary_seed = _choose_summary_seed(meta, body)
    notes_seed = _notes_seed(meta, body)
    transcript_seed = _transcript_seed(path.parent, body)
    extraction = _build_structured_extraction(
        title=title,
        summary=summary_seed,
        notes=notes_seed,
        transcript_text=transcript_seed,
    )

    original_flags = [str(item) for item in (meta.get("extraction_quality_flags") or []) if _clean_text(item)]
    original_structured = bool(_clean_text(meta.get("structured_summary")))
    original_lessons = len([item for item in (meta.get("lessons_learned") or []) if _clean_text(item)])
    original_anecdotes = len([item for item in (meta.get("key_anecdotes") or []) if _clean_text(item)])
    original_quotes = len([item for item in (meta.get("reusable_quotes") or []) if _clean_text(item)])

    meta["summary"] = extraction["summary"] or meta.get("summary") or f"Pending transcript or notes for {title}."
    meta["summary_origin"] = extraction["summary_origin"]
    meta["structured_summary"] = extraction["structured_summary"]
    meta["lessons_learned"] = extraction["lessons_learned"]
    meta["key_anecdotes"] = extraction["key_anecdotes"]
    meta["reusable_quotes"] = extraction["reusable_quotes"]
    meta["open_questions"] = extraction["open_questions"]
    meta["clean_word_count"] = extraction["clean_word_count"]
    meta["sentence_count"] = extraction["sentence_count"]
    meta["extraction_quality_flags"] = extraction["quality_flags"]
    if extraction["clean_transcript"]:
        meta["word_count"] = len(extraction["clean_transcript"].split())

    if write:
        path.write_text(_render_normalized_document(meta, extraction, title), encoding="utf-8")
        routing_status_path = path.parent / "routing_status.json"
        status_payload: dict[str, Any]
        if routing_status_path.exists():
            try:
                status_payload = json.loads(routing_status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                status_payload = {}
        else:
            status_payload = {}
        status_payload["summary_origin"] = extraction["summary_origin"]
        status_payload["quality_flags"] = extraction["quality_flags"]
        routing_status_path.write_text(json.dumps(status_payload, indent=2) + "\n", encoding="utf-8")

    return {
        "path": str(path),
        "title": title,
        "structured_before": original_structured,
        "lessons_before": original_lessons,
        "anecdotes_before": original_anecdotes,
        "quotes_before": original_quotes,
        "flags_before": original_flags,
        "structured_after": bool(extraction["structured_summary"]),
        "lessons_after": len(extraction["lessons_learned"]),
        "anecdotes_after": len(extraction["key_anecdotes"]),
        "quotes_after": len(extraction["reusable_quotes"]),
        "flags_after": extraction["quality_flags"],
        "summary_origin": extraction["summary_origin"],
    }


def run_backfill(root: Path, *, write: bool, limit: int | None) -> dict[str, Any]:
    normalized_paths = sorted(root.rglob("normalized.md"))
    selected = normalized_paths[:limit] if limit is not None else normalized_paths
    results = [_backfill_asset(path, write=write) for path in selected]
    return {
        "root": str(root),
        "write": write,
        "counts": {
            "total": len(normalized_paths),
            "selected": len(selected),
            "processed": len(results),
            "structured_ready_after": sum(1 for item in results if item["structured_after"]),
            "lessons_ready_after": sum(1 for item in results if item["lessons_after"] > 0),
            "anecdotes_ready_after": sum(1 for item in results if item["anecdotes_after"] > 0),
            "quotes_ready_after": sum(1 for item in results if item["quotes_after"] > 0),
            "summary_cleanup_after": sum(1 for item in results if "summary_needs_cleanup" in (item["flags_after"] or [])),
        },
        "processed": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill older long-form ingestions with structured extraction fields.")
    parser.add_argument(
        "--root",
        default="/Users/neo/.openclaw/workspace/knowledge/ingestions",
        help="Root directory containing historical normalized.md long-form ingestions.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on assets to process.")
    parser.add_argument("--write", action="store_true", help="Persist changes. Default is dry-run.")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    result = run_backfill(root, write=args.write, limit=args.limit)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
