"""数据层 —— 一套 SQL 走 SQLite / MySQL，靠 DATABASE_URL 切换。

    DATABASE_URL=sqlite:///data/app.db
    DATABASE_URL=mysql://user:pass@127.0.0.1:3306/verifly_signup?charset=utf8mb4

只用 DB-API（sqlite3 / pymysql），不引 ORM。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import settings

SCHEMA_DIR = Path(__file__).parent


# ---------------------------------------------------------------- 连接


def target() -> tuple[str, dict[str, Any]]:
    """把 DATABASE_URL 解析成 (dialect, 连接参数)。"""
    url = settings.database_url
    if "://" not in url:  # 兼容直接写路径
        return "sqlite", {"path": url}

    parsed = urlparse(url)
    scheme = parsed.scheme.split("+")[0].lower()

    if scheme == "sqlite":
        # 与 SQLAlchemy 一致：sqlite:///rel 是相对路径，sqlite:////abs 是绝对路径
        path = parsed.path[1:] if parsed.path.startswith("/") else parsed.path
        return "sqlite", {"path": path}

    if scheme == "mysql":
        return "mysql", {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/"),
        }

    raise ValueError(f"不支持的 DATABASE_URL：{url}")


def _adapt(sql: str) -> str:
    """统一用 ? 写 SQL，MySQL 侧自动换成 %s。"""
    return sql if target()[0] == "sqlite" else sql.replace("?", "%s")


def connect() -> Any:
    dialect, conf = target()
    if dialect == "sqlite":
        raw = conf["path"]
        if raw in ("", ":memory:"):
            conn = sqlite3.connect(":memory:", isolation_level=None)
            conn.row_factory = sqlite3.Row
            return conn
        db_path = Path(raw)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    import pymysql
    import pymysql.cursors

    return pymysql.connect(
        host=conf["host"],
        port=conf["port"],
        user=conf["user"],
        password=conf["password"],
        database=conf["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=15,
        write_timeout=15,
    )


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _rows(conn: Any, sql: str, args: tuple | list | None = None) -> list[dict[str, Any]]:
    if target()[0] == "sqlite":
        return [dict(r) for r in conn.execute(sql, args or ()).fetchall()]
    with conn.cursor() as cur:
        # 注意：pymysql 只有 args 非 None 时才做 % 格式化，DDL 里的 % 不能传空元组
        cur.execute(_adapt(sql), args)
        return list(cur.fetchall())


def _row(conn: Any, sql: str, args: tuple | list | None = None) -> dict[str, Any] | None:
    rows = _rows(conn, sql, args)
    return rows[0] if rows else None


def _exec(conn: Any, sql: str, args: tuple | list | None = None) -> tuple[int, int]:
    """返回 (rowcount, lastrowid)。"""
    if target()[0] == "sqlite":
        cur = conn.execute(sql, args or ())
        return cur.rowcount, cur.lastrowid or 0
    with conn.cursor() as cur:
        cur.execute(_adapt(sql), args)
        return cur.rowcount, cur.lastrowid or 0


# ---------------------------------------------------------------- 初始化


def init_db() -> None:
    dialect, _ = target()
    schema = SCHEMA_DIR / ("schema_sqlite.sql" if dialect == "sqlite" else "schema_mysql.sql")
    sql = schema.read_text(encoding="utf-8")

    with get_conn() as conn:
        if dialect == "sqlite":
            conn.executescript(sql)
            return
        for statement in [s.strip() for s in sql.split(";") if s.strip()]:
            if statement.startswith("--"):
                # 去掉前导注释行
                statement = "\n".join(
                    line for line in statement.splitlines() if not line.strip().startswith("--")
                ).strip()
            if statement:
                _exec(conn, statement)


def fetch_one(sql: str, args: tuple | list = ()) -> dict[str, Any] | None:
    """查询单行（测试与运维脚本用）。"""
    with get_conn() as conn:
        return _row(conn, sql, args)


def ping() -> None:
    with get_conn() as conn:
        _row(conn, "SELECT 1 AS ok")


# ---------------------------------------------------------------- 写入


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_application(row: dict[str, Any]) -> int:
    cols = list(row)
    sql = "INSERT INTO application ({}) VALUES ({})".format(
        ",".join(cols), ",".join(["?"] * len(cols))
    )
    with get_conn() as conn:
        _, last_id = _exec(conn, sql, list(row.values()))
    return int(last_id)


def create_file(
    file_id: str,
    original_name: str,
    stored_path: str,
    mime: str | None,
    size: int,
    sha256: str,
    kind: str | None,
) -> None:
    sql = (
        "INSERT INTO file "
        "(id, original_name, stored_path, mime, size, sha256, kind, created_at) "
        f"VALUES ({','.join(['?'] * 8)})"
    )
    with get_conn() as conn:
        _exec(
            conn,
            sql,
            (file_id, original_name, stored_path, mime, size, sha256, kind, utcnow()),
        )


def unbound_files(file_ids: list[str]) -> list[dict[str, Any]]:
    if not file_ids:
        return []
    marks = ",".join(["?"] * len(file_ids))
    with get_conn() as conn:
        return _rows(
            conn,
            f"SELECT * FROM file WHERE id IN ({marks}) AND application_id IS NULL",
            list(file_ids),
        )


def bind_files(application_id: int, file_ids: list[str]) -> int:
    if not file_ids:
        return 0
    marks = ",".join(["?"] * len(file_ids))
    with get_conn() as conn:
        count, _ = _exec(
            conn,
            f"UPDATE file SET application_id = ? WHERE id IN ({marks}) AND application_id IS NULL",
            [application_id, *file_ids],
        )
    return count


def set_file_path(file_id: str, stored_path: str) -> None:
    with get_conn() as conn:
        _exec(conn, "UPDATE file SET stored_path = ? WHERE id = ?", (stored_path, file_id))


def delete_application(application_id: int) -> None:
    with get_conn() as conn:
        _exec(conn, "DELETE FROM application WHERE id = ?", (application_id,))


def delete_file(file_id: str) -> None:
    with get_conn() as conn:
        _exec(conn, "DELETE FROM file WHERE id = ?", (file_id,))


def orphan_files(older_than: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _rows(
            conn,
            "SELECT * FROM file WHERE application_id IS NULL AND created_at < ?",
            (older_than,),
        )
