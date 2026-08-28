# BUILD FIX

Lần build #1 đã build ESP32-S3 hợp lệ nhưng chọn nhầm board mặc định `bread-compact-wifi`.

Bản sửa này:
- đăng ký Kconfig đúng trong `choice BOARD_TYPE`;
- ánh xạ CMake đúng sang `robot-ai-private-v1`;
- ép `CONFIG_BOARD_TYPE_ROBOT_AI_PRIVATE_V1=y`;
- thêm marker custom firmware;
- workflow chỉ Success nếu binary thật sự chứa motor, TOF050C/VL6180X và Mac Bridge.

Hãy thay toàn bộ nội dung repo bằng bản này rồi chạy Actions lại.
