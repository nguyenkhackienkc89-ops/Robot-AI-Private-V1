#!/bin/bash
set -euo pipefail
MODEL="qwen3.5:35b-a3b-int4"

echo "Robot AI V6.5 - cài Qwen3.5 35B-A3B INT4"
echo "Model: $MODEL"
if ! command -v ollama >/dev/null 2>&1; then
  echo "Chưa có Ollama."
  exit 1
fi

ollama pull "$MODEL"

echo
echo "Test think=false / context 4096..."
curl -fsS http://127.0.0.1:11434/api/chat -d "{
  \"model\":\"$MODEL\",
  \"messages\":[{\"role\":\"user\",\"content\":\"Trả lời đúng bốn chữ: Tiểu Đệ sẵn sàng\"}],
  \"stream\":false,
  \"think\":false,
  \"keep_alive\":\"5m\",
  \"options\":{\"num_ctx\":4096,\"num_predict\":16}
}" | python3 -m json.tool || true

echo
ollama ps || true
