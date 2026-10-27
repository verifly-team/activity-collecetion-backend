#!/usr/bin/env bash
# 冒烟测试：起服务后执行，验证「上传附件 → 提交表单」两条链路
set -euo pipefail
API=${API:-http://localhost:8000}
cd "$(dirname "$0")/.."

echo "1) 造一个 zip 当附件"
tmp=$(mktemp -d)
echo "hello" > "$tmp/a.txt"
(cd "$tmp" && zip -q photos.zip a.txt)

echo "2) 上传"
FID=$(curl -s -X POST "$API/api/v1/uploads" \
        -F "file=@$tmp/photos.zip" -F "kind=photos" \
      | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")
echo "   file_id=$FID"

echo "3) 提交报名"
python3 - "$FID" "$tmp/payload.json" <<'PYEOF'
import json, sys
fid, out = sys.argv[1], sys.argv[2]
with open("samples/application.example.json", encoding="utf-8") as f:
    payload = json.load(f)
payload["file_ids"] = [fid]
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
PYEOF

curl -s -X POST "$API/api/v1/applications" \
  -H "Content-Type: application/json" \
  -d @"$tmp/payload.json"
echo
echo "完成"
