# 部署操作手册

> 需要人肉操作的只有三步：**建库 → 推镜像 → 起容器**。
> 其余（表结构、附件目录、健康检查）服务启动时自动完成。

镜像地址：

```
crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend
```

---

## 步骤 0：本机准备（一次性）

```bash
# 登录私有仓库（账号：阿里云账号全名；密码：容器镜像服务里设的「固定密码」）
docker login crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com
```

如果报 `Keychain Error. (-67674)`：
**Docker Desktop → Settings → 取消勾选 "Use credential store"**，重启 Docker Desktop 后再 login。
（或打开「钥匙串访问」，解锁 `login` 钥匙串）

---

## 步骤 1：DBA 建库（一次性）

把 [`mysql-init.sql`](./mysql-init.sql) 发给 DBA，改掉里面的库名/密码后执行：

```sql
CREATE DATABASE IF NOT EXISTS `verifly_signup`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'verifly'@'%' IDENTIFIED BY '<改成强密码>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES
  ON `verifly_signup`.* TO 'verifly'@'%';
FLUSH PRIVILEGES;
```

建完告诉我要连接串，或自己填进 `.env` 的 `DATABASE_URL`。

---

## 步骤 2：构建并推送镜像

**方式 A：在 Mac 上构建**（需要能拉 `python:3.12-slim` 的 amd64 基础镜像）

```bash
cd <仓库目录>/server
./deploy/build-push.sh 1.2.0
```

**方式 B：在服务器上构建**（Mac 拉不到基础镜像时用这个）

```bash
# 本机把代码传上去
rsync -av --exclude .git --exclude data --exclude .env --exclude .pytest_cache \
  ./server/ user@<服务器>:/opt/verifly-signup/

# 服务器上
ssh user@<服务器>
cd /opt/verifly-signup
docker build -t crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0 .
docker push crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0
```

推完在阿里云控制台「容器镜像服务 → 镜像仓库」里能看到 `1.2.0` 这个 tag 就成功了。

---

## 步骤 3：服务器上启动

```bash
mkdir -p /opt/verifly/uploads
cd /opt/verifly-signup          # 或任何放 .env 的目录
cp .env.example .env && vim .env   # 填 DATABASE_URL

./deploy/run.sh .env
```

等价的手写命令：

```bash
docker run -d \
  --name verifly-signup \
  --restart unless-stopped \
  --env-file .env \
  -e UPLOAD_DIR=/data/uploads \
  -p 8000:8000 \
  -v /opt/verifly/uploads:/data/uploads \
  crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0
```

---

## 步骤 4：验收

```bash
docker ps --filter name=verifly-signup          # 状态应为 Up (healthy)
curl -s localhost:8000/healthz                  # {"ok":true}
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/docs   # 200

# 跑一遍完整链路（上传 + 提交），用仓库里的冒烟脚本
API=http://localhost:8000 ./samples/smoke.sh
```

再查一下数据：

```bash
mysql -h <host> -u verifly -p verifly_signup \
  -e "SELECT id, brand_name, phone, zones, created_at FROM application ORDER BY id DESC LIMIT 5;"
ls -R /opt/verifly/uploads | head        # 应看到 <报名id>/<uuid>.zip
```

---

## 日常运维

| 操作 | 命令 |
|---|---|
| 看日志 | `docker logs -f verifly-signup` |
| 重启 | `docker restart verifly-signup` |
| 升级 | `docker pull <镜像>:latest && docker rm -f verifly-signup && ./deploy/run.sh .env` |
| 回滚 | `TAG=1.1.0 ./deploy/run.sh .env`（旧 tag 还在仓库里） |
| 清理孤儿附件 | `docker exec -T verifly-signup python -m app.cleanup --hours 24 --dry-run` |

---

## 常见故障

| 现象 | 原因 / 处理 |
|---|---|
| 容器反复重启，日志 `Access denied for user` | `DATABASE_URL` 账号密码或授权范围不对（`'verifly'@'%'`） |
| `/healthz` 返回 503 | 数据库连不上，检查网络白名单、端口、库名 |
| 提交返回 500，日志 `Table doesn't exist` | 账号缺 `CREATE` 权限，让 DBA 直接执行 `app/schema_mysql.sql` |
| 附件传不上去，日志 `Permission denied` | `/opt/verifly/uploads` 属主不是容器内 uid 10001：`chown -R 10001:10001 /opt/verifly/uploads` |
| 中文变问号 | 库表字符集不是 `utf8mb4`，重建库时指定 `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` |
