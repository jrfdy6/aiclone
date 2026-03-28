from __future__ import annotations

import hashlib
import json
import logging
import re
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

from app.services.social_feed_builder_service import discover_linkedin_workspace_root

LOGGER = logging.getLogger(__name__)
USER_AGENT = "AICloneSocialFeed/1.0 (+https://aiclone-frontend-production.up.railway.app)"
DEFAULT_HTTP_TIMEOUT = 12
DEFAULT_REDDIT_LIMIT = 2
DEFAULT_RSS_LIMIT = 2

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
            "name": "AI-native operators in education",
            "platform": "linkedin",
            "relationship": "followed",
            "profile_url": "https://www.linkedin.com/in/ai-native-operator",
            "reason": "Role-safe intrapreneur language and education implementation signals",
            "lenses": ["current-role", "program-leadership", "ai"],
            "priority_weight": 0.9,
        },
        {
            "name": "GTM / revenue / growth operators",
            "platform": "linkedin",
            "relationship": "connected",
            "profile_url": "https://www.linkedin.com/in/gtm-operator",
            "reason": "Market-development, outreach, and trust-building language",
            "lenses": ["admissions", "entrepreneurship"],
            "priority_weight": 0.85,
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
    root = workspace_root or discover_linkedin_workspace_root()
    research_root = root / "research"
    signals_root = research_root / "market_signals"
    watchlist_path = research_root / "watchlists.yaml"
    return root, signals_root, watchlist_path


def ensure_watchlist(workspace_root: Path | None = None) -> dict[str, Any]:
    _, signals_root, watchlist_path = _workspace_paths(workspace_root)
    signals_root.mkdir(parents=True, exist_ok=True)
    if not watchlist_path.exists():
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


def _write_signal(path: Path, entry: dict[str, Any], body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.dump(entry, sort_keys=False, allow_unicode=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body.strip()}\n", encoding="utf-8")
    return path


def _clear_source_family(signals_root: Path, pattern: str) -> None:
    for candidate in signals_root.glob(pattern):
        candidate.unlink(missing_ok=True)


def _reddit_url(subreddit: str, limit: int) -> str:
    clean = subreddit.replace("r/", "").strip()
    return f"https://www.reddit.com/r/{clean}/hot.json?limit={limit}&raw_json=1"


def _build_reddit_entry(source: dict[str, Any], post: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    subreddit = source.get("subreddit", "reddit").replace("r/", "").strip()
    title = _clean_text(post.get("title")) or f"r/{subreddit} post"
    selftext = _clean_text(post.get("selftext"))
    external_url = _clean_text(post.get("url_overridden_by_dest") or post.get("url"))
    permalink = _clean_text(post.get("permalink"))
    source_url = f"https://www.reddit.com{permalink}" if permalink else external_url
    published_at = datetime.fromtimestamp(float(post.get("created_utc", 0) or 0), tz=timezone.utc).isoformat()
    purpose = _clean_text(source.get("purpose")) or "Practitioner signal"
    summary_seed = selftext or title
    summary = _truncate(summary_seed, 320)
    raw_parts = [title]
    if selftext:
        raw_parts.append(selftext)
    elif external_url and external_url != source_url:
        raw_parts.append(f"External link: {external_url}")
    body = "\n\n".join(part for part in raw_parts if part).strip()
    if not body:
        body = title

    entry = {
        "kind": "market_signal",
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_at": published_at,
        "source_platform": "reddit",
        "source_type": "post",
        "source_url": source_url,
        "author": _clean_text(post.get("author")) or "reddit",
        "role_alignment": "market_signal",
        "priority_lane": _clean_text(source.get("priority_lane")) or "current-role",
        "summary": summary,
        "why_it_matters": purpose,
        "watchlist_matches": ["reddit", f"r/{subreddit}"],
        "topics": [purpose],
        "headline_candidates": [title],
        "core_claim": title,
        "supporting_claims": [_truncate(selftext, 240)] if selftext else [],
        "raw_text": body,
        "engagement": {
            "likes": int(post.get("score") or 0),
            "comments": int(post.get("num_comments") or 0),
            "shares": 0,
        },
        "source_metadata": {
            "extraction_method": "reddit_json",
            "subreddit": subreddit,
            "external_url": external_url,
            "post_id": _clean_text(post.get("id")),
        },
    }
    filename = f"{published_at[:10]}__reddit__{_slugify(subreddit)}__{_slugify(_clean_text(post.get('id')) or title)[:80]}.md"
    return entry, body, filename


def fetch_reddit_signals(workspace_root: Path | None = None, *, limit_per_source: int = DEFAULT_REDDIT_LIMIT) -> list[Path]:
    _, signals_root, _ = _workspace_paths(workspace_root)
    watchlist = ensure_watchlist(workspace_root)
    written: list[Path] = []

    for source in watchlist.get("reddit_sources", []):
        subreddit = _clean_text(source.get("subreddit"))
        if not subreddit:
            continue
        slug = _slugify(subreddit.replace("r/", ""))
        _clear_source_family(signals_root, f"*__reddit__{slug}__*.md")
        try:
            payload = json.loads(_http_get(_reddit_url(subreddit, limit_per_source), accept="application/json"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            LOGGER.warning("Skipping reddit source %s: %s", subreddit, exc)
            continue

        posts = (((payload or {}).get("data") or {}).get("children") or [])
        for post_wrapper in posts[:limit_per_source]:
            data = post_wrapper.get("data") or {}
            if data.get("stickied") or not _clean_text(data.get("title")):
                continue
            entry, body, filename = _build_reddit_entry(source, data)
            written.append(_write_signal(signals_root / filename, entry, f"# {entry['title']}\n\n{body}"))
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


def _build_rss_entry(source: dict[str, Any], entry: dict[str, str]) -> tuple[dict[str, Any], str, str]:
    title = _clean_text(entry.get("title")) or _clean_text(source.get("label")) or "RSS signal"
    summary = _truncate(_clean_text(entry.get("summary")) or title, 320)
    source_url = _clean_text(entry.get("link")) or _clean_text(source.get("url"))
    published_at = _parse_datetime(entry.get("published_at"))
    label = _clean_text(source.get("label")) or "rss-feed"
    purpose = _clean_text(source.get("purpose")) or label
    raw_text = "\n\n".join(part for part in [title, summary] if part).strip()
    guid = _clean_text(entry.get("guid")) or source_url or title

    signal = {
        "kind": "market_signal",
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_at": published_at,
        "source_platform": _infer_platform(source),
        "source_type": "article",
        "source_url": source_url,
        "author": _clean_text(entry.get("author")) or label,
        "role_alignment": "market_signal",
        "priority_lane": _clean_text(source.get("priority_lane")) or "current-role",
        "summary": summary,
        "why_it_matters": purpose,
        "watchlist_matches": ["rss", label],
        "topics": [purpose],
        "headline_candidates": [title],
        "core_claim": title,
        "supporting_claims": [summary] if summary and summary.lower() != title.lower() else [],
        "raw_text": raw_text,
        "source_metadata": {
            "extraction_method": "rss_feed",
            "feed_label": label,
            "feed_url": _clean_text(source.get("url")),
            "entry_guid": guid,
        },
    }
    identity = _slugify(guid)[:80] or hashlib.sha1(guid.encode("utf-8")).hexdigest()[:12]
    filename = f"{published_at[:10]}__rss__{_slugify(label)}__{identity}.md"
    return signal, raw_text, filename


def fetch_rss_signals(workspace_root: Path | None = None, *, limit_per_source: int = DEFAULT_RSS_LIMIT) -> list[Path]:
    _, signals_root, _ = _workspace_paths(workspace_root)
    watchlist = ensure_watchlist(workspace_root)
    written: list[Path] = []

    for source in watchlist.get("rss_sources", []):
        label = _clean_text(source.get("label")) or "rss-feed"
        _clear_source_family(signals_root, f"*__rss__{_slugify(label)}__*.md")
        try:
            raw = _http_get(_clean_text(source.get("url")), accept="application/rss+xml, application/atom+xml, text/xml, application/xml")
            root = ET.fromstring(raw)
        except (HTTPError, URLError, TimeoutError, ET.ParseError) as exc:
            LOGGER.warning("Skipping RSS source %s: %s", label, exc)
            continue

        entries = _iter_feed_entries(root)
        for entry in entries[:limit_per_source]:
            if not _clean_text(entry.get("title")):
                continue
            signal, body, filename = _build_rss_entry(source, entry)
            written.append(_write_signal(signals_root / filename, signal, f"# {signal['title']}\n\n{body}"))
    return written
