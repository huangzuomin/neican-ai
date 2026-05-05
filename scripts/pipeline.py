from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from editorial_decision import make_decisions
from event_modeling import model_events
from event_store import merge_modeled_events
from extract_content import extract_content
from fetch_sources import fetch_sources
from knowledge_assets import update_knowledge_assets
from candidate_tracks import discover_candidate_tracks
from track_review import review_candidate_tracks
from timeline_product import run as run_timeline_product
from entity_product import run as run_entity_product
from event_product import run as run_event_product
from entity_registry import sync_entity_registry, normalize_events_entities
from topic_registry import sync_topic_registry
from topic_product import run as run_topic_product
from daily_brief_product import generate_daily_brief
from insight_candidates import detect_insight_candidates
from insight_product import run as run_insight_product


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
    event_store: dict[str, Any]
    decide: dict[str, Any]
    assets: dict[str, Any]
    candidate_tracks: dict[str, Any]
    track_review: dict[str, Any]
    export: dict[str, Any]
    timeline: dict[str, Any]
    entities: dict[str, Any]
    events: dict[str, Any]
    entity_registry: dict[str, Any]
    topic_registry: dict[str, Any]
    topic_product: dict[str, Any]
    daily_brief: dict[str, Any]
    insight_candidates: dict[str, Any]
    insight_product: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _empty(**defaults: int) -> dict[str, Any]:
    return dict(defaults)


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

    # 1. Fetch
    fetch_result = fetch_sources(
        db_path=db_path, sources_path=sources_path, limit=limit,
        source_name=source_name, full_text=full_text, dry_run=dry_run,
    )
    # 2. Extract
    extract_result = extract_content(db_path=db_path, batch=limit, dry_run=dry_run)
    # 3. Model events
    model_result = model_events(db_path=db_path, config_dir=config_dir, mock=mock, limit=limit)
    # 4. Entity registry sync + normalize events BEFORE merge
    entity_registry_result = None if dry_run else sync_entity_registry(db_path=db_path)
    entity_registry_dict = entity_registry_result.to_dict() if entity_registry_result else _empty(synced=0, updated=0, new=0)
    if not dry_run:
        normalize_events_entities(db_path=db_path)
    # 5. Event store (merge) — now uses canonical entity slugs
    event_store_result = None if dry_run else merge_modeled_events(db_path=db_path, config_dir=config_dir)
    event_store_dict = event_store_result.to_dict() if event_store_result else _empty(canonical_events=0, merged_events=0, event_sources=0)
    # 6. Topic registry sync
    topic_registry_result = None if dry_run else sync_topic_registry(db_path=db_path)
    topic_registry_dict = topic_registry_result.to_dict() if topic_registry_result else _empty(synced=0, updated=0, new=0)
    # 7. Editorial decisions
    decide_result = make_decisions(db_path=db_path, config_dir=config_dir, limit=limit, dry_run=dry_run)
    # 8. Knowledge assets
    assets_result = update_knowledge_assets(db_path=db_path, memory_dir=memory_dir) if not dry_run else None
    assets_dict = assets_result.to_dict() if assets_result else _empty(entities_created=0, entities_updated=0, topics_created=0, topics_updated=0, timeline_entries=0, claims_written=0)
    # 9. Candidate tracks
    candidate_result = None if dry_run else discover_candidate_tracks(db_path=db_path)
    candidate_dict = candidate_result.to_dict() if candidate_result else _empty(created=0, updated=0, skipped=0)
    # 10. Track review
    review_result = None if dry_run else review_candidate_tracks(db_path=db_path)
    review_dict = review_result.to_dict() if review_result else _empty(approved=0, merged=0, watch=0, rejected=0)
    # 11. Legacy Hugo export skipped; daily/insight now handled by dedicated products below
    export_dict = {"daily_briefs": 0, "insights": 0, "skipped_approved": 0, "failed_count": 0}
    # 12. Timeline product
    timeline_result = None if dry_run else run_timeline_product(db_path=db_path, site_dir=site_dir)
    timeline_dict = timeline_result.to_dict() if timeline_result else _empty(generated=0, exported_events=0, exported_years=0, exported_tracks=0, skipped=0)
    # 13. Entity product
    entities_result = None if dry_run else run_entity_product(db_path=db_path, site_dir=site_dir, memory_dir=memory_dir)
    entities_dict = entities_result.to_dict() if entities_result else _empty(generated=0, exported=0, source="skipped")
    # 14. Event product
    events_result = None if dry_run else run_event_product(db_path=db_path, site_dir=site_dir)
    events_dict = events_result.to_dict() if events_result else _empty(generated=0, exported=0, source="skipped")
    # 15. Topic product
    topic_product_result = None if dry_run else run_topic_product(db_path=db_path, site_dir=site_dir)
    topic_product_dict = topic_product_result.to_dict() if topic_product_result else _empty(generated=0, exported=0)
    # 16. Track-aware daily brief
    daily_brief_result = None if dry_run else generate_daily_brief(db_path=db_path, site_dir=site_dir, date=run_date)
    daily_brief_dict = daily_brief_result.to_dict() if daily_brief_result else _empty(date="", events_count=0, tracks_count=0, exported=False)
    # 17. Insight candidates
    insight_cand_result = None if dry_run else detect_insight_candidates(db_path=db_path, run_date=run_date)
    insight_cand_dict = insight_cand_result.to_dict() if insight_cand_result else _empty(proposed=0, skipped=0)
    # 18. Insight product
    insight_prod_result = None if dry_run else run_insight_product(db_path=db_path, site_dir=site_dir)
    insight_prod_dict = insight_prod_result.to_dict() if insight_prod_result else _empty(generated=0, exported=0)

    return PipelineResult(
        date=run_date,
        fetch=fetch_result.to_dict(),
        extract=extract_result.to_dict(),
        model=model_result.to_dict(),
        event_store=event_store_dict,
        decide=decide_result.to_dict(),
        assets=assets_dict,
        candidate_tracks=candidate_dict,
        track_review=review_dict,
        export=export_dict,
        timeline=timeline_dict,
        entities=entities_dict,
        events=events_dict,
        entity_registry=entity_registry_dict,
        topic_registry=topic_registry_dict,
        topic_product=topic_product_dict,
        daily_brief=daily_brief_dict,
        insight_candidates=insight_cand_dict,
        insight_product=insight_prod_dict,
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
        date=args.date, limit=args.limit, source_name=args.source_name,
        full_text=args.full_text, mock=args.mock, dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
