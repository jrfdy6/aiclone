from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from app.services import workspace_snapshot_service as workspace_snapshot_module


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")
    return cleaned[:72] or "long_form_source"


def _first_meaningful_line(value: str, *, limit: int = 220) -> str:
    for line in value.splitlines():
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

        clean_transcript = (transcript_text or "").strip()
        clean_notes = (notes or "").strip()
        clean_summary = _clean_text(summary) or _first_meaningful_line(clean_transcript) or _first_meaningful_line(clean_notes)
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
        if clean_transcript:
            transcript_path = raw_dir / "transcript.txt"
            transcript_path.write_text(clean_transcript, encoding="utf-8")
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
        }

        body_lines = []
        if clean_transcript:
            body_lines.extend(["# Clean Transcript / Document", clean_transcript])
        else:
            body_lines.extend(
                [
                    "# Source Notes",
                    clean_notes or f"Pending transcript capture for {clean_title}.",
                    "",
                    "## Owner Notes",
                    "- **Resonance:** Pending owner review.",
                    "- **Disagreements:** Pending owner review.",
                    "- **Applications:** Pending routing review for build and persona implications.",
                    "- **Quotes to reuse:** Pending owner review.",
                    "- **Open questions:** What build implications matter, what persona implications matter, and what should be emphasized?",
                ]
            )
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
