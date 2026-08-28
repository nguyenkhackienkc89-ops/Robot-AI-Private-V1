# Robot AI Private V1 — FULL SOURCE KIT

Bộ này gồm:
- custom board riêng cho XiaoZhi v2.4.2;
- ESP32-S3 N16R8;
- ST7789 1.3" 240x240;
- INMP441 + MAX98357A;
- DRV8833 + 2 motor DC;
- TOF050C / VL6180X;
- mắt động;
- lệnh giọng nói tiến/lùi/quay trái/quay phải/dừng/quay một vòng;
- điều khiển Mac mini qua LAN;
- prompt tính cách riêng.

## Quay 360°
Robot không có encoder bánh xe nên quay 360° theo thời gian.
Mặc định 1700 ms là điểm khởi đầu, cần hiệu chuẩn thực tế.

## Cảnh báo
TOF050C chỉ đo vật cản phía trước, không phải cảm biến chống rơi.
Không thử tiến/lùi/quay 360° trên bàn không có chắn mép.

## Đầu ra build
GitHub Actions kèm sẵn xuất:
Robot_AI_Private_V1_merged.bin
