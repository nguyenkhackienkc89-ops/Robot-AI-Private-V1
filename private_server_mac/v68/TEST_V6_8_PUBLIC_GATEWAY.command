#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../anywhere_gateway" && pwd)"
ENV="$HERE/.env"

[ -f "$ENV" ] || { echo "Missing $ENV"; exit 1; }
set -a; source "$ENV"; set +a

: "${ANYWHERE_PUBLIC_HOST:?Set ANYWHERE_PUBLIC_HOST in .env}"
: "${ROBOT_GATEWAY_SECRET:?Run render_gateway.py}"

BASE="https://${ANYWHERE_PUBLIC_HOST}/r/${ROBOT_GATEWAY_SECRET}"

echo "Local gateway:"
curl --noproxy '*' -fsS http://127.0.0.1:11438/healthz
echo

echo "Public health:"
curl -fsS "https://${ANYWHERE_PUBLIC_HOST}/healthz"
echo

echo "Public OTA GET:"
curl -fsS "${BASE}/xiaozhi/ota/"
echo

echo "Expected WS URL:"
echo "wss://${ANYWHERE_PUBLIC_HOST}/r/${ROBOT_GATEWAY_SECRET}/xiaozhi/v1/"
echo
echo "Use a real ESP32 or websocket client with XiaoZhi headers for full handshake test."
