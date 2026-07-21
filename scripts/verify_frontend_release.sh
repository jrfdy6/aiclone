#!/usr/bin/env bash
set -euo pipefail

FRONTEND_URL="${FRONTEND_URL:-https://aiclone-frontend-production.up.railway.app}"

if [ -z "${CONTROL_PLANE_PASSWORD:-}" ]; then
  echo "CONTROL_PLANE_PASSWORD is required to verify private frontend routes." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cookie_jar="$tmp_dir/cookies.txt"

python3 - "$tmp_dir/login.json" <<'PY'
import json
import os
import sys

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({"password": os.environ["CONTROL_PLANE_PASSWORD"]}, handle)
PY

curl -fsS -c "$cookie_jar" \
  -H "Content-Type: application/json" \
  --data-binary "@$tmp_dir/login.json" \
  "$FRONTEND_URL/api/auth/login" > "$tmp_dir/login-response.json"
python3 - "$tmp_dir/login-response.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload.get("status") == "ok", payload
PY

check_route() {
  local path="$1"
  local label="$2"
  local needle="$3"
  local output_file="$tmp_dir/$(echo "$label" | tr ' ' '_' | tr '/' '_').html"

  curl -fsS -b "$cookie_jar" "$FRONTEND_URL$path" > "$output_file"
  grep -q "$needle" "$output_file"
  echo "$label ok"
}

echo "[1/6] Frontend home route"
check_route "/" "home" "Ops is the homepage."

echo "[2/6] Ops route"
check_route "/ops" "ops" "Mission Control"

echo "[3/6] Brain route"
check_route "/brain" "brain" "What needs you today."

echo "[4/6] Workspace route"
check_route "/workspace" "workspace" "Loading workspace"

echo "[5/6] Posting workspace route"
check_route "/workspace/posting" "workspace_posting" "Loading posting workspace"

echo "[6/6] Inbox route"
check_route "/inbox" "inbox" "Portfolio email routing"

echo
echo "verify_frontend_release.sh passed"
