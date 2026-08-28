# Robot AI Private V6 — Dual Brain

## Mục tiêu
Giữ toàn bộ V5/VuiTV-parity nhưng bổ sung hai hệ não:

### NÃO NHÀ
- XiaoZhi Server riêng trên Mac mini
- Ollama + Qwen3 8B
- không phí token API
- dữ liệu LLM ở local
- ưu tiên điều khiển robot và Mac

### NÃO MÂY
- API cloud tương thích OpenAI `/v1`
- nhà cung cấp/model do người dùng tự chọn
- không có API key nào được nhúng sẵn
- có giới hạn mặc định 50 lượt/ngày để tránh phát sinh phí

## 4 chế độ
1. `local`: chỉ não nhà.
2. `cloud`: chỉ não mây; lỗi thì fallback local.
3. `auto`: mặc định. Hành động robot/Mac dùng local; tác vụ phân tích phức tạp có thể dùng cloud.
4. `council`: hỏi cả hai não, sau đó Qwen local tổng hợp một câu trả lời cuối.

## Vì sao tính cách và giọng không đổi
Robot luôn nói qua cùng XiaoZhi Server riêng:
LLM → prompt Đại Ca/Tiểu Đệ → EdgeTTS NamMinh → loa robot.

Do đó local/cloud/auto/council chỉ thay phần mô hình suy nghĩ, không thay lớp nhân vật và TTS.

## Chuyển bằng giọng
- “Dùng não nhà.”
- “Dùng não mây.”
- “Tự chọn não.”
- “Hai não cùng phân tích.”
- “Đang dùng não nào?”

## Chế độ Xiaozhi công cộng trực tiếp
Firmware còn có `self.robot.server_profile`.

- `private`: trở lại máy chủ riêng.
- `public_xiaozhi`: endpoint công cộng Xiaozhi, giống kiến trúc cloud mà VuiTV sử dụng.

Chuyển profile sẽ reboot robot.

Đây là một chế độ riêng, không phải Router. Muốn giữ cá tính trên Xiaozhi công cộng phải cấu hình Agent bằng file trong `public_xiaozhi/`.

## Chi phí
- Local: không phí API.
- Auto: mặc định ưu tiên local.
- Cloud/Council: có thể phát sinh phí theo nhà cung cấp cloud.
- V6 mặc định CLOUD_DAILY_LIMIT=50; đổi hoặc đặt 0 nếu muốn không giới hạn.

## Riêng tư
- Local: hội thoại LLM không được gửi tới cloud provider.
- Cloud/Council: nội dung request cần xử lý được gửi tới API cloud đã cấu hình.
- API key nằm trong `private_server_mac/dual_brain/.env`, không nhúng vào firmware ESP32.

## Phần cứng/tính năng giữ nguyên V5
- ESP32-S3 N16R8
- ST7789 1.3" 240×240
- INMP441 / MAX98357A
- DRV8833 motor
- TOF050C / VL6180X
- điều khiển web
- Wi-Fi AP / 192.168.4.1
- OTA
- browser flashing
- nhạc/radio
- biểu cảm/phổ nhạc
- Mac Bridge
- tính cách Đại Ca–Tiểu Đệ
- giọng NamMinh trên private server
