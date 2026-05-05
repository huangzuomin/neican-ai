import json
import sys
from pathlib import Path

import pytest
import feedparser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hash_utils import compute_content_hash
from fetch_sources import FetchResult, fetch_sources
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"
FIXTURE_RSS = ROOT / "tests" / "fixtures" / "sample_rss.xml"
ORIGINAL_PARSE = feedparser.parse


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_sources(tmp_path: Path) -> Path:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
sources:
  - name: "Fixture Feed"
    type: rss
    url: "https://example.com/feed.xml"
    enabled: true
    trust_level: 5
    language: en
    fetch_interval_minutes: 120
  - name: "Disabled Feed"
    type: rss
    url: "https://example.com/disabled.xml"
    enabled: false
    trust_level: 1
    language: en
    fetch_interval_minutes: 120
  - name: "Second Fixture Feed"
    type: rss
    url: "https://example.com/second-feed.xml"
    enabled: true
    trust_level: 4
    language: en
    fetch_interval_minutes: 180
""".lstrip(),
        encoding="utf-8",
    )
    return sources_path


def fake_parse(_url):
    return ORIGINAL_PARSE(FIXTURE_RSS.read_text(encoding="utf-8"))


def test_compute_content_hash_is_stable_and_uses_all_fields():
    first = compute_content_hash("Title", "https://example.com/a", "2026-05-01")
    second = compute_content_hash("Title", "https://example.com/a", "2026-05-01")
    changed = compute_content_hash("Title", "https://example.com/b", "2026-05-01")

    assert first == second
    assert first != changed
    assert compute_content_hash(None, None, None)


def test_fetch_sources_inserts_once_and_audits_duplicates(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)
    monkeypatch.setattr("fetch_sources.feedparser.parse", fake_parse)

    first = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)
    second = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)

    assert first == FetchResult(inserted_count=2, skipped_duplicate_count=0, failed_count=0)
    assert second == FetchResult(inserted_count=0, skipped_duplicate_count=2, failed_count=0)

    with get_conn(db_path) as conn:
        sources = conn.execute("SELECT name, url FROM sources ORDER BY name").fetchall()
        raw_items = conn.execute("SELECT title, status, raw_text FROM raw_items").fetchall()
        runs = conn.execute("SELECT status, output_json FROM runs ORDER BY id").fetchall()

    assert [(row["name"], row["url"]) for row in sources] == [
        ("Fixture Feed", "https://example.com/feed.xml"),
        ("Second Fixture Feed", "https://example.com/second-feed.xml"),
    ]
    assert len(raw_items) == 2
    assert {row["status"] for row in raw_items} == {"new"}
    assert all(row["raw_text"] for row in raw_items)
    assert [row["status"] for row in runs] == ["success", "success"]
    assert json.loads(runs[1]["output_json"]) == {
        "inserted_count": 0,
        "skipped_duplicate_count": 2,
        "failed_count": 0,
    }


def test_fetch_sources_dry_run_does_not_write(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)
    monkeypatch.setattr("fetch_sources.feedparser.parse", fake_parse)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=1, dry_run=True)

    assert result == FetchResult(inserted_count=1, skipped_duplicate_count=0, failed_count=0)
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_fetch_sources_upserts_all_enabled_sources_before_limit(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)
    monkeypatch.setattr("fetch_sources.feedparser.parse", fake_parse)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=1)

    assert result == FetchResult(inserted_count=1, skipped_duplicate_count=0, failed_count=0)
    with get_conn(db_path) as conn:
        sources = conn.execute("SELECT name FROM sources ORDER BY name").fetchall()

    assert [row["name"] for row in sources] == ["Fixture Feed", "Second Fixture Feed"]
