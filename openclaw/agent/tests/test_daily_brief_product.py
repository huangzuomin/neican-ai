import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from daily_brief_product import generate_daily_brief
from sqlite_ops import get_conn

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def seed_daily_events(db_path: Path, date: str = "2026-05-01"):
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        for i in range(4):
            conn.execute(
                "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, ?, ?, ?, ?, 'processed')",
                (f"https://t.com/{i+1}", f"Event {i+1}", f"h{i+1}", f"{date}T{10+i}:00:00Z"),
            )
        # Event 1: A-grade on ai-agents track
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (1, 'Agent Tool Released', 'A new agent tool', 'tool_launch', ?, ?, '[\"ai-agents\"]', '[]', 'modeled', 90)",
            (date, json.dumps([{"name": "OpenAI", "slug": "openai", "type": "company"}])),
        )
        # Event 2: B-grade on model track
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (2, 'New LLM Released', 'A new LLM', 'model_release', ?, ?, '[\"llm\"]', '[]', 'modeled', 70)",
            (date, json.dumps([{"name": "Anthropic", "slug": "anthropic", "type": "company"}])),
        )
        # Event 3: C-grade untracked
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (3, 'Minor Update', 'A minor update', 'product_update', ?, '[]', '[]', '[]', 'modeled', 40)",
            (date,),
        )
        # Event 4: A-grade second on agents track
        conn.execute(
            "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
            "VALUES (4, 'MCP Protocol Adoption Grows', 'More companies adopt MCP', 'tool_launch', ?, ?, '[\"mcp\",\"ai-agents\"]', '[]', 'modeled', 85)",
            (date, json.dumps([{"name": "Anthropic", "slug": "anthropic"}, {"name": "OpenAI", "slug": "openai"}])),
        )

        # Decisions: A, B, C, A
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (1, 'insight', 'A', 'pending')")
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (2, 'brief', 'B', 'pending')")
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (3, 'brief', 'C', 'pending')")
        conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (4, 'insight', 'A', 'pending')")

        # Timeline nodes with tracks
        conn.execute(
            "INSERT INTO timeline_nodes (event_id, date, year, month, slug, title, summary, grade, status, tracks_json) "
            "VALUES (1, ?, '2026', '2026-05', 'agent-tool', 'Agent Tool', 's', 'A', 'public', ?)",
            (date, json.dumps(["ai-agents-enterprise"])),
        )
        conn.execute(
            "INSERT INTO timeline_nodes (event_id, date, year, month, slug, title, summary, grade, status, tracks_json) "
            "VALUES (2, ?, '2026', '2026-05', 'new-llm', 'New LLM', 's', 'B', 'public', ?)",
            (date, json.dumps(["model-competition"])),
        )
        conn.execute(
            "INSERT INTO timeline_nodes (event_id, date, year, month, slug, title, summary, grade, status, tracks_json) "
            "VALUES (4, ?, '2026', '2026-05', 'mcp-grow', 'MCP Grows', 's', 'A', 'public', ?)",
            (date, json.dumps(["ai-agents-enterprise"])),
        )
        conn.commit()


def write_tracks_config(tmp_path: Path) -> Path:
    tracks_path = tmp_path / "timeline_tracks.yaml"
    tracks_path.write_text(
        yaml.safe_dump({"tracks": [
            {"slug": "ai-agents-enterprise", "title": "AI Agents 企业化", "description": "test", "match": {}},
            {"slug": "model-competition", "title": "模型能力竞争", "description": "test", "match": {}},
        ]}),
        encoding="utf-8",
    )
    return tracks_path


def test_daily_brief_groups_events_by_timeline_track(tmp_path):
    db_path = init_temp_db(tmp_path)
    tracks_path = write_tracks_config(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_daily_events(db_path, "2026-05-01")
    result = generate_daily_brief(db_path=db_path, site_dir=site_dir, date="2026-05-01", tracks_path=tracks_path)
    assert result.exported
    assert result.events_count == 4
    assert result.tracks_count >= 2

    brief_path = site_dir / "content" / "briefs" / "daily" / "2026-05-01.md"
    assert brief_path.exists()
    content = brief_path.read_text(encoding="utf-8")

    # Must contain key judgment section
    assert "今日关键判断" in content
    assert "A级 2" in content
    assert "B级 1" in content
    assert "C级 1" in content

    # Must group events by track heading
    assert "AI Agents 企业化" in content
    assert "模型能力竞争" in content

    # Must contain A-level highlight section
    assert "A 级事件" in content
    assert "Agent Tool Released" in content

    # Must contain source index
    assert "来源索引" in content


def test_daily_brief_dedupes_same_event_source_and_title(tmp_path):
    db_path = init_temp_db(tmp_path)
    tracks_path = write_tracks_config(tmp_path)
    site_dir = tmp_path / "hugo-site"
    date = "2026-05-01"
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO sources (name, type, url) VALUES ('Test', 'rss', 'https://t.com')")
        for i, title in enumerate(["OpenAI Agent Update", "OpenAI Agent Update"], start=1):
            conn.execute(
                "INSERT INTO raw_items (source_id, source_url, title, content_hash, published_at, status) VALUES (1, ?, ?, ?, ?, 'processed')",
                ("https://t.com/same", title, f"dedupe-{i}", f"{date}T10:00:00Z"),
            )
            conn.execute(
                "INSERT INTO events (raw_item_id, event_title, event_summary, event_type, event_date, entities_json, topics_json, claims_json, status, importance_score) "
                "VALUES (?, ?, 'summary', 'tool_launch', ?, '[]', '[\"ai-agents\"]', '[]', 'modeled', 80)",
                (i, title, date),
            )
            conn.execute("INSERT INTO decisions (event_id, action, decision_grade, status) VALUES (?, 'brief', 'B', 'pending')", (i,))
        conn.commit()

    result = generate_daily_brief(db_path=db_path, site_dir=site_dir, date=date, tracks_path=tracks_path)
    content = (site_dir / "content" / "briefs" / "daily" / f"{date}.md").read_text(encoding="utf-8")

    assert result.events_count == 1
    assert "covered_events:\n- event_1" in content
    assert "event_2" not in content
    assert content.count("https://t.com/same") == 1


def test_daily_brief_includes_track_review_summary(tmp_path):
    db_path = init_temp_db(tmp_path)
    tracks_path = write_tracks_config(tmp_path)
    site_dir = tmp_path / "hugo-site"
    test_date = "2026-05-01"
    seed_daily_events(db_path, test_date)

    # Add a track review decision for this date
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO candidate_tracks (slug, proposed_title, event_count, confidence, status) VALUES ('auto-track', 'Auto Track', 5, 0.85, 'approved')"
        )
        conn.execute(
            "INSERT INTO track_review_decisions (candidate_track_id, decision, proposed_title, reason, confidence, created_at) VALUES (1, 'approved', 'Auto Track', 'Test approved', 0.85, ?)",
            (test_date + "T12:00:00Z",),
        )
        conn.commit()

    result = generate_daily_brief(db_path=db_path, site_dir=site_dir, date=test_date, tracks_path=tracks_path)
    content = (site_dir / "content" / "briefs" / "daily" / f"{test_date}.md").read_text(encoding="utf-8")
    assert "追踪线动态" in content
    assert "通过审核" in content


def test_daily_brief_empty_day(tmp_path):
    db_path = init_temp_db(tmp_path)
    tracks_path = write_tracks_config(tmp_path)
    site_dir = tmp_path / "hugo-site"
    result = generate_daily_brief(db_path=db_path, site_dir=site_dir, date="2026-01-01", tracks_path=tracks_path)
    assert not result.exported
    assert result.events_count == 0
