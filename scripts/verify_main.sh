#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[1/4] Neo retrieval, privacy, recovery, and worker tests"
PYTHONPATH="$ROOT/backend" "$PYTHON_BIN" -m pytest \
  "$ROOT/backend/tests/test_neo_public_knowledge_service.py" \
  "$ROOT/backend/tests/test_neo_guest_security.py" \
  "$ROOT/backend/tests/test_neo_guest_job_recovery.py" \
  -q

echo "[2/4] Public knowledge pack validation"
PYTHONPATH="$ROOT/backend" "$PYTHON_BIN" - <<'PY'
from app.services.neo_public_knowledge_service import load_public_knowledge_pack

pack = load_public_knowledge_pack()
assert pack["review_status"] == "approved_public"
assert all(entry["review_status"] == "approved_public" for entry in pack["entries"])
print(f"approved pack {pack['pack_version']} with {len(pack['entries'])} entries")
PY

echo "[3/4] Frontend contract tests"
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "frontend/node_modules missing. Run: npm --prefix frontend ci" >&2
  exit 1
fi
npm --prefix "$ROOT/frontend" test

echo "[4/4] Frontend production build"
npm --prefix "$ROOT/frontend" run build

echo "Fellowship release verification passed"
