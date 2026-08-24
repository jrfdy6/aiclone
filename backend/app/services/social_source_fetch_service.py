from __future__ import annotations

import hashlib
import logging
import re
import sys
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
from app.services.source_intake_adapter_service import reddit_discovery_envelope, rss_discovery_envelope
from app.services.source_intake_execution_service import SourceIntakeExecutionService
from app.services.source_sharing_policy_service import is_credential_free_public_url
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
                "category": " ".join(
                    _clean_text(child.attrib.get("term") or "".join(child.itertext()))
                    for child in list(entry)
                    if _local_name(child.tag) == "category"
                ),
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
    written: list[Path] = []
    registered = 0
    reused = 0
    captured = 0
    gated_out = 0
    errors: list[dict[str, Any]] = []

    for source in watchlist.get("rss_sources", []):
        label = _clean_text(source.get("label")) or "rss-feed"
        family_pattern = f"*__rss__{_slugify(label)}__*.md"
        keep_filenames: set[str] = set()
        try:
            raw = _http_get(_clean_text(source.get("url")), accept="application/rss+xml, application/atom+xml, text/xml, application/xml")
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

        entries = _iter_feed_entries(root)
        for entry in entries[:limit_per_source]:
            if not _clean_text(entry.get("title")):
                continue
            entry_url = _clean_text(entry.get("link"))
            entry_id = _clean_text(entry.get("guid")) or entry_url or _clean_text(entry.get("title"))
            relevance, admissibility, rights = _configured_gate_state(source)
            try:
                prepared = execution.register_and_gate(
                    rss_discovery_envelope(
                        feed_url=_clean_text(source.get("url")),
                        entry_url=entry_url or None,
                        entry_id=entry_id,
                        title=_clean_text(entry.get("title")) or None,
                        publisher=_clean_text(entry.get("author")) or label,
                        published_at=_clean_text(entry.get("published_at")) or None,
                        rights_state=rights,
                        share_public_content=(
                            rights == "permitted"
                            and is_credential_free_public_url(entry_url)
                        ),
                    ),
                    relevance_state=relevance,
                    admissibility_state=admissibility,
                    reason="configured_rss_watchlist_policy",
                    policy_name="rss_scheduled_intake_gate",
                    capture_kind="raw",
                )
                registered += 1
                decision = prepared["decision"]
                existing_artifact_id = _clean_text(decision.get("existing_artifact_id"))
                if existing_artifact_id:
                    article_preview = {"text": execution.captured_text(existing_artifact_id)}
                elif decision.get("capture_required"):
                    # Deep article capture happens only after canonical duplicate,
                    # relevance, admissibility, and rights gates have passed.
                    article_preview = _article_preview_for_url(entry_url)
                else:
                    gated_out += 1
                    continue
                signal, body, filename = _build_rss_entry(source, entry, article_preview=article_preview)
                capture = execution.attach_or_reuse_text(
                    prepared,
                    text=str(signal.get("raw_text") or body),
                    capture_kind="raw",
                    metadata={"capture_adapter": "rss_article_capture", "capture_version": "1.0.0"},
                )
                canonical_source_id = _clean_text(capture.get("source_id"))
                canonical_artifact_id = _clean_text(capture.get("artifact_id"))
                signal["source_metadata"] = {
                    **dict(signal.get("source_metadata") or {}),
                    "canonical_source_id": canonical_source_id,
                    "canonical_capture_artifact_id": canonical_artifact_id,
                }
                SourceFeedSignalService(execution.store).record(
                    source_id=canonical_source_id,
                    artifact_id=canonical_artifact_id,
                    signal=signal,
                    normalizer_name="rss_feed_article",
                )
                reused += int(capture["reused"])
                captured += 1
            except Exception as exc:
                LOGGER.exception("Canonical RSS intake failed for %s", entry_url or entry_id)
                errors.append(
                    {
                        "stage": "registration_gate_capture_or_projection",
                        "source_ref": entry_url or entry_id,
                        "reason": type(exc).__name__,
                    }
                )
                continue
            keep_filenames.add(filename)
            if write_compatibility_projection:
                written.append(_write_signal(signals_root / filename, signal, f"# {signal['title']}\n\n{body}"))
        if write_compatibility_projection:
            _prune_source_family(signals_root, family_pattern, keep_filenames)
    disposition = _run_disposition(changed=max(0, captured - reused), errors=len(errors), gated_out=gated_out)
    execution.record_run_receipt(
        run_kind="rss_feed",
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
