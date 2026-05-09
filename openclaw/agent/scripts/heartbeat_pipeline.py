from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from info_fetch_requests import pending_route_message
from pipeline import run_pipeline
from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class HeartbeatStatus:
    should_run: bool
    reason: str
    recent_fetch_age_minutes: int | None
    pending_raw_items: int
    pending_events: int
    pending_decisions: int
    pending_info_fetch_requests: int
    info_fetch_route_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeartbeatResult:
    ran: bool
    status: dict[str, Any]
    pipeline: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_sqlite_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def inspect_status(db_path: Path = DB_PATH, min_fetch_interval_minutes: int = 120) -> HeartbeatStatus:
    db_path = Path(db_path)
    if not db_path.exists():
        return HeartbeatStatus(True, "db_missing", None, 0, 0, 0, 0, None)

    with get_conn(db_path) as conn:
        pending_raw_items = conn.execute(
            "SELECT COUNT(*) FROM raw_items WHERE status = 'new'"
        ).fetchone()[0]
        pending_events = conn.execute(
            """
            SELECT COUNT(*)
            FROM events
            LEFT JOIN decisions ON decisions.event_id = events.id
            WHERE events.status = 'modeled' AND decisions.id IS NULL
            """
        ).fetchone()[0]
        pending_decisions = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE status = 'pending'"
        ).fetchone()[0]
        pending_info_fetch_requests = conn.execute(
            "SELECT COUNT(*) FROM info_fetch_requests WHERE status = 'pending'"
        ).fetchone()[0]
        info_fetch_route_message = pending_route_message(conn)
        last_fetch_row = conn.execute(
            """
            SELECT COALESCE(finished_at, started_at) AS last_run
            FROM runs
            WHERE run_type = 'fetch_sources'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    last_fetch = _parse_sqlite_timestamp(last_fetch_row["last_run"] if last_fetch_row else None)
    recent_fetch_age_minutes = None
    if last_fetch:
        recent_fetch_age_minutes = max(0, int((datetime.now(timezone.utc) - last_fetch).total_seconds() // 60))

    if pending_raw_items > 0:
        return HeartbeatStatus(True, "pending_raw_items", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    if pending_events > 0:
        return HeartbeatStatus(True, "pending_events", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    if pending_decisions > 0:
        return HeartbeatStatus(True, "pending_decisions", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    if pending_info_fetch_requests > 0:
        return HeartbeatStatus(True, "pending_info_fetch_requests", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    if recent_fetch_age_minutes is None:
        return HeartbeatStatus(True, "no_previous_fetch", None, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    if recent_fetch_age_minutes >= min_fetch_interval_minutes:
        return HeartbeatStatus(True, "fetch_interval_elapsed", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)
    return HeartbeatStatus(False, "up_to_date", recent_fetch_age_minutes, pending_raw_items, pending_events, pending_decisions, pending_info_fetch_requests, info_fetch_route_message)


def heartbeat_run(
    db_path: Path = DB_PATH,
    date: str | None = None,
    limit: int | None = None,
    source_name: str | None = None,
    full_text: bool = False,
    mock: bool = False,
    dry_run: bool = False,
    min_fetch_interval_minutes: int = 120,
    force: bool = False,
) -> HeartbeatResult:
    status = inspect_status(db_path=db_path, min_fetch_interval_minutes=min_fetch_interval_minutes)
    if not force and not status.should_run:
        return HeartbeatResult(False, status.to_dict(), None)

    pipeline_result = run_pipeline(
        db_path=db_path,
        date=date,
        limit=limit,
        source_name=source_name,
        full_text=full_text,
        mock=mock,
        dry_run=dry_run,
    )
    return HeartbeatResult(True, status.to_dict(), pipeline_result.to_dict())


def main() -> None:
    parser = argparse.ArgumentParser(description="Heartbeat-triggered pipeline runner.")
    parser.add_argument("--date", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", dest="source_name", default=None)
    parser.add_argument("--full-text", action="store_true")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--min-fetch-interval", type=int, default=120, dest="min_fetch_interval_minutes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = heartbeat_run(
        date=args.date,
        limit=args.limit,
        source_name=args.source_name,
        full_text=args.full_text,
        mock=args.mock,
        dry_run=args.dry_run,
        min_fetch_interval_minutes=args.min_fetch_interval_minutes,
        force=args.force,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"[HEARTBEAT] ran={payload['ran']} reason={payload['status']['reason']}")
    if payload["status"].get("info_fetch_route_message"):
        print(payload["status"]["info_fetch_route_message"])
    if payload["pipeline"]:
        print(json.dumps(payload["pipeline"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
