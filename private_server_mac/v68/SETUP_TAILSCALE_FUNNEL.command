#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../anywhere_gateway" && pwd)"

echo "======================================================="
echo " Robot AI V6.8 - Tailscale Funnel setup"
echo "======================================================="

if ! command -v tailscale >/dev/null 2>&1; then
  echo "Chưa có Tailscale CLI."
  echo "Trên macOS Funnel cần bản Tailscale có CLI phù hợp."
  echo "Codex: cài bản chính thức/open-source phù hợp, sau đó tailscale up."
  exit 2
fi

tailscale status >/dev/null 2>&1 || {
  echo "Tailscale chưa đăng nhập/online. Chạy: tailscale up"
  exit 3
}

python3 "$HERE/render_gateway.py"

echo "Starting persistent Funnel for localhost:11438..."
tailscale funnel --bg 11438

echo
tailscale funnel status || true
echo
echo "Lấy hostname HTTPS ở output trên."
echo "Ghi hostname (không https://) vào:"
echo "  $HERE/.env"
echo "dòng:"
echo "  ANYWHERE_PUBLIC_HOST=<hostname.ts.net>"
echo "rồi chạy lại render_gateway.py."
