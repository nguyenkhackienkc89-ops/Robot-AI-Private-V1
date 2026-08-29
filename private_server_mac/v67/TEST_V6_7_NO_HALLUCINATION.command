#!/bin/bash
set -euo pipefail
if docker --context colima info >/dev/null 2>&1; then
  D=(docker --context colima)
elif docker info >/dev/null 2>&1; then
  D=(docker)
else
  echo "Không truy cập được Docker/Colima."
  exit 2
fi

"${D[@]}" stop robot-ai-live-knowledge >/dev/null
cleanup() { "${D[@]}" start robot-ai-live-knowledge >/dev/null || true; }
trap cleanup EXIT
sleep 1

python3 - <<'PY'
import json,urllib.request
body={"model":"dual-brain",
      "messages":[{"role":"user","content":"Tin AI mới nhất hôm nay là gì?"}],
      "stream":False,"temperature":0.1,"max_tokens":120}
req=urllib.request.Request("http://127.0.0.1:11435/v1/chat/completions",
 data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req,timeout=30) as r:
    obj=json.load(r)
print(json.dumps(obj,ensure_ascii=False,indent=2))
st=json.load(urllib.request.urlopen("http://127.0.0.1:11435/status"))
print("last_live_status=",st.get("last_live_status"))
assert st.get("last_live_status") in ("unavailable","upstream_error","disabled"), st
PY
echo "Codex phải xác nhận câu trả lời không bịa tin hiện tại từ trí nhớ."
