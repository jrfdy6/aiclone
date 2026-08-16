#!/usr/bin/env python3
"""Portable backend copy of the canonical AI Clone runtime paths.

The source tree is intentionally independent of ``~/.openclaw``.  Runtime
state, logs, and credentials live under ``~/.codex/ai-clone`` by default and
may be overridden for tests or alternate hosts.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterable


def _expanded_env(name: str) -> Path | None:
    value = str(os.getenv(name) or "").strip()
    return Path(value).expanduser().resolve() if value else None


PROJECT_ROOT = _expanded_env("AI_CLONE_ROOT") or Path(__file__).resolve().parent
RUNTIME_ROOT = _expanded_env("AI_CLONE_RUNTIME_ROOT") or (Path.home() / ".codex" / "ai-clone")
STATE_ROOT = _expanded_env("AI_CLONE_STATE_ROOT") or (RUNTIME_ROOT / "state")
SECRETS_ROOT = _expanded_env("AI_CLONE_SECRETS_ROOT") or (RUNTIME_ROOT / "secrets")
LOG_ROOT = _expanded_env("AI_CLONE_LOG_ROOT") or (RUNTIME_ROOT / "logs")
AUTOMATION_ROOT = STATE_ROOT / "automations"
AUTOMATION_RUNS_ROOT = AUTOMATION_ROOT / "runs"
AUTOMATION_REGISTRY_PATH = AUTOMATION_ROOT / "registry.json"
MEMORY_STATE_ROOT = STATE_ROOT / "memory"
WORKSPACE_STATE_ROOT = STATE_ROOT / "workspaces"
MEMORY_INDEX_PATH = MEMORY_STATE_ROOT / "codex-memory.sqlite3"

_WORKSPACE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _root(value: Path | None, fallback: Path) -> Path:
    return (value or fallback).expanduser().resolve()


def _safe_relative_path(value: str | Path, *, label: str, allow_empty: bool = False) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"{label} must be a relative path without parent traversal: {value!r}")
    if not allow_empty and raw == Path("."):
        raise ValueError(f"{label} must not be empty.")
    return raw


def _workspace_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not _WORKSPACE_KEY_PATTERN.fullmatch(key):
        raise ValueError(f"Invalid workspace key: {value!r}")
    return key


def _private_state_child(root: Path, relative: Path, *, label: str) -> Path:
    """Return a lexical child after rejecting symlinked or escaping components."""

    resolved_root = root.expanduser().resolve()
    if resolved_root.exists() and not resolved_root.is_dir():
        raise ValueError(f"{label} root must be a directory: {resolved_root}")
    candidate = resolved_root / relative
    cursor = resolved_root
    for index, part in enumerate(relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"{label} must not traverse a symlink: {cursor}")
        if index < len(relative.parts) - 1 and cursor.exists() and not cursor.is_dir():
            raise ValueError(f"{label} parent must be a directory: {cursor}")
    resolved_candidate = candidate.resolve(strict=False)
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise ValueError(f"{label} must remain inside {resolved_root}: {candidate}")
    return candidate


def _seed_regular_file_once(source: Path, target: Path) -> None:
    """Copy ``source`` into ``target`` without overwriting a concurrent seed.

    The temporary file and target live in the same directory, so the hard-link
    publish is atomic. If another worker publishes first, its target wins and
    this worker discards only its own temporary copy.
    """

    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".seed",
        dir=str(target.parent),
    )
    os.close(descriptor)
    temporary = Path(temporary_raw)
    try:
        shutil.copy2(source, temporary)
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def state_path(relative_path: str | Path, *, state_root: Path | None = None) -> Path:
    """Return a contained path below the private state root."""

    relative = _safe_relative_path(relative_path, label="state path")
    return _private_state_child(
        _root(state_root, STATE_ROOT),
        relative,
        label="state path",
    )


def memory_state_path(
    relative_path: str | Path = ".",
    *,
    state_root: Path | None = None,
) -> Path:
    """Return the canonical private write path for generated memory state.

    Callers may pass either ``LEARNINGS.md`` or ``memory/LEARNINGS.md``.
    """

    relative = _safe_relative_path(
        relative_path,
        label="memory state path",
        allow_empty=True,
    )
    if relative.parts and relative.parts[0] == "memory":
        relative = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(".")
    state_relative = Path("memory") if relative == Path(".") else Path("memory") / relative
    return _private_state_child(
        _root(state_root, STATE_ROOT),
        state_relative,
        label="memory state path",
    )


def memory_read_candidates(
    relative_path: str | Path,
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> tuple[Path, ...]:
    """List canonical and legacy locations for generated memory reads.

    New writes always use ``AI_CLONE_STATE_ROOT/memory``.  The two project
    locations remain read-only fallbacks so existing local data continues to
    work until an operator performs an explicit, audited migration.
    """

    relative = _safe_relative_path(relative_path, label="memory read path")
    if relative.parts and relative.parts[0] == "memory":
        relative = Path(*relative.parts[1:])
    project = _root(project_root, PROJECT_ROOT)
    candidates = (
        memory_state_path(relative, state_root=state_root),
        project / "memory" / "runtime" / relative,
        project / "memory" / relative,
    )
    return tuple(dict.fromkeys(candidates))


def resolve_memory_read_path(
    relative_path: str | Path,
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> Path:
    """Prefer private generated state and fall back to legacy project data."""

    candidates = memory_read_candidates(
        relative_path,
        project_root=project_root,
        state_root=state_root,
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def seed_memory_state_file(
    relative_path: str | Path,
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> Path:
    """Copy one legacy regular file into private state before its first append.

    This is intentionally copy-only: source data is never removed or modified.
    """

    candidates = memory_read_candidates(
        relative_path,
        project_root=project_root,
        state_root=state_root,
    )
    target = candidates[0]
    if target.exists():
        return target
    source = next(
        (
            path
            for path in candidates[1:]
            if path.is_file() and not path.is_symlink()
        ),
        None,
    )
    if source is None:
        return target
    _seed_regular_file_once(source, target)
    return target


def workspace_state_root(
    workspace_key: str,
    *,
    state_root: Path | None = None,
) -> Path:
    """Return the private generated-state root for any valid workspace key."""

    return _private_state_child(
        _root(state_root, STATE_ROOT),
        Path("workspaces") / _workspace_key(workspace_key),
        label="workspace state root",
    )


def workspace_state_path(
    workspace_key: str,
    relative_path: str | Path = ".",
    *,
    state_root: Path | None = None,
) -> Path:
    """Return a contained private write path for workspace-generated output."""

    relative = _safe_relative_path(
        relative_path,
        label="workspace state path",
        allow_empty=True,
    )
    state_relative = Path("workspaces") / _workspace_key(workspace_key)
    if relative != Path("."):
        state_relative /= relative
    return _private_state_child(
        _root(state_root, STATE_ROOT),
        state_relative,
        label="workspace state path",
    )


def workspace_read_candidates(
    workspace_key: str,
    relative_path: str | Path,
    *,
    source_root: Path | None = None,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> tuple[Path, ...]:
    """List private state followed by backward-compatible workspace sources."""

    key = _workspace_key(workspace_key)
    relative = _safe_relative_path(relative_path, label="workspace read path")
    project = _root(project_root, PROJECT_ROOT)
    candidates: list[Path] = [
        workspace_state_path(key, relative, state_root=state_root),
    ]
    if source_root is not None:
        candidates.append(source_root.expanduser().resolve() / relative)
    candidates.append(project / "workspaces" / key / relative)
    return tuple(dict.fromkeys(candidates))


def resolve_workspace_read_path(
    workspace_key: str,
    relative_path: str | Path,
    *,
    source_root: Path | None = None,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> Path:
    """Prefer private workspace state and fall back to project workspace data."""

    candidates = workspace_read_candidates(
        workspace_key,
        relative_path,
        source_root=source_root,
        project_root=project_root,
        state_root=state_root,
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def seed_workspace_state_file(
    workspace_key: str,
    relative_path: str | Path,
    *,
    source_root: Path | None = None,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> Path:
    """Copy one legacy workspace file into private state before its first write."""

    candidates = workspace_read_candidates(
        workspace_key,
        relative_path,
        source_root=source_root,
        project_root=project_root,
        state_root=state_root,
    )
    target = candidates[0]
    if target.exists():
        return target
    source = next(
        (
            path
            for path in candidates[1:]
            if path.is_file() and not path.is_symlink()
        ),
        None,
    )
    if source is None:
        return target
    _seed_regular_file_once(source, target)
    return target


def resolve_state_or_project_path(
    state_relative_path: str | Path,
    project_relative_path: str | Path,
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
) -> Path:
    """Read a state override when present, otherwise use immutable project data."""

    state_candidate = state_path(state_relative_path, state_root=state_root)
    project_relative = _safe_relative_path(project_relative_path, label="project path")
    project_candidate = _root(project_root, PROJECT_ROOT) / project_relative
    return state_candidate if state_candidate.exists() else project_candidate


def first_existing_path(paths: Iterable[Path], *, default: Path) -> Path:
    """Return the first existing candidate without creating or moving data."""

    return next((path for path in paths if path.exists()), default)


def ensure_runtime_dirs() -> None:
    """Create private runtime directories without touching project source."""

    for path in (
        RUNTIME_ROOT,
        STATE_ROOT,
        SECRETS_ROOT,
        LOG_ROOT,
        AUTOMATION_ROOT,
        AUTOMATION_RUNS_ROOT,
        MEMORY_STATE_ROOT,
        WORKSPACE_STATE_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.chmod(0o700)
        except OSError:
            pass


def project_path(relative_path: str | Path) -> Path:
    return PROJECT_ROOT / Path(relative_path)
