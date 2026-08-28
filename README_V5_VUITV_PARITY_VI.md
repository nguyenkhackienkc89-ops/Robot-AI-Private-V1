# Robot AI Private V5 — VuiTV Feature-Parity Edition

Mục tiêu: tái tạo bộ tính năng và luồng trải nghiệm đang được VuiTV công khai cho Robot V2,
nhưng dùng mã nguồn XiaoZhi/open-source + mã riêng của Robot AI Private.
Không chứa hoặc sao chép firmware đóng của VuiTV.

## Phần cứng khóa theo robot thực tế
- ESP32-S3 N16R8
- ST7789 1.3" 240×240
- INMP441
- MAX98357A
- 2 motor DC + DRV8833
- TOF050C / VL6180X: SDA41 / SCL42
- touch: tắt
- LED trang trí: GPIO38 / GPIO46

## Luồng sử dụng kiểu VuiTV

### Cấu hình Wi‑Fi
Nếu chưa có Wi‑Fi:
1. Robot phát `TieuDe-XXXX`
2. kết nối mạng đó
3. mở `192.168.4.1`
4. chọn Wi‑Fi 2.4 GHz và lưu

Giữ BOOT lâu để vào lại chế độ cấu hình.

### Điều khiển robot trên web
- Khi ở AP: `http://192.168.4.1:8080`
- Khi đã vào LAN: `http://IP-CUA-ROBOT:8080`

Có:
- tiến/lùi/trái/phải/dừng
- quay 360
- nhảy
- hiệu chuẩn 360
- chỉnh ngưỡng ToF
- trạng thái khoảng cách

### OTA
XiaoZhi Server riêng quản lý OTA.
Artifact build sinh:
- `Robot_AI_Private_V5_merged.bin` — USB/full flash
- `robot-ai-private-v1_<version>.bin` — OTA/app binary

### Nạp firmware bằng Chrome/Edge
Artifact có `web_flash/`.
Trên Mac chạy:
`START_WEB_FLASH_MAC.command`
sau đó Chrome/Edge mở localhost và nạp bằng Web Serial.

### Nhạc
Nhạc MP3/WAV cục bộ dùng plugin `play_music` của XiaoZhi và phát qua loa robot.

### Radio
V5 thêm `play_radio_private`:
- VOV1
- VOV2
- VOV Giao thông
Radio được Mac/XiaoZhi Server lấy luồng, chia thành đoạn âm thanh ngắn rồi gửi qua loa robot.

### Biểu cảm / phổ nhạc
Có chế độ `music` tạo phổ động trên TFT.
Đây là hiệu ứng trực quan, không tuyên bố là FFT đo phổ chính xác.

### Công cụ AI
Giữ MCP:
- điều khiển motor
- ToF
- biểu cảm
- đèn
- Mac Bridge
- các công cụ AI của XiaoZhi Server

## Nhân vật KHÔNG thay đổi
- Vai: Tiểu Đệ
- gọi người dùng: Đại Ca
- nam Bắc khoảng 28–32 tuổi
- trầm vừa, rõ chữ
- thông minh, láu cá, hơi ngông
- hơi hỗn có duyên
- kiếm hiệp/giang hồ hiện đại chỉ là gia vị
- câu thường 1–3 câu
- việc nghiêm túc thì bỏ cà khịa

## Giọng
Khóa trên server:
`vi-VN-NamMinhNeural`
rate `-6%`
pitch `-4Hz`

## Từ đánh thức
Giống luồng VuiTV công khai, đây là phần tùy chọn làm sau khi robot hội thoại ổn.
V5 giữ pipeline `assets.bin`; câu “Tiểu Đệ” cần assets/model thật, không tạo file giả.
