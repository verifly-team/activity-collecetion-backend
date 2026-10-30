#!/usr/bin/env bash
# 上传目录诊断：一次看清「配置 / 挂载 / 磁盘 / 数据库」是否一致
#
# 用法（在服务器上）：bash diagnose-upload.sh [容器名] [宿主机附件目录]
#   bash diagnose-upload.sh verifly-signup /verifly/activity/uploads

set -uo pipefail
CONTAINER="${1:-verifly-signup}"
HOST_DIR="${2:-/verifly/activity/uploads}"

say() { printf '%s\n' "$*"; }
hr() { printf '%s\n' "------------------------------------------------------------"; }

hr
say "1) 容器是否存在"
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  say "❌ 找不到容器 $CONTAINER"
  say "   先确认：docker ps -a | grep signup"
  exit 1
fi
say "✅ 容器存在：$(docker inspect -f '{{.State.Status}}  启动于 {{.State.StartedAt}}' "$CONTAINER")"

hr
say "2) 容器里的 UPLOAD_DIR（关键！必须是容器内路径）"
INNER_DIR="$(docker exec "$CONTAINER" printenv UPLOAD_DIR 2>/dev/null || echo '')"
if [ -z "$INNER_DIR" ]; then
  say "⚠️ 没设置 UPLOAD_DIR，用的是代码默认值 data/uploads（相对路径，更危险）"
else
  say "   UPLOAD_DIR = $INNER_DIR"
  case "$INNER_DIR" in
    /data/uploads) say "   ✅ 正确（容器内路径）" ;;
    /verifly/*)    say "   ❌ 错误！这是宿主机路径，容器内没有它，文件会写进容器可写层" ;;
    /*)            say "   ⚠️ 是绝对路径，确认它是不是挂载点" ;;
    *)             say "   ⚠️ 相对路径，会写在容器当前工作目录下" ;;
  esac
fi

hr
say "3) 卷挂载"
docker inspect "$CONTAINER" --format '{{range .Mounts}}   {{.Source}}  ->  {{.Destination}}  ({{.Mode}}){{println}}{{end}}'

hr
say "4) 容器内两个目录的文件数"
for d in "$INNER_DIR" /data/uploads; do
  [ -z "$d" ] && continue
  n="$(docker exec "$CONTAINER" sh -c "ls -1 '$d' 2>/dev/null | wc -l" 2>/dev/null || echo '?')"
  say "   容器内 $d : $n 个文件"
done

hr
say "5) 宿主机目录 $HOST_DIR"
if [ -d "$HOST_DIR" ]; then
  n="$(ls -1A "$HOST_DIR" 2>/dev/null | wc -l | tr -d ' ')"
  say "   存在，$n 个文件"
  ls -lA "$HOST_DIR" 2>/dev/null | head -5 | sed 's/^/   /'
  say "   属主：$(stat -c '%U:%G %a' "$HOST_DIR" 2>/dev/null)"
else
  say "   ❌ 不存在"
fi

hr
say "6) 数据库里的附件记录数"
DB_N="$(docker exec "$CONTAINER" python -c "
import os,sys
sys.path.insert(0,'/app')
try:
    from app import db
    r = db.fetch_one('SELECT COUNT(*) AS n FROM file')
    print(r['n'] if r else 0)
except Exception as e:
    print('ERR:' + str(e)[:60])
" 2>/dev/null || echo '?')"
say "   file 表记录数：$DB_N"

hr
say "7) 结论"
HOST_N="$(ls -1A "$HOST_DIR" 2>/dev/null | wc -l | tr -d ' ')"
if [ "$INNER_DIR" != "/data/uploads" ]; then
  say "❌ 根因：UPLOAD_DIR 不是 /data/uploads"
  say ""
  say "   修复（宿主机执行，会重建容器）："
  say "     cd /verifly/activity && UPLOAD_DIR_HOST=$HOST_DIR ./deploy/run.sh"
  say ""
  say "   注意：docker restart 不会更新环境变量，必须删掉容器重建。"
  say "   旧文件可以抢救：docker cp $CONTAINER:$INNER_DIR/. $HOST_DIR/"
elif [ "${DB_N:-0}" != "0" ] && [ "${HOST_N:-0}" = "0" ]; then
  say "❌ 配置看着对，但宿主机目录是空的"
  say "   可能容器是改配置之前创建的：docker inspect 的 Created 时间 vs 上次修改配置的时间"
  say "   重建：cd /verifly/activity && UPLOAD_DIR_HOST=$HOST_DIR ./deploy/run.sh"
elif [ "${HOST_N:-0}" != "0" ]; then
  say "✅ 宿主机目录有文件，配置看起来是正确的"
else
  say "ℹ️ 目录都是空的，可能确实还没成功上传过"
  say "   传一个测试文件，然后重新跑这个脚本对比"
fi
hr
