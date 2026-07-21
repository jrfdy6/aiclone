#!/usr/bin/env python3
"""Canonical paths for the Codex-native AI Clone runtime.

The source tree is intentionally independent of ``~/.openclaw``.  Runtime
state, logs, and credentials live under ``~/.codex/ai-clone`` by default and
may be overridden for tests or alternate hosts.
"""
from __future__ import annotations

import os
from pathlib import Path


def _expanded_env(name: str) -> Path | None:
    value = str(os.getenv(name) or "").strip()
    return Path(value).expanduser().resolve() if value else None


PROJECT_ROOT = _expanded_env("AI_CLONE_ROOT") or Path(__file__).resolve().parents[1]
RUNTIME_ROOT = _expanded_env("AI_CLONE_RUNTIME_ROOT") or (Path.home() / ".codex" / "ai-clone")
STATE_ROOT = _expanded_env("AI_CLONE_STATE_ROOT") or (RUNTIME_ROOT / "state")
SECRETS_ROOT = _expanded_env("AI_CLONE_SECRETS_ROOT") or (RUNTIME_ROOT / "secrets")
LOG_ROOT = _expanded_env("AI_CLONE_LOG_ROOT") or (RUNTIME_ROOT / "logs")
AUTOMATION_ROOT = STATE_ROOT / "automations"
AUTOMATION_RUNS_ROOT = AUTOMATION_ROOT / "runs"
AUTOMATION_REGISTRY_PATH = AUTOMATION_ROOT / "registry.json"
MEMORY_INDEX_PATH = STATE_ROOT / "memory" / "codex-memory.sqlite3"


def ensure_runtime_dirs() -> None:
    """Create private runtime directories without touching project source."""

    for path in (
        RUNTIME_ROOT,
        STATE_ROOT,
        SECRETS_ROOT,
        LOG_ROOT,
        AUTOMATION_ROOT,
        AUTOMATION_RUNS_ROOT,
        MEMORY_INDEX_PATH.parent,
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.chmod(0o700)
        except OSError:
            pass


def project_path(relative_path: str | Path) -> Path:
    return PROJECT_ROOT / Path(relative_path)
