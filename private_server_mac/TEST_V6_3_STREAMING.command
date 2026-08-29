#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json,time,urllib.request

url="http://127.0.0.1:11435/v1/chat/completions"
body={
 "model":"dual-brain",
 "messages":[{"role":"user","content":"Chào Tiểu Đệ, trả lời một câu thật ngắn."}],
 "stream":True,
 "temperature":0.2,
 "max_tokens":80
}
req=urllib.request.Request(
 url,data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json","Accept":"text/event-stream"}
)
t0=time.perf_counter(); first=None; chunks=0
with urllib.request.urlopen(req,timeout=90) as r:
    for raw in r:
        line=raw.decode("utf-8","replace").strip()
        if not line.startswith("data:"): continue
        data=line[5:].strip()
        if data=="[DONE]": break
        try: obj=json.loads(data)
        except: continue
        delta=((obj.get("choices") or [{}])[0].get("delta") or {})
        if delta.get("content") or delta.get("tool_calls"):
            if first is None:
                first=time.perf_counter()
            chunks+=1
            if delta.get("content"):
                print(delta["content"],end="",flush=True)
print()
t1=time.perf_counter()
print("TTFT:", round(((first or t1)-t0)*1000),"ms")
print("TOTAL:",round((t1-t0)*1000),"ms")
print("CHUNKS:",chunks)
PY
