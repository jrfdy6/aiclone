"""Filesystem and workspace allowlists for local execution workers."""
from __future__ import annotations

import re
from pathlib import Path


WORKSPACE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_workspace_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not WORKSPACE_KEY_PATTERN.fullmatch(key):
        raise ValueError(f"Invalid workspace key: {value!r}")
    return key


def require_within(path: Path, root: Path, *, label: str, must_exist: bool = False) -> Path:
    resolved_root = root.expanduser().resolve()
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside {resolved_root}") from exc
    if must_exist and not resolved.exists():
        raise ValueError(f"{label} does not exist: {resolved}")
    return resolved


def resolve_workspace_root(project_root: Path, workspace_key: str, configured: str | None = None) -> Path:
    key = validate_workspace_key(workspace_key)
    workspace_parent = (project_root / "workspaces").resolve()
    fallback_name = "shared-ops" if key == "shared_ops" else key
    candidate = Path(configured).expanduser() if str(configured or "").strip() else workspace_parent / fallback_name
    return require_within(candidate, workspace_parent, label="workspace root")


def require_execution_packet(path: Path, project_root: Path) -> Path:
    resolved = require_within(
        path,
        project_root / "workspaces",
        label="execution packet",
        must_exist=True,
    )
    if resolved.suffix.lower() != ".json" or resolved.parent.name != "dispatch":
        raise ValueError("Execution packets must be JSON files in a workspace dispatch directory.")
    return resolved


def require_repo_path(path: Path, project_root: Path) -> Path:
    return require_within(path, project_root, label="repository path", must_exist=True)
