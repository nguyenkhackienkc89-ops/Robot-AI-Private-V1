#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$HERE/dual_brain/.env"
EX="$HERE/dual_brain/.env.example"

echo "========================================================"
echo " ROBOT AI PRIVATE V6.6 - LOW LATENCY / FAILOVER"
echo "========================================================"

if [ ! -f "$ENV" ]; then
  cp "$EX" "$ENV"
fi

BACKUP="$HERE/backups/v66-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
cp "$ENV" "$BACKUP/.env" 2>/dev/null || true
cp "$HERE/dual_brain/dual_brain_router.py" "$BACKUP/dual_brain_router.py" 2>/dev/null || true
cp "$HERE/server_providers/edge_stream_private.py" "$BACKUP/edge_stream_private.py" 2>/dev/null || true
cp "$HERE/data/.config.yaml" "$BACKUP/.config.yaml" 2>/dev/null || true

python3 - "$ENV" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
vals={
 "DEEP_BASE_URL":"http://host.docker.internal:31434/v1",
 "DEEP_KEEP_ALIVE":"30m",
 "DEEP_HEALTH_TIMEOUT_SECONDS":"0.35",
 "DEEP_TCP_PREFLIGHT_TIMEOUT_SECONDS":"0.25",
 "DEEP_HEALTH_CACHE_SECONDS":"0.75",
 "DEEP_CIRCUIT_OPEN_SECONDS":"8",
 "DEEP_REQUEST_TIMEOUT_SECONDS":"2.0",
 "DEEP_FAILOVER_TARGET_MS":"1000",
}
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; seen=set()
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        k=line.split("=",1)[0].strip()
        if k in vals:
            out.append(k+"="+vals[k]); seen.add(k); continue
    out.append(line)
for k,v in vals.items():
    if k not in seen:
        out.append(k+"="+v)
p.write_text("\n".join(out)+"\n",encoding="utf-8")
PY
chmod 600 "$ENV"

python3 "$HERE/patch_v63_runtime_config.py"

docker_ok=0
if docker info >/dev/null 2>&1; then
  docker_ok=1
  DOCKER="docker"
elif command -v colima >/dev/null 2>&1 && colima status >/dev/null 2>&1; then
  DOCKER="colima ssh -- docker"
else
  echo "Không tìm thấy Docker daemon/Colima đang chạy."
  exit 2
fi

echo "Recreate CHỈ dual-brain-router và XiaoZhi nếu cần provider mới."
if [ "$docker_ok" = "1" ]; then
  (cd "$HERE" && docker compose up -d --force-recreate dual-brain-router)
  (cd "$HERE" && docker compose up -d --force-recreate xiaozhi-private)
else
  # compose chạy trên host với context Colima nếu CLI host dùng được; nếu không, chỉ restart containers trực tiếp.
  if docker --context colima info >/dev/null 2>&1; then
    (cd "$HERE" && docker --context colima compose up -d --force-recreate dual-brain-router)
    (cd "$HERE" && docker --context colima compose up -d --force-recreate xiaozhi-private)
  else
    colima ssh -- docker restart robot-ai-dual-brain >/dev/null
    colima ssh -- docker restart robot-ai-private-xiaozhi >/dev/null
  fi
fi

sleep 3
echo
echo "Router:"
curl --noproxy '*' -fsS http://127.0.0.1:11435/status | python3 -m json.tool
echo
echo "Tunnel:"
curl --noproxy '*' -fsS http://127.0.0.1:31434/api/tags | grep -Ei 'qwen3\.5.*35b' || true
echo
echo "Backup: $BACKUP"
