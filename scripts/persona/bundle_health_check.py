#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = WORKSPACE_ROOT / "knowledge" / "persona" / "feeze"
INITIATIVES_PATH = BUNDLE_ROOT / "history" / "initiatives.md"

REQUIRED_SECTION_ITEMS: dict[str, tuple[str, int]] = {
    "identity/philosophy.md": ("Core Beliefs", 1),
    "identity/decision_principles.md": ("Core Principles", 1),
    "history/wins.md": ("Wins", 1),
    "history/timeline.md": ("Milestones", 1),
}
REQUIRED_TABLE_ROWS: dict[str, int] = {
    "identity/claims.md": 1,
}
REQUIRED_STORY_COUNT = 1

REVIEW_VOICE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("first_person_reaction", re.compile(r"\b(i love|i agree|i disagree|i think)\b", re.IGNORECASE)),
    ("filler_language", re.compile(r"\b(um|uh|kind of|sort of)\b", re.IGNORECASE)),
    ("planning_voice", re.compile(r"\b(we might need to|figure out a way to)\b", re.IGNORECASE)),
    ("ownership_shift", re.compile(r"\bmy company\b", re.IGNORECASE)),
)
SUSPICIOUS_TITLE_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{11}\b")


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def _parse_initiatives(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current:
                rows.append(current)
            current = {"title": line.replace("## ", "", 1).strip(), "status": "", "purpose": "", "value": "", "proof": ""}
            continue
        if not current:
            continue
        if line.startswith("- Status:"):
            current["status"] = line.replace("- Status:", "", 1).strip()
        elif line.startswith("- Purpose:"):
            current["purpose"] = line.replace("- Purpose:", "", 1).strip()
        elif line.startswith("- Value to persona:"):
            current["value"] = line.replace("- Value to persona:", "", 1).strip()
        elif line.startswith("- Public-facing proof:"):
            current["proof"] = line.replace("- Public-facing proof:", "", 1).strip()
    if current:
        rows.append(current)
    return rows


def _parse_sectioned_lists(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_section = line.replace("## ", "", 1).strip()
            sections[current_section] = []
            continue
        if current_section and line.startswith("- "):
            item = line.replace("- ", "", 1).strip()
            if item and item != "-":
                sections[current_section].append(item)
    return sections


def _parse_claim_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4 or cells[0].lower() == "claim":
            continue
        rows.append(cells)
    return rows


def _parse_story_count(path: Path) -> int:
    return sum(1 for raw_line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines() if raw_line.startswith("## "))


def _line_issues(path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        normalized = _normalize(raw_line)
        if not normalized or normalized.startswith("---"):
            continue
        for issue_type, pattern in REVIEW_VOICE_PATTERNS:
            if pattern.search(normalized):
                issues.append(
                    {
                        "path": str(path.relative_to(BUNDLE_ROOT)),
                        "line": str(line_number),
                        "type": issue_type,
                        "message": "review voice leaked into canonical bundle text",
                        "excerpt": normalized[:220],
                    }
                )
    return issues


def _initiative_issues(path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for entry in _parse_initiatives(path):
        title = _normalize(entry.get("title"))
        if SUSPICIOUS_TITLE_PATTERN.search(title) and len(title.split()) > 6:
            issues.append(
                {
                    "path": str(path.relative_to(BUNDLE_ROOT)),
                    "title": title,
                    "type": "suspicious_title",
                    "message": "initiative title looks like a raw media title rather than a canonical initiative name",
                }
            )
        proof = _normalize(entry.get("proof"))
        value = _normalize(entry.get("value"))
        if not proof:
            issues.append(
                {
                    "path": str(path.relative_to(BUNDLE_ROOT)),
                    "title": title,
                    "type": "missing_proof",
                    "message": "initiative is missing public-facing proof",
                }
            )
        for field_name, field_value in (("value", value), ("proof", proof)):
            for issue_type, pattern in REVIEW_VOICE_PATTERNS:
                if pattern.search(field_value):
                    issues.append(
                        {
                            "path": str(path.relative_to(BUNDLE_ROOT)),
                            "title": title,
                            "field": field_name,
                            "type": issue_type,
                            "message": "initiative field contains review voice instead of canonical language",
                            "excerpt": field_value[:220],
                        }
                    )
    return issues


def _coverage_issues(bundle_root: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    issues: list[dict[str, str]] = []
    coverage = {
        "claims": 0,
        "stories": 0,
        "wins": 0,
        "timeline": 0,
        "philosophy_beliefs": 0,
        "decision_principles": 0,
        "initiatives": 0,
    }

    for rel_path, (section_name, minimum) in REQUIRED_SECTION_ITEMS.items():
        path = bundle_root / rel_path
        if not path.exists():
            issues.append({"path": rel_path, "type": "missing_file", "message": "required legacy canon file is missing"})
            continue
        section_items = _parse_sectioned_lists(path).get(section_name, [])
        count = len(section_items)
        if rel_path.endswith("philosophy.md"):
            coverage["philosophy_beliefs"] = count
        elif rel_path.endswith("decision_principles.md"):
            coverage["decision_principles"] = count
        elif rel_path.endswith("wins.md"):
            coverage["wins"] = count
        elif rel_path.endswith("timeline.md"):
            coverage["timeline"] = count
        if count < minimum:
            issues.append(
                {
                    "path": rel_path,
                    "type": "missing_section_content",
                    "message": f"section '{section_name}' must contain at least {minimum} real item(s)",
                }
            )

    for rel_path, minimum in REQUIRED_TABLE_ROWS.items():
        path = bundle_root / rel_path
        if not path.exists():
            issues.append({"path": rel_path, "type": "missing_file", "message": "required legacy canon file is missing"})
            continue
        count = len(_parse_claim_rows(path))
        coverage["claims"] = count
        if count < minimum:
            issues.append(
                {
                    "path": rel_path,
                    "type": "missing_claims",
                    "message": f"claims table must contain at least {minimum} row(s)",
                }
            )

    story_path = bundle_root / "history/story_bank.md"
    if not story_path.exists():
        issues.append({"path": "history/story_bank.md", "type": "missing_file", "message": "required legacy canon file is missing"})
    else:
        story_count = _parse_story_count(story_path)
        coverage["stories"] = story_count
        if story_count < REQUIRED_STORY_COUNT:
            issues.append(
                {
                    "path": "history/story_bank.md",
                    "type": "missing_stories",
                    "message": f"story bank must contain at least {REQUIRED_STORY_COUNT} story entry",
                }
            )

    if INITIATIVES_PATH.exists():
        coverage["initiatives"] = len(_parse_initiatives(INITIATIVES_PATH))
    else:
        issues.append({"path": "history/initiatives.md", "type": "missing_file", "message": "required legacy canon file is missing"})

    return issues, coverage


def main() -> int:
    if not BUNDLE_ROOT.exists():
        print(json.dumps({"ok": False, "error": f"Bundle root not found: {BUNDLE_ROOT}"}))
        return 1

    issues: list[dict[str, str]] = []
    for path in sorted(BUNDLE_ROOT.rglob("*.md")):
        issues.extend(_line_issues(path))
    if INITIATIVES_PATH.exists():
        issues.extend(_initiative_issues(INITIATIVES_PATH))
    coverage_issues, coverage = _coverage_issues(BUNDLE_ROOT)
    issues.extend(coverage_issues)

    summary = {
        "ok": len(issues) == 0,
        "bundle_root": str(BUNDLE_ROOT),
        "files_scanned": sum(1 for _ in BUNDLE_ROOT.rglob("*.md")),
        "coverage": coverage,
        "issue_count": len(issues),
        "issues": issues,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
