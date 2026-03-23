#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$WORKSPACE_ROOT/tmp"

usage() {
  cat <<'EOF'
Usage: scripts/deploy_railway_service.sh <frontend|backend>

Stages a small deploy context that preserves the top-level service directory
expected by Railway, then runs `railway up` against that staged path.
EOF
}

if [ "${1:-}" = "" ]; then
  usage
  exit 1
fi

case "$1" in
  frontend)
    SERVICE_NAME="aiclone-frontend"
    SOURCE_DIR="$WORKSPACE_ROOT/frontend"
    STAGE_DIR="$TMP_ROOT/frontend-railway-deploy.current"
    CHILD_DIR="frontend"
    RSYNC_EXCLUDES=(--exclude node_modules --exclude .next --exclude .git)
    ;;
  backend)
    SERVICE_NAME="aiclone-backend"
    SOURCE_DIR="$WORKSPACE_ROOT/backend"
    STAGE_DIR="$TMP_ROOT/backend-railway-deploy.current"
    CHILD_DIR="backend"
    RSYNC_EXCLUDES=(--exclude .git)
    ;;
  *)
    usage
    exit 1
    ;;
esac

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR/$CHILD_DIR"
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SOURCE_DIR/" "$STAGE_DIR/$CHILD_DIR/"

echo "Staged deploy context:"
du -sh "$STAGE_DIR"

cd "$WORKSPACE_ROOT"
UP_OUTPUT="$(railway up -s "$SERVICE_NAME" --path-as-root "tmp/$(basename "$STAGE_DIR")" --verbose 2>&1)"
echo "$UP_OUTPUT"

DEPLOY_ID="$(echo "$UP_OUTPUT" | sed -n 's/.*id=\([0-9a-fA-F-]\{36\}\).*/\1/p' | tail -n 1)"
if [ -z "$DEPLOY_ID" ]; then
  DEPLOY_ID="$(railway deployment list --service "$SERVICE_NAME" | sed -n 's/^[[:space:]]*\([0-9a-fA-F-]\{36\}\).*/\1/p' | head -n 1)"
fi

if [ -z "$DEPLOY_ID" ]; then
  echo "Error: could not determine deployment id."
  exit 1
fi

echo "Detected deployment id: $DEPLOY_ID"
echo "Recent deployments for $SERVICE_NAME:"
railway deployment list --service "$SERVICE_NAME" | sed -n '1,8p'

echo "Polling deployment status..."
TERMINAL_STATUS=""
for _ in {1..30}; do
  STATUS_LINE="$(railway deployment list --service "$SERVICE_NAME" | grep "$DEPLOY_ID" | head -n 1 || true)"
  if [ -z "$STATUS_LINE" ]; then
    sleep 10
    continue
  fi

  echo "$STATUS_LINE"
  if echo "$STATUS_LINE" | grep -q 'SUCCESS'; then
    TERMINAL_STATUS="SUCCESS"
    break
  fi
  if echo "$STATUS_LINE" | grep -Eq 'FAILED|CRASHED|REMOVED'; then
    TERMINAL_STATUS="FAILED"
    break
  fi
  sleep 10
done

if [ -z "$TERMINAL_STATUS" ]; then
  echo "Error: timed out waiting for deployment $DEPLOY_ID."
  exit 1
fi

if [ "$TERMINAL_STATUS" != "SUCCESS" ]; then
  echo "Error: deployment $DEPLOY_ID finished in a non-success state."
  exit 1
fi

echo "Deployment completed successfully for $SERVICE_NAME ($DEPLOY_ID)."
