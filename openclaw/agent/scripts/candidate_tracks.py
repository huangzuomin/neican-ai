from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class CandidateTrackResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_tracks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          slug TEXT NOT NULL UNIQUE,
          proposed_title TEXT NOT NULL,
          summary TEXT,
          dominant_topics_json TEXT,
          dominant_entities_json TEXT,
          event_ids_json TEXT,
          event_count INTEGER DEFAULT 0,
          confidence REAL DEFAULT 0,
          reason TEXT,
          status TEXT NOT NULL DEFAULT 'proposed',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_tracks_status ON candidate_tracks(status)")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "candidate-track"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _slug(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("slug") or slugify(str(item.get("name") or ""))).strip()
    return slugify(str(item))


def _name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("slug") or "").strip()
    return str(item).strip()


def fetch_events(conn) -> list[Any]:
    return conn.execute(
        """
        SELECT
          events.id,
          events.event_title,
          events.entities_json,
          events.topics_json,
          events.importance_score,
          events.confidence,
          decisions.decision_grade
        FROM events
        JOIN decisions ON decisions.event_id = events.id
        WHERE decisions.decision_grade IN ('A', 'B')
          AND events.status = 'modeled'
        ORDER BY events.event_date, events.id
        """
    ).fetchall()


def _candidate_title(topics: list[str]) -> str:
    if not topics:
        return "AI 行业新兴信号"
    if "ai-agents" in topics:
        return "Agent 评测与企业采用信号"
    return " / ".join(topic.replace("-", " ") for topic in topics[:2])


def _bucket_key(topic_slugs: list[str]) -> str:
    priority_topics = ["ai-agents", "llm", "ai-policy", "ai-safety", "mcp", "multimodal"]
    for topic in priority_topics:
        if topic in topic_slugs:
            return topic
    return topic_slugs[0]


def discover_candidate_tracks(db_path: Path = DB_PATH, min_events: int = 3) -> CandidateTrackResult:
    created = 0
    updated = 0
    skipped = 0
    with get_conn(db_path) as conn:
        ensure_schema(conn)
        buckets: dict[str, list[Any]] = defaultdict(list)
        for row in fetch_events(conn):
            topic_slugs = sorted({_slug(topic) for topic in json_list(row["topics_json"]) if _slug(topic)})
            if not topic_slugs:
                skipped += 1
                continue
            key = _bucket_key(topic_slugs)
            buckets[key].append(row)

        for key, rows in buckets.items():
            if len(rows) < min_events:
                skipped += len(rows)
                continue
            topics = key.split("+")
            entity_counter: Counter[str] = Counter()
            for row in rows:
                for entity in json_list(row["entities_json"]):
                    name = _name(entity)
                    if name:
                        entity_counter[name] += 1
            event_ids = [int(row["id"]) for row in rows]
            confidence = min(0.95, 0.45 + len(rows) * 0.1 + min(len(entity_counter), 3) * 0.05)
            title = _candidate_title(topics)
            slug = slugify(title)
            data = {
                "slug": slug,
                "proposed_title": title,
                "summary": f"候选线由 {len(rows)} 个 A/B 级事件自动聚合生成。",
                "dominant_topics_json": json.dumps(topics, ensure_ascii=False),
                "dominant_entities_json": json.dumps([name for name, _count in entity_counter.most_common(8)], ensure_ascii=False),
                "event_ids_json": json.dumps(event_ids, ensure_ascii=False),
                "event_count": len(rows),
                "confidence": confidence,
                "reason": f"过去事件集中出现在 {'、'.join(topics)} 主题下。",
                "status": "proposed",
            }
            existing = conn.execute("SELECT id FROM candidate_tracks WHERE slug = ?", (slug,)).fetchone()
            cols = list(data)
            conn.execute(
                f"""
                INSERT INTO candidate_tracks ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})
                ON CONFLICT(slug) DO UPDATE SET {', '.join(f'{col}=excluded.{col}' for col in cols if col != 'slug')}, updated_at=CURRENT_TIMESTAMP
                """,
                tuple(data[col] for col in cols),
            )
            if existing:
                updated += 1
            else:
                created += 1
        return CandidateTrackResult(created=created, updated=updated, skipped=skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover candidate timeline tracks from modeled events.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--min-events", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = discover_candidate_tracks(db_path=args.db, min_events=args.min_events)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
