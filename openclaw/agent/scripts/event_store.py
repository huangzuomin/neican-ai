from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class EventStoreResult:
    canonical_events: int = 0
    merged_events: int = 0
    event_sources: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_sources (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id INTEGER NOT NULL,
          raw_item_id INTEGER NOT NULL UNIQUE,
          source_url TEXT,
          source_title TEXT,
          source_name TEXT,
          published_at TEXT,
          confidence REAL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (event_id) REFERENCES events(id),
          FOREIGN KEY (raw_item_id) REFERENCES raw_items(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_sources_event ON event_sources(event_id)"
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_title_words(title: str, alias_map: dict[str, str] | None = None) -> set[str]:
    """Extract significant content words from title, applying entity alias normalization.

    For CJK text, each character is treated as a word (bigram approach).
    For Latin text, words are split by whitespace after stripping punctuation.
    """
    t = title.lower().strip()
    # Check if title contains CJK characters
    has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', t))

    if has_cjk:
        # CJK: remove punctuation and whitespace, treat each char as a token
        t_clean = re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbfa-z0-9]', '', t)
        words = list(t_clean)
        # Apply alias map: try matching multi-char aliases first
        if alias_map:
            title_str = ''.join(words)
            sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)
            for alias in sorted_aliases:
                if len(alias) > 1 and alias in title_str:
                    title_str = title_str.replace(alias, alias_map[alias])
            words = list(title_str)
        return set(words)
    else:
        # Latin: split by whitespace, remove filler words
        t_clean = re.sub(r'[^a-z0-9\s]', ' ', t)
        t_clean = re.sub(r'\s+', ' ', t_clean).strip()
        filler = {
            "the", "a", "an", "with", "and", "or", "of", "in", "on", "for", "to",
            "is", "has", "its", "new", "from", "by", "that", "this", "are", "was",
            "major", "significant", "important", "latest", "just", "now", "all",
            "updates", "update", "announces", "announced", "releases", "released",
            "launches", "launched", "says", "will", "can", "could", "may",
        }
        words = [w for w in t_clean.split() if w not in filler and len(w) > 1]

        if alias_map:
            # Try multi-word alias matching first (longer aliases first)
            sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)
            title_for_alias = " ".join(words)
            for alias in sorted_aliases:
                if " " in alias and alias in title_for_alias:
                    title_for_alias = title_for_alias.replace(alias, alias_map[alias])
            words = title_for_alias.split()
            # Single-word alias replacement
            words = [alias_map.get(w, w) for w in words]

        return set(words)


def _first_entity_slug(entities_json: str | None) -> str:
    entities = json_list(entities_json)
    for ent in entities:
        if isinstance(ent, dict):
            slug = str(ent.get("slug") or slugify(str(ent.get("name") or "")))
            if slug:
                return slug
    return ""


def _merge_key(title: str, event_date: str | None, entities_json: str | None) -> str:
    """Build merge key for grouping.

    Uses date + first entity slug as the primary grouping key.
    Title similarity is checked separately via _titles_should_merge().
    """
    date_prefix = (event_date or "")[:10]
    entity_slug = _first_entity_slug(entities_json)
    return f"{date_prefix}|{entity_slug}"


def _titles_should_merge(title_a: str, title_b: str, alias_map: dict[str, str] | None = None, threshold: float = 0.6) -> bool:
    """Check if two titles are similar enough to be about the same event.

    Uses Jaccard similarity on content words/tokens, with entity alias normalization.
    For CJK text, uses character-level Jaccard with a lower threshold (0.5)
    since CJK characters carry more meaning individually.
    """
    has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', (title_a + title_b)))
    actual_threshold = 0.5 if has_cjk else threshold

    words_a = _normalize_title_words(title_a, alias_map)
    words_b = _normalize_title_words(title_b, alias_map)
    if not words_a or not words_b:
        return False
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) >= actual_threshold


def _build_alias_map_from_config(config_dir: Path | None = None) -> dict[str, str]:
    """Build alias -> canonical_slug map from entity_aliases.yaml.

    E.g., {'open ai': 'openai', 'chatgpt maker': 'openai', 'deepmind': 'google-deepmind'}
    """
    if config_dir is None:
        config_dir = ROOT / "config"
    aliases_path = config_dir / "entity_aliases.yaml"
    if not aliases_path.exists():
        return {}
    data = yaml.safe_load(aliases_path.read_text(encoding="utf-8")) or {}
    result: dict[str, str] = {}
    for canonical, aliases in data.items():
        canonical_slug = slugify(str(canonical))
        # Map the canonical name itself (lowercased)
        result[canonical.lower().strip()] = canonical_slug
        result[canonical_slug] = canonical_slug
        for alias in (aliases or []):
            alias_str = str(alias).lower().strip()
            result[alias_str] = canonical_slug
            result[slugify(alias_str)] = canonical_slug
    return result


def merge_modeled_events(db_path: Path = DB_PATH, config_dir: Path | None = None) -> EventStoreResult:
    """Merge events that refer to the same real-world occurrence.

    Merge key: content-word-bag of title + event_date first 10 chars + first entity slug.
    Keeps the event with the lowest id (earliest) as canonical, merges others into it.
    Creates event_sources rows for all source raw_items.
    """
    with get_conn(db_path) as conn:
        ensure_schema(conn)
        alias_map = _build_alias_map_from_config(config_dir)

        rows = conn.execute(
            """
            SELECT
              e.id, e.raw_item_id, e.event_title, e.event_date, e.entities_json, e.status AS ev_status,
              r.source_url, r.title AS source_title, s.name AS source_name, r.published_at
            FROM events e
            LEFT JOIN raw_items r ON r.id = e.raw_item_id
            LEFT JOIN sources s ON s.id = r.source_id
            WHERE e.status = 'modeled'
            ORDER BY e.id
            """
        ).fetchall()

        # Group by merge key (date + first entity)
        pre_groups: dict[str, list[Any]] = {}
        for row in rows:
            key = _merge_key(
                row["event_title"] or "",
                row["event_date"],
                row["entities_json"],
            )
            pre_groups.setdefault(key, []).append(row)

        # Within each pre-group, sub-group by title similarity
        groups: dict[str, list[Any]] = {}
        for _key, group_rows in pre_groups.items():
            # Greedy clustering: assign each row to the first cluster whose
            # representative title is similar enough
            clusters: list[list[Any]] = []
            for row in group_rows:
                placed = False
                for cluster in clusters:
                    if _titles_should_merge(cluster[0]["event_title"] or "", row["event_title"] or "", alias_map):
                        cluster.append(row)
                        placed = True
                        break
                if not placed:
                    clusters.append([row])
            for i, cluster in enumerate(clusters):
                groups[f"{_key}#{i}"] = cluster

        canonical_count = 0
        merged_count = 0
        source_count = 0

        for _key, group in groups.items():
            canonical = group[0]
            canonical_id = int(canonical["id"])

            # Create event_sources for canonical event's raw_item
            existing_sources = {
                row["raw_item_id"]
                for row in conn.execute(
                    "SELECT raw_item_id FROM event_sources WHERE event_id = ?",
                    (canonical_id,),
                ).fetchall()
            }

            if canonical["raw_item_id"] and int(canonical["raw_item_id"]) not in existing_sources:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO event_sources
                      (event_id, raw_item_id, source_url, source_title, source_name, published_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_id,
                        int(canonical["raw_item_id"]),
                        canonical["source_url"],
                        canonical["source_title"],
                        canonical["source_name"],
                        canonical["published_at"],
                    ),
                )
                if cur.rowcount > 0:
                    source_count += 1

            # Merge all non-canonical events in this group
            for dup in group[1:]:
                dup_id = int(dup["id"])
                dup_raw_item_id = int(dup["raw_item_id"])

                # Add event_sources for duplicate's raw_item
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO event_sources
                      (event_id, raw_item_id, source_url, source_title, source_name, published_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_id,
                        dup_raw_item_id,
                        dup["source_url"],
                        dup["source_title"],
                        dup["source_name"],
                        dup["published_at"],
                    ),
                )
                if cur.rowcount > 0:
                    source_count += 1

                # Re-point decisions and timeline_nodes from dup to canonical
                conn.execute(
                    "UPDATE decisions SET event_id = ? WHERE event_id = ?",
                    (canonical_id, dup_id),
                )
                conn.execute(
                    "UPDATE timeline_nodes SET event_id = ? WHERE event_id = ?",
                    (canonical_id, dup_id),
                )

                # Mark duplicate as merged
                conn.execute(
                    "UPDATE events SET status = 'merged', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (dup_id,),
                )
                merged_count += 1

            canonical_count += 1

        conn.commit()

        result = EventStoreResult(
            canonical_events=canonical_count,
            merged_events=merged_count,
            event_sources=source_count,
        )
        conn.execute(
            """
            INSERT INTO runs (run_type, status, output_json, finished_at)
            VALUES ('event_store', 'success', ?, CURRENT_TIMESTAMP)
            """,
            (json.dumps(result.to_dict(), ensure_ascii=False),),
        )
        conn.commit()

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Merge duplicate modeled events.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--config-dir", type=Path, default=None)
    args = parser.parse_args()
    result = merge_modeled_events(db_path=args.db, config_dir=args.config_dir)
    print(
        f"[OK] event_store canonical={result.canonical_events} "
        f"merged={result.merged_events} sources={result.event_sources}"
    )


if __name__ == "__main__":
    main()
