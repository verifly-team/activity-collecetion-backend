# 部署手册

## v2 调研字段升级（2026-10）

新增 12 个品牌调研字段 + D 区。**正常无需手工 DDL**：
采集服务启动时 `init_db()` 会检测缺列并自动 `ALTER TABLE ADD COLUMN`。

推荐顺序：

```bash
# 1. 先备份（1 分钟，出事能退）
mysqldump -u root -p --single-transaction verifly_signup application file \
  > backup_$(date +%Y%m%d_%H%M).sql

# 2. 推采集服务 → CI 自动构建部署 → 容器启动时自动加列
git push            # server 仓库

# 3. 确认列已加上（应返回 12 行）
mysql -u root -p verifly_signup -e "SHOW COLUMNS FROM application" | grep -E \
  "founded_year|social_links|brand_intro|channels|has_physical_store|attended_other_events|past_experience|brand_specialty|target_consumers|planned_activities|willing_to_promote|authorize_media"

# 4. 再推导出服务
git push            # export-service 仓库
```

需要手工 DDL 的场景（应用账号无 ALTER 权限等）见 `deploy/migrate_v2.sql`。

前端接完新表单后，把 `.env` 里 `SURVEY_REQUIRED` 改成 `1` 重启容器即可开始强制校验。



> 相关文档：[README](../README.md) · [API](../docs/API.md) · [数据库与存储](../docs/DATABASE.md)

镜像：

```
crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend
```

部署一共五步：**登录仓库 → DBA 建库 → 推镜像 → 起容器 → 验收**。
表结构、附件目录、健康检查都在服务启动时自动完成。

---

## 步骤 0：本机准备（一次性）

```bash
# 登录私有仓库
#   用户名：阿里云账号全名
#   密码：容器镜像服务 → 访问凭证 → 固定密码
docker login crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com
```

若报 `Keychain Error. (-67674)`：
**Docker Desktop → Settings → 取消勾选 "Use credential store"** → 重启 Docker Desktop → 重新 login。
（或打开「钥匙串访问」解锁 `login` 钥匙串）

---

## 步骤 1：DBA 建库（一次性）

把 [`mysql-init.sql`](./mysql-init.sql) 交给 DBA，改掉里面的密码后执行：

```sql
CREATE DATABASE IF NOT EXISTS `verifly_signup`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'verifly'@'%' IDENTIFIED BY '<改成强密码>';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES
  ON `verifly_signup`.* TO 'verifly'@'%';

FLUSH PRIVILEGES;
```

- 给了 `CREATE` 是因为服务首次启动要自建表。若希望 DBA 先手工建表，把 `app/schema_mysql.sql` 给他执行，再把 `CREATE` 收回。
- 应用服务器与数据库不同机时，注意安全组 / 白名单放行。

---

## 步骤 2：构建并推送镜像

### 方式 A：在 Mac 上构建（需要能拉到 `python:3.12-slim` 的 amd64 基础镜像）

```bash
cd <仓库目录>
./deploy/build-push.sh 1.2.0        # 不传参数则用日期 tag
```

脚本等价于：

```bash
REG=crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com
docker build --platform linux/amd64 \
  -t $REG/arceus/activity-66-collection-backend:1.2.0 \
  -t $REG/arceus/activity-66-collection-backend:latest .
docker push $REG/arceus/activity-66-collection-backend:1.2.0
docker push $REG/arceus/activity-66-collection-backend:latest
```

### 方式 B：在服务器上构建（Mac 拉不到基础镜像时用这个）

```bash
# 本机上传代码
rsync -av --exclude .git --exclude data --exclude .env --exclude .pytest_cache \
  ./ user@<服务器>:/verifly/activity-signup/

# 服务器上构建并推送
ssh user@<服务器>
cd /verifly/activity-signup
docker build -t crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0 .
docker push crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0
```

阿里云控制台「容器镜像服务 → 镜像仓库」能看到 `1.2.0` 这个 tag 即为成功。

---

## 步骤 3：服务器准备目录

```bash
mkdir -p /verifly/activity/uploads /verifly/activity/backups

# 容器内以 uid 10001 运行，宿主机目录必须给权限，否则上传报 Permission denied
chown -R 10001:10001 /verifly/activity/uploads
```

| 目录 | 用途 |
|---|---|
| `/verifly/activity/uploads` | **附件本体**，挂载到容器 `/data/uploads` |
| `/verifly/activity/backups` | 备份产物 |

> 文件为什么要放宿主机目录：见 [数据库与存储 · 文件存储](../docs/DATABASE.md#2-文件存储)。

---

## 步骤 4：启动容器

```bash
cd /verifly/activity-signup          # 放 .env 的目录
cp .env.example .env
vim .env                        # 填 DATABASE_URL（必改）、其它按需
```

`.env` 关键项：

```ini
DATABASE_URL=mysql://verifly:<密码>@<MySQL地址>:3306/verifly_signup?charset=utf8mb4
UPLOAD_DIR=/data/uploads
MAX_FILE_MB=20
ALLOWED_ORIGINS=*
```

启动：

```bash
./deploy/run.sh .env
```

等价的手写命令：

```bash
docker run -d \
  --name activity-collection-api \
  --restart unless-stopped \
  --env-file .env \
  -e UPLOAD_DIR=/data/uploads \
  --network host \
  -v /verifly/activity/uploads:/data/uploads \
  crpi-quxtxo1i28qk1e0c.cn-guangzhou.personal.cr.aliyuncs.com/arceus/activity-66-collection-backend:1.2.0
```

换附件目录：`UPLOAD_DIR_HOST=/data/verifly/uploads ./deploy/run.sh .env`

---

## 步骤 5：验收

```bash
docker ps --filter name=activity-collection-api        # Up (healthy)
curl -s localhost:8000/healthz                # {"ok":true}
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/docs   # 200
```

跑一遍完整链路：

```bash
API=http://localhost:8000 ./samples/smoke.sh
```

查数据：

```bash
# 库
mysql -h <host> -u verifly -p verifly_signup \
  -e "SELECT id, brand_name, phone, zones, created_at FROM application ORDER BY id DESC LIMIT 5;"

# 文件（应看到 <报名id>/<uuid>.zip）
ls -R /verifly/activity/uploads | head
```

前端联调：`http://<服务器>:8000/docs` 可以直接在页面上试两个接口。

---

## 步骤 6：备份与定时任务

```bash
# 附件
tar -czf /verifly/activity/backups/uploads-$(date +%F).tar.gz -C /verifly/activity/uploads .

# 数据库
mysqldump -h <host> -u verifly -p --single-transaction \
  --default-character-set=utf8mb4 verifly_signup \
  | gzip > /verifly/activity/backups/db-$(date +%F).sql.gz
```

crontab（清理孤儿附件 + 每日备份）：

```cron
0 3 * * * docker exec -T activity-collection-api python -m app.cleanup --hours 24
0 4 * * * /verifly/activity/backup.sh
```

恢复流程见 [数据库与存储 §3.2](../docs/DATABASE.md#32-恢复)。

---

## 日常运维

| 操作 | 命令 |
|---|---|
| 看日志 | `docker logs -f activity-collection-api` |
| 重启 | `docker restart activity-collection-api` |
| 升级 | `docker pull <镜像>:latest && docker rm -f activity-collection-api && ./deploy/run.sh .env` |
| 回滚 | `TAG=1.2.0 ./deploy/run.sh .env`（旧 tag 保留在仓库） |
| 进容器 | `docker exec -it activity-collection-api sh` |
| 清理孤儿附件 | `docker exec -T activity-collection-api python -m app.cleanup --hours 24 --dry-run` |

---

## 排障

| 现象 | 原因 / 处理 |
|---|---|
| 容器反复重启，日志 `Access denied for user` | `DATABASE_URL` 账号密码不对，或授权不是 `'verifly'@'%'` |
| `/healthz` 返回 503 | 数据库连不上：网络/白名单、端口、库名、账号 |
| 日志 `Table doesn't exist` | 账号缺 `CREATE` 权限，让 DBA 直接执行 `app/schema_mysql.sql` |
| 上传报 500，日志 `Permission denied` | `chown -R 10001:10001 /verifly/activity/uploads` |
| 中文变问号 | 库或表不是 `utf8mb4`，重建库时指定 `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` |
| 提交报 429 | 触发限流，调大 `RATE_LIMIT_PER_MINUTE` 或检查 `X-Forwarded-For` |
| 上传大文件失败 | `MAX_FILE_MB` / `MAX_TOTAL_MB` 没调，或前面有 nginx `client_max_body_size` |
