import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sqlite_ops import get_conn
from timeline_product import run


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_tracks(tmp_path: Path) -> Path:
    tracks_path = tmp_path / "timeline_tracks.yaml"
    tracks_path.write_text(
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
  - slug: ai-governance
    title: AI 治理与监管
    description: 安全评测、数据边界、责任链和跨国监管框架。
    match:
      topics:
        - ai-policy
        - ai-safety
""".lstrip(),
        encoding="utf-8",
    )
    return tracks_path


def insert_decided_event(
    db_path: Path,
    title: str,
    grade: str,
    topics: list[str],
    entities: list[dict],
) -> int:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO sources (name, type, url) VALUES ('Fixture Feed', 'rss', 'https://example.com/feed.xml')"
        )
        source_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO raw_items (
              source_id, source_url, title, published_at, clean_text, content_hash, status
            )
            VALUES (?, ?, ?, '2026-05-03', ?, ?, 'processed')
            """,
            (
                source_id,
                "https://example.com/openai-agent-runtime",
                title,
                "OpenAI agent runtime update with MCP and enterprise governance.",
                f"hash-{title}",
            ),
        )
        raw_item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO events (
              raw_item_id, event_title, event_summary, event_type, event_date,
              entities_json, topics_json, claims_json, importance_score, confidence, status
            )
            VALUES (?, ?, ?, 'product_update', '2026-05-03', ?, ?, ?, 88, 0.82, 'modeled')
            """,
            (
                raw_item_id,
                title,
                "Agent runtime is becoming a governance layer for enterprise AI.",
                json.dumps(entities, ensure_ascii=False),
                json.dumps(topics, ensure_ascii=False),
                json.dumps([{"claim_text": "OpenAI updated its agent runtime.", "confidence": 0.8}], ensure_ascii=False),
            ),
        )
        event_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO decisions (event_id, action, decision_grade, reason, need_review, status)
            VALUES (?, 'publish_article', ?, 'fixture', 0, 'pending')
            """,
            (event_id, grade),
        )
        return event_id


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, _body = text.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_timeline_product_assigns_events_to_tracks_and_exports_track_pages(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    tracks_path = write_tracks(tmp_path)
    event_id = insert_decided_event(
        db_path,
        "OpenAI agent runtime becomes enterprise control plane",
        "A",
        topics=["ai-agents", "mcp"],
        entities=[{"name": "OpenAI", "slug": "openai", "type": "company"}],
    )

    result = run(db_path=db_path, site_dir=site_dir, tracks_path=tracks_path)

    assert result.to_dict()["exported_tracks"] == 1
    with get_conn(db_path) as conn:
        node = conn.execute("SELECT tracks_json FROM timeline_nodes WHERE event_id = ?", (event_id,)).fetchone()
    assert json.loads(node["tracks_json"]) == ["ai-agents-enterprise"]

    index_path = site_dir / "content" / "timeline" / "_index.md"
    track_path = site_dir / "content" / "timeline" / "ai-agents-enterprise" / "_index.md"
    assert index_path.exists()
    assert track_path.exists()
    assert "当前追踪线" in index_path.read_text(encoding="utf-8")
    assert "AI Agents 企业化" in index_path.read_text(encoding="utf-8")
    assert "OpenAI agent runtime becomes enterprise control plane" in track_path.read_text(encoding="utf-8")
    track_fm = read_frontmatter(track_path)
    assert track_fm["type"] == "timeline_track"
    assert track_fm["track"]["slug"] == "ai-agents-enterprise"


def test_timeline_product_does_not_assign_unrelated_event_by_broad_event_type(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    tracks_path = write_tracks(tmp_path)
    event_id = insert_decided_event(
        db_path,
        "Unrelated product update",
        "B",
        topics=[],
        entities=[],
    )

    result = run(db_path=db_path, site_dir=site_dir, tracks_path=tracks_path)

    assert result.to_dict()["exported_tracks"] == 0
    with get_conn(db_path) as conn:
        node = conn.execute("SELECT tracks_json FROM timeline_nodes WHERE event_id = ?", (event_id,)).fetchone()
    assert json.loads(node["tracks_json"]) == []
    assert not (site_dir / "content" / "timeline" / "ai-agents-enterprise" / "_index.md").exists()
