#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${OPENCLAW_WORKSPACE:-/Users/neo/.openclaw/workspace}"
OPENCLAW_ROOT="${OPENCLAW_ROOT:-/Users/neo/.openclaw}"
REPO_ROOT="$WORKSPACE_ROOT"
SNAPSHOT_POINTER="$WORKSPACE_ROOT/docs/runtime_snapshots/core_memory/LATEST.json"
CLEAN_TAG="clean-main-2026-04-08"

usage() {
  cat <<'EOF'
Operator baseline routine

Usage:
  scripts/operator_baseline_routine.sh status
  scripts/operator_baseline_routine.sh snapshot [snapshot_id]
  scripts/operator_baseline_routine.sh runtime-hashes
  scripts/operator_baseline_routine.sh restore-memory [snapshot_id]
  scripts/operator_baseline_routine.sh health
  scripts/operator_baseline_routine.sh restore-guide

Commands:
  status         Show branch, head commit, latest core-memory snapshot, and working tree summary.
  snapshot       Capture a tracked core-memory snapshot for today or the supplied snapshot_id.
  runtime-hashes Print SHA-256 hashes for the non-git OpenClaw runtime files.
  restore-memory Restore the live memory lane from the latest or supplied tracked snapshot.
  health         Run the core runtime health checks used by the restore SOP.
  restore-guide  Print the exact restore commands for the clean baseline.
EOF
}

latest_snapshot_id() {
  python3 - "$SNAPSHOT_POINTER" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except json.JSONDecodeError:
    raise SystemExit(0)
snapshot_id = payload.get("snapshot_id")
if isinstance(snapshot_id, str) and snapshot_id.strip():
    print(snapshot_id.strip())
PY
}

status_cmd() {
  local branch head snapshot_id
  branch="$(git -C "$REPO_ROOT" branch --show-current)"
  head="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  snapshot_id="$(latest_snapshot_id || true)"

  printf 'Operator Baseline Status\n'
  printf '  branch: %s\n' "${branch:-detached}"
  printf '  head: %s\n' "$head"
  printf '  clean_tag: %s\n' "$CLEAN_TAG"
  printf '  latest_snapshot: %s\n' "${snapshot_id:-none}"
  printf '  runtime_note: %s\n' "$WORKSPACE_ROOT/docs/openclaw_runtime_backup_2026-04-08.md"
  printf '\nWorking tree summary:\n'
  git -C "$REPO_ROOT" status --short | sed -n '1,20p'
}

snapshot_cmd() {
  local snapshot_id
  snapshot_id="${1:-$(date -u +%F)}"
  python3 "$WORKSPACE_ROOT/scripts/build_core_memory_snapshot.py" --snapshot-id "$snapshot_id"
  printf '\nNext:\n'
  printf '  git -C %s add docs/runtime_snapshots/core_memory\n' "$REPO_ROOT"
  printf "  git -C %s commit -m 'Update core memory snapshot %s'\n" "$REPO_ROOT" "$snapshot_id"
  printf '  git -C %s push origin main\n' "$REPO_ROOT"
}

runtime_hashes_cmd() {
  shasum -a 256 \
    "$OPENCLAW_ROOT/openclaw.json" \
    "$OPENCLAW_ROOT/cron/jobs.json" \
    "$OPENCLAW_ROOT/agents/main/qmd/xdg-config/qmd/index.yml"
}

restore_memory_cmd() {
  if [[ $# -gt 0 ]]; then
    python3 "$WORKSPACE_ROOT/scripts/restore_core_memory_snapshot.py" --snapshot-id "$1"
  else
    python3 "$WORKSPACE_ROOT/scripts/restore_core_memory_snapshot.py"
  fi
}

health_cmd() {
  printf 'qmd search\n'
  qmd search 'Codex handoff' -c memory-dir-main -n 3 | sed -n '1,20p'
  printf '\ncontext usage\n'
  python3 "$WORKSPACE_ROOT/scripts/context_usage.py"
  printf '\nheartbeat report\n'
  python3 "$WORKSPACE_ROOT/scripts/heartbeat_report.py"
}

restore_guide_cmd() {
  cat <<EOF
git fetch origin --tags
git switch -c restore-clean-main $CLEAN_TAG
python3 $WORKSPACE_ROOT/scripts/restore_core_memory_snapshot.py
shasum -a 256 $OPENCLAW_ROOT/openclaw.json
shasum -a 256 $OPENCLAW_ROOT/cron/jobs.json
shasum -a 256 $OPENCLAW_ROOT/agents/main/qmd/xdg-config/qmd/index.yml
openclaw gateway stop
openclaw gateway start
EOF
}

main() {
  local command="${1:-status}"
  shift || true
  case "$command" in
    status) status_cmd "$@" ;;
    snapshot) snapshot_cmd "$@" ;;
    runtime-hashes) runtime_hashes_cmd "$@" ;;
    restore-memory) restore_memory_cmd "$@" ;;
    health) health_cmd "$@" ;;
    restore-guide) restore_guide_cmd "$@" ;;
    help|-h|--help) usage ;;
    *)
      printf 'Unknown command: %s\n\n' "$command" >&2
      usage >&2
      return 1
      ;;
  esac
}

main "$@"
