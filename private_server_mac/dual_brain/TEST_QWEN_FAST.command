#!/usr/bin/env bash
set -euo pipefail

MODEL="${LOCAL_MODEL:-tieude:qwen3-8b}"
TMP="${TMPDIR:-/tmp}/robot-qwen-fast.json"

curl -fsS http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"$MODEL\",
    \"messages\":[{\"role\":\"user\",\"content\":\"Tôi có 100 triệu đồng và muốn mở thương hiệu mỹ phẩm tại Việt Nam. Chọn một sản phẩm nên bắt đầu, phân bổ 100 triệu và nêu 3 rủi ro lớn nhất. Trả lời ngắn, thực tế.\"}],
    \"stream\":false,
    \"think\":false,
    \"keep_alive\":\"30m\"
  }" > "$TMP"

python3 - "$TMP" <<'PY'
import json, sys

d=json.load(open(sys.argv[1], encoding="utf-8"))
msg=d.get("message", {})
eval_ns=d.get("eval_duration") or 0
eval_count=d.get("eval_count") or 0
tok_s=round(eval_count/(eval_ns/1e9), 2) if eval_ns else 0

print("Model:", d.get("model"))
print("think:false:", "YES" if "thinking" not in msg and "reasoning" not in msg else "NO")
print("Wall:", round((d.get("total_duration") or 0)/1e6, 1), "ms")
print("Load:", round((d.get("load_duration") or 0)/1e6, 1), "ms")
print("Speed:", tok_s, "tok/s")
print()
print(msg.get("content", "").strip())
PY
