#!/usr/bin/env bash
set -euo pipefail

FRONTEND_URL="${FRONTEND_URL:-https://aiclone-frontend-production.up.railway.app}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

check_route() {
  local path="$1"
  local label="$2"
  local needle="$3"
  local output_file="$tmp_dir/$(echo "$label" | tr ' ' '_' | tr '/' '_').html"

  curl -fsS "$FRONTEND_URL$path" > "$output_file"
  grep -q "$needle" "$output_file"
  echo "$label ok"
}

echo "[1/5] Frontend home route"
check_route "/" "home" "Ops is the homepage."

echo "[2/5] Ops route"
check_route "/ops" "ops" "Mission Control"

echo "[3/5] Brain route"
check_route "/brain" "brain" "One surface for the AI clone brain"

echo "[4/5] Workspace route"
check_route "/workspace" "workspace" "Loading workspace"

echo "[5/5] Posting workspace route"
check_route "/workspace/posting" "workspace_posting" "Loading posting workspace"

echo
echo "verify_frontend_release.sh passed"
