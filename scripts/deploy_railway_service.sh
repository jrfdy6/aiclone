#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_ROOT="$WORKSPACE_ROOT/.railway-stage"
CANONICAL_DATA_ROOT="${OPENCLAW_WORKSPACE_ROOT:-/Users/neo/.openclaw/workspace}"
DATA_ROOT="$WORKSPACE_ROOT"

if [ -d "$CANONICAL_DATA_ROOT/knowledge/ingestions" ] && [ "$CANONICAL_DATA_ROOT" != "$WORKSPACE_ROOT" ]; then
  DATA_ROOT="$CANONICAL_DATA_ROOT"
fi

usage() {
  cat <<'EOF'
Usage: scripts/deploy_railway_service.sh <frontend|backend>

Stages a small deploy context that preserves the top-level service directory
expected by Railway, then runs `railway up` against that staged path.
EOF
}

rsync_if_exists() {
  local source_path="$1"
  local destination_path="$2"
  if [ -e "$source_path" ]; then
    mkdir -p "$(dirname "$destination_path")"
    rsync -a "$source_path" "$destination_path"
  fi
}

stage_frontend_brain_sources() {
  local target_root="$1"

  rsync_if_exists "$DATA_ROOT/knowledge/aiclone/" "$target_root/knowledge/aiclone/"
  rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/" "$target_root/knowledge/source-intelligence/"
  rsync_if_exists "$DATA_ROOT/knowledge/persona/feeze/" "$target_root/knowledge/persona/feeze/"
  rsync_if_exists "$DATA_ROOT/docs/" "$target_root/docs/"
  rsync_if_exists "$DATA_ROOT/SOPs/" "$target_root/SOPs/"
  for workspace_dir in shared-ops linkedin-content-os fusion-os easyoutfitapp ai-swag-store agc
  do
    rsync_if_exists "$DATA_ROOT/workspaces/$workspace_dir/docs/" "$target_root/workspaces/$workspace_dir/docs/"
    rsync_if_exists "$DATA_ROOT/workspaces/$workspace_dir/analytics/" "$target_root/workspaces/$workspace_dir/analytics/"
  done
  rsync_if_exists "$DATA_ROOT/workspaces/linkedin-content-os/plans/" "$target_root/workspaces/linkedin-content-os/plans/"

  for rel_path in \
    memory/persistent_state.md \
    memory/LEARNINGS.md \
    memory/daily-briefs.md \
    memory/cron-prune.md \
    memory/dream_cycle_log.md \
    memory/codex_session_handoff.jsonl \
    memory/reports/brain_canonical_memory_sync_latest.md
  do
    rsync_if_exists "$DATA_ROOT/$rel_path" "$target_root/$rel_path"
  done

  latest_daily_log="$(find "$DATA_ROOT/memory" -maxdepth 1 -type f -name '????-??-??.md' 2>/dev/null | sort | tail -n 1 || true)"
  if [ -n "$latest_daily_log" ]; then
    rsync_if_exists "$latest_daily_log" "$target_root/memory/$(basename "$latest_daily_log")"
  fi
}

if [ "${1:-}" = "" ]; then
  usage
  exit 1
fi

case "$1" in
  frontend)
    SERVICE_NAME="aiclone-frontend"
    SOURCE_DIR="$WORKSPACE_ROOT/frontend"
    STAGE_DIR="$STAGE_ROOT/frontend-railway-deploy.current"
    CHILD_DIR="frontend"
    RSYNC_EXCLUDES=(--exclude node_modules --exclude .next --exclude .git --exclude tsconfig.tsbuildinfo)
    ;;
  backend)
    SERVICE_NAME="aiclone-backend"
    SOURCE_DIR="$WORKSPACE_ROOT/backend"
    STAGE_DIR="$STAGE_ROOT/backend-railway-deploy.current"
    CHILD_DIR="backend"
    RSYNC_EXCLUDES=(--exclude .git --exclude .env --exclude .env.* --exclude __pycache__ --exclude '*.pyc')
    ;;
  *)
    usage
    exit 1
    ;;
esac

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR/$CHILD_DIR"
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SOURCE_DIR/" "$STAGE_DIR/$CHILD_DIR/"

if [ "$SERVICE_NAME" = "aiclone-frontend" ]; then
  stage_frontend_brain_sources "$STAGE_DIR"
  stage_frontend_brain_sources "$STAGE_DIR/$CHILD_DIR"
fi

if [ "$SERVICE_NAME" = "aiclone-backend" ]; then
  INGEST_RSYNC_EXCLUDES=(
    --exclude raw/
    --exclude '*/raw/'
    --exclude '*.webm'
    --exclude '*.mp4'
    --exclude '*.mov'
    --exclude '*.m4a'
    --exclude '*.wav'
    --exclude '*.mp3'
  )
  mkdir -p "$STAGE_DIR/knowledge/persona" "$STAGE_DIR/knowledge/aiclone" "$STAGE_DIR/knowledge/ingestions" "$STAGE_DIR/workspaces" "$STAGE_DIR/scripts"
  mkdir -p "$STAGE_DIR/$CHILD_DIR/knowledge/persona" "$STAGE_DIR/$CHILD_DIR/knowledge/aiclone" "$STAGE_DIR/$CHILD_DIR/knowledge/ingestions" "$STAGE_DIR/$CHILD_DIR/workspaces" "$STAGE_DIR/$CHILD_DIR/scripts"
  mkdir -p "$STAGE_DIR/$CHILD_DIR/app/knowledge/persona" "$STAGE_DIR/$CHILD_DIR/app/knowledge/source-intelligence"
  mkdir -p "$STAGE_DIR/$CHILD_DIR/SOPs" "$STAGE_DIR/$CHILD_DIR/deliverables" "$STAGE_DIR/$CHILD_DIR/docs"
  rsync_if_exists "$DATA_ROOT/knowledge/persona/feeze/" "$STAGE_DIR/knowledge/persona/feeze/"
  rsync_if_exists "$DATA_ROOT/knowledge/persona/feeze/" "$STAGE_DIR/$CHILD_DIR/knowledge/persona/feeze/"
  rsync_if_exists "$DATA_ROOT/knowledge/persona/feeze/" "$STAGE_DIR/$CHILD_DIR/app/knowledge/persona/feeze/"
  rsync_if_exists "$DATA_ROOT/knowledge/aiclone/transcripts/" "$STAGE_DIR/knowledge/aiclone/transcripts/"
  rsync_if_exists "$DATA_ROOT/knowledge/aiclone/transcripts/" "$STAGE_DIR/$CHILD_DIR/knowledge/aiclone/transcripts/"
  rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/" "$STAGE_DIR/knowledge/source-intelligence/"
  rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/" "$STAGE_DIR/$CHILD_DIR/knowledge/source-intelligence/"
  rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/" "$STAGE_DIR/$CHILD_DIR/app/knowledge/source-intelligence/"
  if [ -d "$DATA_ROOT/knowledge/ingestions" ]; then
    rsync -a "${INGEST_RSYNC_EXCLUDES[@]}" "$DATA_ROOT/knowledge/ingestions/" "$STAGE_DIR/knowledge/ingestions/"
    rsync -a "${INGEST_RSYNC_EXCLUDES[@]}" "$DATA_ROOT/knowledge/ingestions/" "$STAGE_DIR/$CHILD_DIR/knowledge/ingestions/"
  fi
  for workspace_dir in shared-ops linkedin-content-os fusion-os easyoutfitapp ai-swag-store agc
  do
    rsync_if_exists "$DATA_ROOT/workspaces/$workspace_dir/" "$STAGE_DIR/workspaces/$workspace_dir/"
    rsync_if_exists "$DATA_ROOT/workspaces/$workspace_dir/" "$STAGE_DIR/$CHILD_DIR/workspaces/$workspace_dir/"
  done
  rsync_if_exists "$DATA_ROOT/scripts/personal-brand/" "$STAGE_DIR/scripts/personal-brand/"
  rsync_if_exists "$DATA_ROOT/scripts/personal-brand/" "$STAGE_DIR/$CHILD_DIR/scripts/personal-brand/"
  rsync_if_exists "$DATA_ROOT/SOPs/" "$STAGE_DIR/$CHILD_DIR/SOPs/"
  rsync_if_exists "$DATA_ROOT/deliverables/" "$STAGE_DIR/$CHILD_DIR/deliverables/"
  if [ -f "$DATA_ROOT/docs/persistent_memory_blueprint.md" ]; then
    rsync -a "$DATA_ROOT/docs/persistent_memory_blueprint.md" "$STAGE_DIR/$CHILD_DIR/docs/persistent_memory_blueprint.md"
  fi
fi

echo "Staged deploy context:"
du -sh "$STAGE_DIR"
echo "Deploy mode: local staged context via railway CLI (independent of GitHub webhook timing)."
if [ "$DATA_ROOT" != "$WORKSPACE_ROOT" ]; then
  echo "Data root: $DATA_ROOT"
fi

cd "$WORKSPACE_ROOT"
REL_STAGE_DIR="${STAGE_DIR#$WORKSPACE_ROOT/}"
UP_OUTPUT="$(railway up -s "$SERVICE_NAME" --path-as-root "$REL_STAGE_DIR" --verbose 2>&1)"
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
