#!/bin/bash
set -euo pipefail

CONTAINER="robot-ai-private-xiaozhi"
OUT="/opt/xiaozhi-esp32-server/data/tts_cache/namminh_da_dai_ca.mp3"

run_docker() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif docker --context colima info >/dev/null 2>&1; then
    docker --context colima "$@"
  elif command -v colima >/dev/null 2>&1; then
    colima ssh -- docker "$@"
  else
    return 1
  fi
}

echo "Tạo cache đúng giọng vi-VN-NamMinhNeural: Dạ Đại Ca."
run_docker exec -i "$CONTAINER" python - <<'PY'
import asyncio,os,edge_tts
out="/opt/xiaozhi-esp32-server/data/tts_cache/namminh_da_dai_ca.mp3"
os.makedirs(os.path.dirname(out),exist_ok=True)
async def main():
    c=edge_tts.Communicate("Dạ Đại Ca.",voice="vi-VN-NamMinhNeural")
    await c.save(out)
asyncio.run(main())
print(out, os.path.getsize(out))
PY

echo
echo "Cache đã tạo. Chưa tự bật Instant ACK."
echo "Hãy A/B test rồi chạy ENABLE_V6_6_INSTANT_ACK.command nếu đạt yêu cầu."
