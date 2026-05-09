import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from candidate_tracks import discover_candidate_tracks
from sqlite_ops import get_conn
from track_review import materialize_approved_tracks, review_candidate_tracks


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_existing_tracks(tmp_path: Path) -> Path:
    path = tmp_path / "timeline_tracks.yaml"
    path.write_text(
        """
tracks:
  - slug: ai-agents-enterprise
    title: AI Agents 企业化
    description: 从会调用工具，到能进入企业权限、审计和流程系统。
    match:
      topics:
        - ai-agents
        - mcp
      entities:
        - openai
        - anthropic
        - microsoft
""".lstrip(),
        encoding="utf-8",
    )
    return path


def insert_event(db_path: Path, title: str, topics: list[str], entities: list[dict], day: str) -> int:
    with get_conn(db_path) as conn:
        source = conn.execute("SELECT id FROM sources WHERE url='https://example.com/feed.xml'").fetchone()
        if source:
            source_id = int(source["id"])
        else:
            conn.execute(
                "INSERT INTO sources (name, type, url) VALUES ('Fixture Feed', 'rss', 'https://example.com/feed.xml')"
            )
            source_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO raw_items (
              source_id, source_url, title, published_at, clean_text, content_hash, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'processed')
            """,
            (
                source_id,
                f"https://example.com/{day}/{abs(hash(title))}",
                title,
                f"2026-05-{day}",
                title,
                f"hash-{day}-{title}",
            ),
        )
        raw_item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO events (
              raw_item_id, event_title, event_summary, event_type, event_date,
              entities_json, topics_json, claims_json, importance_score, confidence, status
            )
            VALUES (?, ?, ?, 'industry_trend', ?, ?, ?, '[]', 82, 0.84, 'modeled')
            """,
            (
                raw_item_id,
                title,
                f"Summary for {title}",
                f"2026-05-{day}",
                json.dumps(entities, ensure_ascii=False),
                json.dumps(topics, ensure_ascii=False),
            ),
        )
        event_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO decisions (event_id, action, decision_grade, reason, need_review, status)
            VALUES (?, 'daily_brief_only', 'B', 'fixture', 0, 'pending')
            """,
            (event_id,),
        )
        return event_id


def test_track_review_merges_candidate_into_existing_public_track(tmp_path):
    db_path = init_temp_db(tmp_path)
    tracks_path = write_existing_tracks(tmp_path)
    event_ids = [
        insert_event(
            db_path,
            "Agent evals become enterprise procurement gate",
            ["ai-agents", "mcp"],
            [{"name": "OpenAI", "slug": "openai", "type": "company"}],
            "01",
        ),
        insert_event(
            db_path,
            "Microsoft asks for agent audit and recovery evidence",
            ["ai-agents"],
            [{"name": "Microsoft", "slug": "microsoft", "type": "company"}],
            "02",
        ),
        insert_event(
            db_path,
            "Anthropic positions agent safety evals for enterprise use",
            ["ai-agents", "ai-safety"],
            [{"name": "Anthropic", "slug": "anthropic", "type": "company"}],
            "03",
        ),
    ]

    discovered = discover_candidate_tracks(db_path=db_path, min_events=3)
    reviewed = review_candidate_tracks(db_path=db_path, tracks_path=tracks_path)

    assert discovered.to_dict() == {"created": 1, "updated": 0, "skipped": 0}
    assert reviewed.to_dict() == {"approved": 0, "merged": 1, "watch": 0, "rejected": 0}
    with get_conn(db_path) as conn:
        candidate = conn.execute("SELECT * FROM candidate_tracks").fetchone()
        decision = conn.execute("SELECT * FROM track_review_decisions").fetchone()

    assert candidate["status"] == "merged"
    assert json.loads(candidate["event_ids_json"]) == event_ids
    assert decision["decision"] == "merge"
    assert decision["target_track"] == "ai-agents-enterprise"
    assert "并入" in decision["reason"]


def test_track_review_approves_distinct_candidate_track(tmp_path):
    """Candidate has 5 events, multiple entities, no overlap with existing tracks."""
    db_path = init_temp_db(tmp_path)
    # Use a minimal tracks config with only one track
    tracks_path = tmp_path / "timeline_tracks.yaml"
    tracks_path.write_text(
        "tracks:\n  - slug: existing-track\n    title: Existing\n    description: test\n    match:\n      topics:\n        - some-topic\n",
        encoding="utf-8",
    )

    # Create events in a completely different topic space
    for day in ["01", "02", "03", "04", "05"]:
        insert_event(
            db_path,
            f"Novel signal event {day}",
            ["novel-topic"],
            [{"name": "EntityA", "slug": "entitya", "type": "company"}, {"name": "EntityB", "slug": "entityb", "type": "company"}],
            day,
        )

    discovered = discover_candidate_tracks(db_path=db_path, min_events=3)
    reviewed = review_candidate_tracks(db_path=db_path, tracks_path=tracks_path)

    assert reviewed.approved == 1
    assert reviewed.merged == 0

    with get_conn(db_path) as conn:
        decision = conn.execute(
            "SELECT * FROM track_review_decisions WHERE decision = 'approved'"
        ).fetchone()
        assert decision is not None
        assert decision["decision"] == "approved"


def test_materialize_approved_tracks(tmp_path):
    """Approved tracks should be written to config without overwriting manual tracks."""
    db_path = init_temp_db(tmp_path)
    tracks_path = tmp_path / "timeline_tracks.yaml"
    tracks_path.write_text(
        "tracks:\n  - slug: existing\n    title: Existing\n    description: test\n    match: {}\n",
        encoding="utf-8",
    )

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO candidate_tracks (slug, proposed_title, event_count, confidence, status,
                dominant_topics_json, dominant_entities_json, event_ids_json)
            VALUES ('auto-track', 'Auto Track', 5, 0.85, 'approved',
                '["topic1"]', '["entity1"]', '[1,2,3,4,5]')
            """
        )
        conn.execute(
            """
            INSERT INTO track_review_decisions (candidate_track_id, decision, proposed_title, reason, confidence, evidence_event_ids_json)
            VALUES (1, 'approved', 'Auto Track', 'Test', 0.85, '[1,2,3,4,5]')
            """
        )
        conn.commit()

    count = materialize_approved_tracks(db_path=db_path, tracks_path=tracks_path)
    assert count == 1

    # Verify the generated track was written
    data = yaml.safe_load(tracks_path.read_text(encoding="utf-8"))
    gen_tracks = data.get("generated_tracks") or []
    generated = next(t for t in gen_tracks if t["slug"] == "auto-track")
    assert generated["candidate_track_id"] == 1
    assert generated["evidence_event_ids"] == [1, 2, 3, 4, 5]

    # Verify manual tracks are preserved
    manual = data.get("tracks") or []
    assert any(t["slug"] == "existing" for t in manual)

    # Verify candidate status updated
    with get_conn(db_path) as conn:
        ct = conn.execute("SELECT status FROM candidate_tracks WHERE slug='auto-track'").fetchone()
        assert ct["status"] == "materialized"
