import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from entity_product import generate_from_db, export_hugo
from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def seed_event_with_core_and_noise_entities(db_path: Path) -> None:
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('36kr AI', 'rss', 'https://36kr.com/feed')")
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) "
            "VALUES (1, 'https://36kr.com/p/1', 'OpenAI 发布 Agent 工具', 'h1', '2026-05-01', 'processed')"
        )
        entities = [
            {"name": "OpenAI", "slug": "openai", "type": "company"},
            {"name": "36氪", "slug": "36kr", "type": "organization"},
            {"name": "港交所", "slug": "hkex", "type": "organization"},
        ]
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (1, 'OpenAI 发布 Agent 工具', 'OpenAI 发布面向 Agent 工作流的工具。', 'tool_launch', '2026-05-01', ?, '[\"ai-agents\"]', '[]', 'modeled', 90)",
            (json.dumps(entities, ensure_ascii=False),),
        )
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (1, 'brief', 'B', 'pending')")
        conn.commit()


def seed_event_with_allowlisted_organization(db_path: Path) -> None:
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com/feed')")
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) "
            "VALUES (1, 'https://t.com/gear', 'NVIDIA GEAR Lab 发布机器人研究', 'gear-hash', '2026-05-01', 'processed')"
        )
        entities = [{"name": "NVIDIA GEAR Lab", "slug": "nvidia-gear-lab", "type": "organization"}]
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (1, 'NVIDIA GEAR Lab 发布机器人研究', 'NVIDIA GEAR Lab 发布具身智能研究。', 'research_paper', '2026-05-01', ?, '[\"embodied-ai\"]', '[]', 'modeled', 90)",
            (json.dumps(entities, ensure_ascii=False),),
        )
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (1, 'brief', 'B', 'pending')")
        conn.commit()


def test_entity_product_suppresses_source_media_and_noise_entities(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_event_with_core_and_noise_entities(db_path)

    with get_conn(db_path) as conn:
        generated = generate_from_db(conn)
        rows = conn.execute(
            "SELECT slug, entity_role, entity_quality, status FROM entity_profiles ORDER BY slug"
        ).fetchall()

    assert generated == 3
    by_slug = {row["slug"]: dict(row) for row in rows}
    assert by_slug["openai"]["entity_role"] == "core_actor"
    assert by_slug["openai"]["entity_quality"] == "approved"
    assert by_slug["openai"]["status"] == "public"
    assert by_slug["36kr"]["entity_role"] == "source_media"
    assert by_slug["36kr"]["entity_quality"] == "suppressed"
    assert by_slug["36kr"]["status"] == "suppressed"
    assert by_slug["hkex"]["entity_role"] == "mentioned_context"
    assert by_slug["hkex"]["entity_quality"] == "candidate"
    assert by_slug["hkex"]["status"] == "suppressed"


def test_entity_export_only_writes_public_approved_core_entities(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_event_with_core_and_noise_entities(db_path)

    with get_conn(db_path) as conn:
        generate_from_db(conn)
        exported = export_hugo(conn, site_dir=site_dir)

    assert exported == 1
    assert (site_dir / "content" / "entities" / "openai" / "_index.md").exists()
    assert not (site_dir / "content" / "entities" / "36kr" / "_index.md").exists()
    assert not (site_dir / "content" / "entities" / "hkex" / "_index.md").exists()
    index_text = (site_dir / "content" / "entities" / "_index.md").read_text(encoding="utf-8")
    assert "OpenAI" in index_text
    assert "36氪" not in index_text
    assert "港交所" not in index_text


def test_entity_page_adds_context_and_hides_claim_confidence(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_event_with_core_and_noise_entities(db_path)

    with get_conn(db_path) as conn:
        generate_from_db(conn)
        conn.execute(
            "UPDATE entity_profiles SET claims_json = ? WHERE slug = 'openai'",
            (json.dumps([{"text": "OpenAI 发布面向 Agent 工作流的工具。", "confidence": 0.95}], ensure_ascii=False),),
        )
        export_hugo(conn, site_dir=site_dir)

    text = (site_dir / "content" / "entities" / "openai" / "_index.md").read_text(encoding="utf-8")
    assert "OpenAI 是 neican.ai 追踪的 AI 行业公司。" in text
    assert "tool_launch" in text
    assert "OpenAI 发布面向 Agent 工作流的工具。" in text
    assert "95%" not in text


def test_entity_allowlist_promotes_core_organization_to_public(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_event_with_allowlisted_organization(db_path)

    with get_conn(db_path) as conn:
        generate_from_db(conn)
        row = conn.execute(
            "SELECT entity_role, entity_quality, status FROM entity_profiles WHERE slug = 'nvidia-gear-lab'"
        ).fetchone()
        exported = export_hugo(conn, site_dir=site_dir)

    assert row["entity_role"] == "infrastructure"
    assert row["entity_quality"] == "approved"
    assert row["status"] == "public"
    assert exported == 1
    assert (site_dir / "content" / "entities" / "nvidia-gear-lab" / "_index.md").exists()
