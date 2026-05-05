import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from editorial_decision import DecisionResult, make_decisions
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"
CONFIG_DIR = ROOT / "config"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def insert_event(
    db_path: Path,
    title: str,
    importance: float,
    seo: float,
    knowledge: float,
    risk: float,
    confidence: float,
    entities=None,
    topics=None,
    source_trust_level: int = 5,
    event_type: str = "other",
) -> int:
    entities = entities if entities is not None else []
    topics = topics if topics is not None else []
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO sources (name, type, url, trust_level) VALUES (?, 'rss', ?, ?)",
            (f"Source {title}", f"https://example.com/feed/{title}", source_trust_level),
        )
        source_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO raw_items (source_id, source_url, title, content_hash, status)
            VALUES (?, ?, ?, ?, 'processed')
            """,
            (source_id, f"https://example.com/{title}", title, f"hash-{title}"),
        )
        raw_item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO events (
              raw_item_id, event_title, event_type, entities_json, topics_json,
              claims_json, importance_score, seo_value_score, knowledge_value_score,
              risk_score, confidence, status
            )
            VALUES (?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?, 'modeled')
            """,
            (
                raw_item_id,
                title,
                event_type,
                json.dumps(entities),
                json.dumps(topics),
                importance,
                seo,
                knowledge,
                risk,
                confidence,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_make_decisions_assigns_a_b_c_d_and_review_queue(tmp_path):
    db_path = init_temp_db(tmp_path)
    a_event = insert_event(db_path, "A event", 80, 70, 80, 10, 0.80, topics=["llm"])
    b_event = insert_event(db_path, "B event", 50, 20, 45, 10, 0.70, topics=["ai-agents"])
    c_event = insert_event(db_path, "C event", 20, 10, 10, 10, 0.60, topics=["llm"])
    d_event = insert_event(db_path, "D event", 20, 10, 10, 10, 0.40)

    result = make_decisions(db_path=db_path, config_dir=CONFIG_DIR, limit=10)

    assert result == DecisionResult(decided_count=4, failed_count=0)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT event_id, action, decision_grade, need_review, status FROM decisions ORDER BY event_id"
        ).fetchall()
        reviews = conn.execute("SELECT target_type, target_id, review_type, status FROM review_queue").fetchall()
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='editorial_decision'").fetchone()

    assert [(row["event_id"], row["decision_grade"], row["action"], row["need_review"]) for row in rows] == [
        (a_event, "A", "publish_article", 1),
        (b_event, "B", "daily_brief_only", 0),
        (c_event, "C", "update_assets_only", 0),
        (d_event, "D", "ignore", 0),
    ]
    assert all(row["status"] == "pending" for row in rows)
    assert [(row["target_type"], row["target_id"], row["review_type"], row["status"]) for row in reviews] == [
        ("event", a_event, "a_grade_article", "pending")
    ]
    assert run["status"] == "success"
    assert json.loads(run["output_json"]) == {"decided_count": 4, "failed_count": 0}


def test_make_decisions_sends_high_risk_to_review_queue(tmp_path):
    db_path = init_temp_db(tmp_path)
    event_id = insert_event(db_path, "Risk event", 80, 70, 80, 75, 0.80, topics=["ai-safety"])

    result = make_decisions(db_path=db_path, config_dir=CONFIG_DIR, event_id=event_id)

    assert result == DecisionResult(decided_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        decision = conn.execute("SELECT decision_grade, action, need_review FROM decisions").fetchone()
        review = conn.execute("SELECT target_id, review_type FROM review_queue").fetchone()

    assert decision["decision_grade"] == "D"
    assert decision["action"] == "ignore"
    assert decision["need_review"] == 1
    assert (review["target_id"], review["review_type"]) == (event_id, "high_risk_content")


def test_make_decisions_blocks_high_risk_a_grade_from_weak_source(tmp_path):
    db_path = init_temp_db(tmp_path)
    event_id = insert_event(
        db_path,
        "Policy event from weak source",
        90,
        80,
        85,
        45,
        0.90,
        topics=["ai-policy"],
        source_trust_level=3,
        event_type="policy",
    )

    result = make_decisions(db_path=db_path, config_dir=CONFIG_DIR, event_id=event_id)

    assert result == DecisionResult(decided_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        decision = conn.execute("SELECT decision_grade, action, need_review, reason FROM decisions").fetchone()
        review = conn.execute("SELECT target_id, review_type FROM review_queue").fetchone()

    assert decision["decision_grade"] == "C"
    assert decision["action"] == "review_required"
    assert decision["need_review"] == 1
    assert "source trust" in decision["reason"]
    assert (review["target_id"], review["review_type"]) == (event_id, "source_trust_review")


def test_make_decisions_dry_run_does_not_write(tmp_path):
    db_path = init_temp_db(tmp_path)
    insert_event(db_path, "A event", 80, 70, 80, 10, 0.80, topics=["llm"])

    result = make_decisions(db_path=db_path, config_dir=CONFIG_DIR, dry_run=True)

    assert result == DecisionResult(decided_count=1, failed_count=0)
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
