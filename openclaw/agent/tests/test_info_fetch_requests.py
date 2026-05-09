import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from info_fetch_requests import consume_info_fetch_results, enqueue_info_fetch_request
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def test_consume_info_fetch_results_updates_existing_raw_item(tmp_path):
    db_path = init_temp_db(tmp_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO raw_items (source_url, title, raw_text, clean_text, content_hash, status)
            VALUES ('https://example.com/full', 'Old title', 'Summary', 'Summary', 'hash-old', 'needs_refetch')
            """
        )
        raw_item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        enqueue_info_fetch_request(
            conn,
            source_url="https://example.com/full",
            title="Old title",
            reason="low_extraction_confidence",
            raw_item_id=raw_item_id,
        )

    result = consume_info_fetch_results(
        [
            {
                "source_url": "https://example.com/full",
                "title": "Full title",
                "author": "Reporter",
                "published_at": "2026-05-07T12:00:00Z",
                "clean_text": "Full clean article text about OpenAI and AI agents.",
                "extraction_confidence": 0.92,
            }
        ],
        db_path=db_path,
    )

    assert result.updated_count == 1
    assert result.failed_count == 0
    with get_conn(db_path) as conn:
        raw_item = conn.execute(
            "SELECT title, author, clean_text, extraction_confidence, status FROM raw_items WHERE id = ?",
            (raw_item_id,),
        ).fetchone()
        request = conn.execute(
            "SELECT status, result_json FROM info_fetch_requests WHERE source_url = 'https://example.com/full'"
        ).fetchone()

    assert raw_item["title"] == "Full title"
    assert raw_item["author"] == "Reporter"
    assert raw_item["status"] == "new"
    assert raw_item["extraction_confidence"] == 0.92
    assert request["status"] == "consumed"
    assert "Full clean article text" in request["result_json"]
