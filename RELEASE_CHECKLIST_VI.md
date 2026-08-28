# Checklist phát hành .bin

Chỉ coi firmware là bản phát hành khi:

- [ ] GitHub Actions báo Success.
- [ ] Bước “Verify PRIVATE V1 code is really inside firmware” PASS.
- [ ] Artifact có `Robot_AI_Private_V1_merged.bin`.
- [ ] Artifact có `SHA256.txt`.
- [ ] Không dùng artifact của build #1 cũ.
- [ ] Nạp thử trên robot thật khi robot đặt dưới sàn.
- [ ] Màn hình ST7789 hiển thị đúng.
- [ ] Mic thu được tiếng Việt.
- [ ] Loa phát rõ.
- [ ] Tiến/lùi đúng chiều.
- [ ] Trái/phải đúng chiều.
- [ ] Dừng hoạt động.
- [ ] TOF050C đọc được khoảng cách.
- [ ] Quay 360 đã hiệu chuẩn.
- [ ] Agent dùng prompt FINAL V2.
- [ ] Giọng TTS đã nghe thử trên loa robot.
- [ ] Mac Bridge kết nối được.
