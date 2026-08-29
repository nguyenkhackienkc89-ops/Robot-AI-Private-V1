#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json,time,urllib.request
url="http://127.0.0.1:11435/v1/chat/completions"
body={
 "model":"dual-brain",
 "messages":[{"role":"user","content":"dừng"}],
 "stream":True,
 "tools":[{
   "type":"function",
   "function":{
     "name":"self.robot.motion",
     "description":"Điều khiển motor",
     "parameters":{
       "type":"object",
       "properties":{"action":{"type":"string"}},
       "required":["action"]
     }
   }
 }]
}
req=urllib.request.Request(
 url,data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json","Accept":"text/event-stream"}
)
t0=time.perf_counter(); found=None
with urllib.request.urlopen(req,timeout=10) as r:
    for raw in r:
        line=raw.decode().strip()
        if not line.startswith("data:"): continue
        data=line[5:].strip()
        if data=="[DONE]": break
        obj=json.loads(data)
        delta=((obj.get("choices") or [{}])[0].get("delta") or {})
        if delta.get("tool_calls"):
            found=delta["tool_calls"][0]
            break
elapsed=(time.perf_counter()-t0)*1000
print("FAST TOOL:", json.dumps(found,ensure_ascii=False))
print("ROUTER LATENCY:",round(elapsed),"ms")
assert found and found["function"]["name"]=="self.robot.motion"
assert json.loads(found["function"]["arguments"])["action"]=="stop"
PY
