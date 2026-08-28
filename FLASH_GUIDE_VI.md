# Hướng dẫn nạp sau khi build merged.bin

1. Cắm USB dữ liệu vào ESP32-S3.
2. Nếu cần vào download mode: giữ BOOT, bấm RESET, thả RESET, thả BOOT.
3. Nạp merged binary ở địa chỉ 0x0:
   esptool.py --chip esp32s3 --port <PORT> write_flash 0x0 Robot_AI_Private_V1_merged.bin
4. Khởi động lại và cấu hình Wi‑Fi.
5. Liên kết agent XiaoZhi.
6. Dán `agent_prompt_vi.txt` vào phần nhân vật/agent.
7. Cài `mac_bridge/install_mac_bridge.sh` trên Mac mini.

## Thử chuyển động lần đầu
Đặt robot xuống sàn rộng:
- "tiến" 300–500 ms,
- "lùi",
- "quay trái",
- "quay phải",
- cuối cùng mới "quay một vòng".
