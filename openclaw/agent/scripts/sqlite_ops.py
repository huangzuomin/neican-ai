import sqlite3
from pathlib import Path
from typing import Any


def get_conn(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def execute(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    return conn.execute(sql, params)


def fetchall(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def fetchone(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def upsert(
    conn: sqlite3.Connection,
    table: str,
    data: dict[str, Any],
    conflict_col: str,
) -> sqlite3.Cursor:
    columns = list(data)
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    update_cols = [col for col in columns if col != conflict_col]
    update_sql = ", ".join(f"{col}=excluded.{col}" for col in update_cols)
    sql = (
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict_col}) DO UPDATE SET {update_sql}"
    )
    return conn.execute(sql, tuple(data[col] for col in columns))
