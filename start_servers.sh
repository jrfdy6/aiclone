#!/bin/bash
set -euo pipefail

ROOT="/Users/johnniefields/Desktop/Cursor/aiclone"
FRONTEND_PORT=3000
BACKEND_PORT=3001
BACKEND_LOG="$ROOT/backend/server.log"
FRONTEND_LOG="$ROOT/frontend/server.log"

kill_port() {
  local port=$1
  if lsof -ti :"$port" > /dev/null; then
    echo "Stopping processes on port $port"
    lsof -ti :"$port" | xargs kill -9
  fi
}

kill_port "$FRONTEND_PORT"
kill_port "$BACKEND_PORT"

cd "$ROOT"
source .venv/bin/activate
set -a
source backend/.env
set +a

mkdir -p backend frontend
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

(cd backend && nohup uvicorn app.main:app --port $BACKEND_PORT --reload > "$BACKEND_LOG" 2>&1 &)
(cd frontend && nohup npm run dev -- --port $FRONTEND_PORT > "$FRONTEND_LOG" 2>&1 &)

echo "Backend running on http://127.0.0.1:$BACKEND_PORT"
echo "Frontend running on http://localhost:$FRONTEND_PORT"
