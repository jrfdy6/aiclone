#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="${OPENCLAW_WORKSPACE_ROOT:-/Users/neo/.openclaw/workspace}"
PYTHON_BIN="${LOCAL_CODEX_BRIDGE_PYTHON:-$WORKSPACE_ROOT/.venv-main-safe/bin/python}"
API_BASE_DEFAULT="https://aiclone-production-32dc.up.railway.app/api/content-generation"
SECRET_ENV_FILE="${LOCAL_CODEX_BRIDGE_ENV_FILE:-/Users/neo/.openclaw/secrets/local_codex_bridge.env}"

load_env_file() {
  local candidate="$1"
  if [ -f "$candidate" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$candidate"
    set +a
  fi
}

load_env_file "$ROOT/.env"
load_env_file "$ROOT/backend/.env"
load_env_file "$SECRET_ENV_FILE"

export AI_CLONE_API_BASE_URL="${AI_CLONE_API_BASE_URL:-$API_BASE_DEFAULT}"
export LOCAL_CODEX_BRIDGE_TOKEN="${LOCAL_CODEX_BRIDGE_TOKEN:-${CRON_ACCESS_TOKEN:-}}"
export PATH="${PATH:-/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin}"
WORKSPACE_SLUG="${LOCAL_CODEX_WORKSPACE_SLUG:-linkedin-content-os}"
WORKER_SUFFIX="${LOCAL_CODEX_WORKER_SUFFIX:-}"
if [ -z "$WORKER_SUFFIX" ]; then
  if [ "$WORKSPACE_SLUG" = "linkedin-content-os" ]; then
    WORKER_SUFFIX="feezie-codex-bridge"
  else
    WORKER_SUFFIX="${WORKSPACE_SLUG}-codex-bridge"
  fi
fi
WORKER_ID="${LOCAL_CODEX_WORKER_ID:-$(hostname -s)-$WORKER_SUFFIX}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Local Codex bridge python not found: $PYTHON_BIN" >&2
  exit 1
fi

if [ -z "${LOCAL_CODEX_BRIDGE_TOKEN:-}" ]; then
  echo "LOCAL_CODEX_BRIDGE_TOKEN or CRON_ACCESS_TOKEN must be set for the local Codex bridge." >&2
  exit 1
fi

mkdir -p /Users/neo/.openclaw/logs

exec "$PYTHON_BIN" "$ROOT/scripts/local_codex_bridge.py" \
  --api-base "$AI_CLONE_API_BASE_URL" \
  --workspace-root "$WORKSPACE_ROOT" \
  --workspace-slug "$WORKSPACE_SLUG" \
  --worker-id "$WORKER_ID"
