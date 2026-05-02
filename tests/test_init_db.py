import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_init_db_creates_expected_tables_idempotently():
    db_path = ROOT / "db" / "neican.sqlite"
    if db_path.exists():
        db_path.unlink()

    cmd = [sys.executable, str(ROOT / "scripts" / "init_db.py")]

    first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
    second = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)

    assert "[OK] neican.sqlite initialized with 10 tables" in first.stdout
    assert "[OK] neican.sqlite initialized with 10 tables" in second.stdout
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

    assert {row[0] for row in rows} == {
        "sources",
        "raw_items",
        "events",
        "decisions",
        "review_queue",
        "publish_log",
        "timeline_nodes",
        "entity_profiles",
        "event_catalog",
        "runs",
    }
