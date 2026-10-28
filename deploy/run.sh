#!/usr/bin/env bash
# 在服务器上启动容器（不用 docker compose 的场景）
#   ./deploy/run.sh .env
set -euo pipefail

ENV_FILE="${1:-.env}"
IMAGE="${IMAGE:-crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:latest}"
UPLOAD_DIR_HOST="${UPLOAD_DIR_HOST:-/opt/verifly/uploads}"

mkdir -p "$UPLOAD_DIR_HOST"
docker rm -f verifly-signup >/dev/null 2>&1 || true

docker run -d \
  --name verifly-signup \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  -e UPLOAD_DIR=/data/uploads \
  -p 8000:8000 \
  -v "$UPLOAD_DIR_HOST:/data/uploads" \
  "$IMAGE"

sleep 3
docker ps --filter name=verifly-signup
curl -s localhost:8000/healthz
echo
