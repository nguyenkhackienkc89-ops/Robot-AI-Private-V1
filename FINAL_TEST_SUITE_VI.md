# Bộ kiểm thử Robot AI Private V1

## A. Tính cách
Nói:
- “Mày là ai?”
- “Tao đẹp trai không?”
- “Mày có thông minh không?”
- “Hôm nay nói nghiêm túc nhé.”

Đạt khi:
- xưng “Đại Ca – Tiểu Đệ” tự nhiên;
- không lạm dụng kiếm hiệp;
- câu ngắn;
- khi yêu cầu nghiêm túc thì ngừng cà khịa.

## B. Di chuyển
Đặt robot trên sàn rộng, KHÔNG thử trên mép bàn.

- “Tiến lên một chút.”
- “Dừng.”
- “Lùi lại.”
- “Quay trái.”
- “Quay phải.”
- “Quay một vòng.”

Đạt khi:
- đúng chiều;
- dừng đúng lệnh;
- spin 360 gần đúng 1 vòng.

Nếu quay 360 thiếu/thừa:
dùng `self.robot.calibrate_spin360`.

## C. TOF050C
- Đặt vật cản 10–20 cm phía trước.
- Ra lệnh tiến.

Đạt khi:
- robot không lao tiếp vào vật cản;
- self.robot.distance đọc được số mm hợp lý.

Lưu ý: TOF phía trước KHÔNG chống rơi mép bàn.

## D. Mac mini
Mac và robot cùng mạng LAN.

- “Mở Chrome.”
- “Mở YouTube.”
- “Tìm YouTube robot ESP32.”
- “Mở Word.”
- “Viết vào Word: Đại Ca đang thử robot.”
- “Tăng âm lượng.”

Đạt khi:
- Mac Bridge tự được tìm thấy;
- đúng ứng dụng mở;
- không cần biết IP cố định.

## E. An toàn
Robot KHÔNG được:
- xóa file;
- chạy shell tùy ý;
- nhập mật khẩu;
- cài phần mềm;
- thanh toán.
