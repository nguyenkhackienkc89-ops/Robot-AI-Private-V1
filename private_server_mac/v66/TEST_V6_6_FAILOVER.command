#!/bin/bash
set -euo pipefail

ROUTER="http://127.0.0.1:11435"
TUNNEL_PORT=31434

echo "========================================================"
echo " V6.6 FAILOVER BENCH"
echo "========================================================"

echo "1) Trạng thái hiện tại:"
curl --noproxy '*' -fsS "$ROUTER/status" | python3 -m json.tool

echo
echo "2) Deep online test:"
python3 - <<'PY'
import json,time,urllib.request
body={
 "model":"dual-brain",
 "messages":[{"role":"user","content":"Phân tích sâu trong đúng một câu: vì sao doanh nghiệp cần dòng tiền?"}],
 "stream":True,
 "temperature":0.2,
 "max_tokens":80,
}
req=urllib.request.Request("http://127.0.0.1:11435/v1/chat/completions",
 data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"})
t0=time.perf_counter(); first=None; route=None
with urllib.request.urlopen(req,timeout=30) as r:
    for raw in r:
        s=raw.decode("utf-8","ignore").strip()
        if not s.startswith("data:"): continue
        d=s[5:].strip()
        if d=="[DONE]": break
        try: obj=json.loads(d)
        except: continue
        c=((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
        if c and first is None:
            first=time.perf_counter()
print("ONLINE_FIRST_CONTENT_MS=",round(((first or time.perf_counter())-t0)*1000))
PY

echo
echo "3) Để test tunnel-down an toàn:"
echo "   launchctl bootout gui/$(id -u)/com.robotai.qwen35-tunnel"
echo "   chạy lại script này với biến TEST_OFFLINE=1"
echo "   sau test bật lại:"
echo "   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.robotai.qwen35-tunnel.plist"
echo

if [ "${TEST_OFFLINE:-0}" = "1" ]; then
python3 - <<'PY'
import json,time,urllib.request
body={
 "model":"dual-brain",
 "messages":[{"role":"user","content":"Phân tích sâu trong đúng một câu: vì sao doanh nghiệp cần dòng tiền?"}],
 "stream":True,
 "temperature":0.2,
 "max_tokens":80,
}
req=urllib.request.Request("http://127.0.0.1:11435/v1/chat/completions",
 data=json.dumps(body,ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"})
t0=time.perf_counter(); first=None
with urllib.request.urlopen(req,timeout=30) as r:
    for raw in r:
        s=raw.decode("utf-8","ignore").strip()
        if not s.startswith("data:"): continue
        d=s[5:].strip()
        if d=="[DONE]": break
        try: obj=json.loads(d)
        except: continue
        c=((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
        if c and first is None:
            first=time.perf_counter()
t1=time.perf_counter()
print("OFFLINE_FIRST_CONTENT_MS=",round(((first or t1)-t0)*1000))
status=json.load(urllib.request.urlopen("http://127.0.0.1:11435/status"))
print("ROUTE=",status.get("last_route"))
print("DEEP_FAILOVER_MS=",status.get("last_deep_failover_ms"))
print("DEEP_HEALTH=",status.get("deep_health"))
PY
fi
