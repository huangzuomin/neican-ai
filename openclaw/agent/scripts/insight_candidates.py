from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class InsightCandidateResult:
    proposed: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "insight"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS insight_candidates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          track_slug TEXT NOT NULL,
          proposed_title TEXT NOT NULL,
          thesis TEXT,
          evidence_event_ids_json TEXT,
          entity_slugs_json TEXT,
          topic_slugs_json TEXT,
          confidence REAL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'proposed',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def detect_insight_candidates(
    db_path: Path = DB_PATH, min_a_events: int = 3, min_ab_events: int = 6,
    lookback_days: int = 30, run_date: str | None = None,
) -> InsightCandidateResult:
    with get_conn(db_path) as conn:
        ensure_schema(conn)
        if run_date:
            run_dt = datetime.strptime(run_date, "%Y-%m-%d")
            cutoff = (run_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            upper = run_date
        else:
            run_dt = datetime.now()
            cutoff = (run_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            upper = run_dt.strftime("%Y-%m-%d")
        nodes = conn.execute(
            "SELECT event_id, date, grade, title, entities_json, topics_json, tracks_json "
            "FROM timeline_nodes WHERE status='public' AND date >= ? AND date <= ? AND tracks_json IS NOT NULL AND tracks_json != '[]' "
            "ORDER BY date DESC", (cutoff, upper),
        ).fetchall()

        track_data: dict[str, dict[str, Any]] = defaultdict(lambda: {"a_events": [], "ab_events": [], "entities": Counter(), "entity_names": {}, "topics": Counter(), "event_ids": set()})
        for node in nodes:
            tracks = json_list(node["tracks_json"])
            grade = node["grade"]
            entities = json_list(node["entities_json"])
            topics = json_list(node["topics_json"])
            for ts in tracks:
                td = track_data[ts]
                td["event_ids"].add(int(node["event_id"]))
                if grade == "A":
                    td["a_events"].append(node)
                    td["ab_events"].append(node)
                elif grade == "B":
                    td["ab_events"].append(node)
                for ent in entities:
                    if isinstance(ent, dict):
                        s = ent.get("slug") or slugify(str(ent.get("name") or ""))
                        n = str(ent.get("name") or s)
                        if s:
                            td["entities"][s] += 1
                            td["entity_names"][s] = n
                for topic in topics:
                    t = str(topic) if isinstance(topic, str) else (topic.get("slug") or "") if isinstance(topic, dict) else ""
                    if t:
                        td["topics"][t] += 1

        # Check for approved/merged/materialized tracks
        approved_tracks: set[str] = set()
        for row in conn.execute("SELECT target_track FROM track_review_decisions WHERE decision IN ('approved', 'merge')").fetchall():
            if row["target_track"]:
                approved_tracks.add(row["target_track"])
        for row in conn.execute("SELECT slug FROM candidate_tracks WHERE status = 'materialized'").fetchall():
            approved_tracks.add(row["slug"])

        proposed = skipped = 0
        for track_slug, td in track_data.items():
            a_count = len(td["a_events"])
            ab_count = len(td["ab_events"])
            is_candidate = (a_count >= min_a_events) or (ab_count >= min_ab_events and track_slug in approved_tracks)
            if not is_candidate:
                skipped += 1
                continue
            event_ids = sorted(td["event_ids"])
            event_ids_json = json.dumps(event_ids, ensure_ascii=False)
            if conn.execute("SELECT id FROM insight_candidates WHERE track_slug=? AND evidence_event_ids_json=?", (track_slug, event_ids_json)).fetchone():
                skipped += 1
                continue
            entity_slugs = [s for s, _ in td["entities"].most_common(8)]
            topic_slugs = [s for s, _ in td["topics"].most_common(5)]
            # Build a descriptive title from top entities and topics
            top_entities = [td["entity_names"].get(s, s) for s, _ in td["entities"].most_common(3)]
            top_topics = [s for s, _ in td["topics"].most_common(2)]
            event_titles = [n["title"] for n in td["a_events"][:3]]
            if top_entities and top_topics:
                proposed_title = f"{'、'.join(top_entities)} 在 {'、'.join(top_topics)} 方向的累积变化"
            elif top_entities:
                proposed_title = f"{'、'.join(top_entities)} 的近期动态累积"
            else:
                proposed_title = f"「{track_slug}」追踪线累积洞察"
            thesis = f"在 {lookback_days} 天内，「{track_slug}」追踪线积累了 {a_count} 个 A 级事件和 {ab_count} 个 A/B 级事件，涉及 {len(entity_slugs)} 个核心实体和 {len(topic_slugs)} 个主题。\n\n关键事件包括：{'；'.join(event_titles[:3])}。"
            confidence = min(0.95, 0.5 + a_count * 0.1 + min(len(entity_slugs), 3) * 0.05)
            conn.execute(
                "INSERT INTO insight_candidates (track_slug, proposed_title, thesis, evidence_event_ids_json, entity_slugs_json, topic_slugs_json, confidence, status) "
                "VALUES (?,?,?,?,?,?,?,'proposed')",
                (track_slug, proposed_title, thesis, event_ids_json, json.dumps(entity_slugs, ensure_ascii=False),
                 json.dumps(topic_slugs, ensure_ascii=False), confidence),
            )
            proposed += 1
        conn.commit()
        result = InsightCandidateResult(proposed=proposed, skipped=skipped)
        conn.execute(
            "INSERT INTO runs (run_type, status, output_json, finished_at) VALUES ('insight_candidates', 'success', ?, CURRENT_TIMESTAMP)",
            (json.dumps(result.to_dict(), ensure_ascii=False),),
        )
        conn.commit()
        return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    r = detect_insight_candidates(db_path=args.db)
    print(f"[OK] insight_candidates proposed={r.proposed} skipped={r.skipped}")


if __name__ == "__main__":
    main()
