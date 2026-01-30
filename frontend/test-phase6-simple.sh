#!/usr/bin/env bash
set -euo pipefail

# Minimal smoke test for the currently wired API endpoints.
# NOTE: The filename is historical; it does not exclusively test "Phase 6" routes.

API_URL="${API_URL:-http://localhost:3001}"

echo "==> Using API_URL=$API_URL"

require_curl() {
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required but not installed."
    exit 1
  }
}

hit() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  echo ""
  echo "==> $method $path"

  if [[ "$method" == "GET" ]]; then
    curl -sS -X GET "$API_URL$path" | head -c 1000
    echo ""
    return
  fi

  curl -sS -X "$method" \
    -H 'Content-Type: application/json' \
    -d "$body" \
    "$API_URL$path" | head -c 2000
  echo ""
}

require_curl

# Health + docs (docs response is HTML; we just check it returns content)
hit GET "/health"
hit GET "/api/docs"

# Retrieval endpoints (will return empty results if Firestore has no memory_chunks for that user)
hit POST "/api/chat/" '{"user_id":"dev-user","query":"test query","top_k":3}'
hit POST "/api/knowledge/" '{"user_id":"dev-user","search_query":"test query","top_k":3}'

echo ""
echo "✅ Smoke test completed."
