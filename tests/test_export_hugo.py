import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_hugo import ExportResult, _get_llm_client, export_hugo
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, _body = text.split("---", 2)
    return yaml.safe_load(frontmatter)


def read_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("---", 2)[2]


def insert_decided_event(
    db_path: Path,
    title: str,
    grade: str,
    action: str,
    event_date: str = "2026-05-01",
    status: str = "pending",
    event_type: str = "model_release",
) -> int:
    entities = [{"name": "OpenAI", "slug": "openai", "type": "company"}]
    topics = ["llm"]
    claims = [{"statement": f"{title} happened.", "confidence": 0.8, "sources": ["https://example.com/source"]}]
    with get_conn(db_path) as conn:
        source = conn.execute("SELECT id FROM sources WHERE url = 'https://example.com/feed.xml'").fetchone()
        if source:
            source_id = int(source["id"])
        else:
            conn.execute(
                "INSERT INTO sources (name, type, url) VALUES ('Fixture Source', 'rss', 'https://example.com/feed.xml')"
            )
            source_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO raw_items (
              source_id, source_url, title, published_at, content_hash, status
            )
            VALUES (?, ?, ?, ?, ?, 'processed')
            """,
            (source_id, "https://example.com/source", title, event_date, f"hash-{title}"),
        )
        raw_item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO events (
              raw_item_id, event_title, event_summary, event_type, event_date,
              entities_json, topics_json, claims_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'modeled')
            """,
            (
                raw_item_id,
                title,
                f"Summary for {title}.",
                event_type,
                event_date,
                json.dumps(entities),
                json.dumps(topics),
                json.dumps(claims),
            ),
        )
        event_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO decisions (event_id, action, decision_grade, reason, need_review, status)
            VALUES (?, ?, ?, 'fixture', ?, ?)
            """,
            (event_id, action, grade, 1 if grade == "A" else 0, status),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_export_hugo_prefers_split_model_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "base-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://base.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "base-model")
    monkeypatch.setenv("LLM_API_KEY_CONTENT", "content-key")
    monkeypatch.setenv("LLM_BASE_URL_CONTENT", "https://content.example.com/v1")
    monkeypatch.setenv("LLM_MODEL_CONTENT", "content-model")

    client, model = _get_llm_client()

    assert model == "content-model"
    assert str(client.base_url) == "https://content.example.com/v1/"


def test_export_hugo_writes_daily_brief_insight_and_memory_draft(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory-wiki"
    insert_decided_event(db_path, "Important OpenAI model release", "A", "publish_article")
    insert_decided_event(db_path, "Useful daily update", "B", "daily_brief_only")
    insert_decided_event(db_path, "Related topic note", "C", "update_assets_only")

    result = export_hugo(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        date="2026-05-01",
        mock=True,
    )

    assert result == ExportResult(daily_briefs=1, insights=1, skipped_approved=0, failed_count=0)
    daily_path = site_dir / "content" / "briefs" / "daily" / "2026-05-01.md"
    insight_path = site_dir / "content" / "insights" / "important-openai-model-release.md"
    memory_path = memory_dir / "drafts" / "important-openai-model-release.md"
    assert daily_path.exists()
    assert insight_path.exists()
    assert memory_path.exists()
    daily_fm = read_frontmatter(daily_path)
    insight_fm = read_frontmatter(insight_path)
    daily_body = read_body(daily_path)
    insight_body = read_body(insight_path)
    assert daily_fm["type"] == "daily_brief"
    assert daily_fm["covered_events"]
    assert daily_fm["seo"]["structured_data"] == "Article"
    assert daily_fm["neican"]["review_status"] == "draft"
    assert "## 今日关键判断" in daily_body
    assert "## 值得跟踪" in daily_body
    assert "## 来源索引" in daily_body
    assert insight_fm["type"] == "insight"
    assert insight_fm["decision_grade"] == "A"
    assert insight_fm["sources"][0]["url"] == "https://example.com/source"
    assert insight_fm["entities"][0]["slug"] == "openai"
    assert insight_fm["topics"][0]["slug"] == "llm"
    assert insight_fm["claims"][0]["status"] == "active"
    assert insight_fm["neican"]["review_status"] == "draft"
    assert "## 核心判断" in insight_body
    assert "## 为什么值得关注" in insight_body
    assert "## 后续观察点" in insight_body
    with get_conn(db_path) as conn:
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='hugo_export'").fetchone()
    assert run["status"] == "success"
    assert json.loads(run["output_json"]) == {
        "daily_briefs": 1,
        "failed_count": 0,
        "insights": 1,
        "skipped_approved": 0,
    }


def test_export_hugo_filters_empty_claims(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory-wiki"
    insert_decided_event(db_path, "Important OpenAI model release", "A", "publish_article")
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE events SET claims_json = ?",
            (json.dumps([
                {"statement": "", "confidence": 0.8, "sources": ["https://example.com/source"]},
                {"statement": "Valid claim.", "confidence": 0.9, "sources": ["https://example.com/source"]},
                {"statement": "Missing source.", "confidence": 0.7, "sources": []},
            ]),),
        )

    export_hugo(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        date="2026-05-01",
        mock=True,
    )

    insight_path = site_dir / "content" / "insights" / "important-openai-model-release.md"
    insight_fm = read_frontmatter(insight_path)
    assert insight_fm["claims"] == [
        {"statement": "Valid claim.", "confidence": 0.9, "sources": ["https://example.com/source"], "status": "active"}
    ]


def test_export_hugo_does_not_overwrite_approved_insight(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory-wiki"
    insert_decided_event(db_path, "Important OpenAI model release", "A", "publish_article")
    approved_path = site_dir / "content" / "insights" / "important-openai-model-release.md"
    approved_path.parent.mkdir(parents=True)
    approved_path.write_text(
        """---
title: "Approved"
neican:
  review_status: "approved"
---
Approved content.
""",
        encoding="utf-8",
    )

    result = export_hugo(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        date="2026-05-01",
        mock=True,
    )

    assert result.insights == 0
    assert result.skipped_approved == 1
    assert "Approved content." in approved_path.read_text(encoding="utf-8")


def test_export_hugo_dry_run_does_not_write_files_or_runs(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory-wiki"
    insert_decided_event(db_path, "Useful daily update", "B", "daily_brief_only")

    result = export_hugo(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        date="2026-05-01",
        mock=True,
        dry_run=True,
    )

    assert result == ExportResult(daily_briefs=1, insights=0, skipped_approved=0, failed_count=0)
    assert not site_dir.exists()
    assert not memory_dir.exists()
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
