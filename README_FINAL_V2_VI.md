# Robot AI Private V1 – FINAL V2

Đây là bộ mã nguồn đầy đủ cho robot AI riêng:

## Phần cứng
- ESP32-S3 N16R8
- ST7789 1.3" 240×240
- INMP441
- MAX98357A
- DRV8833
- 2 motor DC giảm tốc
- TOF050C / VL6180X
- đèn trạng thái

## Robot
- mắt động;
- nghe / nói / suy nghĩ / cà khịa / bất ngờ;
- tiến;
- lùi;
- quay trái;
- quay phải;
- dừng;
- quay 360° theo thời gian đã hiệu chuẩn;
- tránh vật cản phía trước bằng TOF050C.

## Nhân vật
Tên vai: Tiểu Đệ.

Phong cách:
- nam Bắc 28–32;
- trầm vừa;
- rõ chữ;
- thông minh;
- láu cá;
- hơi ngông;
- hơi hỗn có duyên;
- giang hồ – kiếm hiệp hiện đại;
- xưng Đại Ca – Tiểu Đệ;
- không biến thành giọng cổ trang quá mức.

## Mac mini
Robot có thể ra lệnh Mac Bridge để:
- mở Chrome / Safari;
- mở YouTube;
- tìm YouTube / web;
- mở Word;
- viết văn bản;
- mở Finder;
- mở ứng dụng;
- gõ chữ;
- chỉnh âm lượng / media.

Không có quyền shell tùy ý và không được tự thực hiện hành động nguy hiểm.

## Build
Bộ này chứa workflow GitHub Actions đã sửa để build custom board thật.
Workflow phải PASS phần kiểm tra binary trước khi artifact được coi là hợp lệ.

Đầu ra cần dùng:
`Robot_AI_Private_V1_merged.bin`

## Quan trọng
File ZIP này KHÔNG phải `.bin` nạp trực tiếp.
Sau khi cập nhật repo GitHub bằng bộ này, chạy workflow.
Chỉ dùng `.bin` từ workflow mới khi trạng thái Success.
