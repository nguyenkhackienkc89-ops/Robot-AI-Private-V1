#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
echo "===== V6.7 COST / PRIVACY AUDIT ====="
grep -E '^(LIVE_PAID_SEARCH_ENABLED|PAID_SEARCH_ENABLED|CLOUD_API_KEY|BLOCK_NONFREE_CLOUD)=' "$HERE/dual_brain/.env" 2>/dev/null || true
echo
curl --noproxy '*' -fsS http://127.0.0.1:11437/health | python3 -m json.tool
echo
echo "Expected: paid_search_enabled=false"
echo "SearXNG vẫn gửi từ khóa tìm kiếm tới các công cụ tìm kiếm upstream được cấu hình."
