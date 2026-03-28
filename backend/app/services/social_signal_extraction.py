from __future__ import annotations

import json
import re
from typing import Any

import certifi
import requests
from bs4 import BeautifulSoup

from app.services.social_signal_utils import normalize_inline_text, normalize_multiline_text

STRUCTURED_POST_TYPES = {
    "socialmediaposting",
    "article",
    "blogposting",
    "newsarticle",
    "webpage",
}

BOILERPLATE_LINES = {
    "skip to search",
    "skip to main content",
    "keyboard shortcuts",
    "close jump menu",
    "home",
    "my network",
    "jobs",
    "messaging",
    "notifications",
    "for business",
    "learning",
    "like",
    "comment",
    "repost",
    "send",
    "follow",
    "add a comment…",
    "add a comment...",
    "most relevant",
    "about",
    "accessibility",
    "help center",
    "privacy & terms",
    "ad choices",
    "advertising",
    "business services",
    "get the linkedin app",
    "more",
    "status is online",
    "compose message",
    "open emoji keyboard",
    "open send options",
    "register now",
    "download now",
    "sounds great",
    "sounds good",
    "will do",
    "remove reaction",
    "great insight!",
    "report this post",
}

BOILERPLATE_PREFIXES = (
    "view ",
    "open ",
    "scroll ",
    "reply to conversation",
    "attach ",
    "close your conversation",
    "current selected sort order",
    "linkedin corporation",
)


def looks_like_boilerplate(line: str) -> bool:
    normalized = normalize_inline_text(line)
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered in BOILERPLATE_LINES:
        return True
    if any(lowered.startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
        return True
    if lowered.startswith("view ") and (" profile" in lowered or " graphic link" in lowered):
        return True
    if lowered.startswith("photo of "):
        return True
    if lowered.endswith(" notifications total"):
        return True
    if " new " in lowered and lowered.endswith(" notifications"):
        return True
    if "visible to anyone on or off linkedin" in lowered:
        return True
    if re.fullmatch(r"[+\d\s]+", normalized):
        return True
    return False


def extract_author_name(value: Any) -> str:
    if isinstance(value, str):
        return normalize_inline_text(value)
    if isinstance(value, list):
        for item in value:
            author = extract_author_name(item)
            if author:
                return author
        return ""
    if isinstance(value, dict):
        return normalize_inline_text(value.get("name"))
    return ""


def flatten_json_ld(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            nodes.extend(flatten_json_ld(item))
        return nodes
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                nodes.extend(flatten_json_ld(item))
        nodes.append(payload)
    return nodes


class SocialSignalExtractionService:
    def _meta_content(self, soup: BeautifulSoup, *, name: str | None = None, property_name: str | None = None) -> str:
        if property_name:
            tag = soup.find("meta", attrs={"property": property_name})
            if tag and tag.get("content"):
                return normalize_inline_text(tag.get("content"))
        if name:
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return normalize_inline_text(tag.get("content"))
        return ""

    def _extract_json_ld_preview(self, soup: BeautifulSoup) -> dict[str, str]:
        preview = {"title": "", "text": "", "author": ""}
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for node in flatten_json_ld(payload):
                raw_types = node.get("@type")
                node_types = raw_types if isinstance(raw_types, list) else [raw_types]
                normalized_types = {normalize_inline_text(node_type).lower() for node_type in node_types if node_type}
                if not normalized_types.intersection(STRUCTURED_POST_TYPES):
                    continue

                title = normalize_inline_text(node.get("headline")) or normalize_inline_text(node.get("name"))
                author = extract_author_name(node.get("author"))
                text = normalize_multiline_text(
                    node.get("articleBody") or node.get("text") or node.get("description")
                )
                if title and not preview["title"]:
                    preview["title"] = title
                if author and not preview["author"]:
                    preview["author"] = author
                if text:
                    preview["text"] = text
                    return preview
        return preview

    def _extract_meta_preview(self, soup: BeautifulSoup) -> dict[str, str]:
        title = (
            self._meta_content(soup, property_name="og:title")
            or self._meta_content(soup, name="twitter:title")
            or normalize_inline_text(soup.title.string if soup.title and soup.title.string else "")
        )
        text = (
            self._meta_content(soup, property_name="og:description")
            or self._meta_content(soup, name="twitter:description")
            or self._meta_content(soup, name="description")
        )
        author = self._meta_content(soup, name="author")
        if not author and " | " in title:
            author = normalize_inline_text(title.split(" | ")[-1])
        return {
            "title": title,
            "text": normalize_multiline_text(text),
            "author": author,
        }

    def _extract_body_preview(self, soup: BeautifulSoup) -> dict[str, str]:
        for tag_name in ["script", "style", "noscript", "svg", "header", "footer", "nav", "aside", "form"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        blocks = (
            soup.find("article")
            or soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.body
            or soup
        )
        raw_lines = [node.get_text(" ", strip=True) for node in blocks.find_all(["p", "li", "div"]) if node.get_text(strip=True)]

        cleaned_lines: list[str] = []
        seen: set[str] = set()
        for line in raw_lines:
            normalized = normalize_inline_text(line)
            lowered = normalized.lower()
            if looks_like_boilerplate(normalized):
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned_lines.append(normalized)

        text = "\n\n".join(cleaned_lines[:12]).strip()
        return {
            "title": cleaned_lines[0][:120] if cleaned_lines else "",
            "text": text,
            "author": "",
        }

    def extract_preview_payload(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        preview = self._extract_json_ld_preview(soup)
        if preview["text"]:
            return preview

        meta_preview = self._extract_meta_preview(soup)
        if meta_preview["text"]:
            return meta_preview

        return self._extract_body_preview(soup)

    def fetch_url_preview(self, url: str) -> dict[str, str]:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 AICloneSocialFeedIngest/1.0"},
            verify=certifi.where(),
        )
        response.raise_for_status()
        return self.extract_preview_payload(response.text)


social_signal_extraction_service = SocialSignalExtractionService()
