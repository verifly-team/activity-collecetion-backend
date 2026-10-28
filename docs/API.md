# API 文档 —— 商家参展申请采集服务

> 版本 `1.2.0` ｜ 更新于 2026-10
> 在线交互版：启动服务后访问 **`/docs`**（Swagger UI）或 **`/openapi.json`**（原始 schema）

---

## 目录

1. [概览](#1-概览)
2. [通用约定](#2-通用约定)
3. [枚举字典](#3-枚举字典)
4. [接口详情](#4-接口详情)
   - [4.1 上传附件 `POST /api/v1/uploads`](#41-上传附件)
   - [4.2 提交申请 `POST /api/v1/applications`](#42-提交申请)
   - [4.3 健康检查 `GET /healthz`](#43-健康检查)
   - [4.4 服务信息 `GET /`](#44-服务信息)
5. [字段总表](#5-字段总表)
6. [完整接入示例](#6-完整接入示例)
7. [数据落地](#7-数据落地)
8. [变更记录](#8-变更记录)

---

## 1. 概览

一个容器、两张表、两个业务接口，用来收 **66th & 2nd 市集** 的商家参展申请。

```
浏览器 / H5
   │
   ├─ ① POST /api/v1/uploads        附件 → 返回 file_id
   │
   └─ ② POST /api/v1/applications   表单 + file_ids → 落库
                          │
                          ├─ data/app.db            SQLite（application / file 两张表）
                          └─ data/uploads/{报名id}/  附件按报名分目录，可直接打包
```

**没有**鉴权、列表、导出、审核接口 —— 运营直接查库导出，附件直接拷目录。

---

## 2. 通用约定

| 项 | 约定 |
|---|---|
| Base URL | `https://<你的域名>`，本地 `http://localhost:8000` |
| 编码 | 请求与响应均为 UTF-8 |
| 请求体 | JSON 接口 `Content-Type: application/json`；上传接口 `multipart/form-data` |
| 时间格式 | ISO 8601 UTC，如 `2026-10-27T13:01:21Z`（展示时自行转 `Asia/Shanghai`） |
| 字段命名 | `snake_case` |
| 未知字段 | **会被拒绝**（`extra="forbid"`），防止前端拼错字段悄悄丢数据 |
| 限流 | 同 IP 每分钟默认 20 次（`RATE_LIMIT_PER_MINUTE` 可调），超了返回 `429` |

### 2.1 成功响应

直接返回业务对象，**不套壳**：

```json
{"id": 1, "files": 1, "created_at": "2026-10-27T13:01:21Z"}
```

### 2.2 错误响应

所有错误统一为：

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "表单校验未通过",
    "fields": [
      {"path": "phone", "message": "请填写有效的 11 位手机号"},
      {"path": "items[0].name", "message": "String should have at least 1 character"}
    ]
  }
}
```

`fields` 仅在字段级校验失败（422）时出现，`path` 指向具体字段，数组用 `items[0].name` 形式。

### 2.3 错误码表

| HTTP | `code` | 含义 | 前端建议处理 |
|---|---|---|---|
| `400` | `BAD_REQUEST` | 扩展名不支持 / 文件为空 / 不是有效 zip / `kind` 非法 / `file_id` 无效或已被使用 / 附件文件缺失 | 提示用户重选文件或重新上传 |
| `409` | `CONFLICT` | 附件被并发提交占用 | 重新上传附件 |
| `413` | `PAYLOAD_TOO_LARGE` | 单文件超限 或 附件合计超限 | 提示压缩/减少文件 |
| `422` | `VALIDATION_ERROR` | 表单字段校验失败 | 按 `error.fields[].path` 定位到输入框标红 |
| `429` | `RATE_LIMITED` | 请求过于频繁 | 退避重试 |
| `500` | `INTERNAL_ERROR` | 服务内部错误 | 提示稍后重试，并联系管理员 |
| `503` | `SERVICE_UNAVAILABLE` | 数据库不可用（仅 `/healthz`） | 触发告警 |

---

## 3. 枚举字典

### 3.1 `categories` —— 经营品类（多选，至少 1 个）

| 值 | 含义 |
|---|---|
| `bag` | 箱包手袋 |
| `watch` | 腕表 |
| `jewelry` | 珠宝配饰 |
| `apparel` | 服饰 |
| `shoe` | 鞋履 |
| `other` | 其他藏品 |

### 3.2 `zones` —— 意向区域（多选，至少 1 个，去重）

| 值 | 含义 |
|---|---|
| `A` | A 区 · 收藏级 Archive |
| `B` | B 区 · 工装与街头 |
| `C` | C 区 · 二手名牌 / 样衣 |

> D 区（Living、餐饮酒水等）另行签约，不在线上表单范围内。

### 3.3 `entity_type` —— 经营主体类型（单选）

| 值 | 含义 |
|---|---|
| `company` | 公司 |
| `individual` | 个体工商户 |
| `personal` | 个人 |

### 3.4 `kind` —— 附件分类（上传时标注，可空）

| 值 | 含义 |
|---|---|
| `photos` | 商品照片 |
| `list` | 商品清单 |
| `other` | 其他 |

### 3.5 `source` —— 提交来源（自由字符串，可空）

约定值：`h5`（默认）· `qrcode` · `word`（运营代录）

---

## 4. 接口详情

### 4.1 上传附件

```
POST /api/v1/uploads
Content-Type: multipart/form-data
```

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `file` | form | file | ✅ | 图片 / PDF / zip |
| `kind` | form | string | | `photos` · `list` · `other` |

**限制**

| 项 | 默认值 | 配置项 |
|---|---|---|
| 单文件大小 | 20 MB | `MAX_FILE_MB` |
| 允许扩展名 | `jpg jpeg png webp heic pdf zip` | `ALLOWED_EXT` |
| zip 校验 | 只校验文件头 `PK`，**不解压**（防 zip 炸弹） | — |

**响应 `201`**

```json
{
  "file_id": "3f2a1c9b0d4e4f7a8b6c5d4e3f2a1b0c",
  "original_name": "photos.zip",
  "size": 8123456,
  "kind": "photos"
}
```

**示例**

```bash
curl -X POST https://example.com/api/v1/uploads \
  -F "file=@./photos.zip" \
  -F "kind=photos"
```

**说明**

- 上传后文件先进暂存区，**提交表单时才绑定**到报名
- 每个 `file_id` 只能被用一次，重复使用返回 `400`
- 传了不提交的孤儿文件，可用 `python -m app.cleanup --hours 24` 清理

---

### 4.2 提交申请

```
POST /api/v1/applications
Content-Type: application/json
```

**请求体**

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
  "structure": {
    "secondhand": 60,
    "new_stock": 30,
    "sample": 10,
    "replica": 0
  },
  "items": [
    {
      "name": "Hermès Birkin 30 金棕",
      "era_series": "2015 年 / Birkin",
      "condition_source": "二手 / 附购买凭证",
      "price": 52000
    }
  ],
  "file_ids": ["3f2a1c9b0d4e4f7a8b6c5d4e3f2a1b0c"],
  "consent": true,
  "source": "h5"
}
```

字段逐项说明见 [第 5 节](#5-字段总表)。

**响应 `201`**

```json
{
  "id": 1,
  "files": 1,
  "created_at": "2026-10-27T13:01:21Z"
}
```

| 字段 | 说明 |
|---|---|
| `id` | 报名 id，附件目录名即 `data/uploads/{id}/` |
| `files` | 本次成功绑定的附件个数 |
| `created_at` | 提交时间（UTC），同时作为同意留痕时间 |

**校验规则（不满足返回 422）**

| 规则 | 说明 |
|---|---|
| 手机号 | 自动去 `+86`、空格、`-`、`()`、`（）`，校验 `^1[3-9]\d{9}$` |
| 联系方式 | `wechat` 与 `email` 至少一项，邮箱格式必须合法 |
| `consent` | 必须显式为 `true`；不传或传 `false` 都会拒绝 |
| 商品结构 | `structure` 四项合计必须 = 100；不传则整列为 `NULL`（允许不填） |
| 价格区间 | `price_max >= price_min` |
| 代表商品 | `items` 最多 20 条，建议 3~5 条 |
| 枚举值 | `categories` / `zones` / `entity_type` 必须是字典内的值 |
| 未知字段 | 出现未定义字段直接拒绝 |

**示例**

```bash
curl -X POST https://example.com/api/v1/applications \
  -H "Content-Type: application/json" \
  -d @samples/application.example.json
```

**错误示例**

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "表单校验未通过",
    "fields": [
      {"path": "structure", "message": "商品结构四项合计须为 100%，当前 90%"}
    ]
  }
}
```

---

### 4.3 健康检查

```
GET /healthz
```

**响应 `200`**

```json
{"ok": true}
```

**响应 `503`** —— 数据库连不上：

```json
{"ok": false, "error": {"code": "SERVICE_UNAVAILABLE", "message": "数据库不可用"}}
```

容器 `HEALTHCHECK` 用的就是它。

---

### 4.4 服务信息

```
GET /
```

未挂静态站时返回：

```json
{
  "service": "66th 商家参展申请采集服务",
  "version": "1.1.0",
  "endpoints": {
    "POST /api/v1/uploads": "上传附件，返回 file_id",
    "POST /api/v1/applications": "提交报名（带 file_ids）",
    "GET /docs": "接口文档（Swagger UI）"
  }
}
```

> `static/index.html` 存在时会改为托管前端静态站。

---

## 5. 字段总表

### 5.1 报名表单 `ApplicationIn`

#### 品牌与联络

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `brand_name` | string | ✅ | 1–120 字 | 品牌 / 店铺名称 |
| `contact_name` | string | ✅ | 1–60 字 | 联系人 |
| `phone` | string | ✅ | 11 位手机号 | 自动规范化 |
| `wechat` | string \| null | 二选一 | ≤ 60 字 | 微信 |
| `email` | string \| null | 二选一 | ≤ 120 字，合法邮箱 | 邮箱 |
| `city` | string \| null | | ≤ 60 字 | 所在城市 |
| `entity_type` | enum \| null | | `company` / `individual` / `personal` | 经营主体类型 |

#### 经营与参展内容

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `is_first_time` | bool | | 默认 `false` | 是否首次参展 |
| `categories` | string[] | ✅ | 至少 1 个，见 [3.1](#31-categories--经营品类多选至少-1-个) | 经营品类 |
| `zones` | string[] | ✅ | 至少 1 个，自动去重，见 [3.2](#32-zones--意向区域多选至少-1-个去重) | 意向区域 |
| `expected_qty` | int \| null | | ≥ 0 | 预计带货件数 |
| `price_min` | int \| null | | ≥ 0 | 价格区间下限（元） |
| `price_max` | int \| null | | ≥ `price_min` | 价格区间上限（元） |
| `structure` | object \| null | | 四项合计 = 100 | 商品结构占比，见下 |
| `structure.secondhand` | int | | 0–100 | 二手 % |
| `structure.new_stock` | int | | 0–100 | 未使用库存 % |
| `structure.sample` | int | | 0–100 | 样衣 % |
| `structure.replica` | int | | 0–100 | 复刻 / 原创 % |
| `items` | object[] | | ≤ 20 条 | 代表商品清单 |
| `items[].name` | string | ✅ | 1–120 字 | 商品及品牌 |
| `items[].era_series` | string \| null | | ≤ 200 字 | 年代 / 系列或库存属性 |
| `items[].condition_source` | string \| null | | ≤ 200 字 | 状态及来源 |
| `items[].price` | int \| null | | ≥ 0 | 拟售价（元） |

#### 附件与合规

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `file_ids` | string[] | | ≤ 20 个，去重 | 先调上传接口拿到的 id |
| `consent` | bool | ✅ | 必须为 `true` | 同意资料用于本次活动审核 |
| `source` | string \| null | | ≤ 30 字 | `h5` / `qrcode` / `word` |

### 5.2 数据库表

**`application`**

| 列 | 类型 | 来自接口字段 |
|---|---|---|
| `id` | INTEGER PK | 自增 |
| `created_at` | TEXT | 服务端生成（UTC） |
| `brand_name` `contact_name` `phone` `wechat` `email` `city` `entity_type` | TEXT | 同名 |
| `is_first_time` | INTEGER | 布尔转 0/1 |
| `categories` `zones` | TEXT | JSON 字符串 |
| `expected_qty` `price_min` `price_max` | INTEGER | 同名 |
| `pct_secondhand` `pct_new_stock` `pct_sample` `pct_replica` | INTEGER | 由 `structure` 拆列 |
| `items_json` | TEXT | `items` 序列化 |
| `consent_at` `privacy_version` | TEXT | 服务端生成 |
| `source` | TEXT | 同名 |

**`file`**

| 列 | 说明 |
|---|---|
| `id` | uuid，同时是磁盘文件名 |
| `application_id` | 关联报名；提交前为 `NULL` |
| `kind` | `photos` / `list` / `other` |
| `original_name` | 用户原始文件名 |
| `stored_path` | 相对 `UPLOAD_DIR`，如 `1/3f2a….zip` |
| `mime` `size` `sha256` `created_at` | 元信息 |

---

## 6. 完整接入示例

### 6.1 curl 全流程

```bash
API=https://example.com

# ① 上传附件
FID=$(curl -s -X POST "$API/api/v1/uploads" \
        -F "file=@photos.zip" -F "kind=photos" \
      | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

# ② 提交表单
curl -s -X POST "$API/api/v1/applications" \
  -H "Content-Type: application/json" \
  -d "{\"brand_name\":\"拾光中古\",\"contact_name\":\"陈小姐\",
       \"phone\":\"13800138000\",\"wechat\":\"shiguang_vtg\",
       \"categories\":[\"bag\"],\"zones\":[\"A\"],
       \"file_ids\":[\"$FID\"],\"consent\":true}"
```

仓库自带可执行脚本：`./samples/smoke.sh`。

### 6.2 浏览器 / 前端（fetch）

```ts
const API = import.meta.env.VITE_API_BASE ?? ''

async function submit(form: FormDataLike, file: File) {
  // ① 上传
  const fd = new FormData()
  fd.append('file', file)
  fd.append('kind', 'photos')
  const upRes = await fetch(`${API}/api/v1/uploads`, { method: 'POST', body: fd })
  if (!upRes.ok) throw await upRes.json()
  const { file_id } = await upRes.json()

  // ② 提交
  const res = await fetch(`${API}/api/v1/applications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...form, file_ids: [file_id], consent: true }),
  })
  if (!res.ok) {
    const { error } = await res.json()
    // 422 时把 error.fields 映射到表单出错提示
    throw error
  }
  return res.json() // { id, files, created_at }
}
```

### 6.3 开发期跨域

`vite.config.mjs`：

```js
server: { proxy: { '/api': 'http://localhost:8000' } }
```

生产同域部署（`static/index.html` 由本服务托管）时无需 CORS。

---

## 7. 数据落地

### 7.1 数据库

服务通过环境变量 **`DATABASE_URL`** 选择后端，两条路径共用同一套 SQL：

```bash
# 线上：MySQL
DATABASE_URL=mysql://verifly:密码@10.0.0.12:3306/verifly_signup?charset=utf8mb4

# 本地：SQLite（不装 MySQL 也能跑）
DATABASE_URL=sqlite:///data/app.db
```

| | MySQL（线上） | SQLite（本地/演示） |
|---|---|---|
| DDL | `app/schema_mysql.sql` | `app/schema_sqlite.sql` |
| 建库 | `deploy/mysql-init.sql` 交 DBA 执行一次 | 自动创建文件 |
| 字符集 | `utf8mb4 / utf8mb4_unicode_ci` | UTF-8 |
| 表结构 | 首次启动自动 `CREATE TABLE IF NOT EXISTS` | 同左 |
| 多 worker | 可以 | 只能 1 个（单写者） |

表：`application`（报名主表）、`file`（附件），字段映射见 [5.2](#52-数据库表)。

### 7.2 附件目录

```
data/uploads/
├── 3f2a….zip          # 已上传、未提交（孤儿，会被 cleanup 清掉）
└── 1/                 # 已提交，按报名 id 分目录
    └── 3f2a….zip
```

### 7.3 导出报名明细

```bash
# MySQL
mysql -h 10.0.0.12 -u verifly -p verifly_signup -e "
SELECT id, created_at, brand_name, contact_name, phone, wechat, city,
       categories, zones, expected_qty,
       CONCAT(price_min,'~',price_max) AS price_range,
       CONCAT('二手',pct_secondhand,'% 未使用',pct_new_stock,'% 样衣',pct_sample,'% 复刻',pct_replica,'%') AS structure,
       items_json
FROM application ORDER BY id" > 报名.tsv
```

```bash
# SQLite
docker compose exec -T signup python - <<'PY' > 报名.csv
import sqlite3, csv, sys
c = sqlite3.connect("/data/app.db"); c.row_factory = sqlite3.Row
w = csv.writer(sys.stdout)
w.writerow(["id","时间","品牌","联系人","手机","微信","城市","品类","区域",
            "带货件数","价格区间","代表商品"])
for r in c.execute("select * from application order by id"):
    w.writerow([r["id"], r["created_at"], r["brand_name"], r["contact_name"], r["phone"],
                r["wechat"], r["city"], r["categories"], r["zones"], r["expected_qty"],
                f'{r["price_min"]}~{r["price_max"]}', r["items_json"]])
PY
```

### 7.4 打包附件 / 清理孤儿

```bash
tar -czf uploads.tar.gz data/uploads/

docker compose exec -T signup python -m app.cleanup --hours 24 --dry-run
docker compose exec -T signup python -m app.cleanup --hours 24
```

## 8. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| `1.2.0` | 2026-10 | 数据库支持 MySQL（`DATABASE_URL` 切换，本地仍可用 SQLite）；新增 `deploy/mysql-init.sql`；compose 内置 MySQL 服务 |
| `1.1.0` | 2026-10 | 统一错误响应结构；`structure` 可空；`consent` 改为必传；附件绑定并发保护；`healthz` 检查数据库；新增孤儿附件清理脚本；补齐本文档 |
| `1.0.0` | 2026-10 | 首版：两个接口、两张表、Docker 部署 |
