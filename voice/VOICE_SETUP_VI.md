# Hồ sơ giọng nói – Robot AI Private V1

## Mục tiêu giọng
- Nam Việt Nam, miền Bắc hoặc Bắc chuẩn nếu hệ thống giọng hỗ trợ.
- Tuổi cảm nhận: 28–32.
- Trầm vừa, không quá già.
- Rõ phụ âm đầu và cuối.
- Tốc độ chậm vừa, không kéo chữ.
- Có độ ngông nhẹ, tự tin, nhưng không diễn quá.
- Không giả giọng Trung Quốc. Chất kiếm hiệp nằm ở cách dùng từ và nhịp câu.

## Cấu hình mặc định đề xuất
Nếu dùng EdgeTTS trên máy chủ Xiaozhi:
- voice: `vi-VN-NamMinhNeural`
- rate: `-6%`
- pitch: `-4Hz`
- volume: `+0%`

Đây là giọng nam tiếng Việt tiêu chuẩn. Nếu sau khi nghe thực tế chưa đủ “Bắc/trầm”, giữ nguyên firmware và chỉ đổi TTS.

## Cấu hình tham khảo
```yaml
selected_module:
  TTS: EdgeTTS

TTS:
  EdgeTTS:
    type: edge
    voice: "vi-VN-NamMinhNeural"
    rate: "-6%"
    volume: "+0%"
    pitch: "-4Hz"
```

Tên trường có thể khác đôi chút tùy phiên bản máy chủ Xiaozhi đang dùng.

## Bài thử giọng
1. “Đại Ca cứ yên tâm. Chuyện nhỏ này giao cho Tiểu Đệ.”
2. “Giang hồ hiểm ác, nhưng cái file này còn hiểm hơn.”
3. “Đại Ca cứ nói. Tiểu Đệ chấp bút.”
4. “Quay một vòng à? Được. Đại Ca nhìn kỹ thân pháp đây.”
5. “Việc nghiêm túc thì nói nghiêm túc. Con số này chưa đủ để kết luận.”

## Tiêu chí đạt
- Nghe rõ từng chữ ở loa nhỏ của robot.
- Không quá nhanh.
- Không quá “MC”.
- Không quá già.
- Không kéo dài chữ “Đại Ca”.
- Cà khịa nghe tự nhiên, không giống đọc kịch bản.
