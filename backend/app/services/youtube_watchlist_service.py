from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import yaml

from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service
from app.services.social_feed_builder_service import discover_linkedin_workspace_root
from app.services.social_source_asset_service import build_source_asset_inventory

LOGGER = logging.getLogger(__name__)
USER_AGENT = "AICloneYouTubeWatchlist/1.0 (+https://aiclone-frontend-production.up.railway.app)"
HTTP_TIMEOUT = 15
ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
WATCHLIST_LIMIT_PER_CHANNEL = max(1, int(os.getenv("YOUTUBE_WATCHLIST_LIMIT_PER_CHANNEL", "3")))
WHISPER_MODEL_NAME = os.getenv("YOUTUBE_INGEST_WHISPER_MODEL", "base")
AUTO_INGEST_MAX_VIDEOS_PER_RUN = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_MAX_VIDEOS_PER_RUN", "3")))
AUTO_INGEST_PER_CHANNEL_LIMIT = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_PER_CHANNEL_LIMIT", "1")))

_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_whisper_model_cache: dict[str, Any] = {}


def _candidate_roots() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/app/backend"), Path("/")]
    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _find_dir(*relative_patterns: str) -> Path | None:
    for base in _candidate_roots():
        for pattern in relative_patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_dir():
                return candidate
    return None


def _watchlist_path(workspace_root: Path | None = None) -> Path:
    resolved_root = workspace_root or discover_linkedin_workspace_root()
    return resolved_root / "research" / "watchlists.yaml"


def _ingestions_root() -> Path:
    direct = _find_dir("backend/knowledge/ingestions", "knowledge/ingestions")
    if direct:
        return direct
    return Path(__file__).resolve().parents[3] / "knowledge" / "ingestions"


def _transcripts_root() -> Path:
    direct = _find_dir("backend/knowledge/aiclone/transcripts", "knowledge/aiclone/transcripts")
    if direct:
        return direct
    return Path(__file__).resolve().parents[3] / "knowledge" / "aiclone" / "transcripts"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _truncate(value: str, limit: int = 280) -> str:
    cleaned = _clean_text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _load_watchlist(workspace_root: Path | None = None) -> dict[str, Any]:
    path = _watchlist_path(workspace_root)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _clean_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _http_get(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = Request(url, headers=headers)
    with urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return response.read()


def _extract_channel_id(url: str) -> str:
    parsed = urlparse(url)
    query_channel = parse_qs(parsed.query).get("channel_id") or []
    if query_channel:
        return _clean_text(query_channel[0])
    match = re.search(r"/channel/([A-Za-z0-9_-]+)", parsed.path)
    if match:
        return match.group(1)
    return ""


def _resolve_channel_feed_url(url: str) -> tuple[str | None, str | None]:
    channel_id = _extract_channel_id(url)
    if channel_id:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", channel_id

    try:
        raw = _http_get(url, accept="text/html")
        html = raw.decode("utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        LOGGER.warning("Unable to resolve YouTube channel feed for %s: %s", url, exc)
        return None, None

    feed_match = re.search(r'https://www\.youtube\.com/feeds/videos\.xml\?channel_id=([A-Za-z0-9_-]+)', html)
    if feed_match:
        channel_id = feed_match.group(1)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", channel_id

    id_match = re.search(r'"channelId":"([A-Za-z0-9_-]+)"', html)
    if id_match:
        channel_id = id_match.group(1)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", channel_id
    return None, None


def _parse_published(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _extract_existing_source_urls() -> set[str]:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        payload = build_source_asset_inventory(
            transcripts_root=_transcripts_root(),
            ingestions_root=_ingestions_root(),
            repo_root=repo_root,
        )
    except Exception:
        return set()
    urls = {
        _clean_text(item.get("source_url"))
        for item in (payload.get("items") or [])
        if isinstance(item, dict) and _clean_text(item.get("source_url"))
    }
    return {url for url in urls if url}


def _auto_ingest_config(watchlist: dict[str, Any]) -> dict[str, Any]:
    config = watchlist.get("youtube_auto_ingest") if isinstance(watchlist.get("youtube_auto_ingest"), dict) else {}
    return {
        "enabled": bool(config.get("enabled", True)),
        "max_videos_per_run": _clean_int(config.get("max_videos_per_run"), AUTO_INGEST_MAX_VIDEOS_PER_RUN),
        "per_channel_limit": _clean_int(config.get("per_channel_limit"), AUTO_INGEST_PER_CHANNEL_LIMIT),
    }


def _channel_auto_ingest_enabled(channel: dict[str, Any]) -> bool:
    if not isinstance(channel, dict):
        return False
    if "auto_ingest" in channel:
        return bool(channel.get("auto_ingest"))
    ingest_mode = _clean_text(channel.get("ingest_mode")).lower()
    if ingest_mode in {"manual_only", "rss_primary", "use_podcast_feed_now"}:
        return False
    return True


def _fetch_channel_entries(channel: dict[str, Any], *, limit: int, existing_urls: set[str]) -> dict[str, Any]:
    channel_name = _clean_text(channel.get("name")) or "YouTube channel"
    channel_url = _clean_text(channel.get("url"))
    purpose = _clean_text(channel.get("purpose"))
    priority_lane = _clean_text(channel.get("priority_lane")) or "ai"
    feed_url, channel_id = _resolve_channel_feed_url(channel_url)
    payload = {
        "name": channel_name,
        "url": channel_url,
        "purpose": purpose,
        "priority_lane": priority_lane,
        "channel_id": channel_id,
        "feed_url": feed_url,
        "videos": [],
    }
    if not feed_url:
        payload["error"] = "Unable to resolve YouTube channel feed."
        return payload

    try:
        raw = _http_get(feed_url, accept="application/atom+xml, application/xml, text/xml")
        root = ET.fromstring(raw)
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        payload["error"] = str(exc)
        return payload

    videos: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        video_id = _clean_text(entry.findtext("yt:videoId", default="", namespaces=ATOM_NS))
        video_url = _clean_text(entry.findtext("atom:link", default="", namespaces=ATOM_NS))
        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        if not video_url or not title:
            continue
        author_name = _clean_text(entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS)) or channel_name
        published_at = _parse_published(entry.findtext("atom:published", default="", namespaces=ATOM_NS))
        summary = _truncate(
            _clean_text(entry.findtext("media:group/media:description", default="", namespaces=ATOM_NS))
            or _clean_text(entry.findtext("atom:group/media:description", default="", namespaces=ATOM_NS))
        )
        thumbnail_url = ""
        thumbnail = entry.find("media:group/media:thumbnail", ATOM_NS)
        if thumbnail is not None:
            thumbnail_url = _clean_text(thumbnail.attrib.get("url"))
        videos.append(
            {
                "title": title,
                "url": video_url,
                "video_id": video_id,
                "author": author_name,
                "published_at": published_at,
                "summary": summary,
                "thumbnail_url": thumbnail_url,
                "priority_lane": priority_lane,
                "channel_name": channel_name,
                "channel_url": channel_url,
                "already_ingested": video_url in existing_urls,
            }
        )
    payload["videos"] = videos
    return payload


def _transcription_runtime() -> dict[str, Any]:
    return {
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "whisper": importlib.util.find_spec("whisper") is not None,
    }


def _can_transcribe() -> bool:
    runtime = _transcription_runtime()
    return runtime["yt_dlp"] and runtime["ffmpeg"] and runtime["whisper"]


def _first_line(value: str | None) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    for line in text.splitlines():
        cleaned = _clean_text(line)
        if cleaned:
            return cleaned
    return text


def _yt_dlp_json(url: str) -> dict[str, Any]:
    result = subprocess.run(
        ["yt-dlp", "--dump-single-json", "--no-playlist", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _download_audio(url: str, temp_dir: str) -> Path:
    output_template = str(Path(temp_dir) / "%(id)s.%(ext)s")
    subprocess.run(
        ["yt-dlp", "--no-playlist", "-x", "--audio-format", "mp3", "-o", output_template, url],
        check=True,
        capture_output=True,
        text=True,
    )
    files = sorted(Path(temp_dir).glob("*"))
    audio_files = [path for path in files if path.suffix.lower() in {".mp3", ".m4a", ".wav", ".webm", ".opus"}]
    if not audio_files:
        raise RuntimeError("yt-dlp did not produce an audio file.")
    return audio_files[0]


def _whisper_model(model_name: str):
    cached = _whisper_model_cache.get(model_name)
    if cached is not None:
        return cached
    import whisper  # type: ignore

    model = whisper.load_model(model_name)
    _whisper_model_cache[model_name] = model
    return model


def _transcribe_youtube_url(url: str) -> tuple[str, dict[str, Any]]:
    metadata = _yt_dlp_json(url)
    with tempfile.TemporaryDirectory(prefix="youtube-watchlist-") as temp_dir:
        audio_path = _download_audio(url, temp_dir)
        model = _whisper_model(WHISPER_MODEL_NAME)
        result = model.transcribe(str(audio_path), verbose=False)
    transcript = _clean_text(result.get("text"))
    return transcript, metadata


def _ingest_watchlist_video(
    *,
    url: str,
    title: str | None = None,
    summary: str | None = None,
    author: str | None = None,
    channel_name: str | None = None,
    priority_lane: str | None = None,
    run_refresh: bool = True,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    transcript_text = ""
    ingestion_mode = "url_only"
    if _can_transcribe():
        transcript_text, metadata = _transcribe_youtube_url(url)
        ingestion_mode = "transcribed" if transcript_text else "url_only"
    else:
        try:
            metadata = _yt_dlp_json(url) if shutil.which("yt-dlp") else {}
        except Exception:
            metadata = {}

    resolved_title = _clean_text(title) or _clean_text(metadata.get("title")) or "YouTube source"
    resolved_summary = _clean_text(summary) or _first_line(_clean_text(metadata.get("description")))
    resolved_author = _clean_text(author) or _clean_text(metadata.get("channel")) or _clean_text(channel_name) or "unknown"
    notes = "\n".join(
        part
        for part in [
            f"Selected from YouTube watchlist: {channel_name}." if _clean_text(channel_name) else "Selected from YouTube watchlist.",
            f"Priority lane: {priority_lane}." if _clean_text(priority_lane) else "",
            "Transcript captured automatically via local media runtime." if ingestion_mode == "transcribed" else "Registered from link. Transcript capture still pending.",
        ]
        if part
    )
    result = brain_long_form_ingest_service.register_source(
        url=url,
        title=resolved_title,
        summary=resolved_summary or None,
        notes=notes,
        transcript_text=transcript_text or None,
        source_type="youtube_transcript",
        author=resolved_author or None,
        run_refresh=run_refresh,
    )
    result["ingestion_mode"] = ingestion_mode
    result["transcript_word_count"] = len((transcript_text or "").split()) if transcript_text else 0
    return result


def build_youtube_watchlist_payload(workspace_root: Path | None = None) -> dict[str, Any]:
    watchlist = _load_watchlist(workspace_root)
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []
    auto_ingest = _auto_ingest_config(watchlist)
    existing_urls = _extract_existing_source_urls()
    channel_payloads = [_fetch_channel_entries(channel, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls) for channel in channels if isinstance(channel, dict)]
    total_videos = sum(len(channel.get("videos") or []) for channel in channel_payloads)
    already_ingested = sum(
        1
        for channel in channel_payloads
        for video in channel.get("videos") or []
        if isinstance(video, dict) and bool(video.get("already_ingested"))
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "runtime": {
            **_transcription_runtime(),
            "can_transcribe": _can_transcribe(),
            "whisper_model": WHISPER_MODEL_NAME,
        },
        "auto_ingest": auto_ingest,
        "channels": channel_payloads,
        "counts": {
            "channels": len(channel_payloads),
            "videos": total_videos,
            "already_ingested": already_ingested,
        },
    }


def _job_snapshot(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "url": job.get("url"),
        "title": job.get("title"),
        "channel_name": job.get("channel_name"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "ingestion_mode": job.get("ingestion_mode"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


def list_ingest_jobs(limit: int = 12) -> list[dict[str, Any]]:
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda item: item.get("created_at") or "", reverse=True)
        return [_job_snapshot(job) for job in jobs[:limit]]


def queue_youtube_ingest(
    *,
    url: str,
    title: str | None = None,
    author: str | None = None,
    summary: str | None = None,
    channel_name: str | None = None,
    priority_lane: str | None = None,
    run_refresh: bool = True,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "url": _clean_text(url),
        "title": _clean_text(title),
        "author": _clean_text(author),
        "summary": _clean_text(summary),
        "channel_name": _clean_text(channel_name),
        "priority_lane": _clean_text(priority_lane),
        "run_refresh": bool(run_refresh),
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "ingestion_mode": "pending",
        "error": None,
        "result": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return _job_snapshot(job)


def sync_watchlist_auto_ingest(
    *,
    workspace_root: Path | None = None,
    max_videos_per_run: int | None = None,
    per_channel_limit: int | None = None,
    run_refresh: bool = False,
) -> dict[str, Any]:
    watchlist = _load_watchlist(workspace_root)
    config = _auto_ingest_config(watchlist)
    if not config["enabled"]:
        return {
            "enabled": False,
            "ingested": [],
            "skipped": [],
            "errors": [],
            "counts": {"discovered": 0, "ingested": 0, "skipped": 0, "errors": 0},
        }

    total_limit = max_videos_per_run or config["max_videos_per_run"]
    channel_limit = per_channel_limit or config["per_channel_limit"]
    existing_urls = _extract_existing_source_urls()
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []

    discovered: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ingested: list[dict[str, Any]] = []

    for channel in channels:
        if not isinstance(channel, dict):
            continue
        if not _channel_auto_ingest_enabled(channel):
            skipped.append(
                {
                    "channel_name": _clean_text(channel.get("name")) or "YouTube channel",
                    "reason": "auto_ingest_disabled",
                }
            )
            continue
        payload = _fetch_channel_entries(channel, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls)
        channel_name = _clean_text(payload.get("name")) or "YouTube channel"
        if payload.get("error"):
            errors.append({"channel_name": channel_name, "reason": payload.get("error")})
            continue
        fresh_videos = [video for video in payload.get("videos") or [] if isinstance(video, dict) and not bool(video.get("already_ingested"))]
        fresh_videos.sort(key=lambda item: _clean_text(item.get("published_at")), reverse=True)
        for video in fresh_videos[:channel_limit]:
            video_copy = dict(video)
            video_copy["channel_name"] = channel_name
            discovered.append(video_copy)

    discovered.sort(key=lambda item: _clean_text(item.get("published_at")), reverse=True)
    selected = discovered[:total_limit]
    selected_urls = {_clean_text(item.get("url")) for item in selected if _clean_text(item.get("url"))}

    for item in discovered[total_limit:]:
        skipped.append({"url": item.get("url"), "title": item.get("title"), "channel_name": item.get("channel_name"), "reason": "run_limit"})

    for item in selected:
        url = _clean_text(item.get("url"))
        try:
            result = _ingest_watchlist_video(
                url=url,
                title=item.get("title"),
                summary=item.get("summary"),
                author=item.get("author"),
                channel_name=item.get("channel_name"),
                priority_lane=item.get("priority_lane"),
                run_refresh=False,
            )
            ingested.append(
                {
                    "url": url,
                    "title": item.get("title"),
                    "channel_name": item.get("channel_name"),
                    "ingestion_mode": result.get("ingestion_mode"),
                    "asset_id": result.get("asset_id"),
                }
            )
        except Exception as exc:  # pragma: no cover - runtime dependent
            LOGGER.exception("Auto-ingest failed for watchlist video %s", url)
            errors.append({"url": url, "title": item.get("title"), "channel_name": item.get("channel_name"), "reason": str(exc)})

    for item in discovered:
        url = _clean_text(item.get("url"))
        if url in selected_urls:
            continue
        if url in existing_urls:
            skipped.append({"url": url, "title": item.get("title"), "channel_name": item.get("channel_name"), "reason": "already_ingested"})

    if run_refresh and ingested:
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        workspace_snapshot_service.refresh_persisted_linkedin_os_state()

    return {
        "enabled": True,
        "auto_ingest": config,
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
        "counts": {
            "discovered": len(discovered),
            "ingested": len(ingested),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }


def run_ingest_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = _ingest_watchlist_video(
            url=job["url"],
            title=job.get("title"),
            summary=job.get("summary"),
            author=job.get("author"),
            channel_name=job.get("channel_name"),
            priority_lane=job.get("priority_lane"),
            run_refresh=bool(job.get("run_refresh", True)),
        )
        with _jobs_lock:
            stored = _jobs.get(job_id)
            if stored:
                stored["status"] = "completed"
                stored["updated_at"] = datetime.now(timezone.utc).isoformat()
                stored["completed_at"] = stored["updated_at"]
                stored["ingestion_mode"] = result.get("ingestion_mode")
                stored["result"] = result
    except Exception as exc:  # pragma: no cover - runtime dependent
        LOGGER.exception("YouTube watchlist ingest failed for %s", job_id)
        with _jobs_lock:
            stored = _jobs.get(job_id)
            if stored:
                stored["status"] = "failed"
                stored["updated_at"] = datetime.now(timezone.utc).isoformat()
                stored["completed_at"] = stored["updated_at"]
                stored["error"] = str(exc)
