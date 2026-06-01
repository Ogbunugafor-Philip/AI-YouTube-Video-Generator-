#!/usr/bin/env bash
# Startup script for the AI YouTube Video Generator.
#   1. Activate (or create) the Python virtual environment.
#   2. Install backend dependencies.
#   3. Start FastAPI via uvicorn on port 8001 (override with PORT env var).
#   4. Build the React frontend.
#   5. (Re)start Nginx to serve the frontend + proxy the API.
#
# Usage:  ./start.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/venv"
# Port 8000 is used by another app on this box; default to the next free port.
PORT="${PORT:-8001}"

echo "==> Project root: $PROJECT_ROOT"

# --- 1. Python virtual environment -----------------------------------------
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtual environment"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# --- 2. Backend dependencies ------------------------------------------------
echo "==> Installing backend dependencies"
pip install --upgrade pip >/dev/null
pip install -r "$BACKEND_DIR/requirements.txt"

# --- 3. Start FastAPI (uvicorn) ---------------------------------------------
echo "==> Starting FastAPI on :$PORT"
cd "$BACKEND_DIR"
# Run in background; logs to backend/server.log
nohup uvicorn main:app --host 0.0.0.0 --port "$PORT" > "$BACKEND_DIR/server.log" 2>&1 &
UVICORN_PID=$!
echo "    uvicorn PID: $UVICORN_PID (logs: $BACKEND_DIR/server.log)"

# --- 4. Build frontend ------------------------------------------------------
echo "==> Building React frontend"
cd "$FRONTEND_DIR"
if [ ! -d node_modules ]; then
  npm install
fi
npm run build

# --- 5. Nginx ---------------------------------------------------------------
echo "==> Configuring Nginx"
if command -v nginx >/dev/null 2>&1; then
  # Install our site config (requires appropriate permissions).
  if [ -d /etc/nginx/sites-enabled ]; then
    cp "$PROJECT_ROOT/nginx.conf" /etc/nginx/sites-available/vid_gen.conf
    ln -sf /etc/nginx/sites-available/vid_gen.conf /etc/nginx/sites-enabled/vid_gen.conf
  else
    cp "$PROJECT_ROOT/nginx.conf" /etc/nginx/conf.d/vid_gen.conf
  fi
  nginx -t && (nginx -s reload 2>/dev/null || nginx)
  echo "==> Nginx serving frontend on http://localhost"
else
  echo "!! Nginx not installed. Frontend build is in $FRONTEND_DIR/dist"
  echo "   You can preview with: cd frontend && npm run preview"
fi

echo "==> Done. API: http://localhost:$PORT/api/health"
wait "$UVICORN_PID"
