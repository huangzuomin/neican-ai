from pathlib import Path

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
EXPECTED_TABLES = 17


def init_db() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn(DB_PATH) as conn:
        conn.executescript(schema_sql)
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]

    print(f"[OK] neican.sqlite initialized with {count} tables")
    if count != EXPECTED_TABLES:
        raise SystemExit(f"Expected {EXPECTED_TABLES} tables, found {count}")


if __name__ == "__main__":
    init_db()
