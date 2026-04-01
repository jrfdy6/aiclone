#!/bin/zsh
set -euo pipefail

WORKSPACE_ROOT="/Users/neo/.openclaw/workspace"
PYTHON_BIN="$WORKSPACE_ROOT/.venv-main-safe/bin/python"
SCRIPT_PATH="$WORKSPACE_ROOT/scripts/runners/run_jean_claude.py"

exec "$PYTHON_BIN" "$SCRIPT_PATH" "$@"
