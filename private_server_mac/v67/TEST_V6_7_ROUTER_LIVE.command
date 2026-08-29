#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json,time,urllib.request
q="Tin AI mới nhất hôm nay có gì đáng chú ý?"
body={"model":"dual-brain","messages":[{"role":"user","content":q}],
      "stream":True,"temperature":0.2,"max_tokens":300}
req=urllib.request.Request("http://127.0.0.1:11435/v1/chat/completions",
 data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"})
t0=time.perf_counter(); first=None
with urllib.request.urlopen(req,timeout=45) as r:
    for raw in r:
        s=raw.decode("utf-8","ignore").strip()
        if not s.startswith("data:"): continue
        d=s[5:].strip()
        if d=="[DONE]": break
        try: obj=json.loads(d)
        except: continue
        c=(((obj.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
        if c:
            if first is None: first=time.perf_counter()
            print(c,end="",flush=True)
t1=time.perf_counter()
print()
print("CONTENT_TTFT_MS=",round(((first or t1)-t0)*1000,1))
print("TOTAL_MS=",round((t1-t0)*1000,1))
status=json.load(urllib.request.urlopen("http://127.0.0.1:11435/status"))
for k in ["version","last_route","last_live_used","last_live_kind","last_live_status",
          "last_live_sources","last_live_elapsed_ms","last_live_checked_at"]:
    print(k,"=",status.get(k))
PY
