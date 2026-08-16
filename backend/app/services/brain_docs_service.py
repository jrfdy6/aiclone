from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from app.services.brain_response_privacy_service import sanitize_brain_payload, sanitize_brain_text
from app.services.workspace_snapshot_service import resolve_workspace_root


WORKSPACE_ROOT = resolve_workspace_root()
MAX_DOC_BYTES = 512 * 1024
MAX_DOCS = 1_500
MAX_MARKDOWN_SNIPPET_CHARS = 240
READABLE_SUFFIXES = {".md", ".jsonl"}
DEPLOYED_SNAPSHOT_READ_MODE = "deployed_snapshot"
DAILY_LOG_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

_EXCLUDED_DIRECTORY_NAMES = frozenset({"runtime_snapshots", "runtime-snapshots"})
_RETIRED_PATH_MARKERS = ("openclaw", "qmd")

DOC_ROOTS: tuple[tuple[str, str], ...] = (
    ("knowledge/aiclone", "Knowledge Docs"),
    ("knowledge/source-intelligence", "Source Intelligence"),
    ("docs", "System Docs"),
    ("SOPs", "Operating Docs"),
    ("deliverables", "Reference Docs"),
    ("knowledge/persona/feeze", "Persona Bundle"),
    ("workspaces/shared-ops/docs", "Workspace Reference"),
    ("workspaces/linkedin-content-os/docs", "Workspace Reference"),
    ("workspaces/fusion-os/docs", "Workspace Reference"),
    ("workspaces/easyoutfitapp/docs", "Workspace Reference"),
    ("workspaces/ai-swag-store/docs", "Workspace Reference"),
    ("workspaces/agc/docs", "Workspace Reference"),
    ("workspaces/work-life-tools/docs", "Workspace Reference"),
    ("workspaces/work-life-tools/briefings", "Workspace Reference"),
)

EXPLICIT_DOCS: tuple[tuple[str, str], ...] = (
    ("SOURCE_OF_TRUTH.md", "Start Here"),
    ("CODEX_STARTUP.md", "Start Here"),
    ("AGENTS.md", "Start Here"),
    ("IDENTITY.md", "Identity"),
    ("CHARTER.md", "Identity"),
    ("SOUL.md", "Identity"),
    ("USER.md", "Identity"),
    ("MEMORY.md", "Canonical Memory"),
    ("README.md", "Reference Docs"),
    ("SOPs/_index.md", "Operating Docs"),
    ("docs/aiclone_system_architecture.md", "System Docs"),
    ("docs/aiclone_brain_architecture.md", "System Docs"),
    ("workspaces/linkedin-content-os/README.md", "Workspace Reference"),
    ("workspaces/linkedin-content-os/AGENTS.md", "Workspace Reference"),
    ("memory/persistent_state.md", "Canonical Memory"),
    ("memory/roadmap.md", "Canonical Memory"),
    ("memory/LEARNINGS.md", "Canonical Memory"),
    ("memory/daily-briefs.md", "Canonical Memory"),
    ("memory/cron-prune.md", "Canonical Memory"),
    ("memory/dream_cycle_log.md", "Canonical Memory"),
    ("memory/codex_session_handoff.jsonl", "Canonical Memory"),
    ("memory/reports/brain_canonical_memory_sync_latest.md", "Canonical Memory"),
)

RUNTIME_MEMORY_PATHS: dict[str, str] = {
    "memory/persistent_state.md": "memory/runtime/persistent_state.md",
    "memory/LEARNINGS.md": "memory/runtime/LEARNINGS.md",
    "memory/codex_session_handoff.jsonl": "memory/runtime/codex_session_handoff.jsonl",
}

PINNED_PATHS = (
    "SOURCE_OF_TRUTH.md",
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
    "docs/aiclone_system_architecture.md",
    "docs/aiclone_brain_architecture.md",
)

DOC_METADATA: dict[str, dict[str, Any]] = {
    "SOURCE_OF_TRUTH.md": {"authority": "binding", "status": "active"},
    "CODEX_STARTUP.md": {"authority": "operating", "status": "active"},
    "AGENTS.md": {"authority": "operating", "status": "active"},
    "IDENTITY.md": {"authority": "identity", "status": "active"},
    "CHARTER.md": {"authority": "identity", "status": "active"},
    "SOUL.md": {"authority": "identity", "status": "active"},
    "USER.md": {"authority": "identity", "status": "active"},
    "MEMORY.md": {"authority": "durable_guardrails", "status": "active"},
    "memory/persistent_state.md": {"authority": "current_context", "status": "active"},
    "memory/roadmap.md": {"authority": "directional", "status": "directional"},
    "SOPs/_index.md": {"authority": "procedure_registry", "status": "active"},
    "docs/aiclone_system_architecture.md": {"authority": "supporting", "status": "reference"},
    "docs/aiclone_brain_architecture.md": {"authority": "supporting", "status": "reference"},
    "workspaces/linkedin-content-os/docs/positioning_contract.md": {
        "authority": "owner_approved_strategy",
        "status": "active",
    },
    "workspaces/linkedin-content-os/docs/editorial_mix.md": {
        "authority": "owner_approved_strategy",
        "status": "active",
    },
    "README.md": {"authority": "orientation", "status": "reference"},
}


def _default_authority(group: str) -> tuple[str, str]:
    if group == "Operating Docs":
        return "procedural", "indexed"
    if group == "Canonical Memory":
        return "evidence", "active"
    if group == "Persona Bundle":
        return "persona_canon", "active"
    if group == "Identity":
        return "identity", "active"
    return "supporting", "reference"


def _contained_path(root: Path, relative_path: str) -> Path | None:
    try:
        base = root.resolve()
        candidate = (base / relative_path).resolve()
        candidate.relative_to(base)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _markdown_snippet(path: Path) -> str:
    """Return bounded heading metadata without indexing arbitrary document bodies."""

    try:
        with path.open("rb") as handle:
            raw = handle.read(8_192).decode("utf-8", errors="replace")
    except OSError:
        return ""

    heading = next(
        (
            match.group(1)
            for line in raw.splitlines()
            if (match := re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)) is not None
        ),
        "",
    )
    if not heading:
        return ""

    # Keep index metadata single-line and presentation-safe. The full document is
    # only returned by the authenticated, on-demand content endpoint.
    snippet = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    snippet = re.sub(r"[`*_~]+", "", snippet)
    snippet = " ".join(snippet.split())
    return sanitize_brain_text(snippet[:MAX_MARKDOWN_SNIPPET_CHARS].rstrip())


def _is_default_excluded(relative_path: Path) -> bool:
    lowered_parts = tuple(part.lower() for part in relative_path.parts)
    if any(part in _EXCLUDED_DIRECTORY_NAMES for part in lowered_parts):
        return True
    logical_path = relative_path.as_posix().lower()
    return any(marker in logical_path for marker in _RETIRED_PATH_MARKERS)


def _record(path: Path, *, display_path: str, group: str) -> dict[str, Any] | None:
    root = WORKSPACE_ROOT.resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
        stat = resolved.stat()
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved.is_file() or resolved.suffix.lower() not in READABLE_SUFFIXES:
        return None
    metadata = DOC_METADATA.get(display_path, {})
    authority, status = _default_authority(group)
    record = {
        "name": Path(display_path).stem,
        "path": display_path,
        "group": group,
        "authority": metadata.get("authority", authority),
        "status": metadata.get("status", status),
        "readOrder": PINNED_PATHS.index(display_path) if display_path in PINNED_PATHS else None,
        "updatedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "readMode": DEPLOYED_SNAPSHOT_READ_MODE,
        "resolvedPath": resolved.relative_to(root).as_posix(),
        "sizeBytes": stat.st_size,
        "_source_path": resolved,
    }
    if resolved.suffix.lower() == ".md":
        record["snippet"] = _markdown_snippet(resolved)
    return record


def _iter_root_records(relative_root: str, group: str) -> list[dict[str, Any]]:
    directory = _contained_path(WORKSPACE_ROOT, relative_root)
    if directory is None or not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if len(records) >= MAX_DOCS:
            break
        try:
            relative = path.relative_to(WORKSPACE_ROOT.resolve())
        except ValueError:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        if _is_default_excluded(relative):
            continue
        record = _record(path, display_path=relative.as_posix(), group=group)
        if record is not None:
            records.append(record)
    return records


def _explicit_record(logical_path: str, group: str) -> dict[str, Any] | None:
    runtime_path = RUNTIME_MEMORY_PATHS.get(logical_path)
    if runtime_path:
        candidate = _contained_path(WORKSPACE_ROOT, runtime_path)
        if candidate is not None and candidate.is_file():
            return _record(candidate, display_path=logical_path, group=group)
    candidate = _contained_path(WORKSPACE_ROOT, logical_path)
    if candidate is None or not candidate.is_file():
        return None
    return _record(candidate, display_path=logical_path, group=group)


def _latest_daily_log_record() -> dict[str, Any] | None:
    memory_root = _contained_path(WORKSPACE_ROOT, "memory")
    if memory_root is None or not memory_root.is_dir():
        return None
    daily_logs = sorted(
        path
        for path in memory_root.glob("*.md")
        if path.is_file() and DAILY_LOG_NAME_RE.fullmatch(path.name)
    )
    if not daily_logs:
        return None
    latest = daily_logs[-1]
    return _record(latest, display_path=f"memory/{latest.name}", group="Canonical Memory")


def _collect_records() -> list[dict[str, Any]]:
    records_by_path: dict[str, dict[str, Any]] = {}
    for relative_root, group in DOC_ROOTS:
        for record in _iter_root_records(relative_root, group):
            records_by_path.setdefault(str(record["path"]), record)
            if len(records_by_path) >= MAX_DOCS:
                break
        if len(records_by_path) >= MAX_DOCS:
            break

    for logical_path, group in EXPLICIT_DOCS:
        record = _explicit_record(logical_path, group)
        if record is not None:
            records_by_path[logical_path] = record

    latest_daily_log = _latest_daily_log_record()
    if latest_daily_log is not None:
        records_by_path[str(latest_daily_log["path"])] = latest_daily_log

    return sorted(
        records_by_path.values(),
        key=lambda item: (
            PINNED_PATHS.index(str(item["path"])) if item["path"] in PINNED_PATHS else len(PINNED_PATHS),
            str(item.get("group") or ""),
            str(item["path"]),
        ),
    )


def list_brain_docs() -> dict[str, Any]:
    records = _collect_records()
    docs = [{key: value for key, value in record.items() if not key.startswith("_")} for record in records]
    groups: dict[str, int] = {}
    for doc in docs:
        group = str(doc.get("group") or "Other")
        groups[group] = groups.get(group, 0) + 1
    payload = {
        "schema_version": "brain_docs_index/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority_path": "SOURCE_OF_TRUTH.md",
        "read_order": list(PINNED_PATHS),
        "count": len(docs),
        "groups": groups,
        "docs": docs,
    }
    return sanitize_brain_payload(payload)


def count_brain_docs() -> int:
    """Use the exact same allowlisted inventory as the Brain Docs index."""

    return len(_collect_records())


def read_brain_doc(doc_path: str) -> dict[str, Any] | None:
    normalized = unquote(str(doc_path or "")).replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or "\x00" in normalized:
        raise ValueError("A valid document path is required.")
    if any(part in {"", ".", ".."} for part in Path(normalized).parts):
        raise ValueError("Document path is outside the Brain docs allowlist.")

    record = next((item for item in _collect_records() if item["path"] == normalized), None)
    if record is None:
        return None
    source_path = record.get("_source_path")
    if not isinstance(source_path, Path):
        return None
    size_bytes = int(record.get("sizeBytes") or 0)
    truncated = size_bytes > MAX_DOC_BYTES
    if truncated:
        with source_path.open("rb") as handle:
            if source_path.suffix.lower() == ".jsonl":
                handle.seek(max(0, size_bytes - MAX_DOC_BYTES))
                raw = handle.read(MAX_DOC_BYTES)
                content = raw.decode("utf-8", errors="replace")
                first_newline = content.find("\n")
                if first_newline >= 0:
                    content = content[first_newline + 1 :]
                preview_note = f"Brain is showing the latest {MAX_DOC_BYTES // 1024} KB of this {size_bytes // 1024} KB log."
            else:
                content = handle.read(MAX_DOC_BYTES).decode("utf-8", errors="replace")
                preview_note = f"Brain is showing the first {MAX_DOC_BYTES // 1024} KB of this {size_bytes // 1024} KB document."
        content = f"> {preview_note}\n\n{content}"
    else:
        content = source_path.read_text(encoding="utf-8", errors="replace")
    payload = {
        **{key: value for key, value in record.items() if not key.startswith("_")},
        "content": content,
        "truncated": truncated,
    }
    return sanitize_brain_payload(payload)
