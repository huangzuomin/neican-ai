import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from insight_candidates import detect_insight_candidates
from insight_product import generate_insight_pages
from sqlite_ops import get_conn

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def seed_track_with_events(db_path: Path, track_slug: str = "test-track", num_a_events: int = 3):
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        for i in range(num_a_events):
            date = f"2026-05-{i+1:02d}"
            conn.execute(
                "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, ?, ?, ?, ?, 'processed')",
                (f"https://t.com/{i+1}", f"Event {i+1}", f"h{i+1}", f"{date}T10:00:00Z"),
            )
            conn.execute(
                "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
                "VALUES (?, ?, ?, 'tool_launch', ?, ?, '[[\"test-topic\"]]', '[]', 'modeled', 80)",
                (i+1, f"Event {i+1}", f"Summary {i+1}", date, json.dumps([{"name": "OpenAI", "slug": "openai"}])),
            )
            conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (?, 'insight', 'A', 'pending')", (i+1,))
            conn.execute(
                "INSERT INTO timeline_nodes (event_id, date, year, month, slug, title, summary, grade, status, tracks_json) "
                "VALUES (?, ?, '2026', '2026-05', ?, ?, ?, 'A', 'public', ?)",
                (i+1, date, f"event-{i+1}", f"Event {i+1}", f"Summary {i+1}", json.dumps([track_slug])),
            )
        conn.commit()


def test_insight_candidate_created_from_track_with_three_a_events(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_track_with_events(db_path, "test-track", num_a_events=3)
    result = detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60)
    assert result.proposed >= 1
    with get_conn(db_path) as conn:
        c = conn.execute("SELECT * FROM insight_candidates WHERE status = 'proposed'").fetchone()
        assert c is not None
        assert c["track_slug"] == "test-track"
        assert len(json.loads(c["evidence_event_ids_json"])) == 3


def test_insight_candidate_skipped_with_too_few_events(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_track_with_events(db_path, "sparse-track", num_a_events=2)
    result = detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60)
    assert result.proposed == 0


def test_insight_candidate_respects_run_date(tmp_path):
    """run_date determines the lookback window, not datetime.now()."""
    db_path = init_temp_db(tmp_path)
    seed_track_with_events(db_path, "test-track", num_a_events=3)

    # run_date='2026-06-01' with lookback=60 => cutoff='2026-04-02'
    # Events are on 2026-05-01..03, within window => should propose
    result = detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60, run_date="2026-06-01")
    assert result.proposed >= 1

    # run_date='2026-01-01' with lookback=30 => cutoff='2025-12-02'
    # Events are on 2026-05-01..03, OUTSIDE window => should not propose
    db_path2 = init_temp_db(tmp_path / "db2")
    seed_track_with_events(db_path2, "test-track", num_a_events=3)
    result2 = detect_insight_candidates(db_path=db_path2, min_a_events=3, lookback_days=30, run_date="2026-01-01")
    assert result2.proposed == 0


def test_insight_candidate_not_duplicated(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_track_with_events(db_path, "test-track", num_a_events=3)
    r1 = detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60)
    r2 = detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60)
    assert r1.proposed >= 1
    assert r2.proposed == 0


def test_insight_product_generates_page(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_track_with_events(db_path, "insight-track", num_a_events=3)
    detect_insight_candidates(db_path=db_path, min_a_events=3, lookback_days=60)
    result = generate_insight_pages(db_path=db_path, site_dir=site_dir)
    assert result.generated >= 1
    assert result.exported >= 1
    files = list((site_dir / "content" / "insights").glob("*.md"))
    assert len(files) >= 1
    content = files[0].read_text(encoding="utf-8")
    fm = content.split("---", 2)[1]
    assert "date: '2026-05-03T09:00:00+08:00'" in fm or 'date: "2026-05-03T09:00:00+08:00"' in fm
    assert "核心判断" in content
    assert "发生了什么" in content
    assert "为什么重要" in content
    assert "反向信号" in content
    assert "下一步观察" in content
    assert "证据链" in content
    assert "来源" in content


def test_insight_product_no_candidates(tmp_path):
    db_path = init_temp_db(tmp_path)
    result = generate_insight_pages(db_path=db_path, site_dir=tmp_path / "site")
    assert result.generated == 0
