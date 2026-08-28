#!/usr/bin/env bash
set -euo pipefail

MODEL="${LOCAL_MODEL:-tieude:qwen3-8b}"

curl -fsS http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"$MODEL\",
    \"messages\":[{\"role\":\"user\",\"content\":\"Chào Tiểu Đệ, trả lời một câu thật ngắn.\"}],
    \"stream\":false,
    \"think\":false,
    \"keep_alive\":\"30m\"
  }" >/dev/null

echo "Qwen warmed: $MODEL, keep_alive=30m"
