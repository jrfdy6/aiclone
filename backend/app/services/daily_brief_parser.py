from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional


_HEADING_RE = re.compile(r"^(?:#{1,6}\s*)?Morning Daily Brief\s*[—-]\s*(.+?)\s*$", re.IGNORECASE)
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%A, %b %d",
    "%a, %b %d",
    "%A, %B %d, %Y",
    "%a, %B %d, %Y",
)


@dataclass
class ParsedBrief:
    brief_date: date
    title: str
    content_markdown: str
    summary: str
    metadata: dict


def _parse_date(raw: str, *, fallback_year: Optional[int] = None) -> Optional[date]:
    cleaned = raw.strip()
    if not cleaned:
        return None

    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            year = parsed.year
            if year == 1900 and fallback_year is not None:
                year = fallback_year
            return date(year, parsed.month, parsed.day)
        except ValueError:
            continue

    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", cleaned)
    if iso_match:
        return date.fromisoformat(iso_match.group(1))
    return None


def _derive_summary(lines: Iterable[str]) -> str:
    bullet_lines = [line.strip().lstrip("-").strip() for line in lines if line.strip().startswith("-")]
    if bullet_lines:
        return " ".join(bullet_lines[:2])[:280]

    text_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return " ".join(text_lines[:2])[:280]


def parse_briefs_markdown(raw: str, *, source_ref: Optional[str] = None, fallback_year: Optional[int] = None) -> List[ParsedBrief]:
    entries: List[ParsedBrief] = []
    current_title: Optional[str] = None
    current_date: Optional[date] = None
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_title, current_date, current_lines
        if not current_title or not current_date:
            current_title = None
            current_date = None
            current_lines = []
            return

        body = "\n".join(current_lines).strip()
        if not body:
            body = current_title
        summary = _derive_summary(current_lines or [current_title])
        entries.append(
            ParsedBrief(
                brief_date=current_date,
                title=current_title,
                content_markdown=body,
                summary=summary,
                metadata={"source_ref": source_ref} if source_ref else {},
            )
        )
        current_title = None
        current_date = None
        current_lines = []

    for line in raw.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            flush()
            title_suffix = match.group(1).strip()
            parsed_date = _parse_date(title_suffix, fallback_year=fallback_year)
            if not parsed_date:
                continue
            current_title = f"Morning Daily Brief — {parsed_date.isoformat()}"
            current_date = parsed_date
            current_lines = [current_title, ""]
            continue

        if current_title:
            current_lines.append(line.rstrip())

    flush()
    return entries
