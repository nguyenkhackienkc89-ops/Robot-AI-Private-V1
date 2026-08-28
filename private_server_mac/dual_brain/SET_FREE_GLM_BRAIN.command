#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV="$HERE/.env"
EXAMPLE="$HERE/.env.example"

if [ ! -f "$ENV" ]; then
  cp "$EXAMPLE" "$ENV"
fi

echo "========================================================"
echo " CẤU HÌNH NÃO MÂY GLM-4-FLASH"
echo "========================================================"
echo "Model: glm-4-flash"
echo "Endpoint: https://open.bigmodel.cn/api/paas/v4"
echo
echo "Cấu hình XiaoZhi công khai hiện mô tả model này là miễn phí,"
echo "nhưng vẫn cần API key và chính sách nhà cung cấp có thể thay đổi."
echo

read -r -s -p "Dán API key Zhipu/BigModel: " KEY
echo
if [ -z "$KEY" ]; then
  echo "Không có API key. Không thay đổi."
  exit 1
fi

python3 - "$ENV" "$KEY" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
key=sys.argv[2]
vals={
 "CLOUD_BASE_URL":"https://open.bigmodel.cn/api/paas/v4",
 "CLOUD_MODEL":"glm-4-flash",
 "CLOUD_API_KEY":key,
 "BLOCK_NONFREE_CLOUD":"true",
 "AUTO_POLICY":"smart_free",
}
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; seen=set()
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

cd "$HERE/.."
docker compose restart dual-brain-router >/dev/null 2>&1 || true
sleep 1
echo
echo "Trạng thái:"
curl -fsS http://127.0.0.1:11435/status || true
echo
echo
echo "Hoàn tất. Chế độ AUTO sẽ ưu tiên GLM cho câu hỏi kiến thức."
