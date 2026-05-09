from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
TRACKS_PATH = ROOT / "config" / "timeline_tracks.yaml"


@dataclass(frozen=True)
class TrackReviewResult:
    approved: int = 0
    merged: int = 0
    watch: int = 0
    rejected: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track_review_decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_track_id INTEGER NOT NULL,
          decision TEXT NOT NULL,
          target_track TEXT,
          proposed_title TEXT,
          reason TEXT,
          confidence REAL DEFAULT 0,
          evidence_event_ids_json TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (candidate_track_id) REFERENCES candidate_tracks(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track_review_decisions_candidate ON track_review_decisions(candidate_track_id)")


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def load_tracks(tracks_path: Path = TRACKS_PATH) -> list[dict[str, Any]]:
    """Load only manually curated tracks (for backward compatibility)."""
    if not tracks_path.exists():
        return []
    data = yaml.safe_load(tracks_path.read_text(encoding="utf-8")) or {}
    return [track for track in data.get("tracks", []) if isinstance(track, dict) and track.get("slug")]


def load_tracks_all(tracks_path: Path = TRACKS_PATH) -> list[dict[str, Any]]:
    """Load both manual and generated tracks for overlap comparison."""
    if not tracks_path.exists():
        return []
    data = yaml.safe_load(tracks_path.read_text(encoding="utf-8")) or {}
    manual = [track for track in (data.get("tracks") or []) if isinstance(track, dict) and track.get("slug")]
    generated = [track for track in (data.get("generated_tracks") or []) if isinstance(track, dict) and track.get("slug")]
    return manual + generated


def _track_overlap(candidate_topics: set[str], candidate_entities: set[str], track: dict[str, Any]) -> int:
    match = track.get("match") or {}
    topics = set(match.get("topics") or [])
    entities = set(match.get("entities") or [])
    return len(candidate_topics.intersection(topics)) + len(candidate_entities.intersection(entities))


def decide_candidate(candidate, tracks: list[dict[str, Any]]) -> dict[str, Any]:
    topics = set(json_list(candidate["dominant_topics_json"]))
    entities = {str(entity).lower().replace(" ", "-") for entity in json_list(candidate["dominant_entities_json"])}
    event_ids = json_list(candidate["event_ids_json"])
    event_count = int(candidate["event_count"] or 0)
    confidence = float(candidate["confidence"] or 0)

    best_track = None
    best_overlap = 0
    for track in tracks:
        overlap = _track_overlap(topics, entities, track)
        if overlap > best_overlap:
            best_track = track
            best_overlap = overlap

    if best_track and best_overlap:
        return {
            "decision": "merge",
            "target_track": best_track["slug"],
            "proposed_title": candidate["proposed_title"],
            "reason": f"候选线与既有「{best_track.get('title') or best_track['slug']}」主线重叠，应并入以避免读者地图碎片化。",
            "confidence": min(0.95, max(confidence, 0.8)),
            "evidence_event_ids": event_ids,
        }
    if event_count >= 5 and confidence >= 0.75:
        return {
            "decision": "approved",
            "target_track": None,
            "proposed_title": candidate["proposed_title"],
            "reason": "候选线具备足够事件数量和独立主题结构，可升格为公开追踪线。",
            "confidence": confidence,
            "evidence_event_ids": event_ids,
        }
    if event_count >= 2:
        return {
            "decision": "watch",
            "target_track": None,
            "proposed_title": candidate["proposed_title"],
            "reason": "候选线有一定复现，但公开价值仍需更多事件验证。",
            "confidence": confidence,
            "evidence_event_ids": event_ids,
        }
    return {
        "decision": "rejected",
        "target_track": None,
        "proposed_title": candidate["proposed_title"],
        "reason": "候选线证据不足，暂不进入追踪线体系。",
        "confidence": confidence,
        "evidence_event_ids": event_ids,
    }


def review_candidate_tracks(db_path: Path = DB_PATH, tracks_path: Path = TRACKS_PATH) -> TrackReviewResult:
    tracks = load_tracks_all(Path(tracks_path))
    counts = {"approved": 0, "merged": 0, "watch": 0, "rejected": 0}
    with get_conn(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute("SELECT * FROM candidate_tracks WHERE status = 'proposed' ORDER BY event_count DESC, id").fetchall()
        for row in rows:
            decision = decide_candidate(row, tracks)
            conn.execute(
                """
                INSERT INTO track_review_decisions (
                  candidate_track_id, decision, target_track, proposed_title, reason,
                  confidence, evidence_event_ids_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    decision["decision"],
                    decision["target_track"],
                    decision["proposed_title"],
                    decision["reason"],
                    decision["confidence"],
                    json.dumps(decision["evidence_event_ids"], ensure_ascii=False),
                ),
            )
            status = "merged" if decision["decision"] == "merge" else decision["decision"]
            conn.execute(
                "UPDATE candidate_tracks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, row["id"]),
            )
            if decision["decision"] == "merge":
                counts["merged"] += 1
            else:
                counts[decision["decision"]] += 1
    # Materialize approved tracks into config
    materialized = materialize_approved_tracks(db_path=db_path, tracks_path=tracks_path)
    return TrackReviewResult(**counts)


def materialize_approved_tracks(db_path: Path = DB_PATH, tracks_path: Path = TRACKS_PATH) -> int:
    """Materialize approved candidate tracks into timeline_tracks.yaml.

    Preserves manually curated tracks. Adds generated tracks in a separate section.
    Returns count of materialized tracks.
    """
    tracks_path = Path(tracks_path)
    with get_conn(db_path) as conn:
        approved = conn.execute(
            """
            SELECT trd.*, ct.slug, ct.proposed_title, ct.dominant_topics_json, ct.dominant_entities_json
            FROM track_review_decisions trd
            JOIN candidate_tracks ct ON ct.id = trd.candidate_track_id
            WHERE trd.decision = 'approved'
              AND ct.status NOT IN ('materialized', 'rejected')
            """
        ).fetchall()

    if not approved:
        return 0

    # Load existing tracks config
    existing_data: dict[str, Any] = {}
    if tracks_path.exists():
        existing_data = yaml.safe_load(tracks_path.read_text(encoding="utf-8")) or {}

    manual_tracks = existing_data.get("tracks") or []
    existing_slugs = {t.get("slug") for t in manual_tracks if isinstance(t, dict)}

    # Load existing generated tracks (if any)
    generated_tracks = existing_data.get("generated_tracks") or []
    generated_slugs = {t.get("slug") for t in generated_tracks if isinstance(t, dict)}

    new_generated: list[dict[str, Any]] = []
    materialized_count = 0

    for row in approved:
        slug = row["slug"]
        if slug in existing_slugs or slug in generated_slugs:
            continue

        topics = json_list(row["dominant_topics_json"])
        entities = json_list(row["dominant_entities_json"])
        evidence_ids = json_list(row["evidence_event_ids_json"])

        track: dict[str, Any] = {
            "slug": slug,
            "title": row["proposed_title"] or slug,
            "description": f"\u81ea\u52a8\u751f\u6210\u8ffd\u8e2a\u7ebf\uff0c\u57fa\u4e8e {len(evidence_ids)} \u4e2a\u4e8b\u4ef6\u3002",
            "source": "track_review",
            "candidate_track_id": row["candidate_track_id"],
            "evidence_event_ids": evidence_ids,
            "match": {
                "topics": topics,
                "entities": entities,
            },
        }
        new_generated.append(track)
        generated_slugs.add(slug)
        materialized_count += 1

        # Update candidate status
        with get_conn(db_path) as conn:
            conn.execute(
                "UPDATE candidate_tracks SET status = 'materialized', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["candidate_track_id"],),
            )
            conn.commit()

    if new_generated:
        all_generated = [t for t in generated_tracks if isinstance(t, dict)] + new_generated
        existing_data["generated_tracks"] = all_generated

        # Write back
        output = yaml.safe_dump(existing_data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        tracks_path.write_text(output, encoding="utf-8")

    return materialized_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Review candidate timeline tracks with automatic skill rules.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--tracks", type=Path, default=TRACKS_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = review_candidate_tracks(db_path=args.db, tracks_path=args.tracks)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
