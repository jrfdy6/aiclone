#!/usr/bin/env python3
"""Verify that the repository's documentation points to one current authority."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import unquote, urlsplit


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_OF_TRUTH = "SOURCE_OF_TRUTH.md"

REQUIRED_CANONICAL_FILES = (
    SOURCE_OF_TRUTH,
    "CODEX_STARTUP.md",
    "AGENTS.md",
    "IDENTITY.md",
    "CHARTER.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "memory/persistent_state.md",
    "memory/roadmap.md",
    "SOPs/_index.md",
)

STARTUP_ORDER_SECTIONS = {
    SOURCE_OF_TRUTH: ("mandatory read order",),
    "CODEX_STARTUP.md": ("first read order", "mandatory read order"),
    "AGENTS.md": ("startup snapshot", "startup order", "read order"),
}

SOURCE_BACKLINK_FILES = (
    "README.md",
    "AGENT_BOOT.md",
    "MEMORY.md",
    "memory/roadmap.md",
    "LEARNINGS.md",
    "doc-updates.md",
    "BOOTSTRAP.md",
    "CUSTOMGPT_INSTRUCTIONS.md",
    "START_FRONTEND_PROMPT.md",
    "frontend/README_ENV_SYNC.md",
    "frontend/README_TESTING.md",
    "automations/README.md",
    "knowledge/source-intelligence/README.md",
)

# These are the system-level maps that can most easily become a competing
# source of truth. The retired runner map stays in this set because its redirect
# to the active authority is a safety boundary, not an active-runtime claim.
KEY_ARCHITECTURE_DOCS = (
    "docs/aiclone_system_architecture.md",
    "docs/aiclone_brain_architecture.md",
    "docs/system_cohesion_contract.md",
    "docs/brain_workspace_exchange_protocol.md",
    "docs/brain_truth_lanes_and_promotion_flow.md",
    "docs/brain_canonical_memory_sync_contract.md",
    "docs/codex_runner_schema.md",
    "docs/codex_local_agent_runner_architecture.md",
    "docs/chronicle_pm_promotion_boundary.md",
    "docs/source_intelligence_contract.md",
    "docs/fallback_policy_contract.md",
)

ROADMAP_EXCLUDED_PARTS = frozenset({".git", "archive", "downloads", "node_modules", "runtime_snapshots"})

_ORDERED_LIST_RE = re.compile(r"^\s*\d+[.)]\s+(?P<body>.+?)\s*$")
_HEADING_RE = re.compile(r"^\s{0,3}(?P<marks>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_REFERENCE_LINK_RE = re.compile(
    r"^\s{0,3}\[[^\]]+\]:\s*(?P<target><[^>\n]+>|\S+)",
    flags=re.MULTILINE,
)
_CANONICAL_TOKEN_RE = re.compile(
    "|".join(re.escape(path) for path in REQUIRED_CANONICAL_FILES),
    flags=re.IGNORECASE,
)
_README_POSITIVE_CLAIMS = (
    re.compile(
        r"\b(?:this\s+)?readme(?:\.md)?\b\s+(?:is|remains|serves\s+as|acts\s+as)\s+"
        r"[^.\n]{0,40}\b(?:(?<!non-)canonical\b|source\s+of\s+truth\b|authoritative\b|binding\s+authority\b)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:canonical\s+(?:source|authority)|source\s+of\s+truth|authoritative\s+source)\b"
        r"[^.\n]{0,100}\b(?:is|:)\s+(?:this\s+)?readme(?:\.md)?\b",
        flags=re.IGNORECASE,
    ),
)


def _read_text(root: Path, relative_path: str) -> str | None:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _mask_markdown_code(text: str) -> str:
    """Mask fenced and inline code while preserving offsets and newlines."""

    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0

    for line in text.splitlines(keepends=True):
        content = line[:-1] if line.endswith("\n") else line
        newline = "\n" if line.endswith("\n") else ""
        stripped = content.lstrip(" ")
        indent = len(content) - len(stripped)
        marker = re.match(r"(`{3,}|~{3,})", stripped) if indent <= 3 else None

        if fence_character is not None:
            output.append(" " * len(content) + newline)
            if marker and marker.group(1)[0] == fence_character and len(marker.group(1)) >= fence_length:
                fence_character = None
                fence_length = 0
            continue

        if marker:
            fence_character = marker.group(1)[0]
            fence_length = len(marker.group(1))
            output.append(" " * len(content) + newline)
            continue

        masked = list(content)
        cursor = 0
        while cursor < len(content):
            if content[cursor] != "`":
                cursor += 1
                continue
            run_end = cursor
            while run_end < len(content) and content[run_end] == "`":
                run_end += 1
            delimiter = content[cursor:run_end]
            closing = content.find(delimiter, run_end)
            if closing < 0:
                cursor = run_end
                continue
            for index in range(cursor, closing + len(delimiter)):
                masked[index] = " "
            cursor = closing + len(delimiter)
        output.append("".join(masked) + newline)

    return "".join(output)


def _destination_from_parentheses(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("<"):
        closing = value.find(">", 1)
        return value[1:closing] if closing >= 0 else value[1:]

    # Markdown permits a quoted title after a whitespace-delimited destination.
    # An unescaped space is not valid inside an unbracketed destination.
    match = re.match(r"(?P<target>(?:\\.|[^\s])+)", value)
    return match.group("target") if match else ""


def _inline_markdown_links(masked_text: str) -> Iterator[tuple[str, int]]:
    cursor = 0
    length = len(masked_text)
    while cursor < length:
        open_bracket = masked_text.find("[", cursor)
        if open_bracket < 0:
            return

        close_bracket = open_bracket + 1
        while close_bracket < length:
            if masked_text[close_bracket] == "\\":
                close_bracket += 2
                continue
            if masked_text[close_bracket] == "]":
                break
            close_bracket += 1
        if close_bracket >= length or close_bracket + 1 >= length or masked_text[close_bracket + 1] != "(":
            cursor = open_bracket + 1
            continue

        depth = 1
        value_start = close_bracket + 2
        position = value_start
        while position < length and depth:
            character = masked_text[position]
            if character == "\\":
                position += 2
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            position += 1
        if depth:
            cursor = close_bracket + 1
            continue

        destination = _destination_from_parentheses(masked_text[value_start : position - 1])
        if destination:
            yield destination, open_bracket
        cursor = position


def markdown_links(text: str) -> list[tuple[str, int]]:
    """Return Markdown link destinations with their zero-based source offsets."""

    masked = _mask_markdown_code(text)
    links = list(_inline_markdown_links(masked))
    links.extend((match.group("target").strip("<>"), match.start()) for match in _REFERENCE_LINK_RE.finditer(masked))
    links.sort(key=lambda item: item[1])
    return links


def _local_link_target(root: Path, source_path: str, destination: str) -> tuple[str, Path, bool] | None:
    raw_destination = destination.replace("\\(", "(").replace("\\)", ")")
    parsed = urlsplit(raw_destination)
    if parsed.scheme or parsed.netloc:
        return None

    decoded_path = unquote(parsed.path).strip()
    if not decoded_path:
        # Anchor-only links do not name a repository file.
        return None

    if decoded_path.startswith("/"):
        filesystem_prefixes = ("/Users/", "/home/", "/private/", "/tmp/", "/var/", "/opt/")
        if (
            decoded_path.startswith(filesystem_prefixes)
            or decoded_path == root.as_posix()
            or decoded_path.startswith(f"{root.as_posix()}/")
        ):
            return decoded_path, Path(decoded_path).resolve(), True
        # Root-relative application routes such as /ops are not repository files.
        return None

    source = root / source_path
    candidate = (source.parent / decoded_path).resolve()
    return decoded_path, candidate, False


def _relative_to_root(root: Path, path: Path) -> str | None:
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _find_section(text: str, accepted_titles: Iterable[str]) -> str | None:
    accepted = {title.casefold() for title in accepted_titles}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = _HEADING_RE.match(line)
        if not heading or heading.group("title").strip().casefold() not in accepted:
            continue
        level = len(heading.group("marks"))
        section_lines: list[str] = []
        for candidate in lines[index + 1 :]:
            next_heading = _HEADING_RE.match(candidate)
            if next_heading and len(next_heading.group("marks")) <= level:
                break
            section_lines.append(candidate)
        return "\n".join(section_lines)
    return None


def _startup_order_defect(path: str, text: str) -> dict[str, Any] | None:
    section = _find_section(text, STARTUP_ORDER_SECTIONS[path])
    if section is None:
        return {
            "code": "startup_order_section_missing",
            "path": path,
            "detail": "No recognized startup/read-order section was found.",
        }

    first_entry = next(
        (match for line in section.splitlines() if (match := _ORDERED_LIST_RE.match(line))),
        None,
    )
    if first_entry is None:
        return {
            "code": "startup_order_missing",
            "path": path,
            "detail": "The startup/read-order section has no ordered entries.",
        }

    body = first_entry.group("body")
    first_token = _CANONICAL_TOKEN_RE.search(body)
    if first_token is None or first_token.group(0).casefold() != SOURCE_OF_TRUTH.casefold():
        return {
            "code": "source_of_truth_not_first",
            "path": path,
            "detail": "The first startup/read-order entry must begin with SOURCE_OF_TRUTH.md.",
        }
    return None


def _has_backlink(root: Path, path: str, text: str, expected_path: str) -> bool:
    expected = (root / expected_path).resolve()
    for destination, _ in markdown_links(text):
        local_target = _local_link_target(root, path, destination)
        if local_target is not None and not local_target[2] and local_target[1] == expected:
            return True
    return False


def _readme_canonical_claim_lines(text: str) -> list[int]:
    claims: list[int] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = re.sub(r"[*_`]+", "", raw_line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        if re.search(r"\b(?:not|never|no\s+longer|non[- ]canonical|subordinate)\b", line, flags=re.IGNORECASE):
            continue
        if any(pattern.search(line) for pattern in _README_POSITIVE_CLAIMS):
            claims.append(line_number)
    return claims


def verify_documentation_truth(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    defects: list[dict[str, Any]] = []
    text_by_path: dict[str, str] = {}

    required_paths = tuple(dict.fromkeys((*REQUIRED_CANONICAL_FILES, *SOURCE_BACKLINK_FILES)))
    for path in required_paths:
        absolute_path = root / path
        if not absolute_path.is_file():
            defects.append({"code": "missing_required_file", "path": path})
            continue
        text = _read_text(root, path)
        if text is None:
            defects.append({"code": "unreadable_document", "path": path})
            continue
        text_by_path[path] = text

    for path in KEY_ARCHITECTURE_DOCS:
        absolute_path = root / path
        if not absolute_path.is_file():
            defects.append({"code": "missing_key_architecture_doc", "path": path})
            continue
        text = _read_text(root, path)
        if text is None:
            defects.append({"code": "unreadable_document", "path": path})
            continue
        text_by_path[path] = text

    sop_paths = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "SOPs").rglob("*.md")
        if path.is_file()
    ) if (root / "SOPs").is_dir() else []
    for path in sop_paths:
        if path in text_by_path:
            continue
        text = _read_text(root, path)
        if text is None:
            defects.append({"code": "unreadable_document", "path": path})
            continue
        text_by_path[path] = text

    roadmap_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.md")
        if path.is_file()
        and "roadmap" in path.name.casefold()
        and not any(part.casefold() in ROADMAP_EXCLUDED_PARTS for part in path.relative_to(root).parts)
    )
    for path in roadmap_paths:
        if path in text_by_path:
            continue
        text = _read_text(root, path)
        if text is None:
            defects.append({"code": "unreadable_document", "path": path})
            continue
        text_by_path[path] = text

    for path in STARTUP_ORDER_SECTIONS:
        text = text_by_path.get(path)
        if text is None:
            continue
        defect = _startup_order_defect(path, text)
        if defect is not None:
            defects.append(defect)

    source_backlink_paths = tuple(dict.fromkeys((*SOURCE_BACKLINK_FILES, *sop_paths, *KEY_ARCHITECTURE_DOCS, *roadmap_paths)))
    for path in source_backlink_paths:
        text = text_by_path.get(path)
        if text is None:
            continue
        if not _has_backlink(root, path, text, SOURCE_OF_TRUTH):
            defects.append(
                {
                    "code": "missing_source_of_truth_backlink",
                    "path": path,
                    "target": SOURCE_OF_TRUTH,
                }
            )

    for path in sop_paths:
        if path == "SOPs/_index.md":
            continue
        text = text_by_path.get(path)
        if text is None:
            continue
        if not _has_backlink(root, path, text, "SOPs/_index.md"):
            defects.append(
                {
                    "code": "missing_sop_index_backlink",
                    "path": path,
                    "target": "SOPs/_index.md",
                }
            )

    for path in roadmap_paths:
        if path == "memory/roadmap.md":
            continue
        text = text_by_path.get(path)
        if text is None:
            continue
        if not _has_backlink(root, path, text, "memory/roadmap.md"):
            defects.append(
                {
                    "code": "missing_portfolio_roadmap_backlink",
                    "path": path,
                    "target": "memory/roadmap.md",
                }
            )

    readme_text = text_by_path.get("README.md")
    if readme_text is not None:
        for line in _readme_canonical_claim_lines(readme_text):
            defects.append(
                {
                    "code": "readme_claims_canonical",
                    "path": "README.md",
                    "line": line,
                    "detail": "README.md must defer to SOURCE_OF_TRUTH.md.",
                }
            )

    checked_link_count = 0
    link_documents = tuple(sorted(text_by_path))
    for path in link_documents:
        text = text_by_path[path]
        for destination, offset in markdown_links(text):
            local_target = _local_link_target(root, path, destination)
            if local_target is None:
                continue
            checked_link_count += 1
            decoded_path, candidate, is_absolute = local_target
            resolved_relative = _relative_to_root(root, candidate)
            line = text.count("\n", 0, offset) + 1
            if is_absolute:
                defects.append(
                    {
                        "code": "absolute_local_markdown_link",
                        "path": path,
                        "line": line,
                        "target": decoded_path,
                    }
                )
            elif resolved_relative is None:
                defects.append(
                    {
                        "code": "local_markdown_link_outside_root",
                        "path": path,
                        "line": line,
                        "target": decoded_path,
                    }
                )
            elif not candidate.exists():
                defects.append(
                    {
                        "code": "broken_local_markdown_link",
                        "path": path,
                        "line": line,
                        "target": decoded_path,
                    }
                )

    defects.sort(
        key=lambda item: (
            str(item.get("path") or ""),
            int(item.get("line") or 0),
            str(item.get("code") or ""),
            str(item.get("target") or ""),
        )
    )
    return {
        "ok": not defects,
        "checked": {
            "required_files": len(required_paths),
            "startup_documents": len(STARTUP_ORDER_SECTIONS),
            "source_backlink_documents": len(source_backlink_paths),
            "sops": len(sop_paths),
            "roadmaps": len(roadmap_paths),
            "key_architecture_docs": len(KEY_ARCHITECTURE_DOCS),
            "local_markdown_links": checked_link_count,
        },
        "defect_count": len(defects),
        "defects": defects,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(WORKSPACE_ROOT), help="Repository root to verify.")
    args = parser.parse_args(argv)

    report = verify_documentation_truth(Path(args.root))
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
