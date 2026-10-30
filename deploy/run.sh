#!/usr/bin/env bash
# 在服务器上启动容器（不用 docker compose 的场景）
#   ./deploy/run.sh .env
set -euo pipefail

ENV_FILE="${1:-.env}"
IMAGE="${IMAGE:-crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:latest}"
UPLOAD_DIR_HOST="${UPLOAD_DIR_HOST:-/verifly/activity/uploads}"
CONTAINER="${CONTAINER:-activity-collection-api}"
PORT="${PORT:-8000}"

# ---- 拦截 .env 里把 UPLOAD_DIR 写成宿主机路径 ----
if [ -f "$ENV_FILE" ]; then
  env_upload="$(
    grep -E '^[[:space:]]*UPLOAD_DIR[[:space:]]*=' "$ENV_FILE" \
      | tail -1 | cut -d= -f2- | tr -d '\r"' | xargs || true
  )"
  if [ -n "$env_upload" ] && [ "$env_upload" != "/data/uploads" ]; then
    echo "WARN: $ENV_FILE 里 UPLOAD_DIR=$env_upload"
    echo "      应为容器内路径 /data/uploads，宿主机路径只能放在 -v 挂载里。"
    echo "      本次启动会用 -e UPLOAD_DIR=/data/uploads 覆盖它。"
    echo "      建议把 .env 里那一行改成 UPLOAD_DIR=/data/uploads"
    echo
  fi
fi

mkdir -p "$UPLOAD_DIR_HOST"
chmod -R a+rX "$UPLOAD_DIR_HOST" 2>/dev/null || true

echo "==> 重建容器 $CONTAINER"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  -e UPLOAD_DIR=/data/uploads \
  -p "$PORT:8000" \
  -v "$UPLOAD_DIR_HOST:/data/uploads" \
  "$IMAGE"

echo "==> 等待启动"
sleep 3
docker ps --filter "name=$CONTAINER"

echo
echo "==> 核对配置（这三处必须对上）"
echo "   容器内 UPLOAD_DIR : $(docker exec "$CONTAINER" printenv UPLOAD_DIR 2>/dev/null || echo 读不到)"
echo "   容器内文件数      : $(docker exec "$CONTAINER" sh -c 'ls -1 /data/uploads 2>/dev/null | wc -l' 2>/dev/null || echo '?')"
echo "   宿主机文件数      : $(ls -1A "$UPLOAD_DIR_HOST" 2>/dev/null | wc -l | tr -d ' ')  ($UPLOAD_DIR_HOST)"
echo
echo "==> 健康检查"
curl -s "localhost:$PORT/healthz"
echo
