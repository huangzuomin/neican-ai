import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from event_store import merge_modeled_events
from sqlite_ops import get_conn


SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def seed_two_sources_same_event(db_path: Path):
    """Insert two raw_items from different sources about the same event."""
    with get_conn(db_path) as conn:
        # Two sources
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Source A', 'rss', 'https://a.com/feed')")
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Source B', 'rss', 'https://b.com/feed')")

        # Two raw items with similar but not identical titles, same date, same entities
        # Word-bag should merge: "Launches", "Model", "Major", "Upgrades" are filler/stopwords
        for i, (sid, url, title) in enumerate([
            (1, "https://a.com/openai-launches-gpt5", "OpenAI Launches GPT-5 Model"),
            (2, "https://b.com/openai-gpt5-release", "OpenAI launches GPT-5 model with major upgrades"),
        ]):
            conn.execute(
                "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (?, ?, ?, ?, ?, 'processed')",
                (sid, url, title, f"hash{i+1}", "2026-05-01T10:00:00Z"),
            )

        # Two events with same merge key (same word-bag + same date + same first entity)
        entities = json.dumps([{"name": "OpenAI", "slug": "openai", "type": "company"}])
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (1, 'OpenAI Launches GPT-5 Model', 'Summary 1', 'model_release', '2026-05-01',
             ?, '["llm"]', '[]', 'modeled', 90)""",
            (entities,),
        )
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (2, 'OpenAI launches GPT-5 model with major upgrades', 'Summary 2', 'model_release', '2026-05-01',
             ?, '["llm"]', '[]', 'modeled', 80)""",
            (entities,),
        )
        conn.commit()


def seed_distinct_events(db_path: Path):
    """Insert two events that should NOT merge (different date or entity)."""
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Source A', 'rss', 'https://a.com/feed')")

        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, 'https://a.com/1', 'OpenAI releases GPT-5', 'h1', '2026-05-01T10:00:00Z', 'processed')"
        )
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, 'https://a.com/2', 'Google releases Gemini 3', 'h2', '2026-05-02T10:00:00Z', 'processed')"
        )

        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (1, 'OpenAI releases GPT-5', 'Summary 1', 'model_release', '2026-05-01',
             '[{"name":"OpenAI","slug":"openai"}]', '["llm"]', '[]', 'modeled', 80)"""
        )
        conn.execute(
            """INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date,
               entities_json, topics_json, claims_json, status, importance_score)
            VALUES (2, 'Google releases Gemini 3', 'Summary 2', 'model_release', '2026-05-02',
             '[{"name":"Google","slug":"google"}]', '["llm"]', '[]', 'modeled', 80)"""
        )
        conn.commit()


def test_event_store_merges_two_raw_items_about_same_event(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_two_sources_same_event(db_path)

    result = merge_modeled_events(db_path=db_path)
    assert result.merged_events == 1
    assert result.canonical_events >= 1
    assert result.event_sources >= 2

    with get_conn(db_path) as conn:
        # One canonical event remains modeled
        public_events = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE status = 'modeled'"
        ).fetchone()["c"]
        assert public_events == 1

        # Merged event
        merged_events = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE status = 'merged'"
        ).fetchone()["c"]
        assert merged_events == 1

        # event_sources has two rows for the canonical event
        sources = conn.execute("SELECT * FROM event_sources").fetchall()
        assert len(sources) == 2
        # Both point to the same canonical event
        event_ids = {s["event_id"] for s in sources}
        assert len(event_ids) == 1


def test_event_store_keeps_distinct_events_separate(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_distinct_events(db_path)

    result = merge_modeled_events(db_path=db_path)
    assert result.merged_events == 0
    assert result.canonical_events == 2

    with get_conn(db_path) as conn:
        public_events = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE status = 'modeled'"
        ).fetchone()["c"]
        assert public_events == 2


def test_normalize_then_merge_combines_alias_variants(tmp_path):
    """Events with different entity name aliases in titles should merge after normalization."""
    from entity_registry import sync_entity_registry, normalize_events_entities

    db_path = init_temp_db(tmp_path)
    aliases_path = tmp_path / "entity_aliases.yaml"
    aliases_path.write_text("OpenAI:\n  - Open AI\n  - ChatGPT maker\n", encoding="utf-8")

    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('A', 'rss', 'https://a.com')")
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('B', 'rss', 'https://b.com')")
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) "
            "VALUES (1, 'https://a.com/1', 't1', 'h1', '2026-05-01T10:00:00Z', 'processed')"
        )
        conn.execute(
            "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) "
            "VALUES (2, 'https://b.com/1', 't2', 'h2', '2026-05-01T11:00:00Z', 'processed')"
        )
        # Two events: same real-world thing, different entity name variant in title
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, "
            "entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (1, 'OpenAI Launches GPT-5 Model', 'S1', 'model_release', '2026-05-01', "
            "'[{\"name\":\"OpenAI\",\"slug\":\"openai\"}]', '[\"llm\"]', '[]', 'modeled', 80)"
        )
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, "
            "entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (2, 'Open AI launches GPT-5 model with major upgrades', 'S2', 'model_release', '2026-05-01', "
            "'[{\"name\":\"Open AI\",\"slug\":\"open-ai\"}]', '[\"llm\"]', '[]', 'modeled', 80)"
        )
        conn.commit()

    # Step 1: sync registry
    sync_entity_registry(db_path=db_path, aliases_path=aliases_path)
    # Step 2: normalize events (rewrites slug to canonical "openai")
    normalize_events_entities(db_path=db_path, aliases_path=aliases_path)
    # Step 3: merge with config_dir so alias map is used in title matching
    result = merge_modeled_events(db_path=db_path, config_dir=tmp_path)

    assert result.merged_events == 1, f"Expected 1 merge, got {result.merged_events}"
    assert result.canonical_events == 1

    with get_conn(db_path) as conn:
        events = conn.execute("SELECT * FROM events WHERE status = 'modeled'").fetchall()
        assert len(events) == 1
        entities = json.loads(events[0]["entities_json"])
        assert entities[0]["slug"] == "openai"
        assert entities[0]["name"] == "OpenAI"


def test_event_store_second_run_does_not_recount_merged_events(tmp_path):
    db_path = init_temp_db(tmp_path)
    seed_two_sources_same_event(db_path)

    first = merge_modeled_events(db_path=db_path)
    second = merge_modeled_events(db_path=db_path)

    assert first.merged_events == 1
    assert second.merged_events == 0
    assert second.event_sources == 0
