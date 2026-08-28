#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
docker compose down
echo "Đã dừng máy chủ Robot AI Private."
