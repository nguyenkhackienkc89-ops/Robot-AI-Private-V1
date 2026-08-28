# Hiệu chuẩn chuyển động

Robot dùng 2 động cơ DC và không có encoder, vì vậy góc quay phụ thuộc:
- điện áp pin;
- mặt sàn;
- độ bám bánh;
- trọng lượng robot.

## Quay một vòng
Giá trị mặc định hiện tại: 1700 ms.

Quy trình:
1. Đánh dấu hướng mặt robot.
2. Nói “quay một vòng”.
3. Nếu robot chỉ quay khoảng 330° → tăng thời gian.
4. Nếu quay khoảng 390° → giảm thời gian.
5. Điều chỉnh từng bước 30–80 ms.
6. Khi đạt gần 360°, lưu bằng `self.robot.calibrate_spin360`.

Ví dụ:
- thiếu khá nhiều: 1850 ms
- quá nhiều: 1600 ms

Không coi 1700 ms là giá trị chính xác cho mọi robot.

## Tiến/lùi
Tốc độ mặc định nên giữ khoảng 35–45% trong giai đoạn thử.
Không chạy tối đa ngay từ đầu.
