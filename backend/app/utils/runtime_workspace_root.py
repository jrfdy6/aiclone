from __future__ import annotations

import os
from pathlib import Path


def resolve_runtime_workspace_root(current_file: str | Path) -> Path:
    """Resolve the repository root in both checkout and flattened service layouts."""

    configured = str(os.getenv("AI_CLONE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    current = Path(current_file).resolve()
    cwd = Path.cwd().resolve()
    candidates = (
        current.parents[3],
        current.parents[2],
        cwd,
        *cwd.parents,
        Path("/app"),
        Path("/app/backend"),
    )
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        has_runtime_helper = (resolved / "scripts" / "runtime_paths.py").is_file()
        has_checkout_app = (resolved / "backend" / "app" / "main.py").is_file()
        has_flattened_app = (resolved / "app" / "main.py").is_file()
        if has_runtime_helper and (
            has_checkout_app
            or has_flattened_app
            or (resolved / "knowledge").is_dir()
            or (resolved / "workspaces").is_dir()
        ):
            return resolved
    raise RuntimeError("Unable to resolve the AI Clone runtime root from required staging markers.")
