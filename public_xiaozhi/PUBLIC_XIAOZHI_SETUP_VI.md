# Xiaozhi công cộng — não dự phòng độc lập

V6 hỗ trợ chuyển firmware trực tiếp sang endpoint Xiaozhi công cộng:
`https://api.tenclass.net/xiaozhi/ota/`

Mục đích:
- dùng hệ cloud tương tự luồng VuiTV;
- có thể hoạt động không phụ thuộc LLM local trên Mac sau khi thiết bị đã được kích hoạt/bind đúng.

## Bắt buộc làm trên tài khoản Xiaozhi
1. Thêm/bind thiết bị vào Agent của bạn.
2. Dán toàn bộ `AGENT_PROMPT_DAI_CA_TIEU_DE.txt` vào mô tả hệ thống Agent.
3. Chọn tiếng Việt.
4. Chọn giọng nam tiếng Việt gần nhất với cấu hình Tiểu Đệ.
5. Kiểm tra MCP tool của robot xuất hiện.

## Chuyển bằng giọng
Trên private server:
“Tiểu Đệ, chuyển hẳn sang Xiaozhi công cộng.”

Robot ghi OTA URL công cộng vào NVS rồi khởi động lại.

Để quay lại:
“Quay về máy chủ riêng.”

Lưu ý:
- Public Xiaozhi Agent là một hệ riêng. V6 không tự đăng nhập hoặc tự cấu hình tài khoản của bạn.
- Giọng `vi-VN-NamMinhNeural` được khóa chắc chắn ở private server; public Agent có thể không cung cấp đúng voice ID này.
