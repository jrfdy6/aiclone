#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AI_CLONE_ROOT="${AI_CLONE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
export AI_CLONE_RUNTIME_ROOT="${AI_CLONE_RUNTIME_ROOT:-$HOME/.codex/ai-clone}"
export AI_CLONE_STATE_ROOT="${AI_CLONE_STATE_ROOT:-$AI_CLONE_RUNTIME_ROOT/state}"
export AI_CLONE_SECRETS_ROOT="${AI_CLONE_SECRETS_ROOT:-$AI_CLONE_RUNTIME_ROOT/secrets}"
export AI_CLONE_LOG_ROOT="${AI_CLONE_LOG_ROOT:-$AI_CLONE_RUNTIME_ROOT/logs}"
export AI_CLONE_PYTHON="${AI_CLONE_PYTHON:-$AI_CLONE_RUNTIME_ROOT/venv/bin/python}"

mkdir -p "$AI_CLONE_STATE_ROOT" "$AI_CLONE_SECRETS_ROOT" "$AI_CLONE_LOG_ROOT"
chmod 700 "$AI_CLONE_RUNTIME_ROOT" "$AI_CLONE_STATE_ROOT" "$AI_CLONE_SECRETS_ROOT" "$AI_CLONE_LOG_ROOT" 2>/dev/null || true

load_runtime_env() {
  local env_file="$1"
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
}

load_runtime_env "$AI_CLONE_SECRETS_ROOT/railway.env"
load_runtime_env "$AI_CLONE_SECRETS_ROOT/backend.env"
load_runtime_env "$AI_CLONE_SECRETS_ROOT/frontend.env"
load_runtime_env "$AI_CLONE_SECRETS_ROOT/control_plane.env"
load_runtime_env "$AI_CLONE_SECRETS_ROOT/local_codex_bridge.env"
