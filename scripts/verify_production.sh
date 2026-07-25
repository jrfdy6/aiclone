#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://aiclone-production-32dc.up.railway.app}"
FRONTEND_URL="${FRONTEND_URL:-https://aiclone-frontend-production.up.railway.app}"

if [ -z "${CONTROL_PLANE_SERVICE_TOKEN:-}" ]; then
  echo "CONTROL_PLANE_SERVICE_TOKEN is required to verify protected backend routes." >&2
  exit 1
fi
if [ -z "${CONTROL_PLANE_PASSWORD:-}" ]; then
  echo "CONTROL_PLANE_PASSWORD is required to verify private frontend routes." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cookie_jar="$tmp_dir/cookies.txt"

backend_get() {
  curl -fsS -H "Authorization: Bearer $CONTROL_PLANE_SERVICE_TOKEN" "$@"
}

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

echo "[1/6] Backend health"
curl -fsS "$BACKEND_URL/health" > "$tmp_dir/health.json"
python3 - "$tmp_dir/health.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
assert payload["status"] == "healthy", payload
print("health ok")
PY

echo "[2/6] Workspace snapshot"
backend_get "$BACKEND_URL/api/workspace/linkedin-os-snapshot" > "$tmp_dir/snapshot.json"
python3 - "$tmp_dir/snapshot.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
feed = payload.get("social_feed") or {}
items = feed.get("items") or []
assert items, "social_feed.items is empty"
assert items[0].get("lens_variants"), "first social feed item missing lens_variants"
doc_entries = payload.get("doc_entries") or []
workspace_files = payload.get("workspace_files") or []
source_assets = payload.get("source_assets") or {}
source_asset_total = ((source_assets.get("counts") or {}).get("total")) or 0
persona_review = payload.get("persona_review_summary") or {}
review_source_counts = persona_review.get("review_source_counts") or {}
long_form_review_total = review_source_counts.get("long_form_media.segment", 0) or 0
long_form_sync = persona_review.get("long_form_sync") or {}
assets_considered = long_form_sync.get("assets_considered", 0) or 0

assert doc_entries, "doc_entries is empty"
assert workspace_files, "workspace_files is empty"

if long_form_review_total > 0:
    assert source_asset_total > 0, "source_assets.counts.total is zero while long-form persona review items exist"
    assert assets_considered > 0, "persona_review_summary.long_form_sync.assets_considered is zero despite long-form source assets"

print(
    f"snapshot ok: {len(items)} items, {len(doc_entries)} docs, {len(workspace_files)} workspace files, "
    f"{source_asset_total} source assets, {assets_considered} assets considered"
)
PY

echo "[3/6] Signal preview route"
curl -fsS -X POST "$BACKEND_URL/api/workspace/ingest-signal" \
  -H "Authorization: Bearer $CONTROL_PLANE_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"AI can augment higher education when context and workflow are clear.","priority_lane":"ai"}' \
  > "$tmp_dir/preview.json"
python3 - "$tmp_dir/preview.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
preview = payload.get("preview_item") or {}
assert preview.get("lens_variants"), "preview missing lens_variants"
print("preview ok")
PY

echo "[4/6] Analytics/logs fallback routes"
backend_get "$BACKEND_URL/api/analytics/compliance" > "$tmp_dir/compliance.json"
backend_get "$BACKEND_URL/api/system/logs/?limit=5" > "$tmp_dir/logs.json"
python3 - "$tmp_dir/compliance.json" "$tmp_dir/logs.json" <<'PY'
import json, sys
json.load(open(sys.argv[1]))
json.load(open(sys.argv[2]))
print("analytics and logs ok")
PY

echo "[5/6] Email drafting canary"
backend_get "$BACKEND_URL/api/email/canary" > "$tmp_dir/email_canary.json"
launchctl list > "$tmp_dir/launchctl.txt"
ps -ef > "$tmp_dir/ps.txt"
python3 - "$tmp_dir/email_canary.json" "$tmp_dir/launchctl.txt" "$tmp_dir/ps.txt" <<'PY'
import json, os, sys

payload = json.load(open(sys.argv[1]))
summary = payload.get("summary") or {}
queue = payload.get("queue") or {}
provider = payload.get("provider") or {}
bridge = payload.get("bridge_registry") or {}
require_email_canary = os.getenv("REQUIRE_EMAIL_CANARY", "").strip().lower() in {"1", "true", "yes", "on"}

assert queue.get("workspace_slug") == "email-drafts", queue
assert int(queue.get("stale_job_count") or 0) == 0, queue

if summary.get("status") == "pass":
    assert provider.get("connected") is True, provider
    assert provider.get("drafts_enabled") is True, provider
    assert bridge.get("configured") is True, bridge
    assert bridge.get("status") == "active", bridge

    launchctl_text = open(sys.argv[2], encoding="utf-8").read()
    assert "com.neo.email_codex_bridge" in launchctl_text, launchctl_text

    ps_lines = open(sys.argv[3], encoding="utf-8").read().splitlines()
    assert any(
        "local_codex_bridge.py" in line and "--workspace-slug email-drafts" in line
        for line in ps_lines
    ), ps_lines
    print("email canary ok")
else:
    assert not require_email_canary, payload
    assert provider.get("drafts_enabled") is False, provider
    assert bridge.get("status") in {"paused", "disabled"}, bridge
    print("email canary skipped: optional drafting lane is intentionally disabled")
PY

echo "[6/6] Frontend ops page"
curl -fsS -b "$cookie_jar" "$FRONTEND_URL/ops" > "$tmp_dir/ops.html"
grep -q "Your operating brief" "$tmp_dir/ops.html"
grep -q "AI Clone" "$tmp_dir/ops.html"
echo "ops page ok"

echo
echo "verify_production.sh passed"
