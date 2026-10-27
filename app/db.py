"""SQLite 数据层 —— 只用标准库，不引 ORM。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def create_application(row: dict) -> int:
    cols = list(row)
    sql = "INSERT INTO application ({}) VALUES ({})".format(
        ",".join(cols), ",".join("?" * len(cols))
    )
    with get_conn() as conn:
        cur = conn.execute(sql, [row[c] for c in cols])
        return int(cur.lastrowid)


def create_file(
    file_id: str,
    original_name: str,
    stored_path: str,
    mime: str | None,
    size: int,
    sha256: str,
    kind: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO file (id, original_name, stored_path, mime, size, sha256, kind, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (file_id, original_name, stored_path, mime, size, sha256, kind, utcnow()),
        )


def unbound_files(file_ids: list[str]) -> list[sqlite3.Row]:
    if not file_ids:
        return []
    marks = ",".join("?" * len(file_ids))
    with get_conn() as conn:
        return conn.execute(
            f"SELECT * FROM file WHERE id IN ({marks}) AND application_id IS NULL", file_ids
        ).fetchall()


def bind_files(application_id: int, file_ids: list[str]) -> int:
    if not file_ids:
        return 0
    marks = ",".join("?" * len(file_ids))
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE file SET application_id = ? WHERE id IN ({marks}) AND application_id IS NULL",
            [application_id, *file_ids],
        )
        return cur.rowcount


def set_file_path(file_id: str, stored_path: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE file SET stored_path = ? WHERE id = ?", (stored_path, file_id))
