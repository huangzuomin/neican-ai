import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from topic_product import generate_topic_pages
from topic_registry import sync_topic_registry
from sqlite_ops import get_conn

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def seed_events_for_topics(db_path: Path):
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        conn.execute("INSERT INTO raw_items (source_id, source_url, title, content_hash, status) VALUES (1, 'https://t.com/1', 't1', 'h1', 'processed')")
        conn.execute("INSERT INTO raw_items (source_id, source_url, title, content_hash, status) VALUES (1, 'https://t.com/2', 't2', 'h2', 'processed')")
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status) VALUES (1, 'Agent Tool Released', 's', 'tool_launch', '2026-05-01', ?, ?, '[]', 'modeled')",
            (json.dumps([{"name": "OpenAI", "slug": "openai"}]), json.dumps(["ai-agents"])),
        )
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status) VALUES (2, 'New LLM Benchmark', 's', 'research_paper', '2026-05-02', ?, ?, '[]', 'modeled')",
            (json.dumps([{"name": "Anthropic", "slug": "anthropic"}]), json.dumps(["llm"])),
        )
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (1, 'brief', 'B', 'pending')")
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (2, 'brief', 'B', 'pending')")
        conn.commit()


def write_taxonomy_for_test(tmp_path: Path) -> Path:
    path = tmp_path / "taxonomy.yaml"
    path.write_text(
        yaml.safe_dump({
            "topic_slugs": ["ai-agents", "llm"],
            "topics": [
                {"slug": "ai-agents", "canonical_name": "AI Agents", "aliases": [], "description": "Agents", "public": True},
                {"slug": "llm", "canonical_name": "LLM", "aliases": [], "description": "LLM", "public": True},
            ],
        }),
        encoding="utf-8",
    )
    return path


def test_topic_product_generates_pages(tmp_path):
    db_path = init_temp_db(tmp_path)
    taxonomy_path = write_taxonomy_for_test(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_events_for_topics(db_path)
    sync_topic_registry(db_path=db_path, taxonomy_path=taxonomy_path)
    result = generate_topic_pages(db_path=db_path, site_dir=site_dir)
    assert result.generated >= 2
    assert result.exported >= 2
    assert (site_dir / "content" / "topics" / "_index.md").exists()
    ai_agents = site_dir / "content" / "topics" / "ai-agents" / "_index.md"
    assert ai_agents.exists()
    assert (site_dir / "content" / "topics" / "llm" / "_index.md").exists()
    text = ai_agents.read_text(encoding="utf-8")
    assert "## 一句话定义" in text
    assert "## 当前判断" in text
    assert "## 最近 30 天变化" in text
    assert "## 下一步观察" in text


def test_topic_product_includes_related_tracks(tmp_path):
    db_path = init_temp_db(tmp_path)
    taxonomy_path = write_taxonomy_for_test(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_events_for_topics(db_path)
    sync_topic_registry(db_path=db_path, taxonomy_path=taxonomy_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO timeline_nodes (
              event_id, slug, title, date, year, month, grade, entities_json, topics_json, tracks_json,
              sources_json, status
            )
            VALUES (1, 'agent-tool-released', 'Agent Tool Released', '2026-05-01', '2026', '2026-05', 'B',
              '[{"name":"OpenAI","slug":"openai"}]', '["ai-agents"]',
              '["ai-agents-enterprise"]', '[]', 'public')
            """
        )
        conn.commit()

    result = generate_topic_pages(db_path=db_path, site_dir=site_dir)

    assert result.generated >= 2
    text = (site_dir / "content" / "topics" / "ai-agents" / "_index.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["related_tracks"] == ["ai-agents-enterprise"]
    assert "## 相关追踪线" in text
    assert "/timeline/ai-agents-enterprise/" in text


def test_topic_product_handles_empty_db(tmp_path):
    db_path = init_temp_db(tmp_path)
    taxonomy_path = write_taxonomy_for_test(tmp_path)
    site_dir = tmp_path / "hugo-site"
    sync_topic_registry(db_path=db_path, taxonomy_path=taxonomy_path)
    result = generate_topic_pages(db_path=db_path, site_dir=site_dir)
    assert result.generated >= 0
