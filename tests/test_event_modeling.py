import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from event_modeling import EventModelingResult, _get_llm_client, model_events
from hash_utils import compute_content_hash
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"
CONFIG_DIR = ROOT / "config"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def insert_source_and_raw_item(
    db_path: Path,
    title: str,
    clean_text: str | None,
    trust_level: int = 5,
    status: str = "new",
) -> int:
    with get_conn(db_path) as conn:
        source = conn.execute("SELECT id FROM sources WHERE url = 'https://example.com/feed.xml'").fetchone()
        if source:
            source_id = int(source["id"])
        else:
            conn.execute(
                """
                INSERT INTO sources (name, type, url, trust_level)
                VALUES ('Fixture Source', 'rss', 'https://example.com/feed.xml', ?)
                """,
                (trust_level,),
            )
            source_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        source_url = f"https://example.com/{abs(hash(title))}"
        conn.execute(
            """
            INSERT INTO raw_items (
              source_id, source_url, title, published_at, raw_text, clean_text,
              content_hash, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_url,
                title,
                "2026-05-01",
                clean_text,
                clean_text,
                compute_content_hash(title, source_url, "2026-05-01"),
                status,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_model_events_creates_mock_event_and_marks_raw_item_processed(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_source_and_raw_item(
        db_path,
        "OpenAI releases GPT model update",
        "OpenAI released a GPT model update for AI agents and llm users.",
    )

    result = model_events(db_path=db_path, config_dir=CONFIG_DIR, mock=True, raw_item_id=raw_item_id)

    assert result == EventModelingResult(modeled_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        raw_item = conn.execute("SELECT status FROM raw_items WHERE id = ?", (raw_item_id,)).fetchone()
        event = conn.execute("SELECT * FROM events WHERE raw_item_id = ?", (raw_item_id,)).fetchone()
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='event_modeling'").fetchone()

    assert raw_item["status"] == "processed"
    assert event["event_title"] == "OpenAI releases GPT model update"
    assert event["event_type"] == "model_release"
    assert event["importance_score"] == 100
    assert event["seo_value_score"] == 60
    assert event["knowledge_value_score"] == 55
    assert event["confidence"] == 0.60
    assert json.loads(event["entities_json"]) == [
        {"name": "OpenAI", "slug": "openai", "type": "company", "role": "mentioned"}
    ]
    assert "llm" in json.loads(event["topics_json"])
    # Fallback claims are now extracted from text, not empty
    claims = json.loads(event["claims_json"])
    assert isinstance(claims, list)
    assert run["status"] == "success"
    run_output = json.loads(run["output_json"])
    assert run_output["failed_count"] == 0
    assert run_output["modeled_count"] == 1
    assert run_output["fallback_count"] == 1
    assert run_output["llm_count"] == 0


def test_model_events_requires_clean_text(tmp_path):
    db_path = init_temp_db(tmp_path)
    raw_item_id = insert_source_and_raw_item(
        db_path,
        "OpenAI releases GPT model update",
        None,
    )

    result = model_events(db_path=db_path, config_dir=CONFIG_DIR, mock=True, raw_item_id=raw_item_id)

    assert result == EventModelingResult(modeled_count=0, failed_count=0)
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM raw_items WHERE id = ?", (raw_item_id,)).fetchone()[0] == "new"


def test_model_events_scores_risk_keywords_and_respects_limit(tmp_path):
    db_path = init_temp_db(tmp_path)
    first_id = insert_source_and_raw_item(db_path, "Funding round", "Company announced funding.")
    second_id = insert_source_and_raw_item(db_path, "Policy issue", "This includes 安全漏洞 and 法律诉讼.")

    result = model_events(db_path=db_path, config_dir=CONFIG_DIR, mock=True, limit=1)

    assert result == EventModelingResult(modeled_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM raw_items WHERE id = ?", (first_id,)).fetchone()[0] == "processed"
        assert conn.execute("SELECT status FROM raw_items WHERE id = ?", (second_id,)).fetchone()[0] == "new"


def test_event_modeling_prefers_split_model_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "base-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://base.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "base-model")
    monkeypatch.setenv("LLM_API_KEY_EVENT", "event-key")
    monkeypatch.setenv("LLM_BASE_URL_EVENT", "https://event.example.com/v1")
    monkeypatch.setenv("LLM_MODEL_EVENT", "event-model")

    client, model = _get_llm_client()

    assert model == "event-model"
    assert str(client.base_url) == "https://event.example.com/v1/"


def test_model_events_uses_parallel_llm_and_logs_counts(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    raw_item_ids = [
        insert_source_and_raw_item(db_path, f"Item {i}", f"OpenAI released model update {i}.")
        for i in range(3)
    ]

    monkeypatch.setenv("LLM_CONCURRENCY", "3")
    monkeypatch.setattr("event_modeling._get_llm_client", lambda: (object(), "fake-model"))

    def fake_llm_model_event(title, clean_text, client, model):
        time.sleep(0.2)
        return {
            "event_title": title,
            "event_summary": clean_text,
            "event_type": "model_release",
            "entities": [{"name": "OpenAI", "slug": "openai", "type": "company"}],
            "topics": ["llm"],
            "importance_score": 88,
            "seo_value_score": 66,
            "knowledge_value_score": 77,
            "risk_score": 0,
            "confidence": 0.91,
            "claims": [{"claim_text": f"{title} claim", "confidence": 0.8}],
        }

    monkeypatch.setattr("event_modeling.llm_model_event", fake_llm_model_event)

    started = time.perf_counter()
    result = model_events(db_path=db_path, config_dir=CONFIG_DIR, mock=False, limit=3)
    elapsed = time.perf_counter() - started

    assert result == EventModelingResult(modeled_count=3, failed_count=0)
    assert elapsed < 0.5

    with get_conn(db_path) as conn:
        events = conn.execute("SELECT event_title, confidence FROM events ORDER BY raw_item_id").fetchall()
        statuses = conn.execute("SELECT status FROM raw_items ORDER BY id").fetchall()
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='event_modeling'").fetchone()

    assert [row["event_title"] for row in events] == [f"Item {i}" for i in range(3)]
    assert all(row["confidence"] == 0.91 for row in events)
    assert [row["status"] for row in statuses][:3] == ["processed", "processed", "processed"]
    run_output = json.loads(run["output_json"])
    assert run_output["llm_count"] == 3
    assert run_output["fallback_count"] == 0
