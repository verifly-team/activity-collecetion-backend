"""66th 商家参展申请 —— 采集服务（2 个接口，够用就好）。"""
from __future__ import annotations

import hashlib
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
from .models import ApplicationIn, SubmitResult, UploadResult

ALLOWED_KINDS = {"photos", "list", "other"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="66th 商家参展申请采集服务",
    version="1.0.0",
    description="两个接口：先传附件拿 file_id，再提交表单。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# ---------------------------------------------------------------- 启动

@app.get("/healthz", tags=["系统"])
def healthz() -> dict:
    try:
        db.ping()
    except Exception:  # noqa: BLE001 - 健康检查只关心能不能连上
        raise HTTPException(status_code=503, detail="数据库不可用")
    return {"ok": True}


# ---------------------------------------------------------------- 1. 上传附件

@app.post("/api/v1/uploads", response_model=UploadResult, status_code=201, tags=["附件"])
async def upload_attachment(
    request: Request,
    file: UploadFile = File(..., description="图片 / PDF / zip 打包件"),
    kind: str | None = Form(None, description="photos / list / other"),
) -> UploadResult:
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

@app.post("/api/v1/applications", response_model=SubmitResult, status_code=201, tags=["报名"])
def submit_application(payload: ApplicationIn, request: Request) -> SubmitResult:
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

    # 文件必须真在磁盘上（防止库里残留脏记录）
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


# ---------------------------------------------------------------- 静态站（有就挂，没有不影响）

if settings.static_path.is_dir() and (settings.static_path / "index.html").exists():
    app.mount("/", StaticFiles(directory=settings.static_path, html=True), name="static")
else:

    @app.get("/", tags=["系统"])
    def index() -> dict:
        return {
            "service": "66th 商家参展申请采集服务",
            "endpoints": {
                "POST /api/v1/uploads": "上传附件，返回 file_id",
                "POST /api/v1/applications": "提交报名（带 file_ids）",
                "GET /docs": "接口文档",
            },
        }
