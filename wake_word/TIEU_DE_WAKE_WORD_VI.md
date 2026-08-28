# Từ đánh thức “Tiểu Đệ”

Xiaozhi ESP32 v2.4.2 có lớp `CustomWakeWord` dùng ESP-SR/MultiNet và có thể đọc cấu hình custom wake word từ `assets.bin`.

## Trạng thái V4
- Firmware đã giữ khả năng custom wake word.
- Nhân vật đã phản hồi theo mẫu: “Tiểu Đệ đây. Đại Ca có gì sai bảo?”
- Chưa đóng gói một `assets.bin` giả.

## Vì sao chưa thể coi câu “Tiểu Đệ” là hoàn tất
Để ESP32 nhận câu này khi chưa kết nối server, `assets.bin` phải chứa:
1. model MultiNet phù hợp;
2. command phoneme/token cho câu đánh thức;
3. `index.json` với action `wake`;
4. ngưỡng nhận dạng đã test với mic INMP441.

Một file text hay đổi tên file không tạo được model đánh thức.

## Quy trình đúng
1. Cho robot chạy ổn bằng nút bấm trước.
2. Tạo custom wake-word assets bằng công cụ quản lý assets của hệ Xiaozhi/VuiTV hoặc pipeline ESP-SR tương thích.
3. Chọn câu hiển thị: `Tiểu Đệ`.
4. Tạo `assets.bin`.
5. Nạp assets riêng, không cần ghi đè toàn bộ merged firmware.
6. Test tối thiểu:
   - 20 lần nói ở 0,5 m;
   - 20 lần ở 1,5 m;
   - có nhạc nền;
   - thử các câu gần âm để đo đánh thức nhầm.

## Mục tiêu
Tỷ lệ nhận đúng nên >90% trong phòng yên tĩnh trước khi bật mặc định.
