from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yaml

from app.services.social_signal_archive_service import load_market_signal_archive_records, sync_market_signal_archive_entry
from app.services.social_feed_builder_service import discover_linkedin_workspace_root
from app.services.social_signal_extraction import social_signal_extraction_service
from app.services.source_feed_signal_service import SourceFeedSignalService
from app.services.integrated_system_store import IntegratedSystemStore
from app.services.source_intake_adapter_service import (
    podcast_discovery_envelope,
    reddit_discovery_envelope,
    rss_discovery_envelope,
)
from app.services.source_intake_execution_service import SourceIntakeExecutionService
from app.services.source_sharing_policy_service import (
    credential_free_public_url,
    is_credential_free_public_url,
)
from app.utils.runtime_workspace_root import resolve_runtime_workspace_root


REPO_ROOT = resolve_runtime_workspace_root(__file__)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_paths import workspace_state_root  # noqa: E402

LOGGER = logging.getLogger(__name__)
USER_AGENT = "AICloneSocialFeed/1.0 (+https://aiclone-frontend-production.up.railway.app)"
DEFAULT_HTTP_TIMEOUT = 12
DEFAULT_REDDIT_LIMIT = 2
DEFAULT_RSS_LIMIT = 2
DEFAULT_PODCAST_AUDIO_TRANSCRIPTION_LIMIT = 1
PODCAST_TRANSCRIPT_MAX_BYTES = 16 * 1024 * 1024
PODCAST_AUDIO_MAX_BYTES = 512 * 1024 * 1024
PODCAST_TRANSCRIPT_ATTEMPT_EVENT = "source.podcast_transcript_attempt"


def _bounded_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(os.getenv(name) or default).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _configured_gate_state(source: dict[str, Any]) -> tuple[str, str, str]:
    relevance = _clean_text(source.get("relevance_state")).lower() or "qualified"
    admissibility = _clean_text(source.get("admissibility_state")).lower() or "admissible"
    rights = _clean_text(source.get("rights_state")).lower() or "permitted"
    if relevance not in {"qualified", "backlog", "rejected"}:
        relevance = "backlog"
    if admissibility not in {"admissible", "restricted", "blocked"}:
        admissibility = "restricted"
    if rights not in {"unknown", "permitted", "owner_controlled", "restricted", "blocked"}:
        rights = "unknown"
    return relevance, admissibility, rights


def _run_disposition(*, changed: int, errors: int, gated_out: int) -> str:
    if errors:
        return "degraded" if changed or gated_out else "failed"
    if gated_out:
        return "degraded"
    return "complete" if changed else "no_change"

DEFAULT_WATCHLIST = {
    "sources": {
        "primary": [
            {
                "platform": "linkedin",
                "purpose": "Native platform language, operator framing, intrapreneurial AI use cases",
            }
        ],
        "secondary": [
            {"platform": "reddit", "purpose": "Practitioner pain, objections, and implementation friction"},
            {"platform": "blogs_news", "purpose": "Product launches, market shifts, and benchmark essays"},
        ],
    },
    "priority_people": [
        {
            "name": "Nate B Jones",
            "platform": "youtube",
            "relationship": "followed",
            "profile_url": "https://www.youtube.com/@NateBJones",
            "reason": "Leadership, AI, and operator framing with practical management language",
            "lenses": ["program-leadership", "ai", "ops-pm"],
            "priority_weight": 0.82,
        },
        {
            "name": "Champion Leadership",
            "platform": "youtube",
            "relationship": "followed",
            "profile_url": "https://www.youtube.com/@championleadership",
            "reason": "Leadership, team standards, and execution discipline signals",
            "lenses": ["program-leadership", "current-role", "ops-pm"],
            "priority_weight": 0.8,
        },
    ],
    "rss_sources": [
        {
            "url": "https://www.oneusefulthing.org/feed",
            "label": "AI-native Ops (Substack)",
            "platform": "substack",
            "purpose": "AI workflow design, operator judgment, and education implementation signals",
            "priority_lane": "ai",
        },
        {
            "url": "https://www.highereddive.com/feeds/news/",
            "label": "Admissions + Ops",
            "platform": "rss",
            "purpose": "Higher-ed operations, enrollment shifts, and student-journey execution signals",
            "priority_lane": "admissions",
        },
    ],
    "reddit_sources": [
        {
            "subreddit": "Using_AI_in_Education",
            "purpose": "Practitioner edge cases and growth experiments",
            "priority_lane": "ai",
        },
        {
            "subreddit": "edtech",
            "purpose": "Product launches, funding news, and operator lessons",
            "priority_lane": "current-role",
        },
    ],
    "topics": [
        "ai implementation in education",
        "admissions and outreach systems",
        "market development and referral trust",
        "leadership and operator clarity",
        "intrapreneurship",
        "edtech product launches",
        "workflow automation",
    ],
    "filters": {
        "prioritize": [
            "operator language",
            "role-safe AI positioning",
            "intrapreneurial framing",
            "leadership lessons",
            "market-development relevance",
        ],
        "avoid": [
            "obvious exit-signaling language",
            "generic hustle content",
            "trend chasing without operational value",
        ],
    },
}


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_data(self) -> str:
        return "".join(self.parts)


def _workspace_paths(workspace_root: Path | None = None) -> tuple[Path, Path, Path]:
    source_root = workspace_root or discover_linkedin_workspace_root()
    # Explicit roots keep tests and bounded import tools self-contained. The
    # production fetch path writes recurring signals only to the canonical
    # private FEEZIE state root while continuing to read the reviewed watchlist
    # from the repository workspace.
    root = source_root if workspace_root is not None else workspace_state_root("feezie-os")
    research_root = root / "research"
    signals_root = research_root / "market_signals"
    watchlist_path = source_root / "research" / "watchlists.yaml"
    return root, signals_root, watchlist_path


def ensure_watchlist(workspace_root: Path | None = None) -> dict[str, Any]:
    _, signals_root, watchlist_path = _workspace_paths(workspace_root)
    if not watchlist_path.exists():
        if workspace_root is None:
            # The privacy-reduced Railway checkout intentionally excludes the
            # owner workspace tree. Its safe-public-feed lane uses this
            # reviewed, credential-free baseline while canonical local runs
            # continue to read the owner-controlled watchlist file.
            return DEFAULT_WATCHLIST
        watchlist_path.parent.mkdir(parents=True, exist_ok=True)
        watchlist_path.write_text(yaml.dump(DEFAULT_WATCHLIST, sort_keys=False), encoding="utf-8")
        return DEFAULT_WATCHLIST
    with watchlist_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or DEFAULT_WATCHLIST


def _slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return lowered or "signal"


def _http_get(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = Request(url, headers=headers)
    with urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT) as response:
        return response.read()


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _clean_multiline_text(value: str | None) -> str:
    if not value:
        return ""
    return "\n".join(line.rstrip() for line in str(value).strip().splitlines()).strip()


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    parser = _HTMLStripper()
    parser.feed(unescape(value))
    return _clean_text(parser.get_data())


def _truncate(text: str, limit: int = 360) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _summarize_text(text: str, *, sentences: int = 2, limit: int = 320) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    parts = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]
    candidate = " ".join(parts[:sentences]) if parts else cleaned
    return _truncate(candidate, limit)


def _supporting_claims_from_text(text: str, *, title: str, summary: str, limit: int = 2) -> list[str]:
    claims: list[str] = []
    seen = {
        _clean_text(title).lower().rstrip("."),
    }
    for segment in re.split(r"(?<=[.!?])\s+", _clean_text(summary)):
        normalized = _clean_text(segment).lower().rstrip(".")
        if normalized:
            seen.add(normalized)
    for segment in re.split(r"(?<=[.!?])\s+", _clean_text(text)):
        claim = _truncate(segment, 240)
        normalized = claim.lower().rstrip(".")
        if not claim or normalized in seen:
            continue
        seen.add(normalized)
        claims.append(claim)
        if len(claims) >= limit:
            break
    return claims


def _parse_datetime(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return datetime.now(timezone.utc).isoformat()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _split_markdown_frontmatter(text: str) -> tuple[str | None, str]:
    """Split frontmatter only at exact, unindented delimiter lines.

    Source excerpts can legitimately contain ``---`` inside quoted YAML
    scalars. A bare substring split truncates those valid scalars and makes a
    verified compatibility projection unreadable on its next refresh.
    """

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None, text
    closing_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r\n") == "---"
        ),
        None,
    )
    if closing_index is None:
        raise ValueError("unterminated Markdown frontmatter")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1 :])


def _load_existing_frontmatter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, _ = _split_markdown_frontmatter(text)
        if frontmatter is None:
            return {}
        payload = yaml.safe_load(frontmatter) or {}
    except (ValueError, yaml.YAMLError):
        LOGGER.warning(
            "Ignoring malformed historical market-signal frontmatter for %s; the next verified write will repair it.",
            path.name,
        )
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_signal(entry: dict[str, Any], body: str) -> str:
    frontmatter = yaml.dump(entry, sort_keys=False, allow_unicode=False)
    return f"---\n{frontmatter}---\n\n{body.strip()}\n"


def _write_signal(path: Path, entry: dict[str, Any], body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    preserved_created_at = _clean_text(_load_existing_frontmatter(path).get("created_at"))
    if preserved_created_at:
        entry = {**entry, "created_at": preserved_created_at}
    rendered = _render_signal(entry, body)
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        path.write_text(rendered, encoding="utf-8")
    sync_market_signal_archive_entry(path, path.parents[2])
    return path


def _prune_source_family(signals_root: Path, pattern: str, keep_filenames: set[str]) -> None:
    if not keep_filenames:
        return
    for candidate in signals_root.glob(pattern):
        if candidate.name in keep_filenames:
            continue
        candidate.unlink(missing_ok=True)


def _reddit_rss_url(subreddit: str) -> str:
    clean = subreddit.replace("r/", "").strip()
    return f"https://www.reddit.com/r/{clean}/.rss"


def _reddit_combined_rss_url(subreddits: list[str], *, limit: int) -> str:
    clean = sorted(
        {
            value.replace("r/", "").strip()
            for value in subreddits
            if re.fullmatch(r"[A-Za-z0-9_]+", value.replace("r/", "").strip())
        },
        key=str.lower,
    )
    if not clean:
        raise ValueError("at least one valid configured subreddit is required")
    bounded_limit = max(1, min(100, int(limit)))
    return f"https://www.reddit.com/r/{'+'.join(clean)}/.rss?limit={bounded_limit}"


def _subreddit_from_feed_entry(entry: dict[str, str]) -> str:
    for value in (entry.get("link"), entry.get("category"), entry.get("guid")):
        match = re.search(r"(?:^|[/\s])r/([A-Za-z0-9_]+)(?:[/\s]|$)", _clean_text(value), re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _build_reddit_feed_entry(source: dict[str, Any], entry: dict[str, str]) -> tuple[dict[str, Any], str, str]:
    subreddit = source.get("subreddit", "reddit").replace("r/", "").strip()
    title = _clean_text(entry.get("title")) or f"r/{subreddit} post"
    summary = _truncate(_clean_text(entry.get("summary")) or title, 320)
    source_url = _clean_text(entry.get("link")) or _reddit_rss_url(subreddit)
    published_at = _parse_datetime(entry.get("published_at"))
    purpose = _clean_text(source.get("purpose")) or "Practitioner signal"
    raw_text = "\n\n".join(part for part in [title, summary] if part).strip()
    guid = _clean_text(entry.get("guid")) or source_url or title
    signal = {
        "kind": "market_signal",
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_at": published_at,
        "source_platform": "reddit",
        "source_type": "post",
        "source_url": source_url,
        "author": _clean_text(entry.get("author")) or "reddit",
        "role_alignment": "market_signal",
        "priority_lane": _clean_text(source.get("priority_lane")) or "current-role",
        "summary": summary,
        "why_it_matters": purpose,
        "watchlist_matches": ["reddit", f"r/{subreddit}"],
        "topics": [purpose],
        "headline_candidates": [title],
        "core_claim": title,
        "supporting_claims": [summary] if summary and summary.lower() != title.lower() else [],
        "raw_text": raw_text,
        "source_metadata": {
            "extraction_method": "reddit_rss",
            "subreddit": subreddit,
            "entry_guid": guid,
        },
    }
    filename = f"{published_at[:10]}__reddit__{_slugify(subreddit)}__{_slugify(guid)[:80]}.md"
    return signal, raw_text, filename


def fetch_reddit_signals(
    workspace_root: Path | None = None,
    *,
    limit_per_source: int = DEFAULT_REDDIT_LIMIT,
    canonical_store: IntegratedSystemStore | None = None,
    run_id: str | None = None,
    write_compatibility_projection: bool = False,
) -> list[Path]:
    _, signals_root, _ = _workspace_paths(workspace_root)
    watchlist = ensure_watchlist(workspace_root)
    execution = SourceIntakeExecutionService(canonical_store or IntegratedSystemStore())
    written: list[Path] = []
    registered = 0
    reused = 0
    captured = 0
    gated_out = 0
    errors: list[dict[str, Any]] = []
    configured_sources = [
        source
        for source in watchlist.get("reddit_sources", [])
        if isinstance(source, dict) and _clean_text(source.get("subreddit"))
    ]
    source_by_subreddit = {
        _clean_text(source.get("subreddit")).replace("r/", "").lower(): source
        for source in configured_sources
    }
    seen_by_subreddit = {name: 0 for name in source_by_subreddit}
    keep_filenames_by_subreddit: dict[str, set[str]] = {
        name: set() for name in source_by_subreddit
    }

    entries: list[dict[str, str]] = []
    if configured_sources:
        try:
            feed_url = _reddit_combined_rss_url(
                [_clean_text(source.get("subreddit")) for source in configured_sources],
                limit=limit_per_source * len(configured_sources),
            )
            raw_feed = _http_get(
                feed_url,
                accept="application/rss+xml, application/atom+xml, text/xml, application/xml",
            )
            entries = _iter_feed_entries(ET.fromstring(raw_feed))
        except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            LOGGER.warning("Skipping configured Reddit feed: %s", exc)
            errors.append(
                {
                    "stage": "reddit_combined_rss_fetch_or_parse",
                    "source_ref": "configured_subreddits",
                    "reason": type(exc).__name__,
                }
            )

    for feed_entry in entries:
        subreddit = _subreddit_from_feed_entry(feed_entry)
        source_key = subreddit.lower()
        source = source_by_subreddit.get(source_key)
        if source is None or seen_by_subreddit[source_key] >= limit_per_source:
            continue
        if not _clean_text(feed_entry.get("title")):
            continue
        seen_by_subreddit[source_key] += 1
        source_url = _clean_text(feed_entry.get("link")) or _reddit_rss_url(subreddit)
        entry_id = _clean_text(feed_entry.get("guid")) or source_url
        relevance, admissibility, rights = _configured_gate_state(source)
        try:
            prepared = execution.register_and_gate(
                reddit_discovery_envelope(
                    subreddit=subreddit,
                    reddit_id=entry_id,
                    canonical_url=source_url or None,
                    title=_clean_text(feed_entry.get("title")) or None,
                    author=_clean_text(feed_entry.get("author")) or None,
                    discovery_surface="configured_combined_subreddit_rss",
                    rights_state=rights,
                    share_public_content=(
                        rights == "permitted"
                        and is_credential_free_public_url(source_url)
                    ),
                ),
                relevance_state=relevance,
                admissibility_state=admissibility,
                reason="configured_reddit_watchlist_policy",
                policy_name="reddit_scheduled_intake_gate",
                capture_kind="raw",
            )
            registered += 1
            if not prepared["decision"].get("capture_required") and not prepared["decision"].get("existing_artifact_id"):
                gated_out += 1
                continue
            entry, body, filename = _build_reddit_feed_entry(source, feed_entry)
            capture = execution.attach_or_reuse_text(
                prepared,
                text=body,
                capture_kind="raw",
                metadata={"capture_adapter": "reddit_combined_rss", "capture_version": "1.0.0"},
            )
            canonical_source_id = _clean_text(capture.get("source_id"))
            canonical_artifact_id = _clean_text(capture.get("artifact_id"))
            entry["source_metadata"] = {
                **dict(entry.get("source_metadata") or {}),
                "canonical_source_id": canonical_source_id,
                "canonical_capture_artifact_id": canonical_artifact_id,
            }
            SourceFeedSignalService(execution.store).record(
                source_id=canonical_source_id,
                artifact_id=canonical_artifact_id,
                signal=entry,
                normalizer_name="reddit_combined_rss",
            )
            reused += int(capture["reused"])
            captured += 1
        except Exception as exc:
            LOGGER.exception("Canonical Reddit RSS intake failed for %s", source_url or entry_id)
            errors.append(
                {
                    "stage": "registration_gate_capture_or_projection",
                    "source_ref": source_url or entry_id,
                    "reason": type(exc).__name__,
                }
            )
            continue
        keep_filenames_by_subreddit[source_key].add(filename)
        if write_compatibility_projection:
            written.append(_write_signal(signals_root / filename, entry, f"# {entry['title']}\n\n{body}"))

    if write_compatibility_projection:
        for source_key, keep_filenames in keep_filenames_by_subreddit.items():
            if not keep_filenames:
                continue
            slug = _slugify(source_key)
            _prune_source_family(
                signals_root,
                f"*__reddit__{slug}__*.md",
                keep_filenames,
            )
    disposition = _run_disposition(changed=max(0, captured - reused), errors=len(errors), gated_out=gated_out)
    execution.record_run_receipt(
        run_kind="reddit_feed",
        disposition=disposition,
        counts={
            "registered": registered,
            "captured": captured,
            "written": len(written),
            "reused": reused,
            "gated_out": gated_out,
            "errors": len(errors),
        },
        errors=errors,
        run_id=run_id,
        provenance={
            "trigger": "local_scheduler",
            "network_mode": "permitted_feed",
            "compatibility_projection": write_compatibility_projection,
        },
    )
    return written


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, *names: str) -> str:
    targets = {name.lower() for name in names}
    for child in list(node):
        if _local_name(child.tag) in targets:
            return _clean_text("".join(child.itertext()))
    return ""


def _rss_item_link(node: ET.Element) -> str:
    for child in list(node):
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return _clean_text(href)
        text = _clean_text("".join(child.itertext()))
        if text:
            return text
    return ""


def _feed_media_attributes(node: ET.Element) -> dict[str, str]:
    enclosure: dict[str, str] = {}
    transcript: dict[str, str] = {}
    for child in list(node):
        local_name = _local_name(child.tag)
        if local_name == "enclosure":
            candidate = {
                "enclosure_url": _clean_text(child.attrib.get("url")),
                "enclosure_type": _clean_text(child.attrib.get("type")),
                "enclosure_length": _clean_text(child.attrib.get("length")),
            }
            if candidate["enclosure_url"]:
                enclosure = candidate
        elif local_name == "content" and not enclosure:
            medium = _clean_text(child.attrib.get("medium")).lower()
            media_type = _clean_text(child.attrib.get("type")).lower()
            if medium == "audio" or media_type.startswith("audio/"):
                candidate_url = _clean_text(child.attrib.get("url"))
                if candidate_url:
                    enclosure = {
                        "enclosure_url": candidate_url,
                        "enclosure_type": media_type,
                        "enclosure_length": _clean_text(child.attrib.get("fileSize")),
                    }
        elif local_name == "transcript" and not transcript:
            candidate_url = _clean_text(child.attrib.get("url")) or _clean_text(
                "".join(child.itertext())
            )
            if candidate_url:
                transcript = {
                    "transcript_url": candidate_url,
                    "transcript_type": _clean_text(child.attrib.get("type")),
                    "transcript_language": _clean_text(
                        child.attrib.get("language") or child.attrib.get("lang")
                    ),
                    "transcript_rel": _clean_text(child.attrib.get("rel")),
                }
    return {**enclosure, **transcript}


def _iter_feed_entries(root: ET.Element) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    root_name = _local_name(root.tag)
    if root_name == "rss":
        channel = next((child for child in list(root) if _local_name(child.tag) == "channel"), None)
        if channel is None:
            return entries
        for item in list(channel):
            if _local_name(item.tag) != "item":
                continue
            description = _child_text(item, "description", "encoded", "summary")
            entries.append(
                {
                    "title": _child_text(item, "title"),
                    "link": _rss_item_link(item),
                    "summary": _strip_html(description),
                    "published_at": _child_text(item, "pubdate", "published", "updated"),
                    "author": _child_text(item, "author", "creator", "dc:creator"),
                    "guid": _child_text(item, "guid"),
                    "duration": _child_text(item, "duration"),
                    **_feed_media_attributes(item),
                }
            )
        return entries

    for entry in root.iter():
        if _local_name(entry.tag) != "entry":
            continue
        summary = _child_text(entry, "summary", "content")
        author = ""
        for child in list(entry):
            if _local_name(child.tag) == "author":
                author = _child_text(child, "name") or _clean_text("".join(child.itertext()))
        entries.append(
            {
                "title": _child_text(entry, "title"),
                "link": _rss_item_link(entry),
                "summary": _strip_html(summary),
                "published_at": _child_text(entry, "published", "updated"),
                "author": author,
                "guid": _child_text(entry, "id"),
                "duration": _child_text(entry, "duration"),
                "category": " ".join(
                    _clean_text(child.attrib.get("term") or "".join(child.itertext()))
                    for child in list(entry)
                    if _local_name(child.tag) == "category"
                ),
                **_feed_media_attributes(entry),
            }
        )
    return entries


def _infer_platform(source: dict[str, Any]) -> str:
    explicit = _clean_text(source.get("platform"))
    if explicit:
        return explicit
    host = urlparse(_clean_text(source.get("url"))).netloc.lower()
    if "substack" in host or "oneusefulthing" in host:
        return "substack"
    return "rss"


def _entry_is_podcast(source: dict[str, Any], entry: dict[str, Any]) -> bool:
    configured = _clean_text(source.get("content_kind")).lower()
    enclosure_type = _clean_text(entry.get("enclosure_type")).lower()
    enclosure_url = _clean_text(entry.get("enclosure_url")).lower()
    return configured in {"podcast", "podcast_episode"} or bool(
        enclosure_type.startswith("audio/")
        or re.search(r"\.(?:mp3|m4a|aac|wav|ogg|opus)(?:$|[?#])", enclosure_url)
    )


def _entry_external_ref(entry: dict[str, Any]) -> str:
    for key in ("guid", "enclosure_url", "link"):
        value = _clean_text(entry.get(key))
        if value:
            return value
    material = "\n".join(
        [
            _clean_text(entry.get("title")),
            _clean_text(entry.get("published_at")),
        ]
    )
    return f"derived:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def _annotate_feed_entry_identities(
    source: dict[str, Any], entries: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], int]:
    link_counts: dict[str, int] = {}
    enclosure_counts: dict[str, int] = {}
    for entry in entries:
        link = _clean_text(entry.get("link"))
        enclosure_url = _clean_text(entry.get("enclosure_url"))
        if link:
            link_counts[link] = link_counts.get(link, 0) + 1
        if enclosure_url:
            enclosure_counts[enclosure_url] = enclosure_counts.get(enclosure_url, 0) + 1

    annotated: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    duplicate_entries = 0
    for raw_entry in entries:
        entry = dict(raw_entry)
        is_podcast = _entry_is_podcast(source, entry)
        origin = "podcast" if is_podcast else "rss"
        external_ref = _entry_external_ref(entry)
        identity_key = (origin, external_ref)
        if identity_key in seen:
            duplicate_entries += 1
            continue
        seen.add(identity_key)

        link = _clean_text(entry.get("link"))
        enclosure_url = _clean_text(entry.get("enclosure_url"))
        canonical_url = ""
        if link and link_counts.get(link) == 1 and is_credential_free_public_url(link):
            canonical_url = link
        elif (
            is_podcast
            and enclosure_url
            and enclosure_counts.get(enclosure_url) == 1
            and is_credential_free_public_url(enclosure_url)
        ):
            canonical_url = enclosure_url
        entry.update(
            {
                "_intake_origin": origin,
                "_external_ref": external_ref,
                "_canonical_url": canonical_url,
            }
        )
        annotated.append(entry)
    return annotated, duplicate_entries


def _feed_route_state(
    store: IntegratedSystemStore,
    *,
    origin: str,
    feed_url: str,
) -> dict[str, dict[str, Any]]:
    store.migrate()
    route = f"{origin}:{_clean_text(feed_url)}"
    with store.connection() as connection:
        rows = connection.execute(
            """SELECT d.external_ref,d.discovery_id,d.relevance_state,
                      s.source_id,s.raw_artifact_id,s.transcript_artifact_id
               FROM discovery_events d
               JOIN sources s ON s.source_id=d.source_id
               WHERE d.origin=? AND d.discovery_route=?
                 AND s.merged_into_source_id IS NULL""",
            (origin, route),
        ).fetchall()
        attempt_rows = connection.execute(
            """SELECT aggregate_id,occurred_at,payload_json
               FROM system_events
               WHERE event_type=? AND aggregate_type='source'
               ORDER BY occurred_at,event_id""",
            (PODCAST_TRANSCRIPT_ATTEMPT_EVENT,),
        ).fetchall()
    state = {
        _clean_text(row["external_ref"]): {
            "source_id": row["source_id"],
            "discovery_id": row["discovery_id"],
            "relevance_state": row["relevance_state"],
            "raw_captured": bool(row["raw_artifact_id"]),
            "transcript_captured": bool(row["transcript_artifact_id"]),
            "transcript_attempt_count": 0,
            "last_transcript_attempt_at": "",
            "last_transcript_attempt_status": "",
        }
        for row in rows
        if _clean_text(row["external_ref"])
    }
    by_source_id = {
        str(item["source_id"]): item
        for item in state.values()
        if item.get("source_id")
    }
    for row in attempt_rows:
        item = by_source_id.get(str(row["aggregate_id"] or ""))
        if item is None:
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        item["transcript_attempt_count"] = int(
            item.get("transcript_attempt_count") or 0
        ) + 1
        item["last_transcript_attempt_at"] = str(row["occurred_at"] or "")
        item["last_transcript_attempt_status"] = _clean_text(
            payload.get("outcome") if isinstance(payload, dict) else ""
        )
    return state


def _entry_envelope(source: dict[str, Any], entry: dict[str, Any], *, rights: str):
    feed_url = _clean_text(source.get("url"))
    canonical_url = _clean_text(entry.get("_canonical_url"))
    external_ref = _clean_text(entry.get("_external_ref"))
    common = {
        "title": _clean_text(entry.get("title")) or None,
        "published_at": _clean_text(entry.get("published_at")) or None,
        "rights_state": rights,
        "share_public_content": bool(
            rights == "permitted" and is_credential_free_public_url(canonical_url)
        ),
    }
    if _clean_text(entry.get("_intake_origin")) == "podcast":
        return podcast_discovery_envelope(
            feed_url=feed_url,
            episode_guid=external_ref,
            episode_url=canonical_url or None,
            publisher=_clean_text(entry.get("author"))
            or _clean_text(source.get("label"))
            or None,
            **common,
        )
    return rss_discovery_envelope(
        feed_url=feed_url,
        entry_url=canonical_url or None,
        entry_id=external_ref,
        publisher=_clean_text(entry.get("author"))
        or _clean_text(source.get("label"))
        or None,
        **common,
    )


def _bounded_public_http_get(url: str, *, accept: str, max_bytes: int) -> bytes:
    validated_url = credential_free_public_url(url)
    request = Request(validated_url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT) as response:
        credential_free_public_url(response.geturl())
        declared_length = response.headers.get("Content-Length")
        if declared_length:
            try:
                if int(declared_length) > max_bytes:
                    raise ValueError("public source exceeds the configured byte limit")
            except ValueError as exc:
                if "exceeds" in str(exc):
                    raise
        chunks: list[bytes] = []
        observed = 0
        while True:
            chunk = response.read(min(64 * 1024, max_bytes - observed + 1))
            if not chunk:
                break
            observed += len(chunk)
            if observed > max_bytes:
                raise ValueError("public source exceeds the configured byte limit")
            chunks.append(chunk)
    return b"".join(chunks)


def _transcript_json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            text for item in value if (text := _transcript_json_text(item).strip())
        )
    if isinstance(value, dict):
        for key in ("segments", "items", "transcript", "captions", "utterances"):
            if key in value:
                text = _transcript_json_text(value[key]).strip()
                if text:
                    return text
        for key in ("text", "body", "content", "caption", "utterance"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key]
    return ""


def _normalize_podcast_transcript(raw: bytes, media_type: str = "") -> str:
    text = raw.decode("utf-8-sig", errors="replace")
    if "json" in _clean_text(media_type).lower() or text.lstrip().startswith(("{", "[")):
        try:
            json_text = _transcript_json_text(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            json_text = ""
        if json_text:
            text = json_text
    if "html" in _clean_text(media_type).lower() or re.search(r"<html\b", text, re.IGNORECASE):
        text = _strip_html(text)

    lines: list[str] = []
    previous = ""
    for raw_line in text.splitlines():
        line = _clean_text(re.sub(r"<[^>]+>", " ", unescape(raw_line)))
        if not line:
            continue
        if line.upper() == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE ")):
            continue
        if re.fullmatch(r"\d+", line) or "-->" in line:
            continue
        if line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def _fetch_podcast_transcript(entry: dict[str, Any]) -> str:
    transcript_url = _clean_text(entry.get("transcript_url"))
    if not transcript_url:
        return ""
    raw = _bounded_public_http_get(
        transcript_url,
        accept="text/vtt,text/plain,application/json,text/html;q=0.8,*/*;q=0.1",
        max_bytes=PODCAST_TRANSCRIPT_MAX_BYTES,
    )
    return _normalize_podcast_transcript(raw, _clean_text(entry.get("transcript_type")))


def _download_podcast_audio(entry: dict[str, Any], destination: Path) -> Path:
    audio_url = credential_free_public_url(entry.get("enclosure_url"))
    configured_max = _bounded_env_int(
        "PODCAST_AUDIO_MAX_BYTES",
        PODCAST_AUDIO_MAX_BYTES,
        minimum=1 * 1024 * 1024,
        maximum=2 * 1024 * 1024 * 1024,
    )
    suffix = Path(urlparse(audio_url).path).suffix.lower()
    if suffix not in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".webm"}:
        suffix = ".mp3"
    output_path = destination / f"episode{suffix}"
    request = Request(
        audio_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "audio/*,application/octet-stream;q=0.8",
        },
    )
    with urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT) as response:
        credential_free_public_url(response.geturl())
        declared_length = response.headers.get("Content-Length")
        if declared_length:
            try:
                if int(declared_length) > configured_max:
                    raise ValueError("podcast audio exceeds the configured byte limit")
            except ValueError as exc:
                if "exceeds" in str(exc):
                    raise
        observed = 0
        with output_path.open("wb") as handle:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > configured_max:
                    raise ValueError("podcast audio exceeds the configured byte limit")
                handle.write(chunk)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ValueError("podcast audio download was empty")
    return output_path


def _transcribe_podcast_audio(entry: dict[str, Any]) -> str:
    from app.services.youtube_watchlist_service import (
        local_media_transcription_runtime,
        transcribe_local_audio_file,
    )

    runtime = local_media_transcription_runtime()
    if not bool(
        runtime.get("ffmpeg") and runtime.get("whisper")
    ):
        raise RuntimeError("local_media_transcription_runtime_unavailable")
    with tempfile.TemporaryDirectory(prefix="podcast-transcript-") as temp_dir:
        audio_path = _download_podcast_audio(entry, Path(temp_dir))
        return _clean_multiline_text(transcribe_local_audio_file(audio_path))


def _article_preview_for_url(url: str) -> dict[str, str]:
    cleaned_url = _clean_text(url)
    if not cleaned_url:
        return {}
    try:
        return social_signal_extraction_service.fetch_url_article_payload(cleaned_url)
    except Exception as exc:
        LOGGER.warning("RSS article enrichment failed for %s: %s", cleaned_url, exc)
        return {}


def _article_entry_from_existing(
    base_entry: dict[str, Any],
    *,
    article_preview: dict[str, str],
) -> tuple[dict[str, Any], str]:
    preview = article_preview or {}
    title = _clean_text(preview.get("title")) or _clean_text(base_entry.get("title")) or "RSS signal"
    article_text = str(preview.get("text") or "").strip()
    fallback_summary = _clean_text(base_entry.get("summary")) or title
    summary = _summarize_text(article_text) or _truncate(fallback_summary, 320)
    supporting_claims = _supporting_claims_from_text(article_text, title=title, summary=summary)
    if not supporting_claims:
        existing_claims = base_entry.get("supporting_claims")
        if isinstance(existing_claims, list):
            supporting_claims = [_clean_text(item) for item in existing_claims if _clean_text(item)][:2]
    if not supporting_claims and summary and summary.lower() != title.lower():
        supporting_claims = [summary]
    raw_text = article_text or str(base_entry.get("raw_text") or "").strip() or "\n\n".join(part for part in [title, summary] if part).strip()
    source_metadata = dict(base_entry.get("source_metadata") or {})
    source_metadata["extraction_method"] = "rss_feed+article_preview" if article_text else _clean_text(source_metadata.get("extraction_method")) or "rss_feed"
    updated_entry = dict(base_entry)
    updated_entry.update(
        {
            "title": title,
            "author": _clean_text(preview.get("author")) or _clean_text(base_entry.get("author")),
            "summary": summary,
            "supporting_claims": supporting_claims,
            "raw_text": raw_text,
            "source_metadata": source_metadata,
        }
    )
    return updated_entry, raw_text


def _build_rss_entry(
    source: dict[str, Any],
    entry: dict[str, str],
    *,
    article_preview: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str, str]:
    source_url = _clean_text(entry.get("link")) or _clean_text(source.get("url"))
    published_at = _parse_datetime(entry.get("published_at"))
    label = _clean_text(source.get("label")) or "rss-feed"
    purpose = _clean_text(source.get("purpose")) or label
    base_title = _clean_text(entry.get("title")) or _clean_text(source.get("label")) or "RSS signal"
    base_summary = _clean_text(entry.get("summary"))
    guid = _clean_text(entry.get("guid")) or source_url or base_title
    base_signal = {
        "kind": "market_signal",
        "title": base_title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_at": published_at,
        "source_platform": _infer_platform(source),
        "source_type": "article",
        "source_url": source_url,
        "author": _clean_text(entry.get("author")) or label,
        "role_alignment": "market_signal",
        "priority_lane": _clean_text(source.get("priority_lane")) or "current-role",
        "summary": base_summary or base_title,
        "why_it_matters": purpose,
        "watchlist_matches": ["rss", label],
        "topics": [purpose],
        "headline_candidates": [base_title],
        "core_claim": base_title,
        "supporting_claims": [_truncate(base_summary, 240)] if base_summary else [],
        "raw_text": "\n\n".join(
            part for part in [base_title, base_summary] if part
        ).strip(),
        "source_metadata": {
            "extraction_method": "rss_feed",
            "feed_label": label,
            "feed_url": _clean_text(source.get("url")),
            "entry_guid": guid,
        },
    }
    signal, raw_text = _article_entry_from_existing(base_signal, article_preview=article_preview or {})
    identity = _slugify(guid)[:80] or hashlib.sha1(guid.encode("utf-8")).hexdigest()[:12]
    filename = f"{published_at[:10]}__rss__{_slugify(label)}__{identity}.md"
    return signal, raw_text, filename


def _build_podcast_entry(
    source: dict[str, Any],
    entry: dict[str, Any],
    *,
    transcript_text: str = "",
) -> tuple[dict[str, Any], str, str]:
    signal, body, filename = _build_rss_entry(
        source,
        entry,
        article_preview={"text": transcript_text} if transcript_text else {},
    )
    episode_url = (
        _clean_text(entry.get("link"))
        or _clean_text(entry.get("_canonical_url"))
        or _clean_text(entry.get("enclosure_url"))
    )
    signal.update(
        {
            "source_platform": "podcast",
            "source_type": "podcast_transcript" if transcript_text else "podcast_episode",
            "source_url": episode_url,
            "raw_text": transcript_text or str(signal.get("raw_text") or body),
            "summary": _summarize_text(transcript_text)
            if transcript_text
            else _clean_text(signal.get("summary")),
            "supporting_claims": _supporting_claims_from_text(
                transcript_text,
                title=_clean_text(signal.get("title")),
                summary=_summarize_text(transcript_text),
            )
            if transcript_text
            else list(signal.get("supporting_claims") or []),
        }
    )
    signal["source_metadata"] = {
        **dict(signal.get("source_metadata") or {}),
        "extraction_method": (
            "podcast_transcript"
            if transcript_text
            else "podcast_feed_show_notes"
        ),
        "entry_guid": _clean_text(entry.get("_external_ref")),
        "duration": _clean_text(entry.get("duration")),
        "enclosure_type": _clean_text(entry.get("enclosure_type")),
        "transcript_link_declared": bool(_clean_text(entry.get("transcript_url"))),
    }
    return signal, str(signal.get("raw_text") or body), filename


def _attach_feed_capture(
    execution: SourceIntakeExecutionService,
    prepared: dict[str, Any],
    *,
    text: str,
    capture_kind: str,
    signal: dict[str, Any],
    normalizer_name: str,
    capture_adapter: str,
) -> dict[str, Any]:
    capture = execution.attach_or_reuse_text(
        prepared,
        text=text,
        capture_kind=capture_kind,
        metadata={"capture_adapter": capture_adapter, "capture_version": "1.0.0"},
    )
    source_id = _clean_text(capture.get("source_id"))
    artifact_id = _clean_text(capture.get("artifact_id"))
    signal["source_metadata"] = {
        **dict(signal.get("source_metadata") or {}),
        "canonical_source_id": source_id,
        "canonical_capture_artifact_id": artifact_id,
    }
    SourceFeedSignalService(execution.store).record(
        source_id=source_id,
        artifact_id=artifact_id,
        signal=signal,
        normalizer_name=normalizer_name,
    )
    return capture


def fetch_rss_signals(
    workspace_root: Path | None = None,
    *,
    limit_per_source: int = DEFAULT_RSS_LIMIT,
    canonical_store: IntegratedSystemStore | None = None,
    run_id: str | None = None,
    write_compatibility_projection: bool = False,
) -> list[Path]:
    _, signals_root, _ = _workspace_paths(workspace_root)
    watchlist = ensure_watchlist(workspace_root)
    execution = SourceIntakeExecutionService(canonical_store or IntegratedSystemStore())
    effective_run_id = str(run_id or f"rss-feed:{uuid.uuid4()}").strip()
    written_by_path: dict[str, Path] = {}
    registered = 0
    registered_new = 0
    discoveries_new = 0
    reused = 0
    captured = 0
    captured_new = 0
    raw_captured = 0
    transcript_captured = 0
    podcast_show_notes_captured = 0
    podcast_audio_transcribed = 0
    podcast_transcript_attempts = 0
    podcast_entries = 0
    podcast_transcript_links = 0
    manifest_entries = 0
    unique_entries = 0
    duplicate_entries = 0
    pending_initial = 0
    podcast_pending_initial = 0
    completed_pending = 0
    podcast_completed_pending = 0
    selected = 0
    gated_out = 0
    errors: list[dict[str, Any]] = []
    audio_candidates: list[dict[str, Any]] = []
    compatibility_families: list[tuple[str, set[str]]] = []

    def record_podcast_transcript_attempt(
        *,
        source_id: str,
        entry: dict[str, Any],
        feed_url: str,
        outcome: str,
        error_class: str | None = None,
    ) -> None:
        nonlocal podcast_transcript_attempts
        external_ref = _clean_text(entry.get("_external_ref"))
        route_fingerprint = hashlib.sha256(
            f"podcast:{feed_url}:{external_ref}".encode("utf-8")
        ).hexdigest()[:16]
        attempted_at = datetime.now(timezone.utc).isoformat()
        try:
            execution.store.append_event(
                event_type=PODCAST_TRANSCRIPT_ATTEMPT_EVENT,
                aggregate_type="source",
                aggregate_id=source_id,
                actor_type="source_intake_scheduler",
                payload={
                    "schema_version": "podcast_transcript_attempt/v1",
                    "run_id": effective_run_id,
                    "outcome": outcome,
                    "capture_kind": "transcript",
                    "error_class": error_class,
                },
                provenance={
                    "origin": "podcast",
                    "discovery_route": f"podcast:{feed_url}",
                    "external_ref_sha256": hashlib.sha256(
                        external_ref.encode("utf-8")
                    ).hexdigest(),
                },
                idempotency_key=(
                    f"podcast-transcript-attempt:{effective_run_id}:"
                    f"{source_id}:{route_fingerprint}"
                ),
                occurred_at=attempted_at,
            )
            podcast_transcript_attempts += 1
        except Exception:
            LOGGER.exception("Podcast transcript-attempt receipt could not be stored")
            errors.append(
                {
                    "stage": "podcast_transcript_attempt_receipt",
                    "source_ref": external_ref,
                    "reason": "canonical_attempt_receipt_unavailable",
                }
            )

    for source in watchlist.get("rss_sources", []):
        if not isinstance(source, dict):
            continue
        label = _clean_text(source.get("label")) or "rss-feed"
        family_pattern = f"*__rss__{_slugify(label)}__*.md"
        keep_filenames: set[str] = set()
        compatibility_families.append((family_pattern, keep_filenames))
        feed_url = _clean_text(source.get("url"))
        try:
            raw = _http_get(
                feed_url,
                accept="application/rss+xml, application/atom+xml, text/xml, application/xml",
            )
            root = ET.fromstring(raw)
        except (HTTPError, URLError, TimeoutError, ET.ParseError) as exc:
            LOGGER.warning("Skipping RSS source %s: %s", label, exc)
            errors.append(
                {
                    "stage": "feed_fetch_or_parse",
                    "source_ref": _clean_text(source.get("url")),
                    "reason": type(exc).__name__,
                }
            )
            continue

        raw_entries = _iter_feed_entries(root)
        entries, feed_duplicate_entries = _annotate_feed_entry_identities(
            source, raw_entries
        )
        manifest_entries += len(raw_entries)
        unique_entries += len(entries)
        duplicate_entries += feed_duplicate_entries
        podcast_entries += sum(
            1
            for entry in entries
            if _clean_text(entry.get("_intake_origin")) == "podcast"
        )
        podcast_transcript_links += sum(
            1 for entry in entries if _clean_text(entry.get("transcript_url"))
        )

        route_state = {
            origin: _feed_route_state(execution.store, origin=origin, feed_url=feed_url)
            for origin in {"rss", "podcast"}
        }
        feed_order = {
            (
                _clean_text(entry.get("_intake_origin")),
                _clean_text(entry.get("_external_ref")),
            ): index
            for index, entry in enumerate(entries)
        }
        pending_entries: list[dict[str, Any]] = []
        for entry in entries:
            origin = _clean_text(entry.get("_intake_origin"))
            external_ref = _clean_text(entry.get("_external_ref"))
            existing = route_state.get(origin, {}).get(external_ref) or {}
            is_captured = bool(
                existing.get("transcript_captured")
                if origin == "podcast"
                else existing.get("raw_captured")
            )
            if not is_captured:
                pending_entries.append(entry)
        pending_entries.sort(
            key=lambda entry: (
                0
                if _clean_text(entry.get("_intake_origin")) != "podcast"
                else 1,
                0
                if not (
                    route_state.get(_clean_text(entry.get("_intake_origin")), {}).get(
                        _clean_text(entry.get("_external_ref"))
                    )
                    or {}
                )
                else 1,
                0
                if int(
                    (
                        route_state.get(
                            _clean_text(entry.get("_intake_origin")), {}
                        ).get(_clean_text(entry.get("_external_ref")))
                        or {}
                    ).get("transcript_attempt_count")
                    or 0
                )
                == 0
                else 1,
                _clean_text(
                    (
                        route_state.get(
                            _clean_text(entry.get("_intake_origin")), {}
                        ).get(_clean_text(entry.get("_external_ref")))
                        or {}
                    ).get("last_transcript_attempt_at")
                ),
                feed_order.get(
                    (
                        _clean_text(entry.get("_intake_origin")),
                        _clean_text(entry.get("_external_ref")),
                    ),
                    len(entries),
                ),
            )
        )
        selected_keys = {
            (
                _clean_text(entry.get("_intake_origin")),
                _clean_text(entry.get("_external_ref")),
            )
            for entry in pending_entries[: max(0, int(limit_per_source))]
        }
        pending_initial += len(pending_entries)
        podcast_pending_initial += sum(
            1
            for entry in pending_entries
            if _clean_text(entry.get("_intake_origin")) == "podcast"
        )

        for entry in entries:
            origin = _clean_text(entry.get("_intake_origin"))
            external_ref = _clean_text(entry.get("_external_ref"))
            entry_key = (origin, external_ref)
            is_selected = entry_key in selected_keys
            prepared: dict[str, Any] | None = None
            existing = route_state.get(origin, {}).get(external_ref)
            if existing and not is_selected:
                continue
            relevance, admissibility, rights = _configured_gate_state(source)
            if existing and _clean_text(existing.get("relevance_state")) == "rejected":
                effective_relevance = "rejected"
            elif is_selected:
                effective_relevance = relevance
            else:
                effective_relevance = "rejected" if relevance == "rejected" else "backlog"
            try:
                prepared = execution.register_and_gate(
                    _entry_envelope(source, entry, rights=rights),
                    relevance_state=effective_relevance,
                    admissibility_state=admissibility,
                    reason="configured_rss_watchlist_policy",
                    policy_name=(
                        "podcast_scheduled_intake_gate"
                        if origin == "podcast"
                        else "rss_scheduled_intake_gate"
                    ),
                    capture_kind="transcript" if origin == "podcast" else "raw",
                )
                registered += 1
                if existing is None:
                    discoveries_new += 1
                if not bool(prepared["registration"]["gate"]["duplicate_source"]):
                    registered_new += 1
                if not is_selected:
                    continue
                selected += 1
                decision = prepared["decision"]
                if decision.get("state") == "not_authorized":
                    gated_out += 1
                    if origin == "podcast":
                        record_podcast_transcript_attempt(
                            source_id=_clean_text(decision.get("source_id")),
                            entry=entry,
                            feed_url=feed_url,
                            outcome="not_authorized",
                        )
                    continue

                if origin == "podcast":
                    transcript_text = ""
                    transcript_fetch_error: str | None = None
                    existing_artifact_id = _clean_text(
                        decision.get("existing_artifact_id")
                    )
                    if existing_artifact_id:
                        transcript_text = execution.captured_text(existing_artifact_id)
                    elif _clean_text(entry.get("transcript_url")):
                        try:
                            transcript_text = _fetch_podcast_transcript(entry)
                        except Exception as exc:
                            transcript_fetch_error = type(exc).__name__
                            errors.append(
                                {
                                    "stage": "podcast_transcript_fetch_or_parse",
                                    "source_ref": external_ref,
                                    "reason": type(exc).__name__,
                                }
                            )

                    if transcript_text:
                        signal, body, filename = _build_podcast_entry(
                            source, entry, transcript_text=transcript_text
                        )
                        capture = _attach_feed_capture(
                            execution,
                            prepared,
                            text=transcript_text,
                            capture_kind="transcript",
                            signal=signal,
                            normalizer_name="podcast_feed_transcript",
                            capture_adapter=(
                                "podcast_transcript_reuse"
                                if existing_artifact_id
                                else "podcast_transcript_link"
                            ),
                        )
                        reused += int(capture["reused"])
                        captured += 1
                        captured_new += int(not capture["reused"])
                        transcript_captured += 1
                        completed_pending += 1
                        podcast_completed_pending += 1
                        record_podcast_transcript_attempt(
                            source_id=_clean_text(decision.get("source_id")),
                            entry=entry,
                            feed_url=feed_url,
                            outcome=(
                                "reused"
                                if existing_artifact_id
                                else "captured_from_declared_transcript"
                            ),
                        )
                        keep_filenames.add(filename)
                        if write_compatibility_projection:
                            path = _write_signal(
                                signals_root / filename,
                                signal,
                                f"# {signal['title']}\n\n{body}",
                            )
                            written_by_path[str(path)] = path
                        continue

                    signal, body, filename = _build_podcast_entry(source, entry)
                    raw_decision = execution.processing.processing_decision(
                        source_id=decision["source_id"],
                        discovery_id=decision["discovery_id"],
                        capture_kind="raw",
                    )
                    if raw_decision.get("existing_artifact_id") or raw_decision.get(
                        "capture_required"
                    ):
                        raw_capture = _attach_feed_capture(
                            execution,
                            {**prepared, "decision": raw_decision},
                            text=str(signal.get("raw_text") or body),
                            capture_kind="raw",
                            signal=signal,
                            normalizer_name="podcast_feed_show_notes",
                            capture_adapter="podcast_feed_show_notes",
                        )
                        reused += int(raw_capture["reused"])
                        raw_captured += 1
                        podcast_show_notes_captured += 1
                        captured_new += int(not raw_capture["reused"])
                        keep_filenames.add(filename)
                        if write_compatibility_projection:
                            path = _write_signal(
                                signals_root / filename,
                                signal,
                                f"# {signal['title']}\n\n{body}",
                            )
                            written_by_path[str(path)] = path
                    if is_credential_free_public_url(entry.get("enclosure_url")):
                        audio_candidates.append(
                            {
                                "source": source,
                                "entry": entry,
                                "prepared": prepared,
                                "family_keep": keep_filenames,
                                "feed_url": feed_url,
                                "transcript_fetch_error": transcript_fetch_error,
                            }
                        )
                    else:
                        record_podcast_transcript_attempt(
                            source_id=_clean_text(decision.get("source_id")),
                            entry=entry,
                            feed_url=feed_url,
                            outcome=(
                                "failed_declared_transcript"
                                if transcript_fetch_error
                                else "deferred_no_transcript_route"
                            ),
                            error_class=transcript_fetch_error,
                        )
                    continue

                existing_artifact_id = _clean_text(decision.get("existing_artifact_id"))
                if existing_artifact_id:
                    article_preview = {
                        "text": execution.captured_text(existing_artifact_id)
                    }
                elif decision.get("capture_required"):
                    # Deep article capture happens only after canonical duplicate,
                    # relevance, admissibility, and rights gates have passed.
                    article_url = _clean_text(entry.get("_canonical_url"))
                    article_preview = (
                        _article_preview_for_url(article_url) if article_url else {}
                    )
                else:
                    gated_out += 1
                    continue
                signal, body, filename = _build_rss_entry(
                    source, entry, article_preview=article_preview
                )
                capture = _attach_feed_capture(
                    execution,
                    prepared,
                    text=str(signal.get("raw_text") or body),
                    capture_kind="raw",
                    signal=signal,
                    normalizer_name="rss_feed_article",
                    capture_adapter="rss_article_capture",
                )
                reused += int(capture["reused"])
                captured += 1
                captured_new += int(not capture["reused"])
                raw_captured += 1
                completed_pending += 1
                keep_filenames.add(filename)
                if write_compatibility_projection:
                    path = _write_signal(
                        signals_root / filename,
                        signal,
                        f"# {signal['title']}\n\n{body}",
                    )
                    written_by_path[str(path)] = path
            except Exception as exc:
                LOGGER.exception("Canonical RSS intake failed for %s", external_ref)
                errors.append(
                    {
                        "stage": "registration_gate_capture_or_projection",
                        "source_ref": external_ref,
                        "reason": type(exc).__name__,
                    }
                )
                if origin == "podcast" and prepared is not None:
                    decision = prepared.get("decision") or {}
                    source_id = _clean_text(decision.get("source_id"))
                    if source_id:
                        record_podcast_transcript_attempt(
                            source_id=source_id,
                            entry=entry,
                            feed_url=feed_url,
                            outcome="failed",
                            error_class=type(exc).__name__,
                        )
                continue

    audio_candidates.sort(
        key=lambda item: _parse_datetime(item["entry"].get("published_at")),
        reverse=True,
    )
    audio_limit = _bounded_env_int(
        "PODCAST_AUDIO_TRANSCRIPTION_LIMIT",
        DEFAULT_PODCAST_AUDIO_TRANSCRIPTION_LIMIT,
        minimum=0,
        maximum=4,
    )
    audio_runtime_blocked = False
    attempted_audio_candidate_ids: set[int] = set()
    for candidate in audio_candidates[:audio_limit]:
        attempted_audio_candidate_ids.add(id(candidate))
        source = candidate["source"]
        entry = candidate["entry"]
        prepared = candidate["prepared"]
        external_ref = _clean_text(entry.get("_external_ref"))
        try:
            transcript_text = _transcribe_podcast_audio(entry)
            if not transcript_text:
                raise RuntimeError("podcast_audio_transcript_empty")
            signal, body, filename = _build_podcast_entry(
                source, entry, transcript_text=transcript_text
            )
            capture = _attach_feed_capture(
                execution,
                prepared,
                text=transcript_text,
                capture_kind="transcript",
                signal=signal,
                normalizer_name="podcast_feed_transcript",
                capture_adapter="podcast_audio_local_whisper",
            )
            reused += int(capture["reused"])
            captured += 1
            captured_new += int(not capture["reused"])
            transcript_captured += 1
            podcast_audio_transcribed += 1
            completed_pending += 1
            podcast_completed_pending += 1
            record_podcast_transcript_attempt(
                source_id=_clean_text(prepared["decision"].get("source_id")),
                entry=entry,
                feed_url=_clean_text(candidate.get("feed_url")),
                outcome="captured_from_audio",
            )
            candidate["family_keep"].add(filename)
            if write_compatibility_projection:
                path = _write_signal(
                    signals_root / filename,
                    signal,
                    f"# {signal['title']}\n\n{body}",
                )
                written_by_path[str(path)] = path
        except Exception as exc:
            reason = str(exc) if str(exc) == "local_media_transcription_runtime_unavailable" else type(exc).__name__
            errors.append(
                {
                    "stage": "podcast_audio_transcription",
                    "source_ref": external_ref,
                    "reason": reason,
                }
            )
            record_podcast_transcript_attempt(
                source_id=_clean_text(prepared["decision"].get("source_id")),
                entry=entry,
                feed_url=_clean_text(candidate.get("feed_url")),
                outcome="failed_audio_transcription",
                error_class=reason,
            )
            if reason == "local_media_transcription_runtime_unavailable":
                audio_runtime_blocked = True
                break

    for candidate in audio_candidates:
        if id(candidate) in attempted_audio_candidate_ids:
            continue
        record_podcast_transcript_attempt(
            source_id=_clean_text(candidate["prepared"]["decision"].get("source_id")),
            entry=candidate["entry"],
            feed_url=_clean_text(candidate.get("feed_url")),
            outcome="deferred_capacity",
        )

    if write_compatibility_projection:
        for family_pattern, keep_filenames in compatibility_families:
            _prune_source_family(signals_root, family_pattern, keep_filenames)

    backlog_remaining = max(0, pending_initial - completed_pending)
    podcast_transcript_deferred = max(
        0, podcast_pending_initial - podcast_completed_pending
    )
    if audio_runtime_blocked:
        # One bounded error already records the unavailable shared runtime;
        # this count preserves the full impact without repeating errors.
        podcast_transcript_deferred = max(
            podcast_transcript_deferred, len(audio_candidates)
        )
    disposition = _run_disposition(
        changed=registered_new + captured_new,
        errors=len(errors),
        gated_out=gated_out,
    )
    execution.record_run_receipt(
        run_kind="rss_feed",
        disposition=disposition,
        counts={
            "manifest_entries": manifest_entries,
            "unique_entries": unique_entries,
            "duplicate_entries": duplicate_entries,
            "podcast_entries": podcast_entries,
            "podcast_transcript_links": podcast_transcript_links,
            "registered": registered,
            "registered_new": registered_new,
            "discoveries_new": discoveries_new,
            "selected": selected,
            "captured": captured,
            "captured_new": captured_new,
            "raw_captured": raw_captured,
            "transcript_captured": transcript_captured,
            "podcast_show_notes_captured": podcast_show_notes_captured,
            "podcast_audio_transcribed": podcast_audio_transcribed,
            "podcast_transcript_attempts": podcast_transcript_attempts,
            "podcast_transcript_deferred": podcast_transcript_deferred,
            "backlog": backlog_remaining,
            "written": len(written_by_path),
            "reused": reused,
            "gated_out": gated_out,
            "errors": len(errors),
        },
        errors=errors,
        run_id=effective_run_id,
        provenance={
            "trigger": "local_scheduler",
            "network_mode": "permitted_feed",
            "full_feed_enumeration": True,
            "podcast_audio_transcription_limit": audio_limit,
            "compatibility_projection": write_compatibility_projection,
        },
    )
    return sorted(written_by_path.values(), key=lambda path: str(path))


def backfill_article_signal_sources(
    workspace_root: Path | None = None,
    *,
    force: bool = False,
    canonical_store: IntegratedSystemStore | None = None,
    run_id: str | None = None,
    compatibility_projection: bool = False,
) -> dict[str, Any]:
    if not compatibility_projection:
        raise RuntimeError(
            "Legacy article-signal backfill is rollback-only; "
            "set compatibility_projection=True explicitly."
        )
    resolved_root, _, _ = _workspace_paths(workspace_root)
    execution = SourceIntakeExecutionService(canonical_store or IntegratedSystemStore())
    restored: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, Any]] = []
    registered = 0
    reused = 0

    for record in load_market_signal_archive_records(resolved_root):
        if not isinstance(record, dict):
            continue
        if _clean_text(record.get("source_type")) != "article":
            continue
        if _clean_text(record.get("source_platform")) not in {"rss", "substack"}:
            continue
        source_url = _clean_text(record.get("source_url"))
        source_path = _clean_text(record.get("source_path"))
        if not source_url or not source_path:
            continue
        signal_path = resolved_root / source_path
        existing_meta = _load_existing_frontmatter(signal_path) if signal_path.exists() else {}
        existing_method = _clean_text((existing_meta.get("source_metadata") or {}).get("extraction_method"))
        if signal_path.exists() and not force and "article_preview" in existing_method:
            skipped.append(signal_path.name)
            continue

        source_metadata = existing_meta.get("source_metadata") or record.get("source_metadata") or {}
        feed_url = _clean_text(source_metadata.get("feed_url")) or source_url
        entry_id = _clean_text(source_metadata.get("entry_guid")) or source_url
        try:
            prepared = execution.register_and_gate(
                rss_discovery_envelope(
                    feed_url=feed_url,
                    entry_url=source_url,
                    entry_id=entry_id,
                    title=_clean_text(existing_meta.get("title") or record.get("title")) or None,
                    publisher=_clean_text(existing_meta.get("author") or record.get("author")) or None,
                    published_at=_clean_text(existing_meta.get("published_at") or record.get("published_at")) or None,
                    rights_state="permitted",
                    share_public_content=is_credential_free_public_url(source_url),
                ),
                relevance_state="qualified",
                admissibility_state="admissible",
                reason="previously_selected_article_backfill",
                policy_name="rss_article_backfill_gate",
                capture_kind="raw",
            )
            registered += 1
            decision = prepared["decision"]
            existing_artifact_id = _clean_text(decision.get("existing_artifact_id"))
            if existing_artifact_id:
                article_preview = {"text": execution.captured_text(existing_artifact_id)}
            elif decision.get("capture_required"):
                article_preview = _article_preview_for_url(source_url)
            else:
                skipped.append(Path(source_path).name)
                continue
            if not article_preview.get("text"):
                skipped.append(Path(source_path).name)
                continue
        except Exception as exc:
            LOGGER.exception("Canonical RSS article backfill failed for %s", source_url)
            errors.append(
                {
                    "stage": "registration_gate_or_capture",
                    "source_ref": source_url,
                    "reason": type(exc).__name__,
                }
            )
            continue

        base_entry = {
            "kind": _clean_text(existing_meta.get("kind") or record.get("kind")) or "market_signal",
            "title": _clean_text(existing_meta.get("title") or record.get("title")),
            "created_at": _clean_text(existing_meta.get("created_at") or record.get("created_at")) or datetime.now(timezone.utc).isoformat(),
            "published_at": _clean_text(existing_meta.get("published_at") or record.get("published_at")) or datetime.now(timezone.utc).isoformat(),
            "source_platform": _clean_text(existing_meta.get("source_platform") or record.get("source_platform")),
            "source_type": _clean_text(existing_meta.get("source_type") or record.get("source_type")) or "article",
            "source_url": source_url,
            "author": _clean_text(existing_meta.get("author") or record.get("author")),
            "role_alignment": _clean_text(existing_meta.get("role_alignment") or record.get("role_alignment")) or "market_signal",
            "priority_lane": _clean_text(existing_meta.get("priority_lane") or record.get("priority_lane")),
            "summary": _clean_text(existing_meta.get("summary") or record.get("summary")),
            "why_it_matters": _clean_text(existing_meta.get("why_it_matters") or record.get("why_it_matters")),
            "watchlist_matches": existing_meta.get("watchlist_matches") or record.get("watchlist_matches") or [],
            "topics": existing_meta.get("topics") or record.get("topics") or [],
            "headline_candidates": existing_meta.get("headline_candidates") or record.get("headline_candidates") or [],
            "core_claim": _clean_text(existing_meta.get("core_claim") or record.get("core_claim")),
            "supporting_claims": existing_meta.get("supporting_claims") or record.get("supporting_claims") or [],
            "raw_text": _clean_multiline_text(existing_meta.get("raw_text") or record.get("body_text")),
            "source_metadata": existing_meta.get("source_metadata") or record.get("source_metadata") or {},
            "engagement": existing_meta.get("engagement") or record.get("engagement") or {},
        }
        entry, body = _article_entry_from_existing(base_entry, article_preview=article_preview)
        try:
            capture = execution.attach_or_reuse_text(
                prepared,
                text=str(entry.get("raw_text") or body),
                capture_kind="raw",
                metadata={"capture_adapter": "rss_article_backfill", "capture_version": "1.0.0"},
            )
            reused += int(capture["reused"])
            entry["source_metadata"] = {
                **dict(entry.get("source_metadata") or {}),
                "canonical_source_id": prepared["decision"]["source_id"],
                "canonical_capture_artifact_id": capture["artifact_id"],
            }
        except Exception as exc:
            LOGGER.exception("Canonical RSS article capture failed for %s", source_url)
            errors.append(
                {
                    "stage": "canonical_capture",
                    "source_ref": source_url,
                    "reason": type(exc).__name__,
                }
            )
            continue
        _write_signal(signal_path, entry, f"# {entry['title']}\n\n{body}")
        if signal_path.exists() and source_path:
            if _clean_text(record.get("source_path")) and not existing_meta:
                restored.append(signal_path.name)
            else:
                updated.append(signal_path.name)

    changed = len(restored) + len(updated)
    disposition = _run_disposition(changed=changed, errors=len(errors), gated_out=len(skipped))
    receipt = execution.record_run_receipt(
        run_kind="rss_article_backfill",
        disposition=disposition,
        counts={
            "registered": registered,
            "restored": len(restored),
            "updated": len(updated),
            "reused": reused,
            "skipped": len(skipped),
            "errors": len(errors),
        },
        errors=errors,
        run_id=run_id,
        provenance={"trigger": "local_backfill", "force": force},
    )
    return {
        "restored": restored,
        "restored_count": len(restored),
        "updated": updated,
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "receipt": {"event_id": receipt["event_id"], "disposition": disposition},
    }
