from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.workspace_registry_service import REPO_ROOT


ROOT = REPO_ROOT
CLEANUP_DECISION_PATH = ROOT / "docs" / "truth_lane_cleanup_decision.md"
RUNTIME_MEMORY_FILES: tuple[tuple[str, Path], ...] = (
    ("learnings", ROOT / "memory" / "runtime" / "LEARNINGS.md"),
    ("persistent_state", ROOT / "memory" / "runtime" / "persistent_state.md"),
)

CLEANUP_MODE_FORWARD_ONLY = "forward_only_with_audit"

_SECTION_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("codex_chronicle_section", re.compile(r"codex chronicle", re.IGNORECASE)),
)
_LINE_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("user_request_language", re.compile(r"\b(i want|can you|please continue|let me know|i think i may have)\b", re.IGNORECASE)),
    ("assistant_interpretation_language", re.compile(r"^(that means|my take is|the short version is|the reality now is)\b", re.IGNORECASE)),
    ("question_shape", re.compile(r"\?$")),
)


def build_truth_lane_cleanup_report(*, include_findings: bool = True, sample_limit: int = 12) -> dict[str, Any]:
    file_reports = [_audit_runtime_memory_file(label, path, sample_limit=sample_limit) for label, path in RUNTIME_MEMORY_FILES]
    category_counts: dict[str, int] = {}
    suspect_line_count = 0
    files_with_suspects = 0
    for report in file_reports:
        suspect_count = int(report.get("suspect_line_count") or 0)
        suspect_line_count += suspect_count
        if suspect_count:
            files_with_suspects += 1
        for category, count in (report.get("category_counts") or {}).items():
            category_counts[category] = int(category_counts.get(category) or 0) + int(count or 0)

    payload: dict[str, Any] = {
        "schema_version": "truth_lane_cleanup_report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cleanup_decision": {
            "mode": CLEANUP_MODE_FORWARD_ONLY,
            "doc_ref": _relative_path(CLEANUP_DECISION_PATH),
            "summary": "Leave historical runtime memory in place, harden forward behavior, and use a standing audit to track suspect residue until a rebuild is explicitly justified.",
        },
        "summary": {
            "files_scanned": len(file_reports),
            "files_with_suspect_residue": files_with_suspects,
            "suspect_line_count": suspect_line_count,
            "category_counts": category_counts,
        },
    }
    if include_findings:
        payload["files"] = file_reports
    return payload


def _audit_runtime_memory_file(label: str, path: Path, *, sample_limit: int) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "file_id": label,
            "path": _relative_path(path),
            "available": False,
            "suspect_line_count": 0,
            "category_counts": {},
            "sample_findings": [],
        }

    findings: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    current_heading = ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = " ".join(raw_line.replace("\xa0", " ").split()).strip()
        if not line:
            continue
        if raw_line.startswith("#"):
            current_heading = line.lstrip("#").strip()
            continue
        if not raw_line.lstrip().startswith("-"):
            continue
        categories = _classify_line(line, current_heading=current_heading)
        if not categories:
            continue
        finding = {
            "heading": current_heading,
            "line": line.lstrip("- ").strip(),
            "categories": categories,
        }
        findings.append(finding)
        for category in categories:
            category_counts[category] = int(category_counts.get(category) or 0) + 1

    return {
        "file_id": label,
        "path": _relative_path(path),
        "available": True,
        "suspect_line_count": len(findings),
        "category_counts": category_counts,
        "sample_findings": findings[: max(1, sample_limit)],
    }


def _classify_line(line: str, *, current_heading: str) -> list[str]:
    categories: list[str] = []
    for category, pattern in _SECTION_CATEGORY_PATTERNS:
        if pattern.search(current_heading):
            categories.append(category)
    for category, pattern in _LINE_CATEGORY_PATTERNS:
        if pattern.search(line):
            categories.append(category)
    return categories


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()
