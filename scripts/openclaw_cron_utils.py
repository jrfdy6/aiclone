#!/usr/bin/env python3
"""Shared helpers for inspecting OpenClaw cron jobs."""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path
from typing import Iterable, List

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
OPENCLAW_ROOT = Path("/Users/neo/.openclaw")
JOBS_JSON = OPENCLAW_ROOT / "cron" / "jobs.json"

ABS_PATH_RE = re.compile(r"(/Users/neo(?:/[^\s`\"'<>),:;]+)+)")
REL_PATH_RE = re.compile(
    r"(?<!\w)(\./[^\s`\"'<>),:;]+|\.\./[^\s`\"'<>),:;]+|(?:scripts|docs|memory|SOPs|skills|automations|backend|frontend|workspaces)/[^\s`\"'<>),:;]+)"
)

SKIP_SUGGESTION_DIRS = {
    ".git",
    "node_modules",
    "downloads",
    "tmp",
    "__pycache__",
}

TEMPLATE_MARKERS = (
    "YYYY-MM-DD",
    "<YYYY-MM-DD>",
    "<date>",
    "<DATE>",
    "<timestamp>",
    "<YYYY>",
    "<MM>",
)


def load_jobs(path: Path | None = None) -> list[dict]:
    jobs_path = path or JOBS_JSON
    data = json.loads(jobs_path.read_text())
    return data.get("jobs", [])


def normalize_reference(token: str) -> str:
    token = token.strip()
    token = token.rstrip("`'\".,:;)]}>")
    token = token.lstrip("`'\"(<[{")
    return token


def extract_references(text: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for regex in (ABS_PATH_RE, REL_PATH_RE):
        for match in regex.finditer(text):
            ref = normalize_reference(match.group(1))
            if not ref or ref in seen:
                continue
            seen.add(ref)
            refs.append(ref)
    return refs


def resolve_reference(
    reference: str,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    source_path: Path | None = None,
) -> Path:
    if reference.startswith("/"):
        return Path(reference)
    if reference.startswith("./") or reference.startswith("../"):
        base = source_path.parent if source_path else workspace_root
        return (base / reference).resolve()
    return (workspace_root / reference).resolve()


def reference_exists(path: Path) -> bool:
    path_str = str(path)
    if any(char in path_str for char in "*?["):
        return bool(glob.glob(path_str))
    return path.exists()


def reference_is_template(reference: str) -> bool:
    if any(marker in reference for marker in TEMPLATE_MARKERS):
        return True
    if reference.endswith("memory_health_") or reference.endswith("audit_log_"):
        return True
    return False


def suggestion_candidates(path: Path, *, workspace_root: Path = WORKSPACE_ROOT, limit: int = 5) -> list[str]:
    basename = path.name
    if not basename or any(char in basename for char in "*?["):
        return []
    search_root = workspace_root
    try:
        relative = path.relative_to(workspace_root)
        if relative.parts:
            candidate_root = workspace_root / relative.parts[0]
            if candidate_root.exists():
                search_root = candidate_root
    except ValueError:
        search_root = workspace_root
    candidates: list[str] = []
    for root, dirs, files in os.walk(search_root):
        dirs[:] = [name for name in dirs if name not in SKIP_SUGGESTION_DIRS]
        if basename in files:
            candidates.append(str(Path(root) / basename))
            if len(candidates) >= limit:
                break
    return candidates


def schedule_label(job: dict) -> str:
    schedule = job.get("schedule") or {}
    kind = schedule.get("kind", "unknown")
    if kind == "cron":
        return f"cron:{schedule.get('expr', 'unknown')}"
    if kind == "every":
        return f"every:{schedule.get('everyMs', 'unknown')}"
    return kind


def iter_job_message_references(jobs: Iterable[dict]) -> Iterable[tuple[dict, str]]:
    for job in jobs:
        message = (job.get("payload") or {}).get("message", "")
        for reference in extract_references(message):
            yield job, reference
