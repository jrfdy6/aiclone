from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
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
from app.services.workspace_snapshot_store import get_snapshot_payload, upsert_snapshot

LOGGER = logging.getLogger(__name__)


def _bounded_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


USER_AGENT = "AICloneYouTubeWatchlist/1.0 (+https://aiclone-frontend-production.up.railway.app)"
HTTP_TIMEOUT = 15
YOUTUBE_WATCHLIST_WORKSPACE_KEY = "linkedin-content-os"
YOUTUBE_WATCHLIST_SNAPSHOT_TYPE = "youtube_watchlist"
LOCAL_WHISPER_PYTHON_ENV = "LOCAL_WHISPER_PYTHON"
LOCAL_WHISPER_FALLBACK_PYTHON = Path("/usr/bin/python3")
LOCAL_WHISPER_RESULT_PREFIX = "AICLONE_LOCAL_WHISPER_RESULT:"
WHISPER_PROBE_TIMEOUT_SECONDS = 20
WHISPER_RUNTIME_PROBE_TTL_SECONDS = _bounded_env_int(
    "YOUTUBE_INGEST_WHISPER_PROBE_TTL_SECONDS",
    300,
    minimum=30,
    maximum=1800,
)
WHISPER_TRANSCRIBE_TIMEOUT_SECONDS = _bounded_env_int(
    "YOUTUBE_INGEST_WHISPER_TIMEOUT_SECONDS",
    3600,
    minimum=60,
    maximum=7200,
)
SUPPORTED_WHISPER_MODELS = {
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large",
    "large-v1",
    "large-v2",
    "large-v3",
    "turbo",
}
LOCAL_WHISPER_ENV_ALLOWLIST = {
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "SSL_CERT_FILE",
    "TMPDIR",
    "TORCH_HOME",
    "XDG_CACHE_HOME",
}
LOCAL_WHISPER_PROBE_CODE = """
import json

try:
    import whisper
    ok = callable(getattr(whisper, "load_model", None))
except Exception:
    ok = False

print("AICLONE_LOCAL_WHISPER_RESULT:" + json.dumps({"ok": ok}))
raise SystemExit(0 if ok else 3)
""".strip()
LOCAL_WHISPER_TRANSCRIBE_CODE = """
import json
import sys

import whisper

if not callable(getattr(whisper, "load_model", None)):
    raise RuntimeError("Whisper module does not expose load_model")
model = whisper.load_model(sys.argv[2])
result = model.transcribe(sys.argv[1], verbose=False)
text = result.get("text", "") if isinstance(result, dict) else ""
print("AICLONE_LOCAL_WHISPER_RESULT:" + json.dumps({"ok": True, "text": text}, ensure_ascii=False))
""".strip()
ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
WATCHLIST_LIMIT_PER_CHANNEL = max(1, int(os.getenv("YOUTUBE_WATCHLIST_LIMIT_PER_CHANNEL", "3")))
WHISPER_MODEL_NAME = os.getenv("YOUTUBE_INGEST_WHISPER_MODEL", "base")
AUTO_INGEST_MAX_VIDEOS_PER_RUN = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_MAX_VIDEOS_PER_RUN", "3")))
AUTO_INGEST_PER_CHANNEL_LIMIT = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_PER_CHANNEL_LIMIT", "1")))
AUTO_PENDING_TRANSCRIPT_BACKFILL_PER_RUN = max(0, int(os.getenv("YOUTUBE_PENDING_TRANSCRIPT_BACKFILL_PER_RUN", "2")))

_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_whisper_model_cache: dict[str, Any] = {}
_whisper_runtime_cache_lock = threading.Lock()
_whisper_runtime_cache_key: tuple[str, str] | None = None
_whisper_runtime_cache_at = 0.0
_whisper_runtime_cache_value: tuple[str, Path | None] | None = None


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    repo_root = _repo_root()
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
    if _running_on_railway():
        # Railway is the authenticated coordination plane, not the media host.
        # Probing /usr/bin/python there can block the first Brain request for
        # the full subprocess timeout even though ingestion is intentionally
        # delegated to the local Mac runner.
        return {
            "yt_dlp": False,
            "ffmpeg": False,
            "whisper": False,
            "whisper_mode": "unavailable",
            "whisper_in_process": False,
            "whisper_subprocess": False,
        }
    whisper_mode, _ = _whisper_runtime_probe()
    whisper_available = whisper_mode != "unavailable"
    return {
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "whisper": whisper_available,
        "whisper_mode": whisper_mode,
        "whisper_in_process": whisper_mode == "in_process",
        "whisper_subprocess": whisper_mode == "local_subprocess",
    }


def _running_on_railway() -> bool:
    return any(
        str(os.getenv(name) or "").strip()
        for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")
    )


def _in_process_whisper_available() -> bool:
    try:
        if importlib.util.find_spec("whisper") is None:
            return False
        whisper_module = importlib.import_module("whisper")
    except Exception:  # pragma: no cover - runtime dependent
        return False
    return callable(getattr(whisper_module, "load_model", None))


def _allowlisted_local_whisper_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv(LOCAL_WHISPER_PYTHON_ENV, "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_absolute():
            candidates.append(configured_path)
        else:
            LOGGER.warning(
                "Ignoring relative %s path; an absolute executable path is required",
                LOCAL_WHISPER_PYTHON_ENV,
            )
    candidates.append(LOCAL_WHISPER_FALLBACK_PYTHON)

    allowed: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_key = str(candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                allowed.append(candidate)
        except OSError:
            continue
    return allowed


def _local_whisper_result(stdout: str) -> dict[str, Any] | None:
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line.startswith(LOCAL_WHISPER_RESULT_PREFIX):
            continue
        try:
            payload = json.loads(line[len(LOCAL_WHISPER_RESULT_PREFIX) :])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _local_whisper_subprocess_env() -> dict[str, str]:
    environment = {
        key: value
        for key in LOCAL_WHISPER_ENV_ALLOWLIST
        if (value := os.getenv(key))
    }
    environment["PATH"] = environment.get("PATH", os.defpath)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _probe_local_whisper_python(python_path: Path) -> bool:
    try:
        result = subprocess.run(
            [str(python_path), "-c", LOCAL_WHISPER_PROBE_CODE],
            check=False,
            capture_output=True,
            text=True,
            timeout=WHISPER_PROBE_TIMEOUT_SECONDS,
            shell=False,
            env=_local_whisper_subprocess_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    payload = _local_whisper_result(result.stdout)
    return result.returncode == 0 and bool(payload and payload.get("ok") is True)


def _uncached_whisper_runtime_probe() -> tuple[str, Path | None]:
    if _in_process_whisper_available():
        return "in_process", None
    for python_path in _allowlisted_local_whisper_python_candidates():
        if _probe_local_whisper_python(python_path):
            return "local_subprocess", python_path
    return "unavailable", None


def _clear_whisper_runtime_probe_cache() -> None:
    global _whisper_runtime_cache_at, _whisper_runtime_cache_key, _whisper_runtime_cache_value
    with _whisper_runtime_cache_lock:
        _whisper_runtime_cache_key = None
        _whisper_runtime_cache_at = 0.0
        _whisper_runtime_cache_value = None


def _whisper_runtime_probe() -> tuple[str, Path | None]:
    global _whisper_runtime_cache_at, _whisper_runtime_cache_key, _whisper_runtime_cache_value
    cache_key = (
        os.getenv(LOCAL_WHISPER_PYTHON_ENV, "").strip(),
        str(LOCAL_WHISPER_FALLBACK_PYTHON),
    )
    now = time.monotonic()
    with _whisper_runtime_cache_lock:
        if (
            _whisper_runtime_cache_key == cache_key
            and _whisper_runtime_cache_value is not None
            and now - _whisper_runtime_cache_at < WHISPER_RUNTIME_PROBE_TTL_SECONDS
        ):
            return _whisper_runtime_cache_value
        probed = _uncached_whisper_runtime_probe()
        _whisper_runtime_cache_key = cache_key
        _whisper_runtime_cache_at = time.monotonic()
        _whisper_runtime_cache_value = probed
        return probed


def _can_attempt_youtube_transcript() -> bool:
    runtime = _transcription_runtime()
    return runtime["yt_dlp"]


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


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def _pending_transcript_summary(summary: str) -> bool:
    lowered = _clean_text(summary).lower()
    if not lowered:
        return True
    return lowered.startswith("selected from youtube watchlist") or lowered.startswith("pending transcript")


def _asset_needs_transcript_backfill(asset: dict[str, Any], *, repo_root: Path) -> bool:
    if _clean_text(asset.get("source_channel")).lower() != "youtube":
        return False
    if _clean_text(asset.get("source_type")).lower() != "youtube_transcript":
        return False
    if not _clean_text(asset.get("source_url")):
        return False
    word_count = asset.get("word_count")
    if isinstance(word_count, (int, float)) and word_count > 0:
        return False

    source_path = _clean_text(asset.get("source_path"))
    if not source_path:
        return False
    normalized_path = repo_root / source_path
    if not normalized_path.exists():
        return False
    raw = normalized_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    meta_word_count = meta.get("word_count")
    if isinstance(meta_word_count, (int, float)) and meta_word_count > 0:
        return False
    body_text = _clean_text(body).lower()
    if body_text.startswith("# source notes") or "transcript capture still pending" in body_text:
        return True
    return _pending_transcript_summary(_clean_text(meta.get("summary")) or _clean_text(asset.get("summary")))


def _pending_youtube_transcript_assets(*, repo_root: Path) -> list[dict[str, Any]]:
    inventory = build_source_asset_inventory(
        transcripts_root=_transcripts_root(),
        ingestions_root=_ingestions_root(),
        repo_root=repo_root,
    )
    return [
        asset
        for asset in (inventory.get("items") or [])
        if isinstance(asset, dict) and _asset_needs_transcript_backfill(asset, repo_root=repo_root)
    ]


def _write_backfilled_transcript(asset: dict[str, Any], transcript_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    repo_root = _repo_root()
    source_path = _clean_text(asset.get("source_path"))
    if not source_path:
        raise RuntimeError("Pending YouTube asset is missing source_path.")
    normalized_path = repo_root / source_path
    if not normalized_path.exists():
        raise RuntimeError(f"Pending YouTube asset not found: {source_path}")

    raw = normalized_path.read_text(encoding="utf-8")
    frontmatter, _body = _parse_frontmatter(raw)
    asset_dir = normalized_path.parent
    raw_dir = asset_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    transcript_rel = "raw/transcript.txt"
    transcript_path = asset_dir / transcript_rel
    transcript_path.write_text(transcript_text.strip() + "\n", encoding="utf-8")

    raw_files = []
    for item in list(frontmatter.get("raw_files") or []):
        text = _clean_text(item)
        if text and text not in raw_files:
            raw_files.append(text)
    if transcript_rel not in raw_files:
        raw_files.append(transcript_rel)

    tags = []
    for item in list(frontmatter.get("tags") or []):
        text = _clean_text(item)
        if text and text not in tags:
            tags.append(text)
    if "auto_transcribed" not in tags:
        tags.append("auto_transcribed")

    summary = _first_line(transcript_text) or _first_line(_clean_text(metadata.get("description"))) or _clean_text(frontmatter.get("summary"))
    if _clean_text(metadata.get("title")) and _clean_text(frontmatter.get("title")).lower() == "youtube source":
        frontmatter["title"] = _clean_text(metadata.get("title"))
    if _clean_text(metadata.get("channel")) and _clean_text(frontmatter.get("author")).lower() in {"", "unknown"}:
        frontmatter["author"] = _clean_text(metadata.get("channel"))
    frontmatter["raw_files"] = raw_files
    frontmatter["word_count"] = len(transcript_text.split())
    frontmatter["summary"] = _truncate(summary, 280) if summary else _clean_text(frontmatter.get("summary"))
    frontmatter["tags"] = tags

    normalized_path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False).strip()}\n---\n\n# Clean Transcript / Document\n{transcript_text.strip()}\n",
        encoding="utf-8",
    )

    routing_status_path = asset_dir / "routing_status.json"
    routing_status_path.write_text(
        json.dumps(
            {
                "asset_id": _clean_text(frontmatter.get("id")) or _clean_text(asset.get("asset_id")),
                "status": "pending_segmentation",
                "source_channel": "youtube",
                "source_type": "youtube_transcript",
                "has_transcript": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "asset_id": _clean_text(frontmatter.get("id")) or _clean_text(asset.get("asset_id")),
        "title": _clean_text(frontmatter.get("title")) or _clean_text(asset.get("title")),
        "source_url": _clean_text(frontmatter.get("source_url")) or _clean_text(asset.get("source_url")),
        "source_path": source_path,
        "word_count": int(frontmatter.get("word_count") or 0),
    }


def backfill_pending_youtube_transcripts(*, limit: int | None = None, run_refresh: bool = False) -> dict[str, Any]:
    repo_root = _repo_root()
    pending_assets = _pending_youtube_transcript_assets(repo_root=repo_root)
    selected_limit = AUTO_PENDING_TRANSCRIPT_BACKFILL_PER_RUN if limit is None else max(0, int(limit))
    selected = pending_assets[:selected_limit] if selected_limit > 0 else []

    backfilled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if not _can_attempt_youtube_transcript():
        for asset in selected:
            skipped.append(
                {
                    "asset_id": _clean_text(asset.get("asset_id")),
                    "title": _clean_text(asset.get("title")),
                    "reason": "transcription_runtime_unavailable",
                }
            )
        return {
            "runtime": _transcription_runtime(),
            "pending_total": len(pending_assets),
            "selected_count": len(selected),
            "backfilled": backfilled,
            "skipped": skipped,
            "errors": errors,
            "counts": {
                "pending_total": len(pending_assets),
                "selected": len(selected),
                "backfilled": 0,
                "skipped": len(skipped),
                "errors": 0,
            },
        }

    for asset in selected:
        url = _clean_text(asset.get("source_url"))
        try:
            transcript_text, metadata = _transcribe_youtube_url(url)
            if not transcript_text:
                skipped.append(
                    {
                        "asset_id": _clean_text(asset.get("asset_id")),
                        "title": _clean_text(asset.get("title")),
                        "reason": "empty_transcript",
                    }
                )
                continue
            updated = _write_backfilled_transcript(asset, transcript_text, metadata)
            updated["transcript_word_count"] = len(transcript_text.split())
            backfilled.append(updated)
        except Exception as exc:  # pragma: no cover - runtime dependent
            LOGGER.exception("Pending YouTube transcript backfill failed for %s", url)
            errors.append(
                {
                    "asset_id": _clean_text(asset.get("asset_id")),
                    "title": _clean_text(asset.get("title")),
                    "url": url,
                    "reason": str(exc),
                }
            )

    if run_refresh and backfilled:
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        workspace_snapshot_service.refresh_persisted_linkedin_os_state()

    return {
        "runtime": _transcription_runtime(),
        "pending_total": len(pending_assets),
        "selected_count": len(selected),
        "backfilled": backfilled,
        "skipped": skipped,
        "errors": errors,
        "counts": {
            "pending_total": len(pending_assets),
            "selected": len(selected),
            "backfilled": len(backfilled),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }


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


def _subtitle_text_from_vtt(path: Path) -> str:
    lines: list[str] = []
    last_line = ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        if line.startswith("NOTE"):
            continue
        if line == last_line:
            continue
        lines.append(line)
        last_line = line
    return " ".join(lines).strip()


def _download_subtitle_transcript(url: str, temp_dir: str) -> str:
    output_template = str(Path(temp_dir) / "%(id)s.%(ext)s")
    subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "en.*,en-US,en",
            "--sub-format",
            "vtt/best",
            "--convert-subs",
            "vtt",
            "-o",
            output_template,
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subtitle_candidates = sorted(Path(temp_dir).glob("*.vtt"), key=lambda item: item.stat().st_size, reverse=True)
    for candidate in subtitle_candidates:
        transcript = _subtitle_text_from_vtt(candidate)
        if transcript:
            return transcript
    return ""


def _whisper_model(model_name: str):
    cached = _whisper_model_cache.get(model_name)
    if cached is not None:
        return cached
    import whisper  # type: ignore

    if not callable(getattr(whisper, "load_model", None)):
        raise RuntimeError(
            "Installed 'whisper' module does not expose load_model; install openai-whisper in the local runtime."
        )
    model = whisper.load_model(model_name)
    _whisper_model_cache[model_name] = model
    return model


def _validated_whisper_model_name(model_name: str) -> str:
    cleaned = _clean_text(model_name).lower()
    if cleaned not in SUPPORTED_WHISPER_MODELS:
        raise RuntimeError("Unsupported local Whisper model configuration.")
    return cleaned


def _transcribe_with_local_whisper_python(audio_path: Path, model_name: str, python_path: Path) -> str:
    try:
        result = subprocess.run(
            [
                str(python_path),
                "-c",
                LOCAL_WHISPER_TRANSCRIBE_CODE,
                str(audio_path),
                model_name,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=WHISPER_TRANSCRIBE_TIMEOUT_SECONDS,
            shell=False,
            env=_local_whisper_subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Local Whisper transcription timed out after {WHISPER_TRANSCRIBE_TIMEOUT_SECONDS} seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError("Local Whisper Python runtime could not be started.") from exc

    payload = _local_whisper_result(result.stdout)
    if result.returncode != 0:
        LOGGER.warning("Local Whisper transcription exited with status %s", result.returncode)
        raise RuntimeError("Local Whisper transcription failed in the allowlisted runtime.")
    if not payload or payload.get("ok") is not True or not isinstance(payload.get("text"), str):
        raise RuntimeError("Local Whisper runtime returned an invalid transcription result.")
    return _clean_text(payload["text"])


def _transcribe_audio(audio_path: Path, model_name: str) -> str:
    resolved_model_name = _validated_whisper_model_name(model_name)
    whisper_mode, python_path = _whisper_runtime_probe()
    if whisper_mode == "in_process":
        result = _whisper_model(resolved_model_name).transcribe(str(audio_path), verbose=False)
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise RuntimeError("In-process Whisper returned an invalid transcription result.")
        return _clean_text(result["text"])
    if whisper_mode == "local_subprocess" and python_path is not None:
        return _transcribe_with_local_whisper_python(audio_path, resolved_model_name, python_path)
    raise RuntimeError("No supported local Whisper runtime is available.")


def _transcribe_youtube_url(url: str) -> tuple[str, dict[str, Any]]:
    metadata = _yt_dlp_json(url)
    with tempfile.TemporaryDirectory(prefix="youtube-watchlist-") as temp_dir:
        try:
            subtitle_transcript = _download_subtitle_transcript(url, temp_dir)
        except Exception:  # pragma: no cover - runtime dependent
            subtitle_transcript = ""
        if subtitle_transcript:
            return subtitle_transcript, metadata
        if not _can_transcribe():
            return "", metadata
        audio_path = _download_audio(url, temp_dir)
        transcript = _transcribe_audio(audio_path, WHISPER_MODEL_NAME)
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
    if _can_attempt_youtube_transcript():
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


def ingest_youtube_watchlist_video(
    *,
    url: str,
    title: str | None = None,
    summary: str | None = None,
    author: str | None = None,
    channel_name: str | None = None,
    priority_lane: str | None = None,
    run_refresh: bool = True,
) -> dict[str, Any]:
    """Deterministic local-runner entrypoint for one signed YouTube ingest action."""
    return _ingest_watchlist_video(
        url=url,
        title=title,
        summary=summary,
        author=author,
        channel_name=channel_name,
        priority_lane=priority_lane,
        run_refresh=run_refresh,
    )


def build_youtube_watchlist_payload(workspace_root: Path | None = None) -> dict[str, Any]:
    watchlist = _load_watchlist(workspace_root)
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []
    existing_urls = _extract_existing_source_urls()
    channel_payloads = [_fetch_channel_entries(channel, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls) for channel in channels if isinstance(channel, dict)]
    return _assemble_youtube_watchlist_payload(watchlist, channel_payloads, data_mode="live_refresh")


def _assemble_youtube_watchlist_payload(
    watchlist: dict[str, Any],
    channel_payloads: list[dict[str, Any]],
    *,
    data_mode: str,
) -> dict[str, Any]:
    auto_ingest = _auto_ingest_config(watchlist)
    total_videos = sum(len(channel.get("videos") or []) for channel in channel_payloads)
    already_ingested = sum(
        1
        for channel in channel_payloads
        for video in channel.get("videos") or []
        if isinstance(video, dict) and bool(video.get("already_ingested"))
    )
    pending_transcript_assets = _pending_youtube_transcript_assets(repo_root=_repo_root())
    runtime = _transcription_runtime()
    return {
        "schema_version": "youtube_watchlist/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "data_mode": data_mode,
        "runtime": {
            **runtime,
            "can_transcribe": bool(runtime.get("yt_dlp") and runtime.get("ffmpeg") and runtime.get("whisper")),
            "whisper_model": WHISPER_MODEL_NAME,
            "scope": "local_codex_runner",
        },
        "auto_ingest": auto_ingest,
        "channels": channel_payloads,
        "counts": {
            "channels": len(channel_payloads),
            "videos": total_videos,
            "already_ingested": already_ingested,
            "pending_transcript_backfill": len(pending_transcript_assets),
        },
        "pending_transcript_backfill": [
            {
                "asset_id": _clean_text(item.get("asset_id")),
                "title": _clean_text(item.get("title")),
                "source_url": _clean_text(item.get("source_url")),
                "source_path": _clean_text(item.get("source_path")),
            }
            for item in pending_transcript_assets[:12]
        ],
    }


def _configured_channel_payload(channel: dict[str, Any]) -> dict[str, Any]:
    channel_url = _clean_text(channel.get("url"))
    channel_id = _extract_channel_id(channel_url)
    return {
        "name": _clean_text(channel.get("name")) or "YouTube channel",
        "url": channel_url,
        "purpose": _clean_text(channel.get("purpose")),
        "priority_lane": _clean_text(channel.get("priority_lane")) or "ai",
        "channel_id": channel_id or None,
        "feed_url": f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}" if channel_id else None,
        "videos": [],
    }


def build_persisted_youtube_watchlist_payload(workspace_root: Path | None = None) -> dict[str, Any]:
    """Read the last local-runner snapshot without network calls or state writes."""
    try:
        persisted = get_snapshot_payload(YOUTUBE_WATCHLIST_WORKSPACE_KEY, YOUTUBE_WATCHLIST_SNAPSHOT_TYPE)
    except Exception:
        persisted = None
    if isinstance(persisted, dict) and persisted.get("schema_version") == "youtube_watchlist/v1":
        payload = dict(persisted)
        payload["data_mode"] = "persisted"
        return payload

    watchlist = _load_watchlist(workspace_root)
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []
    channel_payloads = [_configured_channel_payload(channel) for channel in channels if isinstance(channel, dict)]
    return {
        "schema_version": "youtube_watchlist/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": YOUTUBE_WATCHLIST_WORKSPACE_KEY,
        "data_mode": "configuration_only",
        "runtime": {
            "yt_dlp": False,
            "ffmpeg": False,
            "whisper": False,
            "whisper_mode": "unavailable",
            "whisper_in_process": False,
            "whisper_subprocess": False,
            "can_transcribe": False,
            "whisper_model": WHISPER_MODEL_NAME,
            "scope": "local_codex_runner",
        },
        "auto_ingest": _auto_ingest_config(watchlist),
        "channels": channel_payloads,
        "counts": {
            "channels": len(channel_payloads),
            "videos": 0,
            "already_ingested": 0,
            "pending_transcript_backfill": 0,
        },
        "pending_transcript_backfill": [],
    }


def _persist_youtube_watchlist_payload(payload: dict[str, Any]) -> bool:
    try:
        snapshot = upsert_snapshot(
            YOUTUBE_WATCHLIST_WORKSPACE_KEY,
            YOUTUBE_WATCHLIST_SNAPSHOT_TYPE,
            payload,
            metadata={
                "source": "codex_launchd_youtube_watchlist",
                "payload_generated_at": payload.get("generated_at"),
            },
        )
    except Exception:
        LOGGER.exception("Unable to persist YouTube watchlist snapshot")
        return False
    return snapshot is not None


def youtube_watchlist_runtime_status() -> dict[str, Any]:
    pending_transcript_assets = _pending_youtube_transcript_assets(repo_root=_repo_root())
    runtime = _transcription_runtime()
    return {
        "runtime": {
            **runtime,
            "can_transcribe": _can_transcribe(),
            "whisper_model": WHISPER_MODEL_NAME,
        },
        "pending_transcript_backfill": len(pending_transcript_assets),
        "pending_transcript_assets": [
            {
                "asset_id": _clean_text(item.get("asset_id")),
                "title": _clean_text(item.get("title")),
                "source_url": _clean_text(item.get("source_url")),
                "source_path": _clean_text(item.get("source_path")),
            }
            for item in pending_transcript_assets[:12]
        ],
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
    channel_payloads: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ingested: list[dict[str, Any]] = []
    backfill_result = backfill_pending_youtube_transcripts(run_refresh=False)

    for channel in channels:
        if not isinstance(channel, dict):
            continue
        if not _channel_auto_ingest_enabled(channel):
            channel_payloads.append(_configured_channel_payload(channel))
            skipped.append(
                {
                    "channel_name": _clean_text(channel.get("name")) or "YouTube channel",
                    "reason": "auto_ingest_disabled",
                }
            )
            continue
        payload = _fetch_channel_entries(channel, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls)
        channel_payloads.append(payload)
        channel_name = _clean_text(payload.get("name")) or "YouTube channel"
        if payload.get("error"):
            warnings.append(
                {
                    "kind": "channel_fetch_failed",
                    "channel_name": channel_name,
                    "url": _clean_text(channel.get("url")),
                    "reason": _clean_text(payload.get("error")),
                }
            )
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

    if run_refresh and (ingested or (backfill_result.get("backfilled") or [])):
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        workspace_snapshot_service.refresh_persisted_linkedin_os_state()

    ingested_urls = {_clean_text(item.get("url")) for item in ingested if _clean_text(item.get("url"))}
    if ingested_urls:
        for channel_payload in channel_payloads:
            for video in channel_payload.get("videos") or []:
                if isinstance(video, dict) and _clean_text(video.get("url")) in ingested_urls:
                    video["already_ingested"] = True
    watchlist_payload = _assemble_youtube_watchlist_payload(
        watchlist,
        channel_payloads,
        data_mode="local_runner_refresh",
    )
    watchlist_snapshot_persisted = _persist_youtube_watchlist_payload(watchlist_payload)

    return {
        "enabled": True,
        "auto_ingest": config,
        "backfill": backfill_result,
        "ingested": ingested,
        "skipped": skipped,
        "warnings": warnings,
        "errors": errors,
        "watchlist_snapshot_persisted": watchlist_snapshot_persisted,
        # The local automation reuses the payload for its authenticated
        # Railway mirror. Keeping it private to the caller avoids fetching
        # every channel feed a second time in the same run.
        "_watchlist_payload": watchlist_payload,
        "counts": {
            "discovered": len(discovered),
            "ingested": len(ingested),
            "backfilled": len(backfill_result.get("backfilled") or []),
            "skipped": len(skipped),
            "warnings": len(warnings),
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
