import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from entity_registry import normalize_entity_name, sync_entity_registry, normalize_events_entities
from sqlite_ops import get_conn


SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_aliases(tmp_path: Path) -> Path:
    aliases_path = tmp_path / "entity_aliases.yaml"
    aliases_path.write_text(
        yaml.safe_dump(
            {
                "OpenAI": ["Open AI", "ChatGPT maker"],
                "Anthropic": ["Claude maker"],
                "Google DeepMind": ["DeepMind", "Google AI"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return aliases_path


def seed_events_with_entity_aliases(db_path: Path):
    """Seed events mentioning different alias variants of the same entity."""
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        # Event 1: "OpenAI"
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, 'https://t.com/1', 'Title 1', 'h1', '2026-05-01T10:00:00Z', 'processed')"
        )
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (1, 'Event 1', 'Summary 1', 'tool_launch', '2026-05-01',
             '[{"name":"OpenAI","slug":"openai","type":"company"}]', '["ai-agents"]', '[]', 'modeled', 80)"""
        )
        # Event 2: "Open AI" (alias variant)
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, 'https://t.com/2', 'Title 2', 'h2', '2026-05-02T10:00:00Z', 'processed')"
        )
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (2, 'Event 2', 'Summary 2', 'tool_launch', '2026-05-02',
             '[{"name":"Open AI","slug":"open-ai","type":"company"}]', '["ai-agents"]', '[]', 'modeled', 80)"""
        )
        # Event 3: "ChatGPT maker" (another alias)
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, 'https://t.com/3', 'Title 3', 'h3', '2026-05-03T10:00:00Z', 'processed')"
        )
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (3, 'Event 3', 'Summary 3', 'tool_launch', '2026-05-03',
             '[{"name":"ChatGPT maker","slug":"chatgpt-maker","type":"company"}]', '["ai-agents"]', '[]', 'modeled', 80)"""
        )
        conn.commit()


def test_entity_registry_normalizes_aliases_to_one_slug(tmp_path):
    aliases_path = write_aliases(tmp_path)
    aliases = yaml.safe_load(aliases_path.read_text(encoding="utf-8"))

    slug, name = normalize_entity_name("Open AI", aliases)
    assert slug == "openai"
    assert name == "OpenAI"

    slug2, name2 = normalize_entity_name("ChatGPT maker", aliases)
    assert slug2 == "openai"
    assert name2 == "OpenAI"

    slug3, name3 = normalize_entity_name("OpenAI", aliases)
    assert slug3 == "openai"
    assert name3 == "OpenAI"


def test_entity_registry_upserts_entities_from_events(tmp_path):
    db_path = init_temp_db(tmp_path)
    aliases_path = write_aliases(tmp_path)
    seed_events_with_entity_aliases(db_path)

    result = sync_entity_registry(db_path=db_path, aliases_path=aliases_path)
    assert result.synced >= 1

    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM entity_registry WHERE slug = 'openai'"
        ).fetchone()
        assert row is not None
        assert row["canonical_name"] == "OpenAI"
        aliases_json = json.loads(row["aliases_json"])
        # Should include the variant names seen in events
        assert "ChatGPT maker" in aliases_json or "chatgpt maker" in aliases_json


def test_entity_registry_assigns_role_and_quality_from_entity_type(tmp_path):
    db_path = init_temp_db(tmp_path)
    aliases_path = write_aliases(tmp_path)
    seed_events_with_entity_aliases(db_path)

    sync_entity_registry(db_path=db_path, aliases_path=aliases_path)

    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT entity_type, entity_role, entity_quality, status FROM entity_registry WHERE slug = 'openai'"
        ).fetchone()

    assert row["entity_type"] == "company"
    assert row["entity_role"] == "core_actor"
    assert row["entity_quality"] == "approved"
    assert row["status"] == "active"


def test_entity_registry_uses_allowlist_for_core_organization(tmp_path):
    db_path = init_temp_db(tmp_path)
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) "
            "VALUES (1, 'https://t.com/gear', 'NVIDIA GEAR Lab', 'gear', '2026-05-01', 'processed')"
        )
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_type, event_date, entities_json, topics_json, claims_json, status) "
            "VALUES (1, 'NVIDIA GEAR Lab', 'research_paper', '2026-05-01', ?, '[\"embodied-ai\"]', '[]', 'modeled')",
            (json.dumps([{"name": "NVIDIA GEAR Lab", "slug": "nvidia-gear-lab", "type": "organization"}]),),
        )
        conn.commit()

    sync_entity_registry(db_path=db_path, aliases_path=write_aliases(tmp_path))

    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT entity_type, entity_role, entity_quality FROM entity_registry WHERE slug = 'nvidia-gear-lab'"
        ).fetchone()

    assert row["entity_type"] == "organization"
    assert row["entity_role"] == "infrastructure"
    assert row["entity_quality"] == "approved"


def test_entity_registry_handles_unknown_entity(tmp_path):
    aliases = {"OpenAI": ["Open AI"]}
    slug, name = normalize_entity_name("Unknown Startup", aliases)
    assert slug == "unknown-startup"
    assert name == "Unknown Startup"


def test_normalize_events_entities_rewrites_slugs(tmp_path):
    """After normalize_events_entities, all entity variants should have consistent slug/name."""
    db_path = init_temp_db(tmp_path)
    aliases_path = write_aliases(tmp_path)
    seed_events_with_entity_aliases(db_path)

    updated = normalize_events_entities(db_path=db_path, aliases_path=aliases_path)
    assert updated >= 2  # At least "Open AI" and "ChatGPT maker" events should change

    with get_conn(db_path) as conn:
        events = conn.execute("SELECT entities_json FROM events ORDER BY id").fetchall()
        slugs = set()
        for ev in events:
            entities = json.loads(ev["entities_json"])
            for ent in entities:
                slugs.add(ent["slug"])
        # All three events should now reference the same slug
        assert slugs == {"openai"}, f"Expected all slugs to be 'openai', got {slugs}"
        # All entity names should be canonical "OpenAI"
        for ev in events:
            entities = json.loads(ev["entities_json"])
            for ent in entities:
                assert ent["name"] == "OpenAI", f"Expected canonical name 'OpenAI', got {ent['name']}"
