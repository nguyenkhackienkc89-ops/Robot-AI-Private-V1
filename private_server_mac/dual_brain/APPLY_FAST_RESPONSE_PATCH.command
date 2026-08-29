#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV="$HERE/.env"
EXAMPLE="$HERE/.env.example"

if [ ! -f "$ENV" ]; then
  cp "$EXAMPLE" "$ENV"
fi

python3 - "$ENV" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
required={
  "LOCAL_API_MODE":"native",
  "LOCAL_THINK_DEFAULT":"false",
  "LOCAL_ALLOW_DEEP_THINK_TRIGGER":"true",
  "LOCAL_KEEP_ALIVE":"30m",
  "LOCAL_NUM_PREDICT":"512",
}
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; seen=set()
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        k=line.split("=",1)[0].strip()
        if k in required:
            out.append(k+"="+required[k])
            seen.add(k)
            continue
    out.append(line)
for k,v in required.items():
    if k not in seen:
        out.append(k+"="+v)
p.write_text("\n".join(out)+"\n",encoding="utf-8")
PY

chmod 600 "$ENV"
cd "$HERE/.."
docker compose restart dual-brain-router >/dev/null 2>&1 || true
sleep 1

echo "V6.1.1 Fast Response đã áp dụng."
echo
curl -fsS http://127.0.0.1:11435/status || true
echo
