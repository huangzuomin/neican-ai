import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from candidate_tracks import discover_candidate_tracks
from sqlite_ops import get_conn
from track_review import review_candidate_tracks


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
