#!/bin/bash
set -euo pipefail
URL="http://127.0.0.1:11437/query"

ask() {
  local q="$1"
  echo
  echo "========================================================"
  echo "Q: $q"
  python3 - "$URL" "$q" <<'PY'
import json,sys,urllib.request
url,q=sys.argv[1],sys.argv[2]
req=urllib.request.Request(url,
 data=json.dumps({"query":q},ensure_ascii=False).encode(),
 headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req,timeout=15) as r:
    obj=json.load(r)
print(json.dumps(obj,ensure_ascii=False,indent=2))
PY
}

ask "Tin AI mới nhất hôm nay có gì đáng chú ý?"
ask "Thời tiết Hà Nội hôm nay thế nào?"
ask "Tỷ giá USD/VND hiện tại là bao nhiêu?"
ask "Giá Bitcoin hiện tại là bao nhiêu?"
