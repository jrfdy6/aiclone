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

echo "[1/6] Frontend home route"
check_route "/" "home" "Ops is the homepage."

echo "[2/6] Ops route"
check_route "/ops" "ops" "Mission Control"

echo "[3/6] Brain route"
check_route "/brain" "brain" "One surface for the AI clone brain"

echo "[4/6] Workspace route"
check_route "/workspace" "workspace" "Loading workspace"

echo "[5/6] Posting workspace route"
check_route "/workspace/posting" "workspace_posting" "Loading posting workspace"

echo "[6/6] Inbox route"
check_route "/inbox" "inbox" "Portfolio email routing"

echo
echo "verify_frontend_release.sh passed"
