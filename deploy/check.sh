#!/usr/bin/env bash
# 服务器上一键自检：MySQL 连通性 + 应用健康 + 业务链路
#
#   DB_HOST=172.24.155.121 DB_PASS='密码' ./deploy/check.sh
#   # 用 host 网络时：
#   NET=host DB_HOST=127.0.0.1 DB_PASS='密码' ./deploy/check.sh
set -uo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-verifly}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-verifly_signup}"
REG="${REG:-crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0}"
NET="${NET:-bridge}"
APP="${APP:-http://127.0.0.1:8000}"

pass() { printf '  \033[32m✅ %s\033[0m\n' "$1"; }
fail() { printf '  \033[31m❌ %s\033[0m\n' "$1"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "1/7 MySQL 是否在监听 $DB_PORT"
if ss -lntp 2>/dev/null | grep -q ":$DB_PORT"; then
  pass "$(ss -lntp | grep ":$DB_PORT" | head -1 | awk '{print $4}')"
else
  fail "没有进程监听 $DB_PORT —— MySQL 没起来或端口不对"
fi

head_ "2/7 宿主机能否连到 $DB_HOST:$DB_PORT"
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$DB_HOST/$DB_PORT" 2>/dev/null; then
  pass "宿主机可达"
else
  fail "宿主机不可达（MySQL 挂了或端口被挡）"
fi

head_ "3/7 账号密码是否可用"
if [ -n "$DB_PASS" ]; then
  if mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT 1" >/dev/null 2>&1; then
    pass "账号 $DB_USER 可以访问 $DB_NAME"
  else
    fail "账号或库不可用（Access denied / Unknown database）"
  fi
else
  echo "  ⏭  跳过（未提供 DB_PASS）"
fi

head_ "4/7 容器内能否连到 $DB_HOST:$DB_PORT（NET=$NET）"
if docker run --rm --network "$NET" "$REG" python -c "
import socket, sys
socket.create_connection(('$DB_HOST', $DB_PORT), 5)
" 2>/dev/null; then
  pass "容器网络可达 —— 防火墙没问题"
else
  fail "容器不可达 —— 防火墙挡了 docker 网段，或用了 127.0.0.1 但没走 host 网络"
fi

head_ "5/7 容器内能否用账号登录数据库"
if [ -n "$DB_PASS" ]; then
  if docker run --rm --network "$NET" -e P="$DB_PASS" "$REG" python -c "
import os, pymysql
c = pymysql.connect(host='$DB_HOST', port=$DB_PORT, user='$DB_USER',
                    password=os.environ['P'], database='$DB_NAME', connect_timeout=5)
c.ping(); c.close()
" 2>/dev/null; then
    pass "容器内登录成功"
  else
    fail "容器内登录失败（看上一行报错：Access denied = 密码/授权，timeout = 网络）"
  fi
else
  echo "  ⏭  跳过（未提供 DB_PASS）"
fi

head_ "6/7 应用健康检查"
if curl -sf "$APP/healthz" >/dev/null; then
  pass "$(curl -s "$APP/healthz")"
else
  fail "应用未就绪，看 docker logs --tail 30 verifly-signup"
fi

head_ "7/7 业务链路：上传附件 → 提交报名"
tmp=$(mktemp -d)
echo hello > "$tmp/a.txt"
(cd "$tmp" && zip -q t.zip a.txt) || { fail "服务器没有 zip 命令，跳过"; exit 0; }

FID=$(curl -s -X POST "$APP/api/v1/uploads" -F "file=@$tmp/t.zip" -F "kind=photos" \
      | sed -E 's/.*"file_id":"([^"]+)".*/\1/')
if [ -n "$FID" ] && [ "$FID" != "" ]; then
  pass "上传成功 file_id=$FID"
else
  fail "上传失败"; exit 1
fi

RES=$(curl -s -X POST "$APP/api/v1/applications" -H 'Content-Type: application/json' -d "{
  \"brand_name\":\"自检店铺\",\"contact_name\":\"自检\",\"phone\":\"13800138000\",
  \"wechat\":\"selftest\",\"city\":\"深圳\",\"categories\":[\"bag\"],\"zones\":[\"A\"],
  \"file_ids\":[\"$FID\"],\"consent\":true}")
echo "  $RES"
case "$RES" in
  *'"id"'*) pass "提交成功" ;;
  *) fail "提交失败" ;;
esac

printf '\n\033[1m做完记得删掉这条测试数据：\033[0m\n'
echo "  mysql -h$DB_HOST -u$DB_USER -p $DB_NAME -e \"DELETE FROM application WHERE brand_name='自检店铺';\""
echo "  rm -rf /opt/verifly/uploads/<上面的 id>"
