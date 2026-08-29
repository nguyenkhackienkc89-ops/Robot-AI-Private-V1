#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
AG="$HERE/anywhere_gateway"
CFG="$HERE/data/.config.yaml"
COMPOSE="$HERE/docker-compose.yml"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HERE/backups/v68-$STAMP"
mkdir -p "$BACKUP"
cp "$CFG" "$BACKUP/.config.yaml" 2>/dev/null || true
cp "$COMPOSE" "$BACKUP/docker-compose.yml" 2>/dev/null || true
cp "$AG/.env" "$BACKUP/anywhere.env" 2>/dev/null || true

python3 "$AG/render_gateway.py"

if [ ! -f "$AG/.env" ]; then exit 2; fi
set -a; source "$AG/.env"; set +a
: "${ANYWHERE_PUBLIC_HOST:?Set ANYWHERE_PUBLIC_HOST after Funnel/Tunnel setup}"

python3 "$HERE/v68/MERGE_COMPOSE_V68.py" "$COMPOSE"
python3 "$AG/patch_public_server_config.py" "$CFG" "$ANYWHERE_PUBLIC_HOST"

if docker info >/dev/null 2>&1; then
  DC=(docker compose)
elif docker --context colima info >/dev/null 2>&1; then
  DC=(docker --context colima compose)
else
  echo "Docker/Colima context unavailable. Do not restart all Colima."
  exit 3
fi

cd "$HERE"
"${DC[@]}" up -d anywhere-gateway
sleep 2
curl --noproxy '*' -fsS http://127.0.0.1:11438/healthz

# Recreate only XiaoZhi because websocket/auth config changed.
"${DC[@]}" up -d --force-recreate xiaozhi-private
sleep 5

echo
echo "XiaoZhi OTA local:"
curl --noproxy '*' -fsS http://127.0.0.1:8003/xiaozhi/ota/
echo
echo "Backup: $BACKUP"
echo "No router / Qwen / tunnel-31434 restart performed."
