#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 - "$HERE/.env" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1])
out=[]
for line in p.read_text(encoding="utf-8").splitlines():
    if line.startswith("CLOUD_BASE_URL="): line="CLOUD_BASE_URL="
    elif line.startswith("CLOUD_MODEL="): line="CLOUD_MODEL="
    elif line.startswith("CLOUD_API_KEY="): line="CLOUD_API_KEY="
    out.append(line)
p.write_text("\n".join(out)+"\n",encoding="utf-8")
PY
cd "$HERE/.."
docker compose restart dual-brain-router >/dev/null
echo "Đã xóa cấu hình não mây."
