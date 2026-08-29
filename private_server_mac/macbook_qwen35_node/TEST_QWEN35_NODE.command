#!/bin/bash
set -euo pipefail
MODEL="${1:-qwen3.5:35b-a3b-int4}"
python3 - "$MODEL" <<'PY'
import json,time,urllib.request,sys
model=sys.argv[1]
body={
 "model":model,
 "messages":[{"role":"user","content":"Phân tích trong tối đa 120 từ: vì sao doanh nghiệp cần lợi thế cạnh tranh?"}],
 "stream":True,
 "think":False,
 "keep_alive":"5m",
 "options":{"num_ctx":4096,"num_predict":180}
}
req=urllib.request.Request(
 "http://127.0.0.1:11434/api/chat",
 data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"}
)
t0=time.perf_counter(); first=None; chunks=0; final={}
with urllib.request.urlopen(req,timeout=180) as r:
    for raw in r:
        if not raw.strip(): continue
        obj=json.loads(raw); final=obj
        c=(obj.get("message") or {}).get("content") or ""
        if c:
            if first is None: first=time.perf_counter()
            chunks+=1; print(c,end="",flush=True)
        if obj.get("done"): break
t1=time.perf_counter()
ec=int(final.get("eval_count") or 0)
ens=int(final.get("eval_duration") or 0)
tps=ec/(ens/1e9) if ec and ens else 0
print()
print("TTFT:",round(((first or t1)-t0)*1000),"ms")
print("TOTAL:",round((t1-t0)*1000),"ms")
print("CHUNKS:",chunks)
print("TOK/S:",round(tps,2))
print("LOAD:",round((final.get("load_duration") or 0)/1e6),"ms")
PY
echo
ollama ps || true
