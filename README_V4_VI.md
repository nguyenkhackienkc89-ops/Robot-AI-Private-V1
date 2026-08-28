# Robot AI Private V4 — Product RC1

V4 tập trung sản phẩm hóa những phần V3 còn thiếu.

## Đã bổ sung
1. Control Center trên Mac mini: `http://127.0.0.1:8767`
2. Robot tự phát hiện trong LAN bằng UDP heartbeat.
3. Test tiến/lùi/trái/phải/dừng từ giao diện.
4. Hiệu chuẩn quay 360° từ giao diện và lưu NVS.
5. Chỉnh ngưỡng dừng TOF050C từ giao diện và lưu NVS.
6. OTA đúng cơ chế single-module của Xiaozhi:
   - USB: `Robot_AI_Private_V4_merged.bin`
   - OTA: `robot-ai-private-v1_<version>.bin` (app/xiaozhi.bin)
7. Nhạc cục bộ qua plugin `play_music`, âm thanh phát trên loa robot.
8. Radio/YouTube điều khiển Mac.
9. Tính cách Đại Ca–Tiểu Đệ + giọng NamMinh giữ nguyên.
10. Chuẩn bị đầy đủ quy trình từ đánh thức “Tiểu Đệ”.

## Điểm chưa giả lập
Custom wake word “Tiểu Đệ” cần `assets.bin` thật được sinh từ ESP-SR/MultiNet/Xiaozhi asset pipeline.
Package không chứa một model giả.

## Trình tự triển khai
1. Chạy `private_server_mac/SETUP_PRIVATE_SERVER_MAC.command`.
2. Chạy `control_center/START_CONTROL_CENTER.command`.
3. Đặt IP Mac cố định/DHCP Reservation.
4. Upload V4 lên GitHub.
5. Actions → Build Robot AI Private V4.
6. Nhập IP Mac và version `4.0.0`.
7. Gửi artifact build lại để kiểm tra trước khi nạp USB.
8. Sau khi USB ổn, dùng app-bin trong artifact cho các bản OTA tiếp theo.
