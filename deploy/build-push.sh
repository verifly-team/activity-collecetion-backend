#!/usr/bin/env bash
# 构建镜像并推送到阿里云私有仓库
#   ./deploy/build-push.sh            # 自动打日期 tag
#   ./deploy/build-push.sh 1.2.0      # 指定 tag
set -euo pipefail
cd "$(dirname "$0")/.."

REGISTRY="${REGISTRY:-crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com}"
NAMESPACE="${NAMESPACE:-arceus}"
IMAGE="${IMAGE:-activity-66-collection-backend}"
TAG="${1:-$(date +%Y%m%d-%H%M)}"
PLATFORM="${PLATFORM:-linux/amd64}"
FULL="$REGISTRY/$NAMESPACE/$IMAGE"

echo "==> 构建 $FULL:$TAG  (platform=$PLATFORM)"
DOCKER_BUILDKIT=0 docker build --platform "$PLATFORM" -t "$FULL:$TAG" -t "$FULL:latest" .

echo "==> 推送 $FULL:$TAG"
docker push "$FULL:$TAG"
docker push "$FULL:latest"

echo "==> 完成"
echo "    $FULL:$TAG"
echo "    $FULL:latest"
