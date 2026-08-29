#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$HERE/data/.config.yaml"
cp "$CFG" "$CFG.v66-ack-backup-$(date +%Y%m%d-%H%M%S)"

python3 - "$CFG" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]); t=p.read_text(encoding="utf-8")
if "instant_ack_enabled:" in t:
    t=re.sub(r'(?m)^(\s*)instant_ack_enabled:\s*\S+\s*$',r'\1instant_ack_enabled: false',t)
else:
    t=t.replace("    first_chunk_chars: 26","    first_chunk_chars: 26\n    instant_ack_enabled: false")
p.write_text(t,encoding="utf-8")
PY

if docker --context colima info >/dev/null 2>&1; then
  docker --context colima restart robot-ai-private-xiaozhi >/dev/null
elif docker info >/dev/null 2>&1; then
  docker restart robot-ai-private-xiaozhi >/dev/null
else
  colima ssh -- docker restart robot-ai-private-xiaozhi >/dev/null
fi
echo "Instant ACK NamMinh: DISABLED"
