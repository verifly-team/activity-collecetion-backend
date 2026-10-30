"""66th 商家参展申请 —— 采集服务。

两个业务接口：
    POST /api/v1/uploads       上传附件，拿 file_id
    POST /api/v1/applications  提交报名，带上 file_ids
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import settings
from .errors import install_error_handlers
from .models import ApplicationIn, SubmitResult, UploadResult

ALLOWED_KINDS = {"photos", "list", "other"}
_EXT_TEXT = " / ".join(sorted(settings.allowed_ext))

DESCRIPTION = f"""
66th & 2nd Vintage Fashion Show & Market（深圳）—— **商家参展申请采集服务**。

一个容器、两张表、两个接口。数据进 SQLite，附件落磁盘，运营直接开库导出。

### 提交流程

1. `POST /api/v1/uploads` 逐个上传附件 → 拿到 `file_id`
2. `POST /api/v1/applications` 提交表单，把 `file_ids` 一起带上

### 附件限制

- 单文件 ≤ **{settings.max_file_mb}MB**
- 每份报名 ≤ **{settings.max_files}** 个，合计 ≤ **{settings.max_total_mb}MB**
- 允许类型：{_EXT_TEXT}
- zip 只校验文件头，**不解压**

### 错误格式

所有错误统一返回：

```json
{{"ok": false, "error": {{"code": "VALIDATION_ERROR", "message": "表单校验未通过",
  "fields": [{{"path": "phone", "message": "请填写有效的 11 位手机号"}}]}}}}
```

完整文档见仓库 `docs/API.md`。
"""

TAGS_METADATA = [
    {"name": "附件", "description": "上传图片 / PDF / zip，返回 file_id 供提交时引用。"},
    {"name": "报名", "description": "提交商家参展申请表单。"},
    {"name": "系统", "description": "健康检查与首页。"},
]


logger = logging.getLogger("signup.startup")


def _check_upload_dir() -> None:
    """启动时检查附件目录，装错路径要能立刻发现。"""
    path = settings.upload_path
    try:
        on_disk = sum(1 for _ in path.iterdir())
    except OSError as exc:
        logger.warning("附件目录 %s 读不了：%s", path, exc)
        on_disk = -1
    try:
        in_db = db.fetch_one("SELECT COUNT(*) AS n FROM file")
        in_db = int(in_db["n"]) if in_db else 0
    except Exception:  # noqa: BLE001 - 自检不该影响启动
        in_db = -1

    logger.info("附件目录：%s（磁盘文件 %s 个，数据库 %s 条）", path.resolve(), on_disk, in_db)

    if in_db > 0 and on_disk == 0:
        logger.warning(
            "⚠️ 数据库里有 %d 条附件记录，但 %s 下一个文件都没有！\n"
            "   最常见原因：UPLOAD_DIR 写成了宿主机路径。\n"
            "   UPLOAD_DIR 必须是【容器内路径】（如 /data/uploads），"
            "宿主机路径只能写在 docker run 的 -v 参数里。",
            in_db,
            path,
        )
    elif in_db > 0 and on_disk > 0 and on_disk < in_db:
        logger.warning("⚠️ 数据库 %d 条附件记录，磁盘只有 %d 个文件，挂载可能不完整", in_db, on_disk)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    _check_upload_dir()
    yield


_ENABLE_DOCS = os.getenv("ENABLE_DOCS", "0").lower() in ("1", "true", "yes")

app = FastAPI(
    lifespan=lifespan,
    title="66th 商家参展申请采集服务",
    version="1.3.0",
    description=DESCRIPTION,
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None,
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Verifly",
        "url": "https://github.com/verifly-team/activity-collecetion-backend",
    },
    license_info={"name": "Proprietary"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "object-src 'none'"
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "no-referrer"
    headers["Content-Security-Policy"] = _CSP
    headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.path.startswith("/api/"):
        headers["Cache-Control"] = "no-store"
    return response


install_error_handlers(app)

# ---------------------------------------------------------------- 限流（内存版）

_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _rate_limit(request: Request) -> None:
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return
    key = _client_ip(request)
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="提交过于频繁，请稍后再试")
    q.append(now)
    # 顺手清掉过期 key，避免字典无限增长
    if len(_hits) > 4096:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            _hits.pop(k, None)


# ---------------------------------------------------------------- 系统


@app.get("/healthz", tags=["系统"], summary="健康检查")
def healthz() -> dict:
    """容器 HEALTHCHECK 用；数据库连不上会返回 503。"""
    try:
        db.ping()
    except Exception:  # 健康检查只关心能不能连上
        raise HTTPException(status_code=503, detail="数据库不可用") from None

    info: dict = {"ok": True, "upload_dir": str(settings.upload_path)}
    try:
        info["upload_files"] = sum(1 for _ in settings.upload_path.iterdir())
    except OSError:
        info["upload_files"] = -1
        info["warn"] = "附件目录不可读，检查挂载与权限"
    return info


# ---------------------------------------------------------------- 1. 上传附件


@app.post(
    "/api/v1/uploads",
    response_model=UploadResult,
    status_code=201,
    tags=["附件"],
    summary="上传附件",
    response_description="上传成功，返回 file_id",
    responses={
        400: {"description": "扩展名不支持 / 文件为空 / 不是有效 zip / kind 非法"},
        413: {"description": "超过单文件大小上限"},
        429: {"description": "请求过于频繁"},
    },
)
async def upload_attachment(
    request: Request,
    file: UploadFile = File(..., description="图片 / PDF / zip 打包件"),
    kind: str | None = Form(None, description="photos 商品图 · list 商品清单 · other 其他"),
) -> UploadResult:
    """把附件先存到暂存区，返回 `file_id`；提交表单时用 `file_ids` 引用。"""
    _rate_limit(request)

    if kind and kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=400, detail=f"kind 只能是 {sorted(ALLOWED_KINDS)}，收到：{kind}"
        )

    original = Path(file.filename or "unnamed").name
    ext = Path(original).suffix.lower().lstrip(".")
    if ext not in settings.allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 .{ext or '无'}，允许：{sorted(settings.allowed_ext)}",
        )

    file_id = uuid.uuid4().hex
    dest = settings.upload_path / f"{file_id}.{ext}"
    digest = hashlib.sha256()
    size = 0

    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_file_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"单个文件不能超过 {settings.max_file_mb}MB",
                    )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="文件是空的")
        if ext == "zip":
            with dest.open("rb") as fh:
                if fh.read(2) != b"PK":
                    raise HTTPException(status_code=400, detail="这不是有效的 zip 文件")
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    db.create_file(
        file_id=file_id,
        original_name=original,
        stored_path=dest.name,
        mime=file.content_type,
        size=size,
        sha256=digest.hexdigest(),
        kind=kind,
    )
    return UploadResult(file_id=file_id, original_name=original, size=size, kind=kind)


# ---------------------------------------------------------------- 2. 提交报名


@app.post(
    "/api/v1/applications",
    response_model=SubmitResult,
    status_code=201,
    tags=["报名"],
    summary="提交参展申请",
    response_description="提交成功，返回报名 id",
    responses={
        400: {"description": "file_id 无效 / 已被使用 / 附件文件缺失"},
        409: {"description": "附件被并发提交占用"},
        413: {"description": "附件合计超过上限"},
        422: {"description": "表单校验未通过，明细见 error.fields"},
        429: {"description": "请求过于频繁"},
    },
)
def submit_application(payload: ApplicationIn, request: Request) -> SubmitResult:
    """提交一份完整的商家参展申请。

    - 手机号自动去 `+86` / 空格 / 横线并校验
    - 微信与邮箱至少填一项
    - 商品结构四项若填写则合计必须 100
    - `consent` 必须显式为 `true`
    """
    _rate_limit(request)

    file_ids = list(dict.fromkeys(payload.file_ids))  # 去重保序
    rows = db.unbound_files(file_ids)
    if len(rows) != len(file_ids):
        raise HTTPException(status_code=400, detail="存在无效或已被使用的 file_id，请重新上传")
    if len(rows) > settings.max_files:
        raise HTTPException(status_code=400, detail=f"附件最多 {settings.max_files} 个")
    total = sum(r["size"] for r in rows)
    if total > settings.max_total_bytes:
        raise HTTPException(status_code=413, detail=f"附件合计不能超过 {settings.max_total_mb}MB")

    # 文件必须真在磁盘上，防止库里残留脏记录
    for r in rows:
        if not (settings.upload_path / r["stored_path"]).exists():
            raise HTTPException(status_code=400, detail="附件文件缺失，请重新上传")

    created_at = db.utcnow()
    row = payload.to_row(settings.privacy_version, created_at)
    app_id = db.create_application(row)

    # 并发兜底：同一批 file_id 被两处抢用时，第二处回滚掉刚建的报名
    if db.bind_files(app_id, file_ids) != len(file_ids):
        db.delete_application(app_id)
        raise HTTPException(status_code=409, detail="附件已被其他提交占用，请重新上传")

    # 附件从暂存区挪进 uploads/{报名id}/，方便运维直接打包捞走
    target_dir = settings.upload_path / str(app_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        src = settings.upload_path / r["stored_path"]
        dst = target_dir / src.name
        try:
            src.replace(dst)
            db.set_file_path(r["id"], f"{app_id}/{dst.name}")
        except OSError:
            # 挪不动就保留暂存路径，数据不丢
            pass

    return SubmitResult(id=app_id, files=len(rows), created_at=created_at)


# ---------------------------------------------------------------- 静态站（有就挂）

if settings.static_path.is_dir() and (settings.static_path / "index.html").exists():
    app.mount("/", StaticFiles(directory=settings.static_path, html=True), name="static")
else:

    @app.get("/", tags=["系统"], summary="服务信息")
    def index() -> dict:
        return {
            "service": "66th 商家参展申请采集服务",
            "version": app.version,
            "endpoints": {
                "POST /api/v1/uploads": "上传附件，返回 file_id",
                "POST /api/v1/applications": "提交报名（带 file_ids）",
                "GET /docs": "接口文档（Swagger UI）",
            },
        }
