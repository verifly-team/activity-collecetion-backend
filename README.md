# activity-collection-backend

66th & 2nd Vintage Fashion Show & Market（深圳）—— **商家参展申请采集服务**。

一个容器、两张表、两个接口。收到数据直接进 SQLite，附件落到磁盘目录，运营需要时直接开库导出。

---

## 1. 跑起来

```bash
cp .env.example .env
docker compose up -d --build
curl localhost:8000/healthz          # {"ok":true}
open http://localhost:8000/docs      # 自动生成的接口文档
```

数据都在 `./data`：

```
data/
├── app.db                 # SQLite（报名主表 + 附件表）
└── uploads/
    └── 1/                 # 按报名 id 分目录，运维直接打包捞走
        └── 3f2a….zip
```

不带 Docker 本地跑：

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 2. 两个接口

### 2.1 `POST /api/v1/uploads` —— 先传附件

`multipart/form-data`

| 字段 | 必填 | 说明 |
|---|---|---|
| `file` | ✅ | 图片 / PDF / zip |
| `kind` | | `photos`（商品图）· `list`（商品清单）· `other` |

单文件默认上限 **20MB**，支持 `jpg jpeg png webp heic pdf zip`；zip 只校验文件头，**不解压**（防 zip 炸弹）。

```bash
curl -X POST localhost:8000/api/v1/uploads \
  -F "file=@samples/photos.zip" -F "kind=photos"
# {"file_id":"3f2a…","original_name":"photos.zip","size":311,"kind":"photos"}
```

### 2.2 `POST /api/v1/applications` —— 再提交表单

`application/json`

```json
{
  "brand_name": "拾光中古",
  "contact_name": "陈小姐",
  "phone": "13800138000",
  "wechat": "shiguang_vtg",
  "email": null,
  "city": "深圳",
  "entity_type": "company",
  "is_first_time": false,
  "categories": ["bag", "apparel"],
  "zones": ["A", "C"],
  "expected_qty": 180,
  "price_min": 800,
  "price_max": 28000,
  "structure": {"secondhand": 60, "new_stock": 30, "sample": 10, "replica": 0},
  "items": [
    {
      "name": "Hermès Birkin 30 金棕",
      "era_series": "2015 年 / Birkin",
      "condition_source": "二手 / 附购买凭证",
      "price": 52000
    }
  ],
  "file_ids": ["3f2a…"],
  "consent": true,
  "source": "h5"
}
```

返回：

```json
{"id": 1, "files": 1, "created_at": "2026-10-27T12:45:04Z"}
```

---

## 3. 采集字段

### application（报名主表）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `brand_name` | TEXT | ✅ | 品牌／店铺名称 |
| `contact_name` | TEXT | ✅ | 联系人 |
| `phone` | TEXT | ✅ | 手机号，自动去 `+86`、空格、横线，校验 `^1[3-9]\d{9}$` |
| `wechat` / `email` | TEXT | 二选一 | 至少提供一项 |
| `city` | TEXT | | 所在城市 |
| `entity_type` | TEXT | | `company` 公司 / `individual` 个体工商户 / `personal` 个人 |
| `is_first_time` | INTEGER | | 是否首次参展 |
| `categories` | JSON | ✅ | 经营品类：`bag` 箱包 · `watch` 腕表 · `jewelry` 珠宝 · `apparel` 服饰 · `shoe` 鞋履 · `other` 其他 |
| `zones` | JSON | ✅ | 意向区域：`A` 收藏级 Archive · `B` 工装与街头 · `C` 二手名牌／样衣 |
| `expected_qty` | INTEGER | | 预计带货件数 |
| `price_min` / `price_max` | INTEGER | | 价格区间（元） |
| `pct_secondhand` `pct_new_stock` `pct_sample` `pct_replica` | INTEGER ×4 | | 商品结构占比，**四项合计必须 100** |
| `items_json` | JSON | | 代表商品 3~5 件：`name` / `era_series` / `condition_source` / `price` |
| `consent_at` `privacy_version` | TEXT | ✅ | 同意时间与政策版本（合规留痕） |
| `source` | TEXT | | `h5` / `qrcode` / `word` |
| `created_at` | TEXT | ✅ | UTC ISO8601 |

### file（附件表）

`id` · `application_id` · `kind` · `original_name` · `stored_path` · `mime` · `size` · `sha256` · `created_at`

---

## 4. 运营怎么拿数据

```bash
# 报名明细（Excel 直接打开；items_json 里是代表商品清单）
docker compose exec -T signup python - <<'PY' > 报名.csv
import sqlite3, csv, sys
c = sqlite3.connect("/data/app.db"); c.row_factory = sqlite3.Row
w = csv.writer(sys.stdout)
w.writerow(["id","时间","品牌","联系人","手机","微信","城市","品类","区域","带货件数","价格区间","商品结构","代表商品"])
for r in c.execute("select * from application order by id"):
    w.writerow([r["id"], r["created_at"], r["brand_name"], r["contact_name"], r["phone"],
                r["wechat"], r["city"], r["categories"], r["zones"], r["expected_qty"],
                f'{r["price_min"]}~{r["price_max"]}',
                f'二手{r["pct_secondhand"]}% 未使用{r["pct_new_stock"]}% 样衣{r["pct_sample"]}% 复刻{r["pct_replica"]}%',
                r["items_json"]])
PY

# 附件：按报名分目录，直接打包
tar -czf uploads.tar.gz data/uploads/
```

清理「传了附件但没提交」的孤儿文件（建议加进 crontab，每天跑一次）：

```bash
docker compose exec -T signup python -m app.cleanup --hours 24 --dry-run   # 先看
docker compose exec -T signup python -m app.cleanup --hours 24             # 再删
```

备份数据库：`docker compose exec signup python -c "import sqlite3;sqlite3.connect('/data/app.db').execute(\"VACUUM INTO '/data/app.db.bak'\")"`，或直接复制 `data/app.db`（先停容器最稳）。

---

## 5. 常见问题

**Linux 上启动报 `unable to open database file`**：`./data` 目录是 Docker 用 root 建的，容器里跑的是 uid 10001。先建好目录并给权限：

```bash
mkdir -p data/uploads && sudo chown -R 10001:10001 data
```

**为什么 `--workers 1`**：SQLite 单写者，多 worker 只会互相等锁。这台机器的量级（几百份报名）单进程绰绰有余。

**限流按 IP 算**：如果前面挂了 Nginx / 负载均衡，记得透传 `X-Forwarded-For`，否则所有人共用网关 IP 会一起被限。

## 6. 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_PATH` | `/data/app.db` | SQLite 路径 |
| `UPLOAD_DIR` | `/data/uploads` | 附件目录 |
| `MAX_FILE_MB` | `20` | 单文件上限 |
| `MAX_FILES` | `10` | 每份报名附件个数 |
| `MAX_TOTAL_MB` | `100` | 每份报名附件合计 |
| `ALLOWED_EXT` | `jpg,jpeg,png,webp,heic,pdf,zip` | 允许的扩展名 |
| `ALLOWED_ORIGINS` | `*` | CORS；前后端不同域时改成前端域名 |
| `RATE_LIMIT_PER_MINUTE` | `20` | 同 IP 每分钟请求上限 |
| `PRIVACY_VERSION` | `v1.0` | 写入记录的隐私政策版本 |

---

## 7. 前端怎么接

```ts
// 1) 选完文件立刻上传，拿到 file_id
const fd = new FormData()
fd.append('file', zipFile)
fd.append('kind', 'photos')
const up = await fetch(`${API}/api/v1/uploads`, { method: 'POST', body: fd }).then(r => r.json())

// 2) 提交表单
await fetch(`${API}/api/v1/applications`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ...form, file_ids: [up.file_id], consent: true }),
})
```

开发期跨域：前端 `vite.config.mjs` 里加

```js
server: { proxy: { '/api': 'http://localhost:8000' } }
```

---

## 8. 开发与测试

```bash
pip install -r requirements-dev.txt
pytest -q          # 13 个用例：提交、手机号规范化、结构合计、consent 必传、附件复用、超限、伪 zip、孤儿附件
```

```
app/
├── main.py        # 两个接口 + 限流 + 健康检查
├── cleanup.py     # 孤儿附件清理
├── models.py      # Pydantic 校验（Chinese 报错信息）
├── db.py          # sqlite3 数据层
├── config.py      # 环境变量
└── schema.sql     # 两张表的 DDL
```
