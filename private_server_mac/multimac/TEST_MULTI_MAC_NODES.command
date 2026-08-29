#!/bin/bash
set -euo pipefail

echo "===== MAC MINI 9B ====="
curl -fsS http://127.0.0.1:11434/api/tags | grep -Eo '"name":"[^"]+"' | grep -E 'qwen3\.5|qwen3' || true

echo
echo "===== MACBOOK 35B VIA TUNNEL ====="
curl -fsS http://127.0.0.1:11436/api/tags | grep -Eo '"name":"[^"]+"' | grep -Ei '35b' || true

echo
echo "===== ROUTER ====="
curl -fsS http://127.0.0.1:11435/status | python3 -m json.tool
