# activity-collection-backend

66th & 2nd Vintage Fashion Show & Market（深圳）—— **商家参展申请采集服务**。

一个容器、两张表、两个接口：商家先传附件拿到 `file_id`，再提交表单，数据进 MySQL、文件进磁盘目录，运营直接查库导出。

```
浏览器 / H5
   │
   ├─ ① POST /api/v1/uploads        附件 → file_id
   └─ ② POST /api/v1/applications   表单 + file_ids
                        │
                        ├── MySQL        application / file 两张表
                        └── /verifly/activity/uploads/{报名id}/  附件按人分目录
```

---

## 文档

| 文档 | 内容 |
|---|---|
| **[docs/API.md](docs/API.md)** | 接口契约：请求/响应、字段总表、错误码、枚举字典、curl 与 fetch 示例 |
| **[docs/DATABASE.md](docs/DATABASE.md)** | 数据模型、附件存储布局、文件生命周期、备份与恢复、容量估算 |
| **[deploy/DEPLOY.md](deploy/DEPLOY.md)** | 部署手册：建库 → 推镜像 → 起容器 → 验收 → 日常运维 → 排障 |
| `/docs`（运行时） | Swagger UI，可直接试接口；`/openapi.json` 原始 schema |

---

## 60 秒跑起来（本地）

**带 MySQL（推荐，和线上一致）**

```bash
cp .env.example .env
docker compose up -d --build      # 同时起 mysql:8.0 + 应用
curl localhost:8000/healthz       # {"ok":true}
open http://localhost:8000/docs
```

**不装 MySQL（本地只想看接口）**

```bash
pip install -r requirements.txt
DATABASE_URL=sqlite:///data/app.db uvicorn app.main:app --reload --port 8000
```

**跑一遍完整链路**

```bash
API=http://localhost:8000 ./samples/smoke.sh
```

---

## 能力边界

**做**

- 商家参展申请收集（品牌联络 / 品类 / 区域意向 / 带货规模 / 代表商品 / 附件）
- 文件上传：扩展名白名单、单文件与总量限制、zip 只验文件头不解压
- 服务端校验：手机号规范化、微信与邮箱二选一、商品结构合计 100%、同意留痕
- 数据落地：MySQL（或 SQLite），附件按报名分目录
- 运维：健康检查、限流、孤儿附件清理、Docker 单容器交付

**不做**（明确砍掉，不是遗漏）

- 后台管理界面、列表接口、导出接口、审核流转 → 运营直接查库 / 拷目录
- 支付、分账、结算
- 登录鉴权（提交接口公开 + IP 限流）
- 图片 OCR / 品类识别 / 鉴定

---

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Web | FastAPI + Uvicorn | 自动生成 OpenAPI 文档 |
| 校验 | Pydantic v2 | 中文报错信息，`extra="forbid"` 拒绝未知字段 |
| 数据 | MySQL 8（线上）/ SQLite（本地） | 标准库 `sqlite3` 与 `pymysql` 双驱动，**不引 ORM** |
| 文件 | 本地磁盘 + Docker 卷 | 数据库只存相对路径 |
| 交付 | Docker 单镜像 | 非 root、内置 HEALTHCHECK |

---

## 目录结构

```
.
├── app/
│   ├── main.py            两个业务接口 + 限流 + 健康检查
│   ├── models.py          Pydantic 请求/响应模型与校验规则
│   ├── db.py              数据层（SQLite / MySQL 双驱动）
│   ├── errors.py          统一错误响应
│   ├── config.py          环境变量
│   ├── cleanup.py         孤儿附件清理（python -m app.cleanup）
│   ├── schema_mysql.sql   MySQL 建表
│   └── schema_sqlite.sql  SQLite 建表
├── docs/
│   ├── API.md             接口文档
│   └── DATABASE.md        数据与存储设计
├── deploy/
│   ├── DEPLOY.md          部署手册
│   ├── mysql-init.sql     建库/建账号/授权
│   ├── build-push.sh      构建并推送私有仓库
│   └── run.sh             服务器一键起容器
├── samples/               示例 payload + 冒烟脚本
├── tests/                 14 个 pytest 用例（SQLite / MySQL 双后端均通过）
├── Dockerfile
├── docker-compose.yml     本地：mysql + 应用
└── .env.example           配置模板
```

---

## 状态

| 项 | 状态 |
|---|---|
| 版本 | `1.2.0` |
| 测试 | `pytest` 14 passed ×（SQLite / MySQL 8.0） |
| 代码规范 | `ruff check` / `ruff format --check` 全绿 |
| 镜像 | 已构建并验证（容器 + MySQL / 容器 + SQLite 双链路） |
