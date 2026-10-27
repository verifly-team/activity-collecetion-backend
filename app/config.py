"""环境变量配置。"""

from __future__ import annotations

import os
from pathlib import Path


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


class Settings:
    def __init__(self) -> None:
        self.database_path = os.getenv("DATABASE_PATH", "data/app.db")
        self.upload_dir = os.getenv("UPLOAD_DIR", "data/uploads")
        self.static_dir = os.getenv("STATIC_DIR", "static")

        self.allowed_origins = _env_list("ALLOWED_ORIGINS", "*") or ["*"]
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

        # 附件
        self.max_file_mb = int(os.getenv("MAX_FILE_MB", "20"))  # 单文件
        self.max_files = int(os.getenv("MAX_FILES", "10"))  # 每份报名
        self.max_total_mb = int(os.getenv("MAX_TOTAL_MB", "100"))  # 每份报名合计
        self.allowed_ext = {
            e.lower().lstrip(".")
            for e in _env_list("ALLOWED_EXT", "jpg,jpeg,png,webp,heic,pdf,zip")
        }

        self.privacy_version = os.getenv("PRIVACY_VERSION", "v1.0")

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_total_bytes(self) -> int:
        return self.max_total_mb * 1024 * 1024

    @property
    def static_path(self) -> Path:
        return Path(self.static_dir)

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
