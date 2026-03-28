#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://aiclone-production-32dc.up.railway.app}"
FRONTEND_URL="${FRONTEND_URL:-https://aiclone-frontend-production.up.railway.app}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

echo "[1/5] Backend health"
curl -fsS "$BACKEND_URL/health" > "$tmp_dir/health.json"
python3 - "$tmp_dir/health.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
assert payload["status"] == "healthy", payload
print("health ok")
PY

echo "[2/5] Workspace snapshot"
curl -fsS "$BACKEND_URL/api/workspace/linkedin-os-snapshot" > "$tmp_dir/snapshot.json"
python3 - "$tmp_dir/snapshot.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
feed = payload.get("social_feed") or {}
items = feed.get("items") or []
assert items, "social_feed.items is empty"
assert items[0].get("lens_variants"), "first social feed item missing lens_variants"
source_assets = payload.get("source_assets") or {}
source_asset_total = ((source_assets.get("counts") or {}).get("total")) or 0
persona_review = payload.get("persona_review_summary") or {}
review_source_counts = persona_review.get("review_source_counts") or {}
long_form_review_total = review_source_counts.get("long_form_media.segment", 0) or 0
long_form_sync = persona_review.get("long_form_sync") or {}
assets_considered = long_form_sync.get("assets_considered", 0) or 0

if long_form_review_total > 0:
    assert source_asset_total > 0, "source_assets.counts.total is zero while long-form persona review items exist"
    assert assets_considered > 0, "persona_review_summary.long_form_sync.assets_considered is zero despite long-form source assets"

print(f"snapshot ok: {len(items)} items, {source_asset_total} source assets, {assets_considered} assets considered")
PY

echo "[3/5] Signal preview route"
curl -fsS -X POST "$BACKEND_URL/api/workspace/ingest-signal" \
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

echo "[4/5] Analytics/logs fallback routes"
curl -fsS "$BACKEND_URL/api/analytics/compliance" > "$tmp_dir/compliance.json"
curl -fsS "$BACKEND_URL/api/system/logs/?limit=5" > "$tmp_dir/logs.json"
python3 - "$tmp_dir/compliance.json" "$tmp_dir/logs.json" <<'PY'
import json, sys
json.load(open(sys.argv[1]))
json.load(open(sys.argv[2]))
print("analytics and logs ok")
PY

echo "[5/5] Frontend ops page"
curl -fsS "$FRONTEND_URL/ops" > "$tmp_dir/ops.html"
grep -q "Mission Control" "$tmp_dir/ops.html"
grep -q "AI Clone" "$tmp_dir/ops.html"
echo "ops page ok"

echo
echo "verify_production.sh passed"
