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


def resolve_execution_workspace_root(
    project_root: Path,
    state_root: Path,
    workspace_key: str,
    configured: str | None = None,
) -> Path:
    """Resolve either the canonical private workspace root or a legacy project root."""

    key = validate_workspace_key(workspace_key)
    configured_path = Path(configured).expanduser() if str(configured or "").strip() else None
    private_parent = (state_root / "workspaces").expanduser().resolve()
    project_parent = (project_root / "workspaces").expanduser().resolve()
    if configured_path is not None:
        resolved = configured_path.resolve()
        if resolved == private_parent or private_parent in resolved.parents:
            expected = private_parent / key
            if resolved != expected:
                raise ValueError(f"private workspace root must be exactly {expected}")
            return resolved
        if resolved == project_parent or project_parent in resolved.parents:
            return require_within(resolved, project_parent, label="legacy workspace root")
        raise ValueError(f"workspace root must stay inside {private_parent} or {project_parent}")
    return private_parent / key


def require_execution_packet(
    path: Path,
    project_root: Path,
    *,
    state_root: Path | None = None,
) -> Path:
    roots = [project_root / "workspaces"]
    if state_root is not None:
        roots.insert(0, state_root / "workspaces")
    resolved: Path | None = None
    for root in roots:
        try:
            resolved = require_within(
                path,
                root,
                label="execution packet",
                must_exist=True,
            )
            break
        except ValueError:
            continue
    if resolved is None:
        allowed = " or ".join(str(root.expanduser().resolve()) for root in roots)
        raise ValueError(f"execution packet must stay inside {allowed}")
    if resolved.suffix.lower() != ".json" or resolved.parent.name != "dispatch":
        raise ValueError("Execution packets must be JSON files in a workspace dispatch directory.")
    return resolved


def require_repo_path(path: Path, project_root: Path) -> Path:
    return require_within(path, project_root, label="repository path", must_exist=True)
