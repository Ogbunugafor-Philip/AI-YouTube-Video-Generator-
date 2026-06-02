#!/usr/bin/env bash
# Provision Let's Encrypt SSL for the AI YouTube Video Generator.
#
# Usage:
#   sudo ./setup_ssl.sh your-domain.com you@example.com
#
# Flow (conflict-free on multi-site boxes):
#   1. Install certbot if missing.
#   2. Install a domain-scoped HTTP-only site that serves the ACME http-01
#      challenge (and the app) on port 80.
#   3. Run certbot (webroot) to obtain the real certificate.
#   4. Install the HTTPS site (nginx.conf template) and reload nginx.
#   5. Auto-renewal is handled by certbot's systemd timer.
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBROOT="/var/www/certbot"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "Usage: sudo ./setup_ssl.sh <domain> <email>"
  exit 1
fi

echo "==> Domain: $DOMAIN  Email: $EMAIL"

site_path() {
  # Echo where this box keeps nginx site configs.
  if [ -d /etc/nginx/sites-enabled ]; then echo "/etc/nginx/sites-available/vid_gen.conf"
  else echo "/etc/nginx/conf.d/vid_gen.conf"; fi
}

install_site() {
  # $1 = source config file (already domain-substituted)
  local dest; dest="$(site_path)"
  cp "$1" "$dest"
  if [ -d /etc/nginx/sites-enabled ]; then
    ln -sf "$dest" /etc/nginx/sites-enabled/vid_gen.conf
  fi
}

# --- 1. certbot -------------------------------------------------------------
if ! command -v certbot >/dev/null 2>&1; then
  echo "==> Installing certbot"
  apt-get update -y && apt-get install -y certbot
fi
mkdir -p "$WEBROOT"

# --- 2. HTTP-only site (serves ACME challenge), domain-scoped ---------------
echo "==> Installing temporary HTTP site for the ACME challenge"
HTTP_RENDERED="/tmp/vid_gen_http.conf"
sed "s/server_name _;/server_name $DOMAIN;/" "$PROJECT_ROOT/nginx.http.conf" > "$HTTP_RENDERED"
install_site "$HTTP_RENDERED"
nginx -t && (nginx -s reload 2>/dev/null || systemctl reload nginx || nginx)

# --- 3. Obtain the real certificate -----------------------------------------
echo "==> Requesting Let's Encrypt certificate"
certbot certonly --webroot -w "$WEBROOT" \
  -d "$DOMAIN" \
  --email "$EMAIL" --agree-tos --non-interactive --keep-until-expiring \
  --cert-name "$DOMAIN"

# --- 4. Install the HTTPS site ----------------------------------------------
echo "==> Installing HTTPS site config"
SSL_RENDERED="/tmp/vid_gen_ssl.conf"
sed "s/__DOMAIN__/$DOMAIN/g" "$PROJECT_ROOT/nginx.conf" > "$SSL_RENDERED"
install_site "$SSL_RENDERED"
nginx -t && (nginx -s reload 2>/dev/null || systemctl reload nginx)

echo "==> SSL is live: https://$DOMAIN"
echo "==> Auto-renewal is handled by certbot's systemd timer (certbot.timer)."
echo "    Verify with: systemctl list-timers | grep certbot"
