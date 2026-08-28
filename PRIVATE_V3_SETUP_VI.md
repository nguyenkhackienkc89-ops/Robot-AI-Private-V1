# ROBOT AI PRIVATE V3 — Hoàn thiện tính cách + giọng + máy chủ riêng

## Kiến trúc cuối

Robot ESP32-S3
→ Wi‑Fi LAN
→ XiaoZhi Server riêng trên Mac mini M4
→ ASR SenseVoiceSmall
→ AI Ollama qwen3:8b
→ Prompt “Đại Ca – Tiểu Đệ”
→ EdgeTTS `vi-VN-NamMinhNeural`
→ âm thanh trả về robot

Mac mini đồng thời chạy Robot Mac Bridge để robot có thể mở trình duyệt, YouTube, Word, Finder và các lệnh đã cho phép.

## Điều gì đã được “khóa”
- Tính cách nằm trong `.config.yaml` của máy chủ riêng, không còn phụ thuộc Agent công cộng.
- Giọng TTS được khóa `vi-VN-NamMinhNeural`.
- AI mặc định chạy `qwen3:8b` trên chính Mac mini qua Ollama.
- Firmware V3 được build với `CONFIG_OTA_URL` trỏ thẳng về Mac mini.

## Cài đặt

### Bước 1 — Mac mini
Giải nén gói này trên Mac mini.

Mở:
`private_server_mac/SETUP_PRIVATE_SERVER_MAC.command`

Script sẽ:
- phát hiện IP LAN của Mac;
- cài/khởi động Ollama nếu cần;
- tải qwen3:8b;
- kiểm tra/cài Docker Desktop nếu cần;
- tải SenseVoiceSmall;
- tạo cấu hình tính cách + giọng;
- chạy XiaoZhi Server riêng;
- cài Mac Bridge.

Cuối cùng file:
`private_server_mac/PRIVATE_SERVER_INFO.txt`
sẽ chứa IP và OTA URL.

### Bước 2 — Giữ IP Mac ổn định
Nên vào router đặt DHCP Reservation cho địa chỉ IP của Mac mini.
Nếu IP Mac thay đổi, firmware đang trỏ tới IP cũ sẽ không tìm thấy máy chủ.

### Bước 3 — Build firmware V3
Đưa toàn bộ package V3 lên GitHub repo.

Actions → `Build Robot AI Private V3` → Run workflow.

Nhập:
`private_server_ip` = IPv4 trong `PRIVATE_SERVER_INFO.txt`.

Artifact đúng sẽ là:
`Robot_AI_Private_V3_Firmware`

Bên trong:
`Robot_AI_Private_V3_merged.bin`

### Bước 4 — Nạp USB
Nạp merged bin từ địa chỉ `0x0`.

## Sau khi hoàn tất
Robot không cần Agent công cộng để có cá tính.
Tính cách và giọng được lấy từ máy chủ riêng của Đại Ca.

## Lưu ý
EdgeTTS vẫn cần Internet để tổng hợp giọng.
LLM qwen3:8b và ASR SenseVoiceSmall chạy cục bộ trên Mac.
