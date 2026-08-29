#!/bin/bash
set -euo pipefail
FILE="$(cd "$(dirname "$0")/.." && pwd)/data/tts_latency_v66.jsonl"
if [ ! -f "$FILE" ]; then
  echo "Chưa có $FILE"
  exit 1
fi

python3 - "$FILE" <<'PY'
import json,sys,statistics
rows=[]
for line in open(sys.argv[1],encoding="utf-8"):
    try: rows.append(json.loads(line))
    except: pass
print("records:",len(rows))
for key in [
 "tts_first_to_ack_opus_ms",
 "tts_first_to_edge_start_ms",
 "tts_first_to_edge_audio_ms",
 "tts_first_to_pcm_ms",
 "tts_first_to_opus_ms",
]:
    vals=[float(r[key]) for r in rows if r.get(key) is not None]
    if vals:
        vals.sort()
        p50=statistics.median(vals)
        p95=vals[min(len(vals)-1,max(0,int(len(vals)*0.95)-1))]
        print(f"{key}: last={vals[-1]:.1f}ms p50={p50:.1f}ms p95={p95:.1f}ms n={len(vals)}")
print("LAST 10:")
for r in rows[-10:]:
    print(json.dumps(r,ensure_ascii=False))
PY
