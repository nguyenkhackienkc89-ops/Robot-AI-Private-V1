# MacBook Pro M1 Pro 32GB — Qwen3.5 35B node

V6.5 mặc định dùng `qwen3.5:35b-a3b-int4`.

Cấu hình:
- context 4096
- think=false mặc định
- keep_alive 5m
- chỉ chạy Ollama/Qwen35 trên MacBook
- không cần chạy XiaoZhi/Docker/ASR trên MacBook

Kết nối khuyến nghị: SSH tunnel từ Mac mini.
MacBook vẫn giữ Ollama ở localhost, không mở cổng 11434 ra toàn LAN.
