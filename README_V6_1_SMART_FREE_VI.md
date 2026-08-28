# Robot AI Private V6.1 — Smart-Free Dual Brain

## Mục tiêu
Đưa trải nghiệm “não mây thông minh nhưng không mất tiền” của hệ XiaoZhi vào V6,
trong khi vẫn giữ não local và toàn bộ cá tính riêng.

## Não 1 — GLM-4-Flash
Preset:
- model: `glm-4-flash`
- endpoint: `https://open.bigmodel.cn/api/paas/v4`
- cần API key Zhipu/BigModel
- cấu hình XiaoZhi công khai hiện mô tả model này là miễn phí
- chính sách nhà cung cấp có thể thay đổi, vì vậy không cam kết miễn phí vĩnh viễn

Bật bằng:
`private_server_mac/dual_brain/SET_FREE_GLM_BRAIN.command`

## Não 2 — Qwen3 8B local
- Ollama trên Mac mini
- không API
- không phí token
- hoạt động khi mất Internet
- ưu tiên motor, Mac Bridge, dữ liệu nhạy cảm và fallback

## Chế độ AUTO mặc định
Khi GLM đã cấu hình:
- hỏi kiến thức / giải thích / tư vấn / phân tích → ưu tiên GLM
- motor / Mac / dữ liệu riêng tư → Qwen local
- GLM lỗi hoặc mất mạng → Qwen local
- không có API key → Qwen local

Đây là chế độ nên dùng hàng ngày.

## Chặn model có thể tính phí
`BLOCK_NONFREE_CLOUD=true`

Khi bật:
Router chỉ chấp nhận đúng:
- `https://open.bigmodel.cn/api/paas/v4`
- `glm-4-flash`

Mọi cloud khác bị coi là không sẵn sàng.

## Hội ý hai não
Mode `council`:
1. Qwen local phân tích.
2. GLM-4-Flash phân tích.
3. Qwen local tổng hợp câu trả lời cuối.

## Tính cách và giọng
Không đổi:
- Đại Ca – Tiểu Đệ
- nam Bắc
- trầm vừa
- rõ chữ
- thông minh, láu cá, hơi ngông
- kiếm hiệp hiện đại
- TTS private: `vi-VN-NamMinhNeural`

LLM chỉ tạo nội dung. Prompt nhân vật + TTS vẫn nằm ở XiaoZhi Server riêng.

## Xiaozhi công cộng
V6.1 vẫn giữ profile `public_xiaozhi` để chuyển hẳn sang hệ Xiaozhi công cộng khi muốn.
Đây là chế độ khác với GLM qua Router.

## Không thay đổi phần robot
Giữ toàn bộ:
- ESP32-S3 N16R8
- ST7789 240×240
- INMP441
- MAX98357A
- DRV8833
- TOF050C
- motor web control
- 192.168.4.1
- OTA
- Chrome/Edge flashing
- nhạc, VOV
- biểu cảm
- Mac Bridge
