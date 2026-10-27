"""清理「传了附件但没提交表单」的孤儿文件。

    python -m app.cleanup --hours 24           # 真删
    python -m app.cleanup --hours 24 --dry-run # 只看不删
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import db
from .config import settings


def main() -> None:
    ap = argparse.ArgumentParser(description="清理未提交的孤儿附件")
    ap.add_argument("--hours", type=int, default=24, help="超过多少小时未提交即清理，默认 24")
    ap.add_argument("--dry-run", action="store_true", help="只打印不删除")
    args = ap.parse_args()

    db.init_db()
    cutoff = (
        (datetime.now(timezone.utc) - timedelta(hours=args.hours))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    rows = db.orphan_files(cutoff)
    total = 0
    for r in rows:
        total += r["size"]
        print(f"{r['id']}  {r['original_name']}  {r['size']}B  {r['created_at']}")
        if not args.dry_run:
            (settings.upload_path / r["stored_path"]).unlink(missing_ok=True)
            db.delete_file(r["id"])

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}共 {len(rows)} 个孤儿附件，{total / 1024 / 1024:.2f}MB")


if __name__ == "__main__":
    main()
