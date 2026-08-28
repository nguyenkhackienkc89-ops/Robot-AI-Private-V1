#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
echo "=== Containers ==="
docker compose ps
echo
echo "=== XiaoZhi logs (last 40 lines) ==="
docker logs --tail 40 robot-ai-private-xiaozhi 2>&1 || true
echo
echo "=== Ollama ==="
curl -fsS http://127.0.0.1:11434/api/tags || true
echo
echo "=== OTA ==="
curl -fsS http://127.0.0.1:8003/xiaozhi/ota/ || true
echo
