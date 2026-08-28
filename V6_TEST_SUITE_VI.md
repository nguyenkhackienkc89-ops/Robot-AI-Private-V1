# Test V6

## 1. Không cloud
- Chạy setup Mac.
- `/status` phải báo cloud_ready=false.
- mode auto trả lời bằng local.
- lệnh motor/Mac vẫn hoạt động.

## 2. Não nhà
Nói “Dùng não nhà”.
Kiểm tra mode=local và last_route=local.

## 3. Não mây
Chạy `SET_CLOUD_BRAIN.command`.
Nói “Dùng não mây”.
Kiểm tra last_route=cloud.
Xác nhận cùng cách xưng Đại Ca/Tiểu Đệ và cùng giọng TTS.

## 4. Auto
Nói lệnh motor → phải ưu tiên local.
Đưa bài phân tích dài → nếu đủ threshold và cloud sẵn sàng có thể chuyển cloud.

## 5. Council
Nói “Hai não cùng phân tích...”.
Không dùng council cho motor/Word.
Kết quả cuối chỉ có một câu trả lời tổng hợp.

## 6. Giới hạn phí
Đặt CLOUD_DAILY_LIMIT=1.
Sau một lượt cloud, lượt kế tiếp phải fallback/local hoặc báo hết hạn mức.

## 7. Xiaozhi công cộng
Sau khi bind Agent công cộng:
“Chuyển hẳn sang Xiaozhi công cộng.”
Robot reboot.
Kiểm tra endpoint public.
Sau đó gọi self.robot.server_profile action=private để quay về.

## 8. An toàn
- Không đưa API key vào chat.
- Không commit `.env` có API key lên repo công khai.
- Motor test trên sàn, không test mép bàn.
