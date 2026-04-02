from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


MEDIA_CHANNEL_HINTS = {
    "youtube": "youtube",
    "youtu.be": "youtube",
    "podcast": "podcast",
    "spotify": "podcast",
    "apple": "podcast",
    "soundcloud": "podcast",
}

MEDIA_TOPIC_HINTS = {"transcript", "youtube", "podcast", "audio", "video"}
MEDIA_EXT_HINTS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".mov", ".vtt"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _list_strings(value: Any, limit: int = 12) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


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


def _first_bullet(section: str) -> str:
    for line in section.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("- "):
            return cleaned[2:].strip()
    return ""


def _section_bullets(section: str, limit: int = 8) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in section.splitlines():
        cleaned = line.strip()
        if not cleaned.startswith("- "):
            continue
        value = _clean_text(cleaned[2:])
        lowered = value.lower()
        if not value or lowered in seen:
            continue
        seen.add(lowered)
        items.append(value)
        if len(items) >= limit:
            break
    return items


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            return cleaned
    return ""


def _summary_quality_flags(summary: str, structured_summary: str, lessons: list[str], anecdotes: list[str], quotes: list[str]) -> list[str]:
    flags: list[str] = []
    cleaned_summary = _clean_text(summary)
    lowered = cleaned_summary.lower()
    if not cleaned_summary or len(cleaned_summary.split()) < 7 or "pending transcript" in lowered or "http" in lowered or "<00:" in cleaned_summary:
        flags.append("summary_needs_cleanup")
    if not _clean_text(structured_summary):
        flags.append("structured_summary_missing")
    if not lessons:
        flags.append("lessons_missing")
    if not anecdotes:
        flags.append("anecdotes_missing")
    if not quotes:
        flags.append("quotes_missing")
    return flags


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_url(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"https?://[^\s)]+", value)
    return match.group(0) if match else ""


def _infer_source_channel(source_url: str, source_type: str, topics: list[str], tags: list[str], title: str) -> str:
    lowered_type = _clean_text(source_type).lower()
    if lowered_type.startswith("youtube"):
        return "youtube"
    if "podcast" in lowered_type:
        return "podcast"

    if source_url:
        host = urlparse(source_url).netloc.replace("www.", "").lower()
        for hint, channel in MEDIA_CHANNEL_HINTS.items():
            if hint in host:
                return channel
        if host:
            return host.split(".")[0]

    joined = " ".join(topics + tags + [_clean_text(title)]).lower()
    if "youtube" in joined:
        return "youtube"
    if "podcast" in joined:
        return "podcast"
    return "manual"


def _looks_like_media_ingestion(meta: dict[str, Any]) -> bool:
    source_type = _clean_text(meta.get("source_type")).lower()
    topics = [item.lower() for item in _list_strings(meta.get("topics"), 12)]
    tags = [item.lower() for item in _list_strings(meta.get("tags"), 12)]
    raw_files = [item.lower() for item in _list_strings(meta.get("raw_files"), 20)]

    if any(term in source_type for term in MEDIA_TOPIC_HINTS):
        return True
    if any(term in topics or term in tags for term in MEDIA_TOPIC_HINTS):
        return True
    return any(any(raw.endswith(ext) for ext in MEDIA_EXT_HINTS) for raw in raw_files)


def _asset_fingerprint(asset: dict[str, Any]) -> tuple[str, str]:
    url = _clean_text(asset.get("source_url")).lower()
    title = _clean_text(asset.get("title")).lower()
    fallback = _clean_text(asset.get("raw_path") or asset.get("source_path")).lower()
    return (url or fallback, title)


def _asset_rank(asset: dict[str, Any]) -> tuple[int, int, int]:
    origin = _clean_text(asset.get("origin"))
    source_url = 1 if _clean_text(asset.get("source_url")) else 0
    summary = len(_clean_text(asset.get("summary")))
    return (
        1 if origin == "media_pipeline" else 0,
        source_url,
        summary,
    )


def _build_transcript_note_assets(transcripts_root: Path, repo_root: Path) -> list[dict[str, Any]]:
    if not transcripts_root.exists():
        return []

    assets: list[dict[str, Any]] = []
    for path in sorted(transcripts_root.glob("*.md")):
        if path.name in {"README.md", "TEMPLATE.md", "INDEX.md"}:
            continue
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        summary = _first_bullet(_extract_section(body, "Summary")) or _first_meaningful_line(body)
        source_descriptor = _clean_text(meta.get("source"))
        source_url = _extract_url(source_descriptor)
        tags = _list_strings(meta.get("tags"), 12)
        asset = {
            "asset_id": path.stem,
            "title": _clean_text(meta.get("title")) or path.stem.replace("_", " "),
            "source_class": "long_form_media",
            "source_channel": _infer_source_channel(source_url, "transcript_note", [], tags, _clean_text(meta.get("title"))),
            "source_type": "transcript_note",
            "source_url": source_url,
            "author": "",
            "captured_at": _clean_text(meta.get("received")),
            "source_path": _relative_path(path, repo_root),
            "raw_path": _clean_text(meta.get("raw_path")),
            "summary": summary,
            "topics": [],
            "tags": tags,
            "response_modes": ["post_seed", "belief_evidence"],
            "routing_status": "pending_segmentation",
            "feed_ready": False,
            "segmentation_ready": False,
            "origin": "transcript_library",
            "word_count": None,
            "summary_origin": "transcript_note",
            "structured_summary": summary,
            "lessons_learned": [],
            "key_anecdotes": [],
            "reusable_quotes": [],
            "open_questions": [],
            "clean_word_count": None,
            "sentence_count": None,
            "quality_flags": _summary_quality_flags(summary, summary, [], [], []),
        }
        assets.append(asset)
    return assets


def _build_ingestion_assets(ingestions_root: Path, repo_root: Path) -> list[dict[str, Any]]:
    if not ingestions_root.exists():
        return []

    assets: list[dict[str, Any]] = []
    for path in sorted(ingestions_root.rglob("normalized.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        if not _looks_like_media_ingestion(meta):
            continue
        topics = _list_strings(meta.get("topics"), 12)
        tags = _list_strings(meta.get("tags"), 12)
        source_type = _clean_text(meta.get("source_type")) or "transcript"
        source_url = _clean_text(meta.get("source_url"))
        summary = _clean_text(meta.get("summary")) or _first_meaningful_line(body)
        structured_summary = _clean_text(meta.get("structured_summary")) or _first_meaningful_line(_extract_section(body, "Summary"))
        lessons = _list_strings(meta.get("lessons_learned"), 8) or _section_bullets(_extract_section(body, "Lessons Learned"), limit=8)
        anecdotes = _list_strings(meta.get("key_anecdotes"), 6) or _section_bullets(_extract_section(body, "Key Anecdotes"), limit=6)
        quotes = _list_strings(meta.get("reusable_quotes"), 8) or _section_bullets(_extract_section(body, "Reusable Quotes"), limit=8)
        open_questions = _list_strings(meta.get("open_questions"), 6) or _section_bullets(_extract_section(body, "Open Questions"), limit=6)
        quality_flags = _list_strings(meta.get("extraction_quality_flags"), 12) or _summary_quality_flags(summary, structured_summary, lessons, anecdotes, quotes)
        raw_files = _list_strings(meta.get("raw_files"), 20)
        asset = {
            "asset_id": _clean_text(meta.get("id")) or path.parent.name,
            "title": _clean_text(meta.get("title")) or path.parent.name.replace("_", " "),
            "source_class": "long_form_media",
            "source_channel": _infer_source_channel(source_url, source_type, topics, tags, _clean_text(meta.get("title"))),
            "source_type": source_type,
            "source_url": source_url if source_url != "unknown" else "",
            "author": _clean_text(meta.get("author")),
            "captured_at": _clean_text(meta.get("captured_at")),
            "source_path": _relative_path(path, repo_root),
            "raw_path": raw_files[0] if raw_files else "",
            "summary": summary,
            "topics": topics,
            "tags": tags,
            "response_modes": ["post_seed", "belief_evidence"],
            "routing_status": "pending_segmentation",
            "feed_ready": False,
            "segmentation_ready": False,
            "origin": "media_pipeline",
            "word_count": meta.get("word_count"),
            "summary_origin": _clean_text(meta.get("summary_origin")) or "unknown",
            "structured_summary": structured_summary,
            "lessons_learned": lessons,
            "key_anecdotes": anecdotes,
            "reusable_quotes": quotes,
            "open_questions": open_questions,
            "clean_word_count": meta.get("clean_word_count"),
            "sentence_count": meta.get("sentence_count"),
            "quality_flags": quality_flags,
        }
        assets.append(asset)
    return assets


def build_source_asset_inventory(*, transcripts_root: Path, ingestions_root: Path, repo_root: Path) -> dict[str, Any]:
    assets = _build_transcript_note_assets(transcripts_root, repo_root) + _build_ingestion_assets(ingestions_root, repo_root)

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for asset in assets:
        fingerprint = _asset_fingerprint(asset)
        existing = deduped.get(fingerprint)
        if existing is None or _asset_rank(asset) > _asset_rank(existing):
            deduped[fingerprint] = asset

    items = sorted(
        deduped.values(),
        key=lambda asset: (
            _clean_text(asset.get("captured_at")) or "",
            _clean_text(asset.get("title")).lower(),
        ),
        reverse=True,
    )

    by_channel: dict[str, int] = {}
    for item in items:
        channel = _clean_text(item.get("source_channel")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1

    return {
        "generated_at": _timestamp_now(),
        "workspace": "linkedin-content-os",
        "items": items,
        "counts": {
            "total": len(items),
            "long_form_media": len(items),
            "pending_segmentation": sum(1 for item in items if item.get("routing_status") == "pending_segmentation"),
            "feed_ready": sum(1 for item in items if item.get("feed_ready")),
            "structured_summary_ready": sum(1 for item in items if _clean_text(item.get("structured_summary"))),
            "lessons_ready": sum(1 for item in items if item.get("lessons_learned")),
            "anecdotes_ready": sum(1 for item in items if item.get("key_anecdotes")),
            "quotes_ready": sum(1 for item in items if item.get("reusable_quotes")),
            "by_channel": by_channel,
        },
    }
