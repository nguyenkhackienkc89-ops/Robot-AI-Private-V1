#!/bin/bash
set -euo pipefail
MODE="${1:-}"
if [[ ! "$MODE" =~ ^(local|cloud|auto|council)$ ]]; then
  echo "Dùng: ./BRAIN_MODE.command local|cloud|auto|council"
  exit 1
fi
curl -fsS -X POST -H 'Content-Type: application/json' \
  -d "{\"mode\":\"$MODE\"}" http://127.0.0.1:11435/mode
echo
