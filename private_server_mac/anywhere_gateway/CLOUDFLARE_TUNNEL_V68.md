# V6.8 — Cloudflare Tunnel alternative

Dùng phương án này nếu Tailscale Funnel có độ trễ/băng thông không đạt hoặc triển khai cần hạ tầng Cloudflare.

## Điều kiện
- Một zone/domain đang dùng Cloudflare DNS.
- `cloudflared` trên Mac mini hoặc container.
- Không mở port 8000/8003 trên router.

Cloudflare Tunnel hỗ trợ WebSocket và public hostname có thể map về dịch vụ local.

## Kiến trúc
`https/wss://robot.example.com` → Cloudflare Tunnel → `http://127.0.0.1:11438` → nginx secret-path gateway → XiaoZhi.

## Các bước Codex
1. Cài `cloudflared`.
2. `cloudflared tunnel login` — người dùng duyệt cấp quyền.
3. Tạo named tunnel, ví dụ `robot-ai-private`.
4. Tạo DNS route, ví dụ `robot.<domain>`.
5. Cấu hình ingress:
   - hostname: `robot.<domain>`
   - service: `http://127.0.0.1:11438`
6. Chạy tunnel dạng service/LaunchAgent để tự khởi động.
7. Ghi `ANYWHERE_PUBLIC_HOST=robot.<domain>` vào `anywhere_gateway/.env`.
8. Chạy `render_gateway.py`.
9. Patch XiaoZhi `.config.yaml` bằng `patch_public_server_config.py`.
10. Test WSS và OTA trước khi build firmware.

## Lưu ý bảo mật
- Không publish `8000`, `8003`, `11435`, `11437`.
- Chỉ publish gateway `11438` qua tunnel.
- Secret path là lớp bí mật thứ nhất.
- XiaoZhi `server.auth.enabled=true` + token là lớp xác thực thứ hai.
- Không commit `anywhere_gateway/.env`, Cloudflare credentials, `auth_key`.
