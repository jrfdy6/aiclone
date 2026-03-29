#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = WORKSPACE_ROOT / "knowledge" / "persona" / "feeze"
INITIATIVES_PATH = BUNDLE_ROOT / "history" / "initiatives.md"

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


def main() -> int:
    if not BUNDLE_ROOT.exists():
        print(json.dumps({"ok": False, "error": f"Bundle root not found: {BUNDLE_ROOT}"}))
        return 1

    issues: list[dict[str, str]] = []
    for path in sorted(BUNDLE_ROOT.rglob("*.md")):
        issues.extend(_line_issues(path))
    if INITIATIVES_PATH.exists():
        issues.extend(_initiative_issues(INITIATIVES_PATH))

    summary = {
        "ok": len(issues) == 0,
        "bundle_root": str(BUNDLE_ROOT),
        "files_scanned": sum(1 for _ in BUNDLE_ROOT.rglob("*.md")),
        "issue_count": len(issues),
        "issues": issues,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
