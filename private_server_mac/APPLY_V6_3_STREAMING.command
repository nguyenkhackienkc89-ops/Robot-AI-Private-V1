#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV="$HERE/dual_brain/.env"
EXAMPLE="$HERE/dual_brain/.env.example"

[ -f "$ENV" ] || cp "$EXAMPLE" "$ENV"

python3 - "$ENV" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
vals={
 "STREAMING_ENABLED":"true",
 "LOCAL_STREAMING_ENABLED":"true",
 "CLOUD_STREAMING_ENABLED":"true",
 "FAST_COMMANDS_ENABLED":"true",
 "LOCAL_THINK_DEFAULT":"false",
 "LOCAL_SINGLE_RESIDENT":"true",
 "LOCAL_NUM_CTX":"8192",
 "LOCAL_KEEP_ALIVE":"10m",
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
    if k not in seen:
        out.append(k+"="+v)
p.write_text("\n".join(out)+"\n",encoding="utf-8")
PY
chmod 600 "$ENV"

python3 "$HERE/patch_v63_runtime_config.py"

cd "$HERE"
docker-compose up -d --force-recreate dual-brain-router xiaozhi-private
sleep 2

echo
echo "===== ROUTER ====="
curl -fsS http://127.0.0.1:11435/status || true
echo
echo
echo "===== EDGE STREAM PROVIDER ====="
docker exec robot-ai-private-xiaozhi sh -lc \
  'ffmpeg -version | head -1; python -c "import core.providers.tts.edge_stream_private as m; print(\"EdgeStreamPrivate: OK\")"' || true
echo
echo "V6.3 đã áp dụng."
