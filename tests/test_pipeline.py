import json
import sys
from pathlib import Path

import feedparser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline import PipelineResult, run_pipeline
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"
FIXTURE_RSS = ROOT / "tests" / "fixtures" / "sample_rss.xml"
ORIGINAL_PARSE = feedparser.parse
CONFIG_DIR = ROOT / "config"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_sources(tmp_path: Path) -> Path:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
sources:
  - name: "Fixture Feed"
    type: rss
    url: "https://example.com/feed.xml"
    enabled: true
    trust_level: 5
    language: en
    fetch_interval_minutes: 120
""".lstrip(),
        encoding="utf-8",
    )
    return sources_path


def fake_parse(_url):
    return ORIGINAL_PARSE(FIXTURE_RSS.read_text(encoding="utf-8"))


def test_run_pipeline_mock_end_to_end(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    sources_path = write_sources(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory-wiki"
    monkeypatch.setattr("fetch_sources.feedparser.parse", fake_parse)

    result = run_pipeline(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        sources_path=sources_path,
        config_dir=CONFIG_DIR,
        date="2026-05-01",
        limit=2,
        mock=True,
    )

    assert isinstance(result, PipelineResult)
    assert result.fetch["inserted_count"] == 2
    assert result.extract["processed_count"] == 2
    assert result.model["modeled_count"] == 2
    assert result.decide["decided_count"] == 2
    assert result.export["daily_briefs"] == 1
    assert result.export["insights"] == 0
    assert (site_dir / "content" / "briefs" / "daily" / "2026-05-01.md").exists()
    assert (site_dir / "content" / "timeline" / "_index.md").exists()
    assert (site_dir / "content" / "entities" / "_index.md").exists()
    assert not (site_dir / "content" / "insights").exists()


def test_run_pipeline_passes_flags_and_order(monkeypatch, tmp_path):
    calls: list[tuple[str, dict]] = []

    class Result:
        def __init__(self, **kwargs):
            self._data = kwargs

        def to_dict(self):
            return self._data

    def fake_fetch_sources(**kwargs):
        calls.append(("fetch", kwargs))
        return Result(inserted_count=1, skipped_duplicate_count=0, failed_count=0)

    def fake_extract_content(**kwargs):
        calls.append(("extract", kwargs))
        return Result(processed_count=1, failed_count=0)

    def fake_model_events(**kwargs):
        calls.append(("model", kwargs))
        return Result(modeled_count=1, failed_count=0)

    def fake_make_decisions(**kwargs):
        calls.append(("decide", kwargs))
        return Result(decided_count=1, failed_count=0)

    def fake_export_hugo(**kwargs):
        calls.append(("export", kwargs))
        return Result(daily_briefs=1, insights=0, skipped_approved=0, failed_count=0)

    def fake_run_timeline_product(**kwargs):
        calls.append(("timeline", kwargs))
        return Result(generated=1, exported_events=1, exported_years=1, exported_tracks=1, skipped=0)

    def fake_run_entity_product(**kwargs):
        calls.append(("entities", kwargs))
        return Result(generated=1, exported=1, source="db")

    def fake_run_event_product(**kwargs):
        calls.append(("events", kwargs))
        return Result(generated=1, exported=1, source="timeline_nodes")

    monkeypatch.setattr("pipeline.fetch_sources", fake_fetch_sources)
    monkeypatch.setattr("pipeline.extract_content", fake_extract_content)
    monkeypatch.setattr("pipeline.model_events", fake_model_events)
    monkeypatch.setattr("pipeline.make_decisions", fake_make_decisions)
    monkeypatch.setattr("pipeline.export_hugo", fake_export_hugo)
    monkeypatch.setattr("pipeline.run_timeline_product", fake_run_timeline_product)
    monkeypatch.setattr("pipeline.run_entity_product", fake_run_entity_product)
    monkeypatch.setattr("pipeline.run_event_product", fake_run_event_product)
    monkeypatch.setattr("pipeline.update_knowledge_assets", lambda **kwargs: Result(entities_created=0, entities_updated=0, topics_created=0, topics_updated=0, timeline_entries=0, claims_written=0))

    result = run_pipeline(
        db_path=tmp_path / "db.sqlite",
        site_dir=tmp_path / "site",
        memory_dir=tmp_path / "memory",
        sources_path=tmp_path / "sources.yaml",
        config_dir=tmp_path / "config",
        date="2026-06-01",
        limit=5,
        source_name="OpenAI Blog",
        full_text=True,
        mock=True,
        dry_run=True,
    )

    assert result.to_dict() == {
        "date": "2026-06-01",
        "fetch": {"inserted_count": 1, "skipped_duplicate_count": 0, "failed_count": 0},
        "extract": {"processed_count": 1, "failed_count": 0},
        "model": {"modeled_count": 1, "failed_count": 0},
        "decide": {"decided_count": 1, "failed_count": 0},
        "assets": {"entities_created": 0, "entities_updated": 0, "topics_created": 0, "topics_updated": 0, "timeline_entries": 0, "claims_written": 0},
        "export": {"daily_briefs": 1, "insights": 0, "skipped_approved": 0, "failed_count": 0},
        "timeline": {"generated": 0, "exported_events": 0, "exported_years": 0, "exported_tracks": 0, "skipped": 0},
        "entities": {"generated": 0, "exported": 0, "source": "skipped"},
        "events": {"generated": 0, "exported": 0, "source": "skipped"},
    }
    assert [name for name, _ in calls] == ["fetch", "extract", "model", "decide", "export"]
    assert calls[0][1]["source_name"] == "OpenAI Blog"
    assert calls[0][1]["full_text"] is True
    assert calls[0][1]["dry_run"] is True
    assert calls[2][1]["mock"] is True
    assert calls[3][1]["dry_run"] is True
    assert calls[4][1]["date"] == "2026-06-01"
    assert calls[4][1]["mock"] is True


def test_pipeline_main_json_shape(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "pipeline.run_pipeline",
        lambda **kwargs: PipelineResult(
            date="2026-07-01",
            fetch={"inserted_count": 1, "skipped_duplicate_count": 0, "failed_count": 0},
            extract={"processed_count": 1, "failed_count": 0},
            model={"modeled_count": 1, "failed_count": 0},
            decide={"decided_count": 1, "failed_count": 0},
            assets={"entities_created": 0, "entities_updated": 0, "topics_created": 0, "topics_updated": 0, "timeline_entries": 0, "claims_written": 0},
            export={"daily_briefs": 1, "insights": 1, "skipped_approved": 0, "failed_count": 0},
            timeline={"generated": 1, "exported_events": 1, "exported_years": 1, "exported_tracks": 1, "skipped": 0},
            entities={"generated": 1, "exported": 1, "source": "db"},
            events={"generated": 1, "exported": 1, "source": "timeline_nodes"},
        ),
    )

    from pipeline import main

    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--date", "2026-07-01", "--mock"])
    main()
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["date"] == "2026-07-01"
    assert parsed["export"]["insights"] == 1
