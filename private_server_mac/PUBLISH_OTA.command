#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_BIN="${1:-}"
VERSION="${2:-}"

if [ -z "$APP_BIN" ] || [ -z "$VERSION" ]; then
  echo "Dùng: ./PUBLISH_OTA.command /duong-dan/xiaozhi.bin 4.0.1"
  exit 1
fi
if [ ! -f "$APP_BIN" ]; then echo "Không thấy file: $APP_BIN"; exit 1; fi
if ! echo "$VERSION" | grep -Eq '^[0-9][0-9A-Za-z._-]*$'; then
  echo "Version không hợp lệ"; exit 1
fi

mkdir -p "$HERE/data/bin"
DEST="$HERE/data/bin/robot-ai-private-v1_${VERSION}.bin"
cp "$APP_BIN" "$DEST"
echo "Đã publish OTA:"
echo "$DEST"
echo
echo "Khởi động lại server để nhận ngay:"
docker restart robot-ai-private-xiaozhi >/dev/null 2>&1 || true
