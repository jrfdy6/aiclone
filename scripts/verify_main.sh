#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
GENERATED_FILES=(
  "frontend/app/brain/workspaceSnapshot.ts"
  "frontend/legacy/content-pipeline/workspaceSnapshot.ts"
)
RESTORE_AFTER_VERIFY=()

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$ROOT/.venv-main-safe/bin/python" ]; then
    PYTHON_BIN="$ROOT/.venv-main-safe/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

prepare_cleanup() {
  local path
  for path in "${GENERATED_FILES[@]}"; do
    if git -C "$ROOT" diff --quiet -- "$path"; then
      RESTORE_AFTER_VERIFY+=("$path")
    fi
  done
}

cleanup_generated_files() {
  if [ "${#RESTORE_AFTER_VERIFY[@]}" -eq 0 ]; then
    return
  fi
  local path
  for path in "${RESTORE_AFTER_VERIFY[@]}"; do
    git -C "$ROOT" restore --worktree -- "$path" >/dev/null 2>&1 || true
  done
}

prepare_cleanup
trap cleanup_generated_files EXIT

require_python_module() {
  local module="$1"
  if ! "$PYTHON_BIN" - <<PY >/dev/null 2>&1
import ${module}
PY
  then
    echo "Missing Python dependency: ${module}" >&2
    echo "Install backend requirements first: pip install -r backend/requirements.txt" >&2
    exit 1
  fi
}

echo "[1/6] Backend workspace smoke tests"
require_python_module fastapi
require_python_module requests
PYTHONPATH="$ROOT/backend" "$PYTHON_BIN" -m unittest backend.tests.test_workspace_smoke

echo "[2/6] Persona bundle health"
"$PYTHON_BIN" "$ROOT/scripts/persona/bundle_health_check.py"

echo "[3/6] Frontend production build"
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "frontend/node_modules missing. Run: npm --prefix frontend ci" >&2
  exit 1
fi
npm --prefix "$ROOT/frontend" run build

echo "[4/6] Repo hygiene"
"$PYTHON_BIN" "$ROOT/scripts/verify_repo_hygiene.py"

echo "[5/6] Repo surface truth"
"$PYTHON_BIN" "$ROOT/scripts/verify_repo_surface_truth.py"

echo "[6/6] Working tree sanity"
git -C "$ROOT" status --short

echo
echo "verify_main.sh passed"
