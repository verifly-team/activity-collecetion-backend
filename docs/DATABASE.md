# 数据与存储设计

> 版本 `1.2.0` ｜ 相关文档：[API.md](API.md) · [DEPLOY.md](../deploy/DEPLOY.md)

服务只存两样东西：**报名数据进数据库，文件本体进磁盘目录**。数据库里只保存文件的相对路径。

```
                      ┌──────────────────────────────────────────┐
商家提交 ────────────▶ │  MySQL: verifly_signup                   │
                      │   ├── application  报名主表              │
                      │   └── file         附件元数据            │
                      └──────────────────────────────────────────┘
                                     │ stored_path = "12/3f2a….zip"
                                     ▼
                      ┌──────────────────────────────────────────┐
                      │  磁盘: /verifly/activity/uploads              │
                      │   ├── 12/                                │
                      │   │   └── 3f2a….zip                      │
                      │   └── 3f2a….zip  （已传未提交的孤儿）    │
                      └──────────────────────────────────────────┘
```

---

## 1. 数据库

### 1.1 选型

| 环境 | `DATABASE_URL` | 说明 |
|---|---|---|
| 线上 | `mysql://user:pass@host:3306/verifly_signup?charset=utf8mb4` | 服务器现成实例，单独建库 |
| 本地 | `sqlite:///data/app.db` | 不装 MySQL 也能开发 |

两套 DDL：`app/schema_mysql.sql` / `app/schema_sqlite.sql`，服务启动时自动执行（`CREATE TABLE IF NOT EXISTS`），无需手工迁移。

字符集固定 `utf8mb4 / utf8mb4_unicode_ci`，中文与 emoji 均可存。

### 1.2 `application` —— 报名主表

一次提交一行。完整字段含义见 [API.md · 字段总表](API.md#5-字段总表)，这里只列存储要点：

| 列 | 类型（MySQL） | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED PK | 自增，同时决定附件子目录名 `uploads/{id}/` |
| `brand_name` / `contact_name` / `phone` | VARCHAR NOT NULL | 核心联络信息 |
| `wechat` / `email` | VARCHAR NULL | 至少一项非空（接口层校验） |
| `city` / `entity_type` | VARCHAR NULL | 城市、主体类型 |
| `is_first_time` | TINYINT(1) | 是否首次参展 |
| `categories` | VARCHAR(200) | JSON 数组字符串，如 `["bag","apparel"]` |
| `zones` | VARCHAR(50) | JSON 数组字符串，如 `["A","C"]` |
| `expected_qty` / `price_min` / `price_max` | INT | 带货规模 |
| `pct_secondhand` / `pct_new_stock` / `pct_sample` / `pct_replica` | TINYINT | 商品结构，四项合计 100（不填则全 NULL） |
| `items_json` | TEXT | 代表商品清单 JSON 数组 |
| `consent_at` / `privacy_version` | VARCHAR | 同意留痕 |
| `source` | VARCHAR(30) | `h5` / `qrcode` / `word` |
| `created_at` | VARCHAR(32) | ISO8601 UTC 字符串 |

索引：`phone`、`city`、`created_at`。

> **为什么 JSON 存 VARCHAR/TEXT 而不是 JSON 类型**：这两列只做整体读写、不参与查询，保持与 SQLite 完全一致的 DDL 语义，迁移成本最低。

### 1.3 `file` —— 附件元数据

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | VARCHAR(32) PK | uuid hex，同时是磁盘文件名 |
| `application_id` | BIGINT NULL | 关联报名；**提交前为 NULL** 即为孤儿 |
| `kind` | VARCHAR(20) | `photos` / `list` / `other` |
| `original_name` | VARCHAR(255) | 用户原始文件名（如 `照片.zip`） |
| `stored_path` | VARCHAR(255) | 相对 `UPLOAD_DIR` 的路径，如 `12/3f2a….zip` |
| `mime` / `size` / `sha256` | — | 元信息，`sha256` 用于排重与完整性校验 |
| `created_at` | VARCHAR(32) | 上传时间 |

外键 `fk_file_application` → `application(id)` **ON DELETE CASCADE**：删报名自动清附件记录。

---

## 2. 文件存储

### 2.1 目录布局

```
$UPLOAD_DIR/                     容器内 /data/uploads，宿主机 /verifly/activity/uploads
├── 3f2a1c9b0d4e….zip            ← 已上传、尚未提交（孤儿）
├── 4d2f7a318c9e….png            ← 同上
├── 12/                          ← 报名 id=12 的附件
│   ├── 8b1c9e77a1b2….zip
│   └── 4d2f7a318c9e….png
└── 13/
    └── a1b2c3d4e5f6….zip
```

- **文件名用 uuid**：避免重名冲突、中文乱码、路径穿越（原始文件名只存库，不落盘）
- **按报名 id 分目录**：运营要某家的材料，`ls /verifly/activity/uploads/12/` 即可
- **提交时移动**：从根目录挪进 `{报名id}/`，同时更新 `stored_path`

### 2.2 一个文件的生命周期

| 阶段 | 磁盘 | 数据库 |
|---|---|---|
| 空 | — | — |
| `POST /uploads` 成功 | `uploads/3f2a….zip` | `application_id=NULL`，`stored_path=3f2a….zip` |
| `POST /applications` 成功 | 挪到 `uploads/12/3f2a….zip` | `application_id=12`，`stored_path=12/3f2a….zip` |
| 提交失败 / 用户放弃 | 留在根目录 | 始终 `NULL` → 定时清理 |
| 删除报名 | 需手工删目录 | `ON DELETE CASCADE` 删元数据 |

> ⚠️ 数据库删了报名，**磁盘文件不会自动删**。要清干净得同时删 `uploads/{id}/` 目录（见 §4.3）。

### 2.3 容量估算

| 场景 | 估算 |
|---|---|
| 100 家 × 1 个 zip（上限 20MB） | 最坏约 2GB，实际多在 500MB ~ 1GB |
| 建议磁盘预留 | 20GB（含备份） |

超过 50GB、需要 CDN 或多机共享时，再考虑对象存储（见 §5）。

---

## 3. 备份与恢复

### 3.1 备份（库 + 文件必须同一时点）

```bash
STAMP=$(date +%F)

# ① 文件
tar -czf /verifly/activity/backups/uploads-$STAMP.tar.gz -C /verifly/activity/uploads .

# ② 数据库
mysqldump -h <host> -u verifly -p --single-transaction \
  --default-character-set=utf8mb4 verifly_signup \
  | gzip > /verifly/activity/backups/db-$STAMP.sql.gz
```

放进 crontab：

```cron
0 3 * * * /verifly/activity/backup.sh
```

### 3.2 恢复

```bash
gunzip < db-2026-12-20.sql.gz | mysql -h <host> -u verifly -p verifly_signup
tar -xzf uploads-2026-12-20.tar.gz -C /verifly/activity/uploads
chown -R 10001:10001 /verifly/activity/uploads
```

### 3.3 校验一致性

附件是否齐全（库里记了但磁盘没文件的）：

```sql
SELECT id, stored_path FROM file WHERE application_id IS NOT NULL;
```

```bash
# 逐个核对（在宿主机执行）
mysql -N -h <host> -u verifly -p verifly_signup \
  -e "SELECT stored_path FROM file WHERE application_id IS NOT NULL" \
| while read p; do [ -f "/verifly/activity/uploads/$p" ] || echo "缺失: $p"; done
```

---

## 4. 运维脚本

### 4.1 清理孤儿附件

传了附件却没提交的记录会一直堆在根目录：

```bash
docker exec -T activity-collection-api python -m app.cleanup --hours 24 --dry-run   # 先看
docker exec -T activity-collection-api python -m app.cleanup --hours 24            # 再删
```

建议挂 crontab 每天跑一次。

### 4.2 导出报名明细

```bash
mysql -h <host> -u verifly -p verifly_signup -e "
SELECT id, created_at, brand_name, contact_name, phone, wechat, city,
       categories, zones, expected_qty,
       CONCAT(price_min,'~',price_max) AS price_range,
       CONCAT('二手',pct_secondhand,'% 未使用',pct_new_stock,
              '% 样衣',pct_sample,'% 复刻',pct_replica,'%') AS structure,
       items_json
FROM application ORDER BY id" > 报名.tsv
```

### 4.3 删除某个报名（含附件）

```sql
DELETE FROM application WHERE id = 123;   -- file 记录随外键级联删除
```

```bash
rm -rf /verifly/activity/uploads/123
```

---

## 5. 何时该换对象存储

当前「本地磁盘 + 卷」方案适用于单机、GB 级数据，成本最低、备份最直观。出现下列情况再迁 OSS / COS：

- 单机磁盘不够，或需要 CDN 加速
- 多台应用实例共享附件
- 不希望自己管备份与扩容

迁移时只需改 `app/main.py` 上传落盘那一段（约 30 行），`file` 表和接口完全不用动 —— 因为库里存的本就是「路径字符串」。
