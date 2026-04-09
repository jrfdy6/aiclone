#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${UPDATE_ROADMAP_PYTHON:-python3}"

exec "$PYTHON_BIN" "$ROOT/scripts/update_roadmap.py" "$@"
