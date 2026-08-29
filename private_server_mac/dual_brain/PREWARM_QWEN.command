#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV="$HERE/.env"
[ -f "$ENV" ] || cp "$HERE/.env.example" "$ENV"

python3 - "$ENV" <<'PY'
import json, sys, time, urllib.request
from pathlib import Path

env={}
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line=raw.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k,v=line.split("=",1); env[k.strip()]=v.strip()

root=env.get("LOCAL_BASE_URL","http://127.0.0.1:11434/v1").rstrip("/")
if root.endswith("/v1"): root=root[:-3]
root=root.rstrip("/")
if "host.docker.internal" in root:
    root=root.replace("host.docker.internal","127.0.0.1")

def get(url):
    with urllib.request.urlopen(url,timeout=5) as r:
        return json.loads(r.read().decode())

model=env.get("LOCAL_MODEL","auto")
if not model or model.lower()=="auto":
    installed=[x.get("name") or x.get("model") for x in get(root+"/api/tags").get("models",[])]
    candidates=[x.strip() for x in env.get("LOCAL_MODEL_CANDIDATES","tieude:qwen3-8b,qwen3:8b").split(",") if x.strip()]
    model=next((c for c in candidates if c in installed), candidates[0])

payload={
  "model":model,
  "messages":[{"role":"user","content":"Trả lời đúng hai chữ: sẵn sàng"}],
  "stream":False,
  "think":False,
  "keep_alive":env.get("LOCAL_KEEP_ALIVE","30m"),
  "options":{"num_predict":8}
}
data=json.dumps(payload,ensure_ascii=False).encode()
req=urllib.request.Request(root+"/api/chat",data=data,headers={"Content-Type":"application/json"})
t=time.perf_counter()
with urllib.request.urlopen(req,timeout=90) as r:
    obj=json.loads(r.read().decode())
elapsed=(time.perf_counter()-t)*1000
print("Model:",model)
print("Warm-up:",round(elapsed),"ms")
print("Load:",round((obj.get("load_duration") or 0)/1e6),"ms")
print("Nội dung:",(obj.get("message") or {}).get("content",""))
PY
