import json
import sys
from pathlib import Path
from types import SimpleNamespace

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


def fake_parse(_content):
    return ORIGINAL_PARSE(FIXTURE_RSS.read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, content: bytes):
        self._content = content

    def raise_for_status(self):
        pass

    @property
    def content(self):
        return self._content


def fake_requests_get(url, **kwargs):
    return FakeResponse(FIXTURE_RSS.read_bytes())


@pytest.fixture(autouse=True)
def _patch_fetch(monkeypatch):
    """Patch requests.get and feedparser.parse so tests never hit the network."""
    monkeypatch.setattr("fetch_sources.requests.get", fake_requests_get)
    monkeypatch.setattr("fetch_sources.feedparser.parse", fake_parse)


def test_compute_content_hash_is_stable_and_uses_all_fields():
    first = compute_content_hash("Title", "https://example.com/a", "2026-05-01")
    second = compute_content_hash("Title", "https://example.com/a", "2026-05-01")
    changed = compute_content_hash("Title", "https://example.com/b", "2026-05-01")

    assert first == second
    assert first != changed
    assert compute_content_hash(None, None, None)


def test_fetch_sources_inserts_once_and_audits_duplicates(tmp_path):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

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


def test_fetch_sources_dry_run_does_not_write(tmp_path):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=1, dry_run=True)

    assert result == FetchResult(inserted_count=1, skipped_duplicate_count=0, failed_count=0)
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_fetch_sources_upserts_all_enabled_sources_before_limit(tmp_path):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=1)

    assert result == FetchResult(inserted_count=1, skipped_duplicate_count=0, failed_count=0)
    with get_conn(db_path) as conn:
        sources = conn.execute("SELECT name FROM sources ORDER BY name").fetchall()

    assert [row["name"] for row in sources] == ["Fixture Feed", "Second Fixture Feed"]


def test_fetch_sources_full_text_routes_summary_items_without_http_fetch(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    def fail_if_called(_url):
        raise AssertionError("neican-editor must not fetch full text directly")

    monkeypatch.setattr("fetch_sources.fetch_full_text", fail_if_called)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=1, full_text=True)

    assert result == FetchResult(
        inserted_count=1,
        skipped_duplicate_count=0,
        failed_count=0,
        routed_full_text_count=1,
    )
    with get_conn(db_path) as conn:
        request = conn.execute(
            "SELECT source_url, status, route_message FROM info_fetch_requests"
        ).fetchone()

    assert request["source_url"] == "https://example.com/openai-model-update"
    assert request["status"] == "pending"
    assert request["route_message"].startswith("需要抓取：")


def test_fetch_sources_handles_network_error_gracefully(tmp_path, monkeypatch):
    """A failing source should not crash the whole batch."""
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    call_count = 0

    def flaky_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "example.com/feed.xml" in url:
            raise ConnectionError("simulated timeout")
        return FakeResponse(FIXTURE_RSS.read_bytes())

    monkeypatch.setattr("fetch_sources.requests.get", flaky_get)

    result = fetch_sources(db_path=db_path, sources_path=sources_path, limit=5)

    assert result.failed_count >= 1
    # The second source should still have been processed
    assert result.inserted_count >= 1


def test_fetch_sources_updates_last_fetched_at(tmp_path):
    """Each source should have last_fetched_at updated after fetching."""
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    fetch_sources(db_path=db_path, sources_path=sources_path, limit=5)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT name, last_fetched_at FROM sources WHERE enabled = 1 ORDER BY name"
        ).fetchall()

    assert len(rows) == 2
    for row in rows:
        assert row["last_fetched_at"] is not None, f"{row['name']} missing last_fetched_at"


def test_fetch_sources_time_window_skips_old_entries_on_second_run(tmp_path, monkeypatch):
    """Second fetch with last_fetched_at should skip entries outside the window.

    Uses a fixture where entries have old pubDates (2026-05-01). On first fetch,
    last_fetched_at is set to 'now'. On second fetch, the entries are too old
    (published before last_fetched_at - grace_period) and get skipped.
    """
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    # First fetch: allow all
    first = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)
    assert first.inserted_count == 2

    # Set last_fetched_at to a future date so entries become "old"
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE sources SET last_fetched_at = '2099-06-01T00:00:00Z' WHERE enabled = 1"
        )

    # Second fetch: entries from 2026-05-01 are outside the window
    second = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)
    assert second.inserted_count == 0
    assert second.skipped_duplicate_count == 2


def test_fetch_sources_time_window_allows_recent_entries_on_second_run(tmp_path, monkeypatch):
    """Second fetch with last_fetched_at should allow entries published after the cutoff.

    Uses a fixture where entries have pubDates set to 'now'. Both fetches
    should succeed because entries are within the time window.
    """
    from datetime import datetime, timezone
    import email.utils

    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)

    now_rfc = email.utils.formatdate(usegmt=True)
    recent_rss = f'''<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Recent Feed</title>
    <link>https://example.com/ai</link>
    <item>
      <title>Recent Entry</title>
      <link>https://example.com/recent-entry</link>
      <pubDate>{now_rfc}</pubDate>
      <description>Recent content</description>
    </item>
  </channel>
</rss>'''

    def fake_get_recent(url, **kwargs):
        return FakeResponse(recent_rss.encode())

    monkeypatch.setattr("fetch_sources.requests.get", fake_get_recent)
    monkeypatch.setattr("fetch_sources.feedparser.parse", lambda c: ORIGINAL_PARSE(c))

    # First fetch
    first = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)
    assert first.inserted_count >= 1  # At least 1 recent entry (sources share same fake RSS)

    # Set last_fetched_at to 1 hour ago — entries published 'now' are within window
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE sources SET last_fetched_at = ? WHERE enabled = 1",
            (cutoff,)
        )

    # Change URL to avoid content_hash collision
    newer_rss = recent_rss.replace(
        "recent-entry", "newer-entry"
    ).replace(
        "Recent Entry", "Newer Entry"
    )
    monkeypatch.setattr("fetch_sources.requests.get", lambda url, **kw: FakeResponse(newer_rss.encode()))

    second = fetch_sources(db_path=db_path, sources_path=sources_path, limit=2)
    assert second.inserted_count >= 1  # Recent entries should pass time window
