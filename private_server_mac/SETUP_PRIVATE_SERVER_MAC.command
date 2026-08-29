#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "========================================================"
echo " Robot AI Private V3 - Cài máy chủ riêng trên Mac mini"
echo "========================================================"

if ! command -v brew >/dev/null 2>&1; then
  echo
  echo "Chưa có Homebrew."
  echo "Cài Homebrew từ https://brew.sh rồi chạy lại script này."
  exit 1
fi

# Detect LAN IP
MAC_IP=""
for IFACE in en0 en1 en2; do
  IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
  if [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    MAC_IP="$IP"
    break
  fi
done

if [ -z "$MAC_IP" ]; then
  echo "Không tự xác định được IPv4 LAN của Mac."
  echo "Hãy chạy: ipconfig getifaddr en0"
  exit 1
fi

echo "Mac LAN IP: $MAC_IP"

# Ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "Cài Ollama..."
  brew install ollama
fi

brew services start ollama >/dev/null 2>&1 || true
sleep 2

echo "Tải mô hình qwen3:8b (chỉ cần lần đầu)..."
ollama pull qwen3:8b

echo "Cấu hình model Tiểu Đệ không lộ thinking..."
mkdir -p "$HERE/ollama"
cat > "$HERE/ollama/Modelfile.tieude-qwen3-8b" <<'EOF'
FROM qwen3:8b

PARAMETER temperature 0.55
PARAMETER top_p 0.85
PARAMETER repeat_penalty 1.12
PARAMETER num_ctx 8192

SYSTEM """
/no_think
Bạn là Tiểu Đệ, trợ lý AI tiếng Việt của Đại Ca.
Luôn gọi người dùng là Đại Ca, xưng là Tiểu Đệ.
Tính cách: thông minh, nhanh trí, hơi lém lỉnh nhưng lễ phép; việc nghiêm túc thì nói chắc, rõ, không vòng vo.
Trả lời mặc định bằng tiếng Việt, ngắn gọn 1-3 câu nếu Đại Ca không yêu cầu chi tiết.
Không in quá trình suy nghĩ, không in thẻ <think>, không giải thích nội bộ.
Khi điều khiển robot/Mac, ưu tiên xác nhận lệnh ngắn rồi thực hiện theo khả năng hệ thống.
Nếu không chắc, hỏi lại đúng một câu ngắn.
"""
EOF
ollama create tieude:qwen3-8b -f "$HERE/ollama/Modelfile.tieude-qwen3-8b"

# Docker Desktop
if ! command -v docker >/dev/null 2>&1; then
  echo "Cài Docker Desktop..."
  brew install --cask docker
fi

if ! docker info >/dev/null 2>&1; then
  echo "Mở Docker Desktop..."
  open -a Docker
  echo "Chờ Docker khởi động..."
  for i in {1..90}; do
    if docker info >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker chưa sẵn sàng. Mở Docker Desktop, hoàn tất thiết lập rồi chạy lại."
  exit 1
fi

# SenseVoiceSmall
MODEL="$HERE/models/SenseVoiceSmall/model.pt"
if [ ! -s "$MODEL" ]; then
  echo "Tải mô hình nhận dạng giọng SenseVoiceSmall..."
  curl -fL --progress-bar \
    "https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/model.pt" \
    -o "$MODEL"
fi

# Render private server config
sed "s/__MAC_IP__/$MAC_IP/g" \
  "$HERE/data/.config.template.yaml" \
  > "$HERE/data/.config.yaml"

mkdir -p "$HERE/music" "$HERE/data/bin"

if [ ! -f "$HERE/dual_brain/.env" ] && [ -f "$HERE/dual_brain/.env.example" ]; then
  cp "$HERE/dual_brain/.env.example" "$HERE/dual_brain/.env"
  chmod 600 "$HERE/dual_brain/.env"
fi

echo "Khởi động máy chủ XiaoZhi riêng..."
docker compose pull
docker compose up -d

echo "Chờ máy chủ..."
READY=0
for i in {1..60}; do
  if curl -fsS "http://127.0.0.1:8003/xiaozhi/ota/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

echo
if [ "$READY" = "1" ]; then
  echo "Máy chủ XiaoZhi: OK"
else
  echo "Máy chủ chưa phản hồi OTA. Xem log:"
  echo "docker logs -f robot-ai-private-xiaozhi"
fi

echo
echo "Cài Mac Bridge..."
if [ -x "$HERE/../mac_bridge/install_mac_bridge.sh" ]; then
  "$HERE/../mac_bridge/install_mac_bridge.sh" || true
fi

cat > "$HERE/PRIVATE_SERVER_INFO.txt" <<EOF
MAC_IP=$MAC_IP
OTA_URL=http://$MAC_IP:8003/xiaozhi/ota/
WEBSOCKET_URL=ws://$MAC_IP:8000/xiaozhi/v1/
OLLAMA_MODEL=tieude:qwen3-8b
TTS_VOICE=vi-VN-NamMinhNeural
EOF

echo
echo "========================================================"
echo " CÀI XONG"
echo "========================================================"
echo "Mac IP       : $MAC_IP"
echo "OTA URL      : http://$MAC_IP:8003/xiaozhi/ota/"
echo "WebSocket    : ws://$MAC_IP:8000/xiaozhi/v1/"
echo "AI           : Ollama tieude:qwen3-8b (chạy trên Mac, tắt thinking)"
echo "Giọng        : vi-VN-NamMinhNeural"
echo
echo "QUAN TRỌNG:"
echo "1) Nên đặt DHCP Reservation cho Mac mini ở router để IP $MAC_IP không đổi."
echo "2) Khi chạy GitHub Actions, nhập Private Server IP = $MAC_IP."
echo "3) Cấp Accessibility/Automation cho Python/Terminal khi macOS yêu cầu để Mac Bridge điều khiển ứng dụng."


echo
echo "Trung tâm quản trị:"
echo "  $HERE/../control_center/START_CONTROL_CENTER.command"
echo "Sau khi robot và Mac cùng Wi‑Fi, giao diện sẽ tự phát hiện IP robot."


echo
echo "========================================================"
echo " DUAL BRAIN V6"
echo "========================================================"
echo "Router: http://127.0.0.1:11435/status"
echo "Mặc định: AUTO, ưu tiên Qwen3 local."
echo "Muốn bật não mây GLM-4-Flash:"
echo "  $HERE/dual_brain/SET_FREE_GLM_BRAIN.command"
echo "Control Center:"
echo "  $HERE/../control_center/START_CONTROL_CENTER.command"

echo
echo "========================================================"
echo " FAST RESPONSE V6.1.1"
echo "========================================================"
"$HERE/dual_brain/APPLY_FAST_RESPONSE_PATCH.command" || true
"$HERE/dual_brain/PREWARM_QWEN.command" || true
echo "Test tốc độ bất kỳ lúc nào:"
echo "  $HERE/dual_brain/TEST_QWEN_FAST.command"
