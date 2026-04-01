#!/usr/bin/env bash
set -euo pipefail

cd /Users/neo/.openclaw/workspace
python3 scripts/runners/write_execution_result.py "$@"
