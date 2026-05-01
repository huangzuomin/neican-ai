import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_content import ExtractResult, extract_content
from hash_utils import compute_content_hash
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def insert_raw_item(db_path: Path, raw_text: str | None, status: str = "new") -> int:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO raw_items (
              source_url, title, raw_text, content_hash, status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"https://example.com/{abs(hash(raw_text))}",
                "Sample item",
                raw_text,
                compute_content_hash("Sample item", f"https://example.com/{abs(hash(raw_text))}", None),
                status,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_extract_content_cleans_html_and_keeps_status_new(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_raw_item(
        db_path,
        """
        <html>
          <body>
            <nav>Navigation should disappear</nav>
            <article><h1>Model update</h1><p>Useful paragraph about AI.</p></article>
            <script>alert('remove me')</script>
          </body>
        </html>
        """,
    )

    result = extract_content(db_path=db_path, raw_item_id=raw_item_id)

    assert result == ExtractResult(processed_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT clean_text, extraction_confidence, status FROM raw_items").fetchone()
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='extract_content'").fetchone()

    assert "Model update" in row["clean_text"]
    assert "Useful paragraph about AI." in row["clean_text"]
    assert "Navigation should disappear" not in row["clean_text"]
    assert "alert" not in row["clean_text"]
    assert 0.0 <= row["extraction_confidence"] <= 1.0
    assert row["status"] == "new"
    assert run["status"] == "success"
    assert json.loads(run["output_json"]) == {"failed_count": 0, "processed_count": 1}


def test_extract_content_normalizes_plain_text(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_raw_item(db_path, " First line.\n\n\n Second    line. ")

    result = extract_content(db_path=db_path, raw_item_id=raw_item_id)

    assert result == ExtractResult(processed_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT clean_text, status FROM raw_items").fetchone()

    assert row["clean_text"] == "First line.\n\nSecond line."
    assert row["status"] == "new"


def test_extract_content_dry_run_does_not_write(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_raw_item(db_path, "<p>Dry run text.</p>")

    result = extract_content(db_path=db_path, raw_item_id=raw_item_id, dry_run=True)

    assert result == ExtractResult(processed_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT clean_text, extraction_confidence FROM raw_items").fetchone()
        run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    assert row["clean_text"] is None
    assert row["extraction_confidence"] is None
    assert run_count == 0


def test_extract_content_marks_empty_raw_text_failed(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_raw_item(db_path, None)

    result = extract_content(db_path=db_path, raw_item_id=raw_item_id)

    assert result == ExtractResult(processed_count=0, failed_count=1)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT status, error_message FROM raw_items").fetchone()
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='extract_content'").fetchone()

    assert row["status"] == "failed"
    assert "raw_text is empty" in row["error_message"]
    assert run["status"] == "failed"
    assert json.loads(run["output_json"]) == {"failed_count": 1, "processed_count": 0}
