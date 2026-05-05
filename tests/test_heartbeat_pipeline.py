import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from heartbeat_pipeline import HeartbeatResult, heartbeat_run, inspect_status
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def test_inspect_status_triggers_when_db_missing(tmp_path):
    db_path = tmp_path / "missing.sqlite"
    status = inspect_status(db_path=db_path)
    assert status.should_run is True
    assert status.reason == "db_missing"


def test_inspect_status_skips_when_recent_and_clean(tmp_path):
    db_path = init_temp_db(tmp_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_type, status, started_at, finished_at) VALUES ('fetch_sources', 'success', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    status = inspect_status(db_path=db_path, min_fetch_interval_minutes=120)
    assert status.should_run is False
    assert status.reason == "up_to_date"


def test_inspect_status_triggers_on_pending_work(tmp_path):
    db_path = init_temp_db(tmp_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO raw_items (source_url, title, content_hash, status) VALUES ('https://example.com/a', 'A', 'hash-a', 'new')"
        )
    status = inspect_status(db_path=db_path)
    assert status.should_run is True
    assert status.reason == "pending_raw_items"
    assert status.pending_raw_items == 1


def test_heartbeat_run_respects_skip_and_force(monkeypatch, tmp_path):
    db_path = init_temp_db(tmp_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_type, status, started_at, finished_at) VALUES ('fetch_sources', 'success', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )

    called = []

    class FakePipelineResult:
        def to_dict(self):
            return {"date": "2026-05-01"}

    monkeypatch.setattr("heartbeat_pipeline.run_pipeline", lambda **kwargs: called.append(kwargs) or FakePipelineResult())

    skipped = heartbeat_run(db_path=db_path)
    forced = heartbeat_run(db_path=db_path, force=True, dry_run=True)

    assert skipped == HeartbeatResult(False, skipped.status, None)
    assert forced.ran is True
    assert forced.pipeline == {"date": "2026-05-01"}
    assert called[0]["dry_run"] is True


def test_heartbeat_main_json_path(monkeypatch, capsys):
    monkeypatch.setattr(
        "heartbeat_pipeline.heartbeat_run",
        lambda **kwargs: HeartbeatResult(
            True,
            {"should_run": True, "reason": "pending_events", "recent_fetch_age_minutes": 180, "pending_raw_items": 0, "pending_events": 2, "pending_decisions": 0},
            {"date": "2026-05-01"},
        ),
    )
    from heartbeat_pipeline import main

    monkeypatch.setattr(sys, "argv", ["heartbeat_pipeline.py", "--json"])
    main()
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["ran"] is True
    assert parsed["status"]["reason"] == "pending_events"
