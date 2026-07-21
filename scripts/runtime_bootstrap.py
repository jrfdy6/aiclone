#!/usr/bin/env python3
"""Ensure operational scripts run inside the workspace virtualenv when available."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from runtime_paths import PROJECT_ROOT, RUNTIME_ROOT

WORKSPACE_ROOT = PROJECT_ROOT
VENV_PYTHON = RUNTIME_ROOT / "venv" / "bin" / "python"
BOOTSTRAP_ENV = "AICLONE_RUNTIME_BOOTSTRAPPED"


def maybe_reexec_with_workspace_venv() -> None:
    if os.environ.get(BOOTSTRAP_ENV) == "1":
        return
    if not VENV_PYTHON.exists():
        return
    current = Path(sys.executable).resolve()
    target = VENV_PYTHON.resolve()
    if current == target:
        return
    env = dict(os.environ)
    env[BOOTSTRAP_ENV] = "1"
    os.execve(str(target), [str(target), *sys.argv], env)
