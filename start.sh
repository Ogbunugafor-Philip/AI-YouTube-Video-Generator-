#!/usr/bin/env bash
# Startup script for the AI YouTube Video Generator.
#   1. Activate (or create) the Python virtual environment.
#   2. Install backend dependencies.
#   3. Start FastAPI under PM2 (autorestart on crash / reboot).
#   4. Install the liveness watchdog cron job (server-down email alerts).
#   5. Build the React frontend.
#   6. (Re)start Nginx to serve the frontend + proxy the API.
#
# Usage:  ./start.sh
# For HTTPS, run:  sudo ./setup_ssl.sh <domain> <email>   (one time)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/venv"
# Port 8000 is used by another app on this box; default to the next free port.
PORT="${PORT:-8003}"

echo "==> Project root: $PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/logs"

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

# --- 3. Start FastAPI under PM2 ---------------------------------------------
echo "==> Starting FastAPI under PM2 on :$PORT"
if command -v pm2 >/dev/null 2>&1; then
  pm2 startOrReload "$PROJECT_ROOT/ecosystem.config.js" --update-env
  pm2 save
  # Make PM2 (and the app) come back automatically after a reboot.
  pm2 startup systemd -u "$(whoami)" --hp "$HOME" >/dev/null 2>&1 || true
  echo "    PM2 managing 'vid-gen-api' (logs: pm2 logs vid-gen-api)"
else
  echo "!! PM2 not installed (npm i -g pm2). Falling back to nohup uvicorn."
  cd "$BACKEND_DIR"
  nohup "$VENV_DIR/bin/uvicorn" main:app --host 0.0.0.0 --port "$PORT" \
    > "$PROJECT_ROOT/logs/api-out.log" 2>&1 &
  echo "    uvicorn PID: $! (logs: logs/api-out.log)"
fi

# --- 4. Install the liveness watchdog cron job ------------------------------
echo "==> Installing watchdog cron (server-down email alerts, every 5 min)"
WATCHDOG_CMD="*/5 * * * * $VENV_DIR/bin/python $BACKEND_DIR/watchdog.py >> $PROJECT_ROOT/logs/watchdog.log 2>&1"
# Idempotent: drop any prior watchdog line, then add the current one.
( crontab -l 2>/dev/null | grep -v "watchdog.py" ; echo "$WATCHDOG_CMD" ) | crontab - \
  && echo "    watchdog cron installed" \
  || echo "!! Could not install cron (no crontab?). Run watchdog.py via your scheduler."

# --- 5. Build frontend ------------------------------------------------------
echo "==> Building React frontend"
cd "$FRONTEND_DIR"
if [ ! -d node_modules ]; then
  npm install
fi
npm run build

# Deploy the build to a www-data-readable location (nginx workers run as
# www-data and cannot read files under /root).
WEB_ROOT="/var/www/vidgen"
echo "==> Deploying frontend to $WEB_ROOT"
mkdir -p "$WEB_ROOT"
rm -rf "${WEB_ROOT:?}/"*
cp -r "$FRONTEND_DIR/dist/." "$WEB_ROOT/"
chmod -R a+rX "$WEB_ROOT"

# --- 6. Nginx ---------------------------------------------------------------
echo "==> Configuring Nginx"
if command -v nginx >/dev/null 2>&1; then
  # If SSL has already been provisioned, leave the HTTPS config in place and
  # just reload; otherwise install the HTTP-only bootstrap config.
  if ls /etc/letsencrypt/live/*/fullchain.pem >/dev/null 2>&1; then
    echo "    SSL certificate detected — keeping existing HTTPS config."
  else
    if [ -d /etc/nginx/sites-enabled ]; then
      cp "$PROJECT_ROOT/nginx.http.conf" /etc/nginx/sites-available/vid_gen.conf
      ln -sf /etc/nginx/sites-available/vid_gen.conf /etc/nginx/sites-enabled/vid_gen.conf
    else
      cp "$PROJECT_ROOT/nginx.http.conf" /etc/nginx/conf.d/vid_gen.conf
    fi
    echo "    Installed HTTP config. For HTTPS run: sudo ./setup_ssl.sh <domain> <email>"
  fi
  nginx -t && (nginx -s reload 2>/dev/null || nginx)
  echo "==> Nginx serving frontend"
else
  echo "!! Nginx not installed. Frontend build is in $FRONTEND_DIR/dist"
  echo "   You can preview with: cd frontend && npm run preview"
fi

echo "==> Done. API health: http://localhost:$PORT/api/health"
echo "    Manage the API with: pm2 status | pm2 logs vid-gen-api | pm2 restart vid-gen-api"
