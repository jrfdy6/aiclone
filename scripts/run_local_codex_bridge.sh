#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="${AI_CLONE_ROOT:-/Users/neo/Documents/Codex/AI-Clone}"
PYTHON_BIN="${LOCAL_CODEX_BRIDGE_PYTHON:-$HOME/.codex/ai-clone/venv/bin/python}"
API_BASE_DEFAULT="https://aiclone-production-32dc.up.railway.app/api/content-generation"
SECRET_ENV_FILE="${LOCAL_CODEX_BRIDGE_ENV_FILE:-$HOME/.codex/ai-clone/secrets/control_plane.env}"

read_env_value() {
  local candidate="$1"
  local requested_key="$2"
  local line=""
  local value=""
  [ -f "$candidate" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "$requested_key"=*)
        value="${line#*=}"
        case "$value" in
          \"*\") value="${value#\"}"; value="${value%\"}" ;;
          \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        printf '%s' "$value"
        return 0
        ;;
    esac
  done < "$candidate"
}

export AI_CLONE_API_BASE_URL="${AI_CLONE_API_BASE_URL:-$API_BASE_DEFAULT}"
export LOCAL_CODEX_BRIDGE_TOKEN="${LOCAL_CODEX_BRIDGE_TOKEN:-$(read_env_value "$SECRET_ENV_FILE" "LOCAL_CODEX_BRIDGE_TOKEN")}"
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
  echo "LOCAL_CODEX_BRIDGE_TOKEN must be set for the local Codex bridge." >&2
  exit 1
fi

mkdir -p "${AI_CLONE_LOG_ROOT:-$HOME/.codex/ai-clone/logs}"

BRIDGE_ENV=(
  "HOME=$HOME"
  "PATH=$PATH"
  "AI_CLONE_API_BASE_URL=$AI_CLONE_API_BASE_URL"
  "LOCAL_CODEX_BRIDGE_TOKEN=$LOCAL_CODEX_BRIDGE_TOKEN"
)
for name in LANG LC_ALL LOGNAME SHELL SSL_CERT_DIR SSL_CERT_FILE TERM TMPDIR USER \
  LOCAL_CODEX_BRIDGE_MODEL LOCAL_CODEX_BRIDGE_REASONING_EFFORT \
  LOCAL_CODEX_BRIDGE_POLL_SECONDS LOCAL_CODEX_BRIDGE_TIMEOUT_SECONDS \
  LOCAL_CODEX_BRIDGE_HTTP_TIMEOUT_SECONDS LOCAL_CODEX_BRIDGE_HTTP_RETRIES \
  LOCAL_CODEX_BRIDGE_ERROR_BACKOFF_SECONDS LOCAL_CODEX_BRIDGE_MAX_ERROR_BACKOFF_SECONDS; do
  if [ -n "${!name:-}" ]; then
    BRIDGE_ENV+=("$name=${!name}")
  fi
done

exec /usr/bin/env -i "${BRIDGE_ENV[@]}" "$PYTHON_BIN" "$ROOT/scripts/local_codex_bridge.py" \
  --api-base "$AI_CLONE_API_BASE_URL" \
  --workspace-root "$WORKSPACE_ROOT" \
  --workspace-slug "$WORKSPACE_SLUG" \
  --worker-id "$WORKER_ID"
