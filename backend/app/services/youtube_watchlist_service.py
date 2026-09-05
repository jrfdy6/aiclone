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
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import yaml

from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service
from app.services.content_lifecycle_service import PrivateContentArtifactStore
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.open_brain_db import database_configured
from app.services.source_intake_adapter_service import SourceIntakeAdapterService, youtube_discovery_envelope
from app.services.source_intake_execution_service import SourceIntakeExecutionService
from app.services.source_processing_service import SourceProcessingService
from app.services.social_feed_builder_service import discover_linkedin_workspace_root
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.workspace_snapshot_store import get_snapshot_payload, upsert_snapshot
from app.utils.runtime_workspace_root import resolve_runtime_workspace_root

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
YOUTUBE_CAPTURE_ATTEMPT_EVENT = "source.youtube_capture_attempt"
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
YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
WATCHLIST_LIMIT_PER_CHANNEL = max(1, int(os.getenv("YOUTUBE_WATCHLIST_LIMIT_PER_CHANNEL", "3")))
WHISPER_MODEL_NAME = os.getenv("YOUTUBE_INGEST_WHISPER_MODEL", "base")
AUTO_INGEST_MAX_VIDEOS_PER_RUN = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_MAX_VIDEOS_PER_RUN", "3")))
AUTO_INGEST_PER_CHANNEL_LIMIT = max(1, int(os.getenv("YOUTUBE_AUTO_INGEST_PER_CHANNEL_LIMIT", "1")))
AUTO_PENDING_TRANSCRIPT_BACKFILL_PER_RUN = max(0, int(os.getenv("YOUTUBE_PENDING_TRANSCRIPT_BACKFILL_PER_RUN", "2")))
PLAYLIST_MANIFEST_TIMEOUT_SECONDS = _bounded_env_int(
    "YOUTUBE_PLAYLIST_MANIFEST_TIMEOUT_SECONDS",
    120,
    minimum=15,
    maximum=600,
)
PLAYLIST_MANIFEST_MAX_ENTRIES = _bounded_env_int(
    "YOUTUBE_PLAYLIST_MANIFEST_MAX_ENTRIES",
    5_000,
    minimum=100,
    maximum=20_000,
)
PLAYLIST_PROJECTION_WINDOW = _bounded_env_int(
    "YOUTUBE_PLAYLIST_PROJECTION_WINDOW",
    12,
    minimum=3,
    maximum=50,
)

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
    return resolve_runtime_workspace_root(__file__)


def _state_root() -> Path:
    configured = str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex" / "ai-clone" / "state").resolve()


def _ingestions_root() -> Path:
    return _state_root() / "memory" / "source-intelligence" / "ingestions"


def _transcripts_root() -> Path:
    return _state_root() / "memory" / "source-intelligence" / "transcripts"


def _legacy_ingestions_root() -> Path:
    direct = _find_dir("backend/knowledge/ingestions", "knowledge/ingestions")
    if direct:
        return direct
    return _repo_root() / "knowledge" / "ingestions"


def _legacy_transcripts_root() -> Path:
    direct = _find_dir("backend/knowledge/aiclone/transcripts", "knowledge/aiclone/transcripts")
    if direct:
        return direct
    return _repo_root() / "knowledge" / "aiclone" / "transcripts"


def _source_asset_fingerprint(asset: dict[str, Any]) -> tuple[str, str]:
    source_url = _clean_text(asset.get("source_url")).lower()
    title = _clean_text(asset.get("title")).lower()
    source_path = _clean_text(asset.get("source_path")).lower()
    return (source_url or source_path, title)


def _combined_source_asset_inventory() -> dict[str, Any]:
    """Merge private generated assets with immutable legacy project fallbacks."""

    sources = (
        (_transcripts_root(), _ingestions_root(), _state_root()),
        (_legacy_transcripts_root(), _legacy_ingestions_root(), _repo_root()),
    )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for transcripts_root, ingestions_root, reference_root in sources:
        inventory = build_source_asset_inventory(
            transcripts_root=transcripts_root,
            ingestions_root=ingestions_root,
            repo_root=reference_root,
        )
        for item in inventory.get("items") or []:
            if not isinstance(item, dict):
                continue
            # Private state is visited first and remains authoritative after a
            # legacy pending asset has been copied forward for backfill.
            deduped.setdefault(_source_asset_fingerprint(item), item)

    items = sorted(
        deduped.values(),
        key=lambda item: (
            _clean_text(item.get("captured_at")),
            _clean_text(item.get("title")).lower(),
        ),
        reverse=True,
    )
    by_channel: dict[str, int] = {}
    for item in items:
        channel = _clean_text(item.get("source_channel")) or "unknown"
        by_channel[channel] = by_channel.get(channel, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "items": items,
        "counts": {
            "total": len(items),
            "long_form_media": len(items),
            "pending_segmentation": sum(
                1 for item in items if item.get("routing_status") == "pending_segmentation"
            ),
            "feed_ready": sum(1 for item in items if item.get("feed_ready")),
            "by_channel": by_channel,
        },
    }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _truncate(value: str, limit: int = 280) -> str:
    cleaned = _clean_text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


class YouTubeMediaCaptureError(RuntimeError):
    """Safe, stage-specific media failure with no command, URL, path, or stderr."""

    def __init__(
        self,
        *,
        stage: str,
        reason: str,
        fallback_from_stage: str | None = None,
        fallback_from_reason: str | None = None,
    ) -> None:
        self.stage = stage
        self.reason = reason
        self.fallback_from_stage = fallback_from_stage
        self.fallback_from_reason = fallback_from_reason
        super().__init__(f"{stage}: {reason}")


def _safe_runtime_error_code(exc: BaseException) -> str:
    """Return a stable diagnostic without commands, paths, URLs, or stderr."""

    if isinstance(exc, YouTubeMediaCaptureError):
        return exc.reason
    if isinstance(exc, HTTPError):
        if exc.code == 404:
            return "youtube_source_not_found"
        if exc.code in {401, 403}:
            return "youtube_source_access_denied"
        if exc.code == 429:
            return "youtube_rate_limited"
        if 500 <= exc.code <= 599:
            return "youtube_service_unavailable"
        return "youtube_feed_http_error"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "youtube_media_timeout"
    if isinstance(exc, subprocess.CalledProcessError):
        return "youtube_media_command_failed"
    if isinstance(exc, json.JSONDecodeError):
        return "youtube_metadata_invalid"
    if isinstance(exc, ET.ParseError):
        return "youtube_feed_invalid"
    if isinstance(exc, URLError):
        return "youtube_network_unavailable"
    if isinstance(exc, (TimeoutError, OSError)):
        return "youtube_runtime_unavailable"
    return f"youtube_{re.sub(r'(?<!^)(?=[A-Z])', '_', type(exc).__name__).lower()}"


def _safe_media_command_reason(exc: BaseException, *, stage: str) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"youtube_{stage}_timeout"
    if isinstance(exc, OSError):
        return "youtube_media_runtime_unavailable"
    output = ""
    if isinstance(exc, subprocess.CalledProcessError):
        output = " ".join(
            value
            for value in (str(exc.stderr or ""), str(exc.stdout or ""))
            if value
        ).lower()
    if "sign in to confirm" in output or "not a bot" in output:
        return "youtube_provider_auth_challenge"
    if "http error 429" in output or "too many requests" in output:
        return "youtube_rate_limited"
    if "http error 403" in output or "forbidden" in output:
        return "youtube_source_access_denied"
    if "private video" in output or "video unavailable" in output:
        return "youtube_source_unavailable"
    if "requested format is not available" in output or "no video formats found" in output:
        return "youtube_format_unavailable"
    if "unable to download" in output or "download failed" in output:
        return "youtube_download_failed"
    return f"youtube_{stage}_command_failed"


def _run_youtube_media_command(
    args: list[str],
    *,
    stage: str,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise YouTubeMediaCaptureError(
            stage=stage,
            reason=_safe_media_command_reason(exc, stage=stage),
        ) from None


def _safe_runtime_error_details(
    exc: BaseException,
    *,
    default_stage: str,
) -> dict[str, str]:
    details = {
        "stage": (
            exc.stage
            if isinstance(exc, YouTubeMediaCaptureError)
            else default_stage
        ),
        "reason": _safe_runtime_error_code(exc),
    }
    if (
        isinstance(exc, YouTubeMediaCaptureError)
        and exc.fallback_from_stage
    ):
        details["fallback_from_stage"] = exc.fallback_from_stage
    if (
        isinstance(exc, YouTubeMediaCaptureError)
        and exc.fallback_from_reason
    ):
        details["fallback_from_reason"] = exc.fallback_from_reason
    return details


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


def _extract_playlist_id(url: str) -> str:
    parsed = urlparse(url)
    query_playlist = parse_qs(parsed.query).get("playlist_id") or parse_qs(parsed.query).get("list") or []
    if query_playlist:
        return _clean_text(query_playlist[0])
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


def _resolve_playlist_feed_url(url: str) -> tuple[str | None, str | None]:
    playlist_id = _extract_playlist_id(url)
    if not playlist_id:
        return None, None
    return f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}", playlist_id


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
    try:
        payload = _combined_source_asset_inventory()
    except Exception:
        return set()
    urls = {
        _clean_text(item.get("source_url"))
        for item in (payload.get("items") or [])
        if isinstance(item, dict) and _clean_text(item.get("source_url"))
    }
    return {url for url in urls if url}


def _youtube_video_id(value: str | None) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    parsed = urlparse(raw.removeprefix("url:"))
    host = (parsed.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        return _clean_text(parsed.path.strip("/").split("/", 1)[0])
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        values = parse_qs(parsed.query).get("v") or []
        if values:
            return _clean_text(values[0])
    return ""


def _validated_provider_video_id(*values: Any) -> str:
    """Accept only the 11-character public video identity from provider data."""

    for value in values:
        raw = _clean_text(value)
        if not raw:
            continue
        candidate = raw if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(raw) else _youtube_video_id(raw)
        if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate):
            return candidate
    return ""


def _canonical_youtube_state(store: IntegratedSystemStore) -> dict[str, dict[str, Any]]:
    """Return compact canonical registration/capture state keyed by video ID."""

    store.migrate()
    with store.connection() as connection:
        rows = connection.execute(
            """SELECT source_id,canonical_identity,canonical_url,raw_artifact_id,
                      transcript_artifact_id,metadata_json
               FROM sources
               WHERE source_kind='youtube_video' AND merged_into_source_id IS NULL"""
        ).fetchall()
    state: dict[str, dict[str, Any]] = {}
    for row in rows:
        video_id = _youtube_video_id(row["canonical_url"]) or _youtube_video_id(
            str(row["canonical_identity"] or "").removeprefix("url:")
        )
        if not video_id:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}
            shared_id = _clean_text(
                metadata.get("shared_external_source_id")
                if isinstance(metadata, dict)
                else None
            )
            if shared_id.lower().startswith("youtube:"):
                video_id = _clean_text(shared_id.split(":", 1)[1])
        if not video_id:
            continue
        captured = bool(row["transcript_artifact_id"] or row["raw_artifact_id"])
        current = state.get(video_id)
        if current is None or (captured and not current["captured"]):
            state[video_id] = {
                "source_id": row["source_id"],
                "registered": True,
                "captured": captured,
                "capture_attempt_count": 0,
                "last_capture_attempt_at": "",
                "last_capture_outcome": "",
            }
    if not state:
        return state
    by_source_id = {
        str(item["source_id"]): item
        for item in state.values()
        if item.get("source_id")
    }
    with store.connection() as connection:
        attempt_rows = connection.execute(
            """SELECT aggregate_id,occurred_at,payload_json
               FROM system_events
               WHERE event_type=? AND aggregate_type='source'
               ORDER BY occurred_at,event_id""",
            (YOUTUBE_CAPTURE_ATTEMPT_EVENT,),
        ).fetchall()
    for row in attempt_rows:
        item = by_source_id.get(str(row["aggregate_id"] or ""))
        if item is None:
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        item["capture_attempt_count"] = int(item.get("capture_attempt_count") or 0) + 1
        item["last_capture_attempt_at"] = str(row["occurred_at"] or "")
        item["last_capture_outcome"] = _clean_text(
            payload.get("outcome") if isinstance(payload, dict) else ""
        )
    return state


def _capture_queue_key(
    item: dict[str, Any],
    canonical_state: dict[str, dict[str, Any]],
    *,
    playlist: bool,
) -> tuple[Any, ...]:
    video_id = _clean_text(item.get("video_id")) or _youtube_video_id(
        _clean_text(item.get("url"))
    )
    state = canonical_state.get(video_id) or {}
    registered = bool(state.get("registered") or item.get("canonical_registered"))
    attempt_count = int(state.get("capture_attempt_count") or 0)
    last_attempt_at = _clean_text(state.get("last_capture_attempt_at"))
    if playlist:
        tie_breaker: Any = -int(item.get("playlist_position") or 0)
    else:
        try:
            tie_breaker = -datetime.fromisoformat(
                _clean_text(item.get("published_at")).replace("Z", "+00:00")
            ).timestamp()
        except (TypeError, ValueError):
            tie_breaker = 0
    return (
        0 if not registered else 1,
        0 if attempt_count == 0 else 1,
        last_attempt_at,
        tie_breaker,
        video_id,
    )


def _captured_youtube_urls(state: dict[str, dict[str, Any]]) -> set[str]:
    urls: set[str] = set()
    for video_id, item in state.items():
        if not bool(item.get("captured")):
            continue
        urls.update(
            {
                f"https://youtube.com/watch?v={video_id}",
                f"https://www.youtube.com/watch?v={video_id}",
                f"https://youtu.be/{video_id}",
            }
        )
    return urls


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


def _designated_playlist(watchlist: dict[str, Any]) -> dict[str, Any] | None:
    playlist = watchlist.get("youtube_designated_playlist")
    if not isinstance(playlist, dict) or not _clean_text(playlist.get("url")):
        return None
    return playlist


def _canonical_intake_services(
    store: IntegratedSystemStore | None = None,
) -> tuple[IntegratedSystemStore, SourceIntakeAdapterService, SourceProcessingService]:
    resolved_store = store or IntegratedSystemStore(_state_root() / "system" / "ai-clone.sqlite3")
    artifact_store = PrivateContentArtifactStore(resolved_store.database_path.parent / "artifacts")
    return (
        resolved_store,
        SourceIntakeAdapterService(resolved_store),
        SourceProcessingService(resolved_store, artifact_store),
    )


def _register_youtube_discovery(
    *,
    adapter: SourceIntakeAdapterService,
    processing: SourceProcessingService,
    item: dict[str, Any],
    origin: str,
    discovery_route: str,
    relevance_state: str,
    reason: str,
) -> dict[str, Any]:
    registration = adapter.register(
        youtube_discovery_envelope(
            origin=origin,
            url=_clean_text(item.get("url")),
            video_id=_clean_text(item.get("video_id")) or None,
            discovery_route=discovery_route,
            title=_clean_text(item.get("title")) or None,
            author=_clean_text(item.get("author")) or _clean_text(item.get("channel_name")) or None,
            published_at=_clean_text(item.get("published_at")) or None,
            priority_lane=_clean_text(item.get("priority_lane")) or None,
            # This adapter receives the captured item from the public YouTube
            # surface. The envelope still revalidates the URL before stamping.
            share_public_content=True,
        )
    )
    current_relevance = _clean_text(registration["discovery"].get("relevance_state"))
    effective_relevance = relevance_state
    if relevance_state == "backlog" and current_relevance in {"qualified", "rejected"}:
        effective_relevance = current_relevance
    gate = processing.qualify(
        discovery_id=registration["discovery"]["discovery_id"],
        relevance_state=effective_relevance,
        admissibility_state="admissible",
        reason="scheduled_replay_preserved_prior_gate" if effective_relevance != relevance_state else reason,
        policy_name="youtube_scheduled_intake_gate",
        policy_version="1.0.0",
    )
    decision = processing.processing_decision(
        source_id=registration["source"]["source_id"],
        discovery_id=registration["discovery"]["discovery_id"],
        capture_kind="transcript",
    )
    return {"registration": registration, "gate": gate, "decision": decision}


def _fetch_youtube_feed_entries(
    source: dict[str, Any],
    *,
    limit: int,
    existing_urls: set[str],
    feed_url: str | None,
    source_id: str | None,
    source_id_key: str,
    fallback_name: str,
) -> dict[str, Any]:
    source_name = _clean_text(source.get("name")) or fallback_name
    source_url = _clean_text(source.get("url"))
    purpose = _clean_text(source.get("purpose"))
    priority_lane = _clean_text(source.get("priority_lane")) or "ai"
    payload = {
        "name": source_name,
        "url": source_url,
        "purpose": purpose,
        "priority_lane": priority_lane,
        source_id_key: source_id,
        "feed_url": feed_url,
        "videos": [],
    }
    if not feed_url:
        payload["error"] = f"Unable to resolve {fallback_name.lower()} feed."
        return payload

    try:
        raw = _http_get(feed_url, accept="application/atom+xml, application/xml, text/xml")
        root = ET.fromstring(raw)
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        payload["error"] = _safe_runtime_error_code(exc)
        return payload

    videos: list[dict[str, Any]] = []
    seen_video_keys: set[str] = set()
    invalid_entry_count = 0
    for entry in root.findall("atom:entry", ATOM_NS):
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        link = entry.find("atom:link", ATOM_NS)
        provider_url = _clean_text(link.attrib.get("href")) if link is not None else ""
        video_id = _validated_provider_video_id(
            entry.findtext("yt:videoId", default="", namespaces=ATOM_NS),
            provider_url,
        )
        if not video_id:
            invalid_entry_count += 1
            continue
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        if not title:
            continue
        # YouTube playlist Atom feeds can repeat the same entry. Collapse only
        # duplicates inside this feed route so channel-versus-playlist
        # discoveries remain distinct canonical lineage events.
        video_key = video_id or video_url
        if video_key in seen_video_keys:
            continue
        seen_video_keys.add(video_key)
        author_name = _clean_text(entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS)) or source_name
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
                "channel_name": source_name,
                "channel_url": source_url,
                "already_ingested": video_url in existing_urls,
            }
        )
        if len(videos) >= limit:
            break
    payload["videos"] = videos
    payload["invalid_entry_count"] = invalid_entry_count
    return payload


def _fetch_channel_entries(channel: dict[str, Any], *, limit: int, existing_urls: set[str]) -> dict[str, Any]:
    channel_url = _clean_text(channel.get("url"))
    feed_url, channel_id = _resolve_channel_feed_url(channel_url)
    payload = _fetch_youtube_feed_entries(
        channel,
        limit=limit,
        existing_urls=existing_urls,
        feed_url=feed_url,
        source_id=channel_id,
        source_id_key="channel_id",
        fallback_name="YouTube channel",
    )
    if not payload.get("error"):
        return payload
    try:
        fallback = _fetch_flat_channel_entries(channel, limit=limit, existing_urls=existing_urls)
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        payload["fallback_error"] = _safe_runtime_error_code(exc)
        return payload
    fallback["feed_warning"] = payload.get("error")
    return fallback


def _fetch_flat_channel_entries(
    channel: dict[str, Any],
    *,
    limit: int,
    existing_urls: set[str],
) -> dict[str, Any]:
    """Use the existing local yt-dlp runtime when a channel's Atom feed is unavailable."""

    channel_url = _clean_text(channel.get("url"))
    executable = shutil.which("yt-dlp")
    if not executable:
        raise RuntimeError("yt-dlp is unavailable for bounded channel discovery")
    result = _run_youtube_media_command(
        [
            executable,
            "--flat-playlist",
            "--playlist-end",
            str(max(1, limit)),
            "--dump-single-json",
            "--no-warnings",
            "--no-update",
            channel_url,
        ],
        stage="channel_manifest",
        timeout=PLAYLIST_MANIFEST_TIMEOUT_SECONDS,
    )
    decoded = json.loads(result.stdout)
    raw_entries = decoded.get("entries") if isinstance(decoded, dict) else None
    if not isinstance(raw_entries, list):
        raise RuntimeError("YouTube channel manifest did not contain entries")

    source_name = _clean_text(channel.get("name")) or _clean_text(decoded.get("title")) or "YouTube channel"
    purpose = _clean_text(channel.get("purpose"))
    priority_lane = _clean_text(channel.get("priority_lane")) or "ai"
    channel_id = _clean_text(decoded.get("channel_id")) or _clean_text(decoded.get("uploader_id")) or _extract_channel_id(channel_url)
    videos: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()
    invalid_entry_count = 0
    for raw_entry in raw_entries[: max(1, limit)]:
        if not isinstance(raw_entry, dict):
            continue
        video_id = _validated_provider_video_id(
            raw_entry.get("id"),
            raw_entry.get("url"),
            raw_entry.get("webpage_url"),
        )
        if not video_id:
            invalid_entry_count += 1
            continue
        if video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        videos.append(
            {
                "title": _clean_text(raw_entry.get("title")) or f"YouTube video {video_id}",
                "url": video_url,
                "video_id": video_id,
                "author": _clean_text(raw_entry.get("channel")) or _clean_text(raw_entry.get("uploader")) or source_name,
                "published_at": _published_at_from_flat_entry(raw_entry),
                "summary": "",
                "priority_lane": priority_lane,
                "channel_name": source_name,
                "channel_url": _clean_text(raw_entry.get("channel_url")) or _clean_text(raw_entry.get("uploader_url")) or channel_url,
                "already_ingested": video_url in existing_urls,
            }
        )
    return {
        "name": source_name,
        "url": channel_url,
        "purpose": purpose,
        "priority_lane": priority_lane,
        "channel_id": channel_id or None,
        "feed_url": None,
        "discovery_mode": "yt_dlp_channel_fallback",
        "inspection_window_count": len(videos),
        "invalid_entry_count": invalid_entry_count,
        "videos": videos,
    }


def _published_at_from_flat_entry(entry: dict[str, Any]) -> str | None:
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, (int, float)):
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    upload_date = _clean_text(entry.get("upload_date"))
    if re.fullmatch(r"\d{8}", upload_date):
        try:
            return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return None


def _fetch_flat_playlist_manifest(
    playlist: dict[str, Any],
    *,
    existing_urls: set[str],
) -> dict[str, Any]:
    playlist_url = _clean_text(playlist.get("url"))
    playlist_id = _extract_playlist_id(playlist_url)
    executable = shutil.which("yt-dlp")
    if not executable:
        raise RuntimeError("yt-dlp is unavailable for complete playlist discovery")
    result = _run_youtube_media_command(
        [
            executable,
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            "--no-update",
            playlist_url,
        ],
        stage="playlist_manifest",
        timeout=PLAYLIST_MANIFEST_TIMEOUT_SECONDS,
    )
    decoded = json.loads(result.stdout)
    raw_entries = decoded.get("entries") if isinstance(decoded, dict) else None
    if not isinstance(raw_entries, list):
        raise RuntimeError("YouTube playlist manifest did not contain entries")
    if len(raw_entries) > PLAYLIST_MANIFEST_MAX_ENTRIES:
        raise RuntimeError("YouTube playlist manifest exceeds the configured safety bound")

    source_name = _clean_text(playlist.get("name")) or _clean_text(decoded.get("title")) or "YouTube playlist"
    purpose = _clean_text(playlist.get("purpose"))
    priority_lane = _clean_text(playlist.get("priority_lane")) or "ai"
    videos: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()
    duplicate_entries = 0
    invalid_entries = 0
    for ordinal, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            continue
        video_id = _validated_provider_video_id(
            raw_entry.get("id"),
            raw_entry.get("url"),
            raw_entry.get("webpage_url"),
        )
        if not video_id:
            invalid_entries += 1
            continue
        if video_id in seen_video_ids:
            duplicate_entries += 1
            continue
        seen_video_ids.add(video_id)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            playlist_position = int(raw_entry.get("playlist_index") or ordinal)
        except (TypeError, ValueError):
            playlist_position = ordinal
        videos.append(
            {
                "title": _clean_text(raw_entry.get("title")) or f"YouTube video {video_id}",
                "url": video_url,
                "video_id": video_id,
                "author": _clean_text(raw_entry.get("channel"))
                or _clean_text(raw_entry.get("uploader"))
                or source_name,
                "published_at": _published_at_from_flat_entry(raw_entry),
                "summary": "",
                "thumbnail_url": _clean_text(raw_entry.get("thumbnail")),
                "priority_lane": priority_lane,
                "channel_name": source_name,
                "channel_url": _clean_text(raw_entry.get("channel_url"))
                or _clean_text(raw_entry.get("uploader_url")),
                "playlist_position": playlist_position,
                "live_status": _clean_text(raw_entry.get("live_status")) or None,
                "already_ingested": video_url in existing_urls,
            }
        )

    return {
        "name": source_name,
        "url": playlist_url,
        "purpose": purpose,
        "priority_lane": priority_lane,
        "playlist_id": playlist_id,
        "feed_url": None,
        "discovery_mode": "yt_dlp_flat_manifest",
        "coverage_state": "complete_manifest",
        "manifest_counts": {
            "entries": len(raw_entries),
            "unique_videos": len(videos),
            "duplicate_entries": duplicate_entries,
            "invalid_entries": invalid_entries,
        },
        "videos": videos,
    }


def _fetch_playlist_entries(playlist: dict[str, Any], *, limit: int, existing_urls: set[str]) -> dict[str, Any]:
    try:
        return _fetch_flat_playlist_manifest(playlist, existing_urls=existing_urls)
    except Exception as exc:
        LOGGER.warning("Complete YouTube playlist discovery failed; using bounded Atom fallback: %s", exc)
        manifest_error = type(exc).__name__
    playlist_url = _clean_text(playlist.get("url"))
    feed_url, playlist_id = _resolve_playlist_feed_url(playlist_url)
    payload = _fetch_youtube_feed_entries(
        playlist,
        limit=limit,
        existing_urls=existing_urls,
        feed_url=feed_url,
        source_id=playlist_id,
        source_id_key="playlist_id",
        fallback_name="YouTube playlist",
    )
    payload["discovery_mode"] = "bounded_atom_fallback"
    payload["coverage_state"] = "degraded_bounded_fallback"
    payload["manifest_warning"] = manifest_error
    payload["manifest_counts"] = {
        "entries": len(payload.get("videos") or []),
        "unique_videos": len(payload.get("videos") or []),
        "duplicate_entries": 0,
        "invalid_entries": int(payload.get("invalid_entry_count") or 0),
    }
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


def local_media_transcription_runtime() -> dict[str, Any]:
    """Expose the one local media runtime used by YouTube and podcast capture."""

    return dict(_transcription_runtime())


def transcribe_local_audio_file(audio_path: Path) -> str:
    """Transcribe one already-downloaded audio file through the canonical runtime."""

    return _transcribe_audio(audio_path, WHISPER_MODEL_NAME)


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


def _contained_source_path(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Source asset path must be a contained logical path.")
    resolved_root = root.expanduser().resolve()
    candidate = (resolved_root / relative).resolve(strict=False)
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("Source asset path escapes its storage root.")
    return candidate


def _asset_normalized_path(asset: dict[str, Any]) -> Path | None:
    source_path = _clean_text(asset.get("source_path"))
    if not source_path:
        return None
    relative = Path(source_path)
    if relative.parts[:2] == ("memory", "source-intelligence"):
        return _contained_source_path(_state_root(), source_path)
    return _contained_source_path(_repo_root(), source_path)


def _private_asset_reference(path: Path) -> str:
    return path.resolve(strict=False).relative_to(
        _state_root().resolve(strict=False)
    ).as_posix()


def _seed_legacy_asset_to_private_state(asset: dict[str, Any]) -> Path:
    """Copy one legacy ingestion directory before applying a mutable backfill."""

    source_path = _asset_normalized_path(asset)
    if source_path is None or not source_path.is_file() or source_path.is_symlink():
        raise RuntimeError("Pending YouTube asset is missing a safe normalized source file.")

    private_root = _ingestions_root().resolve(strict=False)
    try:
        source_path.relative_to(private_root)
        return source_path
    except ValueError:
        pass

    legacy_root = _legacy_ingestions_root().resolve(strict=False)
    try:
        relative = source_path.relative_to(legacy_root)
    except ValueError as exc:
        raise RuntimeError("Pending YouTube asset is outside the reviewed legacy ingestion root.") from exc

    source_dir = source_path.parent
    if any(path.is_symlink() for path in source_dir.rglob("*")):
        raise RuntimeError("Pending YouTube asset contains a symlink and cannot be copied safely.")

    target_path = private_root / relative
    if target_path.exists():
        if not target_path.is_file() or target_path.is_symlink():
            raise RuntimeError("Private YouTube asset target is not a safe regular file.")
        return target_path

    target_dir = target_path.parent
    target_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(
        prefix=f".{target_dir.name}.",
        suffix=".seed",
        dir=str(target_dir.parent),
    ) as temporary_root:
        staged_dir = Path(temporary_root) / target_dir.name
        shutil.copytree(source_dir, staged_dir)
        try:
            staged_dir.rename(target_dir)
        except OSError:
            if not target_path.is_file() or target_path.is_symlink():
                raise

    for directory in [target_dir, *[path for path in target_dir.rglob("*") if path.is_dir()]]:
        directory.chmod(0o700)
    for file_path in (path for path in target_dir.rglob("*") if path.is_file()):
        file_path.chmod(0o600)
    return target_path


def _asset_needs_transcript_backfill(
    asset: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> bool:
    if _clean_text(asset.get("source_channel")).lower() != "youtube":
        return False
    if _clean_text(asset.get("source_type")).lower() != "youtube_transcript":
        return False
    if not _clean_text(asset.get("source_url")):
        return False
    word_count = asset.get("word_count")
    if isinstance(word_count, (int, float)) and word_count > 0:
        return False

    normalized_path = _asset_normalized_path(asset)
    if normalized_path is None:
        return False
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


def _pending_youtube_transcript_assets(
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    inventory = _combined_source_asset_inventory()
    return [
        asset
        for asset in (inventory.get("items") or [])
        if isinstance(asset, dict) and _asset_needs_transcript_backfill(asset)
    ]


def _write_backfilled_transcript(asset: dict[str, Any], transcript_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    normalized_path = _seed_legacy_asset_to_private_state(asset)

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
        "source_path": _private_asset_reference(normalized_path),
        "word_count": int(frontmatter.get("word_count") or 0),
    }


def backfill_pending_youtube_transcripts(
    *,
    limit: int | None = None,
    run_refresh: bool = False,
    canonical_store: IntegratedSystemStore | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    repo_root = _repo_root()
    pending_assets = _pending_youtube_transcript_assets(repo_root=repo_root)
    selected_limit = AUTO_PENDING_TRANSCRIPT_BACKFILL_PER_RUN if limit is None else max(0, int(limit))
    selected = pending_assets[:selected_limit] if selected_limit > 0 else []

    resolved_store, adapter, processing = _canonical_intake_services(canonical_store)
    execution = SourceIntakeExecutionService(resolved_store, processing.artifacts)

    backfilled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    prepared_assets: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for asset in selected:
        url = _clean_text(asset.get("source_url"))
        try:
            prepared = _register_youtube_discovery(
                adapter=adapter,
                processing=processing,
                item={
                    "url": url,
                    "title": _clean_text(asset.get("title")),
                    "author": _clean_text(asset.get("author")),
                },
                origin="youtube_watchlist",
                discovery_route="youtube:legacy_pending_transcript_backfill",
                relevance_state="qualified",
                reason="previously_selected_pending_transcript_backfill",
            )
            prepared_assets.append((asset, prepared))
        except Exception as exc:
            LOGGER.exception("Canonical registration failed for pending YouTube transcript %s", url)
            errors.append(
                {
                    "asset_id": _clean_text(asset.get("asset_id")),
                    "title": _clean_text(asset.get("title")),
                    "url": url,
                    "stage": "canonical_registration_or_gate",
                    "reason": type(exc).__name__,
                }
            )

    runtime_available = _can_attempt_youtube_transcript()
    for asset, prepared in prepared_assets:
        url = _clean_text(asset.get("source_url"))
        try:
            decision = prepared["decision"]
            existing_artifact_id = _clean_text(decision.get("existing_artifact_id"))
            if existing_artifact_id:
                transcript_text = execution.captured_text(existing_artifact_id)
                metadata = {}
                capture_reused = True
            else:
                if not decision.get("capture_required"):
                    skipped.append(
                        {
                            "asset_id": _clean_text(asset.get("asset_id")),
                            "title": _clean_text(asset.get("title")),
                            "reason": "expensive_processing_not_authorized",
                        }
                    )
                    continue
                if not runtime_available:
                    skipped.append(
                        {
                            "asset_id": _clean_text(asset.get("asset_id")),
                            "title": _clean_text(asset.get("title")),
                            "reason": "transcription_runtime_unavailable",
                        }
                    )
                    continue
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
                capture = processing.attach_captured_text(
                    source_id=decision["source_id"],
                    text=transcript_text,
                    capture_kind="transcript",
                    metadata={"capture_adapter": "youtube_legacy_backfill", "capture_version": "1.0.0"},
                )
                capture_reused = bool(capture["reused"])
            updated = _write_backfilled_transcript(asset, transcript_text, metadata)
            updated["transcript_word_count"] = len(transcript_text.split())
            updated["canonical_source_id"] = decision["source_id"]
            updated["canonical_capture_reused"] = capture_reused
            backfilled.append(updated)
        except Exception as exc:  # pragma: no cover - runtime dependent
            LOGGER.exception("Pending YouTube transcript backfill failed for %s", url)
            error_details = _safe_runtime_error_details(
                exc,
                default_stage="canonical_capture_or_projection",
            )
            errors.append(
                {
                    "asset_id": _clean_text(asset.get("asset_id")),
                    "title": _clean_text(asset.get("title")),
                    "url": url,
                    **error_details,
                    "error_class": type(exc).__name__,
                }
            )

    if run_refresh and backfilled:
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        workspace_snapshot_service.refresh_persisted_linkedin_os_state()

    counts = {
        "pending_total": len(pending_assets),
        "selected": len(selected),
        "registered": len(prepared_assets),
        "backfilled": len(backfilled),
        "skipped": len(skipped),
        "errors": len(errors),
    }
    disposition = (
        "degraded"
        if errors or skipped
        else "complete"
        if selected
        else "no_change"
    )
    receipt = execution.record_run_receipt(
        run_kind="youtube_transcript_backfill",
        disposition=disposition,
        counts=counts,
        errors=errors,
        run_id=run_id,
        provenance={"trigger": "local_scheduler", "runtime_available": runtime_available},
    )
    return {
        "runtime": _transcription_runtime(),
        "pending_total": len(pending_assets),
        "selected_count": len(selected),
        "backfilled": backfilled,
        "skipped": skipped,
        "errors": errors,
        "counts": counts,
        "receipt": {"event_id": receipt["event_id"], "disposition": disposition},
    }


def _yt_dlp_json(url: str) -> dict[str, Any]:
    result = _run_youtube_media_command(
        ["yt-dlp", "--dump-single-json", "--no-playlist", url],
        stage="metadata",
    )
    return json.loads(result.stdout)


def _download_audio(url: str, temp_dir: str) -> Path:
    output_template = str(Path(temp_dir) / "%(id)s.%(ext)s")
    _run_youtube_media_command(
        ["yt-dlp", "--no-playlist", "-x", "--audio-format", "mp3", "-o", output_template, url],
        stage="audio_download",
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
    _run_youtube_media_command(
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
        stage="subtitle_download",
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
        subtitle_failure: YouTubeMediaCaptureError | None = None
        try:
            subtitle_transcript = _download_subtitle_transcript(url, temp_dir)
        except YouTubeMediaCaptureError as exc:  # pragma: no cover - runtime dependent
            subtitle_failure = exc
            subtitle_transcript = ""
        except Exception as exc:  # pragma: no cover - runtime dependent
            subtitle_failure = YouTubeMediaCaptureError(
                stage="subtitle_download",
                reason=_safe_runtime_error_code(exc),
            )
            subtitle_transcript = ""
        if subtitle_transcript:
            return subtitle_transcript, metadata
        if not _can_transcribe():
            if subtitle_failure is not None:
                metadata = dict(metadata)
                metadata["capture_diagnostic"] = _safe_runtime_error_details(
                    subtitle_failure,
                    default_stage="subtitle_download",
                )
            return "", metadata
        try:
            audio_path = _download_audio(url, temp_dir)
        except YouTubeMediaCaptureError as exc:
            if subtitle_failure is not None:
                exc.fallback_from_stage = subtitle_failure.stage
                exc.fallback_from_reason = subtitle_failure.reason
            raise
        try:
            transcript = _transcribe_audio(audio_path, WHISPER_MODEL_NAME)
        except Exception:
            raise YouTubeMediaCaptureError(
                stage="local_transcription",
                reason="youtube_local_transcription_failed",
                fallback_from_stage=(
                    subtitle_failure.stage if subtitle_failure is not None else None
                ),
                fallback_from_reason=(
                    subtitle_failure.reason if subtitle_failure is not None else None
                ),
            ) from None
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
    canonical_processing: SourceProcessingService | None = None,
    canonical_source_id: str | None = None,
    captured_transcript_text: str | None = None,
    captured_metadata: dict[str, Any] | None = None,
    include_legacy_projection: bool = False,
) -> dict[str, Any]:
    metadata: dict[str, Any] = dict(captured_metadata or {})
    transcript_text = captured_transcript_text or ""
    ingestion_mode = "canonical_reuse" if captured_transcript_text is not None else "url_only"
    if captured_transcript_text is None and _can_attempt_youtube_transcript():
        transcript_text, metadata = _transcribe_youtube_url(url)
        ingestion_mode = "transcribed" if transcript_text else "url_only"
    elif captured_transcript_text is None:
        try:
            metadata = _yt_dlp_json(url) if shutil.which("yt-dlp") else {}
        except Exception:
            metadata = {}

    resolved_title = (
        _clean_text(title)
        or _clean_text(metadata.get("title"))
        or _clean_text(metadata.get("source_title"))
        or "YouTube source"
    )
    resolved_summary = _clean_text(summary) or _first_line(_clean_text(metadata.get("description")))
    resolved_author = (
        _clean_text(author)
        or _clean_text(metadata.get("channel"))
        or _clean_text(metadata.get("source_author"))
        or _clean_text(channel_name)
        or "unknown"
    )

    canonical_capture: dict[str, Any] | None = None
    if transcript_text and canonical_processing is not None and canonical_source_id:
        canonical_capture = canonical_processing.attach_captured_text(
            source_id=canonical_source_id,
            text=transcript_text,
            capture_kind="transcript",
            metadata={
                "capture_adapter": "youtube_local_media",
                "capture_version": "1.0.0",
                "source_title": resolved_title,
                "source_author": resolved_author,
            },
        )
    result: dict[str, Any] = {
        "asset_id": str(
            canonical_capture["artifact"]["artifact_id"]
            if canonical_capture
            else canonical_source_id or ""
        ),
        "title": resolved_title,
        "source_url": url,
        "source_type": "youtube_transcript",
        "source_channel": "youtube",
        "source_path": None,
        "routing_status_path": None,
        "has_transcript": bool(transcript_text),
        "refreshed_snapshots": [],
        "compatibility_projection": "not_requested",
    }
    if include_legacy_projection:
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
            ingestions_root=_ingestions_root(),
            reference_root=_state_root(),
            compatibility_projection=True,
        )
        result["compatibility_projection"] = "written"
    result["ingestion_mode"] = ingestion_mode
    capture_diagnostic = metadata.get("capture_diagnostic")
    if isinstance(capture_diagnostic, dict):
        result["capture_diagnostic"] = {
            key: value
            for key, value in capture_diagnostic.items()
            if key
            in {
                "stage",
                "reason",
                "fallback_from_stage",
                "fallback_from_reason",
            }
            and isinstance(value, str)
        }
    result["transcript_word_count"] = len((transcript_text or "").split()) if transcript_text else 0
    result["canonical_source_id"] = canonical_source_id
    result["canonical_capture"] = (
        {
            "artifact_id": canonical_capture["artifact"]["artifact_id"],
            "content_sha256": canonical_capture["artifact"]["content_sha256"],
            "reused": canonical_capture["reused"],
        }
        if canonical_capture
        else None
    )
    if include_legacy_projection and canonical_processing is not None and canonical_source_id:
        projection_event = canonical_processing.store.append_event(
            event_type="source.compatibility_projection_completed",
            aggregate_type="source",
            aggregate_id=canonical_source_id,
            actor_type="youtube_watchlist_intake",
            payload={
                "projection_kind": "brain_long_form_markdown",
                "asset_id": _clean_text(result.get("asset_id")),
                "source_path": _clean_text(result.get("source_path")),
            },
            provenance={"role": "restart_safe_compatibility_projection", "version": "1.0.0"},
            artifact_refs=(
                [canonical_capture["artifact"]["artifact_id"]]
                if canonical_capture
                else []
            ),
            idempotency_key=f"source-projection:youtube-brain-long-form:{canonical_source_id}",
        )
        result["canonical_projection_event_id"] = projection_event["event_id"]
    return result


def _completed_youtube_projection(store: IntegratedSystemStore, source_id: str) -> dict[str, Any] | None:
    with store.connection() as connection:
        event = connection.execute(
            """SELECT * FROM system_events
               WHERE event_type='source.compatibility_projection_completed'
                 AND aggregate_type='source' AND aggregate_id=?
               ORDER BY occurred_at DESC LIMIT 1""",
            (source_id,),
        ).fetchone()
    return dict(event) if event else None


def _canonical_artifact_metadata(store: IntegratedSystemStore, artifact_id: str) -> dict[str, Any]:
    with store.connection() as connection:
        artifact = connection.execute(
            "SELECT metadata_json FROM artifacts WHERE artifact_id=?",
            (artifact_id,),
        ).fetchone()
    if not artifact:
        raise ValueError("canonical transcript artifact is missing")
    try:
        metadata = json.loads(artifact["metadata_json"] or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical transcript artifact metadata is invalid") from exc
    return metadata if isinstance(metadata, dict) else {}


def ingest_youtube_watchlist_video(
    *,
    url: str,
    title: str | None = None,
    summary: str | None = None,
    author: str | None = None,
    channel_name: str | None = None,
    priority_lane: str | None = None,
    run_refresh: bool = True,
    canonical_store: IntegratedSystemStore | None = None,
    include_legacy_projection: bool = False,
) -> dict[str, Any]:
    """Deterministic local-runner entrypoint for one signed YouTube ingest action."""
    store, adapter, processing = _canonical_intake_services(canonical_store)
    item = {
        "url": url,
        "title": title,
        "summary": summary,
        "author": author,
        "channel_name": channel_name,
        "priority_lane": priority_lane,
    }
    prepared = _register_youtube_discovery(
        adapter=adapter,
        processing=processing,
        item=item,
        origin="youtube_watchlist",
        discovery_route="youtube:owner_requested_ingest",
        relevance_state="qualified",
        reason="owner_requested_ingest",
    )
    decision = prepared["decision"]
    if decision["state"] == "reuse_existing_capture":
        if not include_legacy_projection:
            return {
                "asset_id": decision["existing_artifact_id"],
                "source_path": None,
                "canonical_source_id": decision["source_id"],
                "canonical_capture": {
                    "artifact_id": decision["existing_artifact_id"],
                    "reused": True,
                },
                "compatibility_projection": "not_requested",
                "ingestion_mode": "canonical_reuse",
                "transcript_word_count": 0,
            }
        completed_projection = _completed_youtube_projection(store, decision["source_id"])
        if completed_projection:
            projection_payload = json.loads(completed_projection["payload_json"])
            return {
                "asset_id": projection_payload.get("asset_id"),
                "source_path": projection_payload.get("source_path"),
                "canonical_source_id": decision["source_id"],
                "canonical_capture": {
                    "artifact_id": decision["existing_artifact_id"],
                    "reused": True,
                },
                "canonical_projection_event_id": completed_projection["event_id"],
                "compatibility_projection": "reused",
                "ingestion_mode": "canonical_reuse",
                "transcript_word_count": 0,
            }
        execution = SourceIntakeExecutionService(store, processing.artifacts)
        transcript_text = execution.captured_text(decision["existing_artifact_id"])
        return _ingest_watchlist_video(
            url=url,
            title=title,
            summary=summary,
            author=author,
            channel_name=channel_name,
            priority_lane=priority_lane,
            run_refresh=run_refresh,
            canonical_processing=processing,
            canonical_source_id=decision["source_id"],
            captured_transcript_text=transcript_text,
            captured_metadata=_canonical_artifact_metadata(store, decision["existing_artifact_id"]),
            include_legacy_projection=True,
        )
    if not decision["capture_required"]:
        raise ValueError("YouTube source has not passed canonical expensive-processing gates")
    return _ingest_watchlist_video(
        url=url,
        title=title,
        summary=summary,
        author=author,
        channel_name=channel_name,
        priority_lane=priority_lane,
        run_refresh=run_refresh,
        canonical_processing=processing,
        canonical_source_id=prepared["registration"]["source"]["source_id"],
        include_legacy_projection=include_legacy_projection,
    )


def _annotate_canonical_youtube_state(
    source_payloads: list[dict[str, Any]],
    canonical_state: dict[str, dict[str, Any]],
) -> None:
    for source in source_payloads:
        for video in source.get("videos") or []:
            if not isinstance(video, dict):
                continue
            video_id = _clean_text(video.get("video_id")) or _youtube_video_id(
                _clean_text(video.get("url"))
            )
            state = canonical_state.get(video_id) or {}
            video["canonical_registered"] = bool(
                state.get("registered") or video.get("canonical_registered")
            )
            video["already_ingested"] = bool(
                state.get("captured") or video.get("already_ingested")
            )
            video["transcript_attempt_count"] = int(
                state.get("capture_attempt_count") or 0
            )
            video["last_transcript_attempt_status"] = (
                _clean_text(state.get("last_capture_outcome")) or None
            )


def _bounded_projection_source(source: dict[str, Any], *, playlist: bool) -> dict[str, Any]:
    projected = {key: value for key, value in source.items() if key != "videos"}
    videos = [dict(item) for item in (source.get("videos") or []) if isinstance(item, dict)]
    if playlist:
        videos.sort(
            key=lambda item: (
                int(item.get("playlist_position") or 0),
                _clean_text(item.get("video_id")),
            ),
            reverse=True,
        )
        videos = videos[:PLAYLIST_PROJECTION_WINDOW]
    projected["videos"] = videos
    projected["inspection_window_count"] = len(videos)
    return projected


def build_youtube_watchlist_payload(
    workspace_root: Path | None = None,
    *,
    canonical_store: IntegratedSystemStore | None = None,
) -> dict[str, Any]:
    watchlist = _load_watchlist(workspace_root)
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []
    canonical_state: dict[str, dict[str, Any]] = {}
    if canonical_store is not None or workspace_root is None:
        try:
            canonical_state = _canonical_youtube_state(
                canonical_store
                or IntegratedSystemStore(_state_root() / "system" / "ai-clone.sqlite3")
            )
        except Exception:
            LOGGER.exception("Unable to read canonical YouTube state for the watchlist snapshot")
    existing_urls = _extract_existing_source_urls() | _captured_youtube_urls(canonical_state)
    channel_payloads = [_fetch_channel_entries(channel, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls) for channel in channels if isinstance(channel, dict)]
    playlist = _designated_playlist(watchlist)
    playlist_payloads = (
        [_fetch_playlist_entries(playlist, limit=WATCHLIST_LIMIT_PER_CHANNEL, existing_urls=existing_urls)]
        if playlist
        else []
    )
    _annotate_canonical_youtube_state(
        [*channel_payloads, *playlist_payloads], canonical_state
    )
    return _assemble_youtube_watchlist_payload(
        watchlist,
        channel_payloads,
        playlist_payloads=playlist_payloads,
        data_mode="live_refresh",
    )


def _assemble_youtube_watchlist_payload(
    watchlist: dict[str, Any],
    channel_payloads: list[dict[str, Any]],
    *,
    playlist_payloads: list[dict[str, Any]] | None = None,
    data_mode: str,
) -> dict[str, Any]:
    playlist_payloads = playlist_payloads or []
    auto_ingest = _auto_ingest_config(watchlist)
    source_payloads = [*channel_payloads, *playlist_payloads]
    total_videos = sum(len(source.get("videos") or []) for source in source_payloads)
    already_ingested = sum(
        1
        for source in source_payloads
        for video in source.get("videos") or []
        if isinstance(video, dict) and bool(video.get("already_ingested"))
    )
    pending_transcript_assets = _pending_youtube_transcript_assets(repo_root=_repo_root())
    runtime = _transcription_runtime()
    playlist_videos = [
        video
        for source in playlist_payloads
        for video in (source.get("videos") or [])
        if isinstance(video, dict)
    ]
    playlist_manifest_entries = sum(
        int((source.get("manifest_counts") or {}).get("entries") or 0)
        for source in playlist_payloads
    )
    playlist_duplicate_entries = sum(
        int((source.get("manifest_counts") or {}).get("duplicate_entries") or 0)
        for source in playlist_payloads
    )
    playlist_registered = sum(
        1 for video in playlist_videos if bool(video.get("canonical_registered"))
    )
    playlist_captured = sum(
        1 for video in playlist_videos if bool(video.get("already_ingested"))
    )
    for source in playlist_payloads:
        if isinstance(source.get("coverage"), dict):
            continue
        source_videos = [
            video
            for video in (source.get("videos") or [])
            if isinstance(video, dict)
        ]
        source_manifest = (
            source.get("manifest_counts")
            if isinstance(source.get("manifest_counts"), dict)
            else {}
        )
        source_captured = sum(
            1 for video in source_videos if bool(video.get("already_ingested"))
        )
        source_attempted_pending = sum(
            1
            for video in source_videos
            if not bool(video.get("already_ingested"))
            and int(video.get("transcript_attempt_count") or 0) > 0
        )
        source_unattempted = sum(
            1
            for video in source_videos
            if bool(video.get("canonical_registered"))
            and not bool(video.get("already_ingested"))
            and int(video.get("transcript_attempt_count") or 0) == 0
        )
        source["coverage"] = {
            "manifest_entries": int(source_manifest.get("entries") or 0),
            "unique_videos": len(source_videos),
            "duplicate_entries": int(source_manifest.get("duplicate_entries") or 0),
            "registered": sum(
                1 for video in source_videos if bool(video.get("canonical_registered"))
            ),
            "newly_registered_this_run": 0,
            "captured": source_captured,
            "backlog": max(0, len(source_videos) - source_captured),
            "unattempted_backlog": source_unattempted,
            "retry_pending": source_attempted_pending,
            "selected_for_capture_this_run": 0,
            "captured_this_run": 0,
            "capture_reused_this_run": 0,
            "capture_deferred_this_run": 0,
            "capture_failed_this_run": 0,
        }
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
        "channels": [
            _bounded_projection_source(source, playlist=False)
            for source in channel_payloads
        ],
        "designated_playlists": [
            _bounded_projection_source(source, playlist=True)
            for source in playlist_payloads
        ],
        "counts": {
            "channels": len(channel_payloads),
            "designated_playlists": len(playlist_payloads),
            "videos": total_videos,
            "already_ingested": already_ingested,
            "pending_transcript_backfill": len(pending_transcript_assets),
            "playlist_manifest_entries": playlist_manifest_entries,
            "playlist_unique_videos": len(playlist_videos),
            "playlist_duplicate_entries": playlist_duplicate_entries,
            "playlist_registered": playlist_registered,
            "playlist_captured": playlist_captured,
            "playlist_backlog": max(0, len(playlist_videos) - playlist_captured),
            "playlist_unattempted_backlog": sum(
                1
                for video in playlist_videos
                if bool(video.get("canonical_registered"))
                and not bool(video.get("already_ingested"))
                and int(video.get("transcript_attempt_count") or 0) == 0
            ),
            "playlist_retry_pending": sum(
                1
                for video in playlist_videos
                if not bool(video.get("already_ingested"))
                and int(video.get("transcript_attempt_count") or 0) > 0
            ),
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
    playlist = _designated_playlist(watchlist)
    playlist_payloads = []
    if playlist:
        feed_url, playlist_id = _resolve_playlist_feed_url(_clean_text(playlist.get("url")))
        playlist_payloads.append(
            {
                "name": _clean_text(playlist.get("name")) or "YouTube playlist",
                "url": _clean_text(playlist.get("url")),
                "purpose": _clean_text(playlist.get("purpose")),
                "priority_lane": _clean_text(playlist.get("priority_lane")) or "ai",
                "playlist_id": playlist_id,
                "feed_url": feed_url,
                "videos": [],
            }
        )
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
        "designated_playlists": playlist_payloads,
        "counts": {
            "channels": len(channel_payloads),
            "designated_playlists": len(playlist_payloads),
            "videos": 0,
            "already_ingested": 0,
            "pending_transcript_backfill": 0,
            "playlist_manifest_entries": 0,
            "playlist_unique_videos": 0,
            "playlist_duplicate_entries": 0,
            "playlist_registered": 0,
            "playlist_captured": 0,
            "playlist_backlog": 0,
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
    canonical_store: IntegratedSystemStore | None = None,
    include_legacy_projection: bool = False,
    include_legacy_pending_backfill: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    watchlist = _load_watchlist(workspace_root)
    config = _auto_ingest_config(watchlist)
    resolved_store, adapter, processing = _canonical_intake_services(canonical_store)
    execution = SourceIntakeExecutionService(resolved_store, processing.artifacts)
    effective_run_id = str(run_id or f"youtube-watchlist:{uuid.uuid4()}").strip()
    if not config["enabled"]:
        counts = {"discovered": 0, "registered": 0, "ingested": 0, "skipped": 0, "warnings": 0, "errors": 0}
        receipt = execution.record_run_receipt(
            run_kind="youtube_watchlist",
            disposition="no_change",
            counts=counts,
            provenance={"trigger": "local_scheduler", "reason": "auto_ingest_disabled"},
            run_id=effective_run_id,
        )
        return {
            "enabled": False,
            "ingested": [],
            "skipped": [],
            "errors": [],
            "counts": counts,
            "receipt": {"event_id": receipt["event_id"], "disposition": "no_change"},
        }

    total_limit = max_videos_per_run or config["max_videos_per_run"]
    channel_limit = per_channel_limit or config["per_channel_limit"]
    canonical_state = _canonical_youtube_state(resolved_store)
    existing_urls = _extract_existing_source_urls() | _captured_youtube_urls(
        canonical_state
    )
    channels = watchlist.get("youtube_channels") if isinstance(watchlist.get("youtube_channels"), list) else []

    discovered: list[dict[str, Any]] = []
    canonical_candidates: list[dict[str, Any]] = []
    registered: list[dict[str, Any]] = []
    channel_payloads: list[dict[str, Any]] = []
    playlist_payloads: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ingested: list[dict[str, Any]] = []
    reused_captures: list[dict[str, Any]] = []
    deferred_captures: list[dict[str, Any]] = []
    backfill_result: dict[str, Any] = {
        "status": "not_requested",
        "backfilled": [],
        "skipped": [],
        "errors": [],
        "counts": {
            "pending_total": 0,
            "selected": 0,
            "backfilled": 0,
            "skipped": 0,
            "errors": 0,
        },
    }

    def record_capture_attempt(
        item: dict[str, Any],
        *,
        source_id: str,
        outcome: str,
        error_class: str | None = None,
    ) -> None:
        attempted_at = datetime.now(timezone.utc).isoformat()
        video_id = _clean_text(item.get("video_id")) or _youtube_video_id(
            _clean_text(item.get("url"))
        )
        payload = {
            "schema_version": "youtube_capture_attempt/v1",
            "run_id": effective_run_id,
            "outcome": outcome,
            "capture_kind": "transcript",
            "error_class": error_class,
        }
        try:
            resolved_store.append_event(
                event_type=YOUTUBE_CAPTURE_ATTEMPT_EVENT,
                aggregate_type="source",
                aggregate_id=source_id,
                actor_type="source_intake_scheduler",
                payload=payload,
                provenance={
                    "origin": _clean_text(item.get("_intake_origin")),
                    "discovery_route": _clean_text(item.get("_discovery_route")),
                    "video_id": video_id,
                },
                idempotency_key=f"youtube-capture-attempt:{effective_run_id}:{source_id}",
                occurred_at=attempted_at,
            )
        except Exception:
            LOGGER.exception("YouTube capture-attempt receipt could not be stored")
            warnings.append(
                {
                    "kind": "capture_attempt_receipt_failed",
                    "stage": "capture_attempt_receipt",
                    "reason": "canonical_attempt_receipt_unavailable",
                }
            )
            return
        if video_id:
            state = canonical_state.setdefault(
                video_id,
                {
                    "source_id": source_id,
                    "registered": True,
                    "captured": False,
                    "capture_attempt_count": 0,
                    "last_capture_attempt_at": "",
                    "last_capture_outcome": "",
                },
            )
            state["source_id"] = source_id
            state["registered"] = True
            state["capture_attempt_count"] = int(
                state.get("capture_attempt_count") or 0
            ) + 1
            state["last_capture_attempt_at"] = attempted_at
            state["last_capture_outcome"] = outcome
            if outcome in {"captured", "reused"}:
                state["captured"] = True
    if include_legacy_pending_backfill:
        backfill_result = backfill_pending_youtube_transcripts(
            run_refresh=False,
            canonical_store=resolved_store,
        )
    for error in backfill_result.get("errors") or []:
        detail = error if isinstance(error, dict) else {"reason": str(error)}
        errors.append({"stage": "transcript_backfill", **detail})

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
        _annotate_canonical_youtube_state([payload], canonical_state)
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
        fresh_videos.sort(
            key=lambda item: _capture_queue_key(
                item,
                canonical_state,
                playlist=False,
            )
        )
        discovery_route = f"youtube:watchlist:{_clean_text(channel.get('url'))}"
        for video in payload.get("videos") or []:
            if not isinstance(video, dict):
                continue
            video_copy = dict(video)
            video_copy["channel_name"] = channel_name
            video_copy["_intake_origin"] = "youtube_watchlist"
            video_copy["_discovery_route"] = discovery_route
            canonical_candidates.append(video_copy)
        for video in fresh_videos[:channel_limit]:
            video_copy = dict(video)
            video_copy["channel_name"] = channel_name
            video_copy["_intake_origin"] = "youtube_watchlist"
            video_copy["_discovery_route"] = discovery_route
            discovered.append(video_copy)

    playlist = _designated_playlist(watchlist)
    if playlist:
        playlist_payload = _fetch_playlist_entries(
            playlist,
            limit=WATCHLIST_LIMIT_PER_CHANNEL,
            existing_urls=existing_urls,
        )
        _annotate_canonical_youtube_state([playlist_payload], canonical_state)
        playlist_payloads.append(playlist_payload)
        playlist_name = _clean_text(playlist_payload.get("name")) or "YouTube playlist"
        if playlist_payload.get("error"):
            warnings.append(
                {
                    "kind": "playlist_fetch_failed",
                    "playlist_name": playlist_name,
                    "url": _clean_text(playlist.get("url")),
                    "reason": _clean_text(playlist_payload.get("error")),
                }
            )
        else:
            if playlist_payload.get("coverage_state") != "complete_manifest":
                warnings.append(
                    {
                        "kind": "playlist_manifest_degraded",
                        "playlist_name": playlist_name,
                        "url": _clean_text(playlist.get("url")),
                        "reason": _clean_text(playlist_payload.get("manifest_warning"))
                        or "complete_manifest_unavailable",
                    }
                )
            discovery_route = f"youtube:playlist:{_clean_text(playlist.get('url'))}"
            playlist_fresh: list[dict[str, Any]] = []
            for video in playlist_payload.get("videos") or []:
                if not isinstance(video, dict):
                    continue
                video_copy = dict(video)
                video_copy["channel_name"] = playlist_name
                video_copy["_intake_origin"] = "youtube_playlist"
                video_copy["_discovery_route"] = discovery_route
                canonical_candidates.append(video_copy)
                if not bool(video.get("already_ingested")):
                    playlist_fresh.append(video_copy)
            # A video never before seen on this route represents current owner
            # intent and is handled before the historical backlog. The owner
            # playlist currently appends additions, so higher positions drain
            # first inside each class without treating publication date as the
            # save date.
            playlist_fresh.sort(
                key=lambda item: _capture_queue_key(
                    item,
                    canonical_state,
                    playlist=True,
                )
            )
            if _channel_auto_ingest_enabled(playlist):
                discovered.extend(playlist_fresh[:channel_limit])
            elif playlist_fresh:
                skipped.append({"playlist_name": playlist_name, "reason": "auto_ingest_disabled"})

    discovered.sort(
        key=lambda item: (
            0 if _clean_text(item.get("_intake_origin")) == "youtube_playlist" else 1,
            *_capture_queue_key(
                item,
                canonical_state,
                playlist=_clean_text(item.get("_intake_origin")) == "youtube_playlist",
            ),
        )
    )
    selected = discovered[:total_limit]
    selected_keys = {
        (
            _clean_text(item.get("_intake_origin")),
            _clean_text(item.get("_discovery_route")),
            _clean_text(item.get("video_id")) or _clean_text(item.get("url")),
        )
        for item in selected
    }
    selected_urls = {_clean_text(item.get("url")) for item in selected if _clean_text(item.get("url"))}

    for item in discovered[total_limit:]:
        skipped.append({"url": item.get("url"), "title": item.get("title"), "channel_name": item.get("channel_name"), "reason": "run_limit"})

    prepared_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in canonical_candidates:
        candidate_key = (
            _clean_text(item.get("_intake_origin")),
            _clean_text(item.get("_discovery_route")),
            _clean_text(item.get("video_id")) or _clean_text(item.get("url")),
        )
        is_selected = candidate_key in selected_keys
        try:
            prepared = _register_youtube_discovery(
                adapter=adapter,
                processing=processing,
                item=item,
                origin=candidate_key[0],
                discovery_route=candidate_key[1],
                relevance_state="qualified" if is_selected else "backlog",
                reason="scheduled_capture_selected" if is_selected else "not_selected_for_expensive_processing",
            )
            prepared_by_key[candidate_key] = prepared
            registered.append(
                {
                    "source_id": prepared["registration"]["source"]["source_id"],
                    "discovery_id": prepared["registration"]["discovery"]["discovery_id"],
                    "origin": candidate_key[0],
                    "selected": is_selected,
                    "duplicate_source": prepared["registration"]["gate"]["duplicate_source"],
                    "new_source": not bool(
                        prepared["registration"]["gate"]["duplicate_source"]
                    ),
                }
            )
        except Exception as exc:
            LOGGER.exception("Canonical YouTube discovery registration failed")
            errors.append(
                {
                    "url": _clean_text(item.get("url")),
                    "title": _clean_text(item.get("title")),
                    "stage": "canonical_registration_or_gate",
                    "reason": type(exc).__name__,
                }
            )

    processed_source_ids: set[str] = set()
    for item in selected:
        url = _clean_text(item.get("url"))
        candidate_key = (
            _clean_text(item.get("_intake_origin")),
            _clean_text(item.get("_discovery_route")),
            _clean_text(item.get("video_id")) or url,
        )
        prepared = prepared_by_key.get(candidate_key)
        if not prepared:
            skipped.append({"url": url, "title": item.get("title"), "reason": "canonical_gate_unavailable"})
            continue
        decision = prepared["decision"]
        source_id = decision["source_id"]
        if source_id in processed_source_ids:
            skipped.append({"url": url, "title": item.get("title"), "reason": "duplicate_canonical_source_in_run"})
            continue
        processed_source_ids.add(source_id)
        if decision["state"] == "reuse_existing_capture":
            reused_captures.append(
                {
                    "url": url,
                    "title": item.get("title"),
                    "channel_name": item.get("channel_name"),
                    "origin": item.get("_intake_origin"),
                    "ingestion_mode": "canonical_reuse",
                    "asset_id": decision["existing_artifact_id"],
                    "canonical_source_id": source_id,
                }
            )
            record_capture_attempt(item, source_id=source_id, outcome="reused")
            continue
        if not decision["capture_required"]:
            skipped.append({"url": url, "title": item.get("title"), "reason": "expensive_processing_not_authorized"})
            record_capture_attempt(item, source_id=source_id, outcome="not_authorized")
            continue
        try:
            result = _ingest_watchlist_video(
                url=url,
                title=item.get("title"),
                summary=item.get("summary"),
                author=item.get("author"),
                channel_name=item.get("channel_name"),
                priority_lane=item.get("priority_lane"),
                run_refresh=False,
                canonical_processing=processing,
                canonical_source_id=source_id,
                include_legacy_projection=include_legacy_projection,
            )
            result_summary = {
                "url": url,
                "title": item.get("title"),
                "channel_name": item.get("channel_name"),
                "origin": item.get("_intake_origin"),
                "ingestion_mode": result.get("ingestion_mode"),
                "asset_id": result.get("asset_id"),
                "canonical_source_id": source_id,
            }
            if result.get("canonical_capture") and bool(result.get("has_transcript")):
                ingested.append(result_summary)
                record_capture_attempt(item, source_id=source_id, outcome="captured")
            else:
                capture_diagnostic = (
                    result.get("capture_diagnostic")
                    if isinstance(result.get("capture_diagnostic"), dict)
                    else None
                )
                deferred_captures.append(
                    {
                        **result_summary,
                        "reason": "transcript_not_yet_available",
                        **(
                            {"capture_diagnostic": capture_diagnostic}
                            if capture_diagnostic
                            else {}
                        ),
                    }
                )
                record_capture_attempt(item, source_id=source_id, outcome="deferred")
        except Exception as exc:  # pragma: no cover - runtime dependent
            LOGGER.exception("Auto-ingest failed for watchlist video %s", url)
            error_details = _safe_runtime_error_details(
                exc,
                default_stage="transcript_capture",
            )
            errors.append(
                {
                    "url": url,
                    "title": item.get("title"),
                    "channel_name": item.get("channel_name"),
                    "origin": item.get("_intake_origin"),
                    **error_details,
                    "error_class": type(exc).__name__,
                }
            )
            record_capture_attempt(
                item,
                source_id=source_id,
                outcome="failed",
                error_class=type(exc).__name__,
            )

    for item in discovered:
        url = _clean_text(item.get("url"))
        if url in selected_urls:
            continue
        if url in existing_urls:
            skipped.append({"url": url, "title": item.get("title"), "channel_name": item.get("channel_name"), "reason": "already_ingested"})

    if deferred_captures:
        warnings.append(
            {
                "kind": "transcript_capture_deferred",
                "count": len(deferred_captures),
                "reason": "selected_sources_remain_registered_without_a_transcript",
            }
        )

    if run_refresh and include_legacy_projection and (ingested or (backfill_result.get("backfilled") or [])):
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        workspace_snapshot_service.refresh_persisted_linkedin_os_state()

    ingested_urls = {_clean_text(item.get("url")) for item in ingested if _clean_text(item.get("url"))}
    reused_urls = {
        _clean_text(item.get("url"))
        for item in reused_captures
        if _clean_text(item.get("url"))
    }
    registered_video_ids = {
        _clean_text(item.get("video_id")) or _youtube_video_id(_clean_text(item.get("url")))
        for item in canonical_candidates
        if _clean_text(item.get("video_id")) or _youtube_video_id(_clean_text(item.get("url")))
    }
    for source_payload in [*channel_payloads, *playlist_payloads]:
        for video in source_payload.get("videos") or []:
            if not isinstance(video, dict):
                continue
            video_id = _clean_text(video.get("video_id")) or _youtube_video_id(
                _clean_text(video.get("url"))
            )
            if video_id in registered_video_ids:
                video["canonical_registered"] = True
            if _clean_text(video.get("url")) in ingested_urls | reused_urls:
                video["already_ingested"] = True
    _annotate_canonical_youtube_state(
        [*channel_payloads, *playlist_payloads],
        canonical_state,
    )

    playlist_newly_registered = sum(
        1
        for item in registered
        if item.get("origin") == "youtube_playlist" and bool(item.get("new_source"))
    )
    playlist_selected = sum(
        1
        for item in registered
        if item.get("origin") == "youtube_playlist" and bool(item.get("selected"))
    )
    playlist_captured_new = sum(
        1 for item in ingested if item.get("origin") == "youtube_playlist"
    )
    playlist_capture_reused = sum(
        1 for item in reused_captures if item.get("origin") == "youtube_playlist"
    )
    playlist_capture_deferred = sum(
        1 for item in deferred_captures if item.get("origin") == "youtube_playlist"
    )
    playlist_capture_failed = sum(
        1 for item in errors if item.get("origin") == "youtube_playlist"
    )
    for playlist_payload in playlist_payloads:
        playlist_videos = [
            item
            for item in (playlist_payload.get("videos") or [])
            if isinstance(item, dict)
        ]
        captured_total = sum(
            1 for item in playlist_videos if bool(item.get("already_ingested"))
        )
        attempted_pending = sum(
            1
            for item in playlist_videos
            if not bool(item.get("already_ingested"))
            and int(item.get("transcript_attempt_count") or 0) > 0
        )
        unattempted_backlog = sum(
            1
            for item in playlist_videos
            if bool(item.get("canonical_registered"))
            and not bool(item.get("already_ingested"))
            and int(item.get("transcript_attempt_count") or 0) == 0
        )
        playlist_payload["coverage"] = {
            "manifest_entries": int(
                (playlist_payload.get("manifest_counts") or {}).get("entries") or 0
            ),
            "unique_videos": len(playlist_videos),
            "duplicate_entries": int(
                (playlist_payload.get("manifest_counts") or {}).get("duplicate_entries")
                or 0
            ),
            "registered": sum(
                1 for item in playlist_videos if bool(item.get("canonical_registered"))
            ),
            "newly_registered_this_run": playlist_newly_registered,
            "captured": captured_total,
            "backlog": max(0, len(playlist_videos) - captured_total),
            "unattempted_backlog": unattempted_backlog,
            "retry_pending": attempted_pending,
            "selected_for_capture_this_run": playlist_selected,
            "captured_this_run": playlist_captured_new,
            "capture_reused_this_run": playlist_capture_reused,
            "capture_deferred_this_run": playlist_capture_deferred,
            "capture_failed_this_run": playlist_capture_failed,
        }
    watchlist_payload = _assemble_youtube_watchlist_payload(
        watchlist,
        channel_payloads,
        playlist_payloads=playlist_payloads,
        data_mode="local_runner_refresh",
    )
    snapshot_store_configured = database_configured()
    watchlist_snapshot_persisted = (
        _persist_youtube_watchlist_payload(watchlist_payload)
        if snapshot_store_configured
        else False
    )
    watchlist_snapshot_persistence = (
        "persisted"
        if watchlist_snapshot_persisted
        else "failed"
        if snapshot_store_configured
        else "not_configured"
    )
    if snapshot_store_configured and not watchlist_snapshot_persisted:
        warnings.append(
            {
                "kind": "watchlist_snapshot_persist_failed",
                "stage": "watchlist_snapshot",
                "reason": "configured_snapshot_store_unavailable",
            }
        )

    counts = {
        "discovered": len(discovered),
        "registered": len(registered),
        "registered_new": sum(1 for item in registered if bool(item.get("new_source"))),
        "ingested": len(ingested),
        "capture_reused": len(reused_captures),
        "capture_deferred": len(deferred_captures),
        "backfilled": len(backfill_result.get("backfilled") or []),
        "skipped": len(skipped),
        "warnings": len(warnings),
        "errors": len(errors),
    }
    backfill_counts = backfill_result.get("counts") if isinstance(backfill_result.get("counts"), dict) else {}
    degraded = bool(errors or warnings or int(backfill_counts.get("errors") or 0))
    changed = bool(
        counts["registered_new"]
        or ingested
        or int(backfill_counts.get("backfilled") or 0)
    )
    disposition = "degraded" if degraded else "complete" if changed else "no_change"
    receipt = execution.record_run_receipt(
        run_kind="youtube_watchlist",
        disposition=disposition,
        counts=counts,
        errors=[*errors, *warnings],
        provenance={
            "trigger": "local_scheduler",
            "snapshot_store_configured": snapshot_store_configured,
            "snapshot_persistence": watchlist_snapshot_persistence,
        },
        run_id=effective_run_id,
    )
    return {
        "enabled": True,
        "auto_ingest": config,
        "backfill": backfill_result,
        "ingested": ingested,
        "capture_reused": reused_captures,
        "capture_deferred": deferred_captures,
        "registered": registered,
        "skipped": skipped,
        "warnings": warnings,
        "errors": errors,
        "watchlist_snapshot_persisted": watchlist_snapshot_persisted,
        "watchlist_snapshot_persistence": watchlist_snapshot_persistence,
        "receipt": {"event_id": receipt["event_id"], "disposition": disposition},
        # The local automation reuses the payload for its authenticated
        # Railway mirror. Keeping it private to the caller avoids fetching
        # every channel feed a second time in the same run.
        "_watchlist_payload": watchlist_payload,
        "counts": counts,
    }


def run_ingest_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = ingest_youtube_watchlist_video(
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
                stored["error"] = _safe_runtime_error_code(exc)
