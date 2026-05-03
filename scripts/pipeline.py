from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from editorial_decision import make_decisions
from event_modeling import model_events
from export_hugo import export_hugo
from extract_content import extract_content
from fetch_sources import fetch_sources
from knowledge_assets import update_knowledge_assets
from candidate_tracks import discover_candidate_tracks
from track_review import review_candidate_tracks
from timeline_product import run as run_timeline_product
from entity_product import run as run_entity_product
from event_product import run as run_event_product


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
MEMORY_DIR = ROOT / "memory-wiki"
SOURCES_PATH = ROOT / "config" / "sources.yaml"
CONFIG_DIR = ROOT / "config"


@dataclass(frozen=True)
class PipelineResult:
    date: str
    fetch: dict[str, Any]
    extract: dict[str, Any]
    model: dict[str, Any]
    decide: dict[str, Any]
    assets: dict[str, Any]
    candidate_tracks: dict[str, Any]
    track_review: dict[str, Any]
    export: dict[str, Any]
    timeline: dict[str, Any]
    entities: dict[str, Any]
    events: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def run_pipeline(
    db_path: Path = DB_PATH,
    site_dir: Path = SITE_DIR,
    memory_dir: Path = MEMORY_DIR,
    sources_path: Path = SOURCES_PATH,
    config_dir: Path = CONFIG_DIR,
    date: str | None = None,
    limit: int | None = None,
    source_name: str | None = None,
    full_text: bool = False,
    mock: bool = False,
    dry_run: bool = False,
) -> PipelineResult:
    run_date = date or default_date()

    fetch_result = fetch_sources(
        db_path=db_path,
        sources_path=sources_path,
        limit=limit,
        source_name=source_name,
        full_text=full_text,
        dry_run=dry_run,
    )
    extract_result = extract_content(
        db_path=db_path,
        batch=limit,
        dry_run=dry_run,
    )
    model_result = model_events(
        db_path=db_path,
        config_dir=config_dir,
        mock=mock,
        limit=limit,
    )
    decide_result = make_decisions(
        db_path=db_path,
        config_dir=config_dir,
        limit=limit,
        dry_run=dry_run,
    )
    assets_result = update_knowledge_assets(
        db_path=db_path,
        memory_dir=memory_dir,
    ) if not dry_run else update_knowledge_assets.__wrapped__() if hasattr(update_knowledge_assets, '__wrapped__') else None
    assets_dict = assets_result.to_dict() if assets_result else {"entities_created": 0, "entities_updated": 0, "topics_created": 0, "topics_updated": 0, "timeline_entries": 0, "claims_written": 0}
    candidate_result = None if dry_run else discover_candidate_tracks(db_path=db_path)
    candidate_dict = candidate_result.to_dict() if candidate_result else {"created": 0, "updated": 0, "skipped": 0}
    review_result = None if dry_run else review_candidate_tracks(db_path=db_path)
    review_dict = review_result.to_dict() if review_result else {"approved": 0, "merged": 0, "watch": 0, "rejected": 0}
    export_result = export_hugo(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
        date=run_date,
        mock=mock,
        dry_run=dry_run,
    )
    timeline_result = None if dry_run else run_timeline_product(
        db_path=db_path,
        site_dir=site_dir,
    )
    timeline_dict = timeline_result.to_dict() if timeline_result else {"generated": 0, "exported_events": 0, "exported_years": 0, "exported_tracks": 0, "skipped": 0}
    entities_result = None if dry_run else run_entity_product(
        db_path=db_path,
        site_dir=site_dir,
        memory_dir=memory_dir,
    )
    entities_dict = entities_result.to_dict() if entities_result else {"generated": 0, "exported": 0, "source": "skipped"}
    events_result = None if dry_run else run_event_product(
        db_path=db_path,
        site_dir=site_dir,
    )
    events_dict = events_result.to_dict() if events_result else {"generated": 0, "exported": 0, "source": "skipped"}

    return PipelineResult(
        date=run_date,
        fetch=fetch_result.to_dict(),
        extract=extract_result.to_dict(),
        model=model_result.to_dict(),
        decide=decide_result.to_dict(),
        assets=assets_dict,
        candidate_tracks=candidate_dict,
        track_review=review_dict,
        export=export_result.to_dict(),
        timeline=timeline_dict,
        entities=entities_dict,
        events=events_dict,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run neican.ai end-to-end pipeline.")
    parser.add_argument("--date", default=None, help="Export date, defaults to today (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Max items per stage")
    parser.add_argument("--source", dest="source_name", default=None, help="Only fetch one source by name")
    parser.add_argument("--full-text", action="store_true", help="Fetch full article HTML during source collection")
    parser.add_argument("--mock", action="store_true", help="Use fallback/mock content generation + event modeling")
    parser.add_argument("--dry-run", action="store_true", help="Avoid writes where supported")
    args = parser.parse_args()

    result = run_pipeline(
        date=args.date,
        limit=args.limit,
        source_name=args.source_name,
        full_text=args.full_text,
        mock=args.mock,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
