#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$HERE/dual_brain/.env"
EX="$HERE/dual_brain/.env.example"
[ -f "$ENV" ] || cp "$EX" "$ENV"

python3 - "$ENV" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
vals={
 "DEEP_ENABLED":"true",
 "DEEP_BASE_URL":"http://host.docker.internal:11436/v1",
 "DEEP_MODEL":"qwen3.5:35b-a3b-int4",
 "DEEP_MODEL_CANDIDATES":"qwen3.5:35b-a3b-int4,qwen3.5:35b-a3b",
 "DEEP_NUM_CTX":"4096",
 "DEEP_NUM_PREDICT":"768",
 "DEEP_KEEP_ALIVE":"5m",
 "DEEP_THINK_DEFAULT":"false",
 "DEEP_COMPLEXITY_THRESHOLD":"2",
 "DEEP_MAX_RTT_MS":"120",
 "DEEP_FALLBACK_TO_FAST":"true",
 "AUTO_PREFER_DEEP_FOR_COMPLEX":"true",
 "AUTO_CLOUD_FALLBACK_ONLY":"true",
}
lines=p.read_text(encoding="utf-8").splitlines()
out=[];seen=set()
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        k=line.split("=",1)[0].strip()
        if k in vals:
            out.append(k+"="+vals[k]);seen.add(k);continue
    out.append(line)
for k,v in vals.items():
    if k not in seen: out.append(k+"="+v)
p.write_text("\n".join(out)+"\n",encoding="utf-8")
PY
chmod 600 "$ENV"

cd "$HERE"
docker compose restart dual-brain-router || true
sleep 2
curl -fsS http://127.0.0.1:11435/status | python3 -m json.tool
