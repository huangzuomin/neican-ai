from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
ENTITY_ALIASES_PATH = ROOT / "config" / "entity_aliases.yaml"
ENTITY_ALLOWLIST_PATH = ROOT / "config" / "entity_allowlist.yaml"


@dataclass(frozen=True)
class EntityRegistryResult:
    synced: int = 0
    updated: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_registry (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          slug TEXT NOT NULL UNIQUE,
          canonical_name TEXT NOT NULL,
          entity_type TEXT NOT NULL DEFAULT 'organization',
          entity_role TEXT NOT NULL DEFAULT 'mentioned_context',
          entity_quality TEXT NOT NULL DEFAULT 'candidate',
          aliases_json TEXT,
          confidence REAL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(entity_registry)").fetchall()}
    if "entity_role" not in existing_cols:
        conn.execute("ALTER TABLE entity_registry ADD COLUMN entity_role TEXT NOT NULL DEFAULT 'mentioned_context'")
    if "entity_quality" not in existing_cols:
        conn.execute("ALTER TABLE entity_registry ADD COLUMN entity_quality TEXT NOT NULL DEFAULT 'candidate'")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    # Detect poor-quality slugs from Chinese/Unicode names
    if not slug or slug == "entity" or slug.isdigit() or len(slug) < 3:
        import hashlib
        hash_suffix = hashlib.md5(value.encode()).hexdigest()[:8]
        base = slug if (slug and slug != "entity") else "entity"
        slug = f"{base}-{hash_suffix}"
    return slug


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def load_aliases(aliases_path: Path = ENTITY_ALIASES_PATH) -> dict[str, list[str]]:
    """Load entity aliases from YAML config.

    Returns dict mapping canonical_name -> list of alias strings.
    """
    if not aliases_path.exists():
        return {}
    data = yaml.safe_load(aliases_path.read_text(encoding="utf-8")) or {}
    return {str(k): [str(a) for a in (v or [])] for k, v in data.items() if k}


def build_alias_map(aliases: dict[str, list[str]]) -> dict[str, tuple[str, str]]:
    """Build reverse lookup: lowercase alias or name -> (slug, canonical_name)."""
    mapping: dict[str, tuple[str, str]] = {}
    for canonical_name, alias_list in aliases.items():
        slug = slugify(canonical_name)
        # Map the canonical name itself
        mapping[canonical_name.lower().strip()] = (slug, canonical_name)
        for alias in alias_list:
            mapping[alias.lower().strip()] = (slug, canonical_name)
    return mapping


def normalize_entity_name(
    value: str,
    aliases: dict[str, list[str]] | None = None,
) -> tuple[str, str]:
    """Normalize an entity name to (slug, canonical_name).

    If aliases dict is provided, attempts alias lookup.
    Falls back to slugify(value).
    """
    if aliases is None:
        aliases = load_aliases()
    alias_map = build_alias_map(aliases)
    key = value.lower().strip()
    if key in alias_map:
        return alias_map[key]
    # Slugify as fallback
    slug = slugify(value)
    # Use original value as canonical name (title-cased)
    canonical = value.strip()
    if canonical and canonical == canonical.lower():
        # All lowercase — try to title-case
        canonical = canonical.title()
    return slug, canonical


def classify_registry_entity(entity_type_value: str) -> tuple[str, str]:
    if entity_type_value == "company":
        return "core_actor", "approved"
    if entity_type_value in {"model", "tool"}:
        return "product_or_model", "approved"
    if entity_type_value == "person":
        return "core_actor", "candidate"
    return "mentioned_context", "candidate"


def load_entity_policy(path: Path = ENTITY_ALLOWLIST_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policy: dict[str, dict[str, str]] = {}
    for item in data.get("approved_entities", []) or []:
        if isinstance(item, dict) and item.get("slug"):
            policy[str(item["slug"])] = {
                "entity_type": str(item.get("entity_type") or ""),
                "entity_role": str(item.get("entity_role") or "mentioned_context"),
                "entity_quality": str(item.get("entity_quality") or "approved"),
            }
    for item in data.get("suppressed_entities", []) or []:
        if isinstance(item, dict) and item.get("slug"):
            policy[str(item["slug"])] = {
                "entity_type": str(item.get("entity_type") or ""),
                "entity_role": str(item.get("entity_role") or "source_media"),
                "entity_quality": str(item.get("entity_quality") or "suppressed"),
            }
    return policy


def sync_entity_registry(
    db_path: Path = DB_PATH,
    aliases_path: Path = ENTITY_ALIASES_PATH,
) -> EntityRegistryResult:
    """Sync entity_registry from events + aliases config."""
    aliases = load_aliases(aliases_path)
    alias_map = build_alias_map(aliases)
    entity_policy = load_entity_policy()

    with get_conn(db_path) as conn:
        ensure_schema(conn)

        # Extract all entity names from events
        rows = conn.execute(
            "SELECT entities_json FROM events WHERE entities_json IS NOT NULL AND entities_json != '[]'"
        ).fetchall()

        entity_counter: Counter[str] = Counter()
        entity_names: dict[str, str] = {}  # slug -> canonical_name
        entity_types: dict[str, Counter[str]] = {}
        entity_aliases_collected: dict[str, set[str]] = {}  # slug -> set of raw names seen

        for row in rows:
            entities = json_list(row["entities_json"])
            for ent in entities:
                if isinstance(ent, dict):
                    raw_name = str(ent.get("name") or ent.get("slug") or "").strip()
                    raw_type = str(ent.get("type") or ent.get("entity_type") or "organization")
                else:
                    raw_name = str(ent).strip()
                    raw_type = "organization"
                if not raw_name:
                    continue

                # Try alias resolution
                key = raw_name.lower().strip()
                if key in alias_map:
                    slug, canonical = alias_map[key]
                else:
                    slug = slugify(raw_name)
                    canonical = raw_name.strip()

                entity_counter[slug] += 1
                entity_names[slug] = canonical
                entity_types.setdefault(slug, Counter())[raw_type] += 1
                entity_aliases_collected.setdefault(slug, set()).add(raw_name)

        synced = 0
        updated = 0
        skipped = 0

        for slug, count in entity_counter.items():
            canonical = entity_names[slug]
            collected_aliases = entity_aliases_collected.get(slug, set())

            # Also include aliases from config
            config_aliases = set()
            for _canonical_name, alias_list in aliases.items():
                if slugify(_canonical_name) == slug:
                    config_aliases.update(a.lower().strip() for a in alias_list)

            all_aliases = collected_aliases | config_aliases
            # Remove the canonical name from aliases
            all_aliases.discard(canonical)
            aliases_json = json.dumps(sorted(all_aliases), ensure_ascii=False)
            entity_type_value = entity_types.get(slug, Counter({"organization": 1})).most_common(1)[0][0]
            policy = entity_policy.get(slug, {})
            entity_type_value = policy.get("entity_type") or entity_type_value
            if policy:
                entity_role = policy["entity_role"]
                entity_quality = policy["entity_quality"]
            else:
                entity_role, entity_quality = classify_registry_entity(entity_type_value)

            existing = conn.execute(
                "SELECT id FROM entity_registry WHERE slug = ?", (slug,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE entity_registry
                       SET canonical_name = ?, entity_type = ?, entity_role = ?, entity_quality = ?,
                           aliases_json = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE slug = ?""",
                    (canonical, entity_type_value, entity_role, entity_quality, aliases_json, slug),
                )
                updated += 1
            else:
                conn.execute(
                    """INSERT INTO entity_registry (
                         slug, canonical_name, entity_type, entity_role, entity_quality, aliases_json, confidence
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (slug, canonical, entity_type_value, entity_role, entity_quality, aliases_json, min(0.95, 0.5 + count * 0.05)),
                )
                synced += 1

        conn.commit()

        result = EntityRegistryResult(synced=synced, updated=updated, skipped=skipped)
        conn.execute(
            """
            INSERT INTO runs (run_type, status, output_json, finished_at)
            VALUES ('entity_registry', 'success', ?, CURRENT_TIMESTAMP)
            """,
            (json.dumps(result.to_dict(), ensure_ascii=False),),
        )
        conn.commit()
        return result


def normalize_events_entities(
    db_path: Path = DB_PATH,
    aliases_path: Path = ENTITY_ALIASES_PATH,
) -> int:
    """Re-write events.entities_json using registry-normalized slugs and names.

    Returns count of events updated.
    """
    aliases = load_aliases(aliases_path)

    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, entities_json FROM events WHERE entities_json IS NOT NULL AND entities_json != '[]'"
        ).fetchall()

        updated = 0
        for row in rows:
            entities = json_list(row["entities_json"])
            changed = False
            for i, ent in enumerate(entities):
                if not isinstance(ent, dict):
                    continue
                raw_name = str(ent.get("name") or ent.get("slug") or "").strip()
                if not raw_name:
                    continue
                slug, canonical = normalize_entity_name(raw_name, aliases)
                if ent.get("slug") != slug or ent.get("name") != canonical:
                    ent["slug"] = slug
                    ent["name"] = canonical
                    changed = True
            if changed:
                conn.execute(
                    "UPDATE events SET entities_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(entities, ensure_ascii=False), row["id"]),
                )
                updated += 1
        conn.commit()
        return updated


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sync entity registry from events + aliases config.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--aliases", type=Path, default=ENTITY_ALIASES_PATH)
    args = parser.parse_args()
    # Normalize events FIRST so sync reads clean slugs
    norm = normalize_events_entities(db_path=args.db, aliases_path=args.aliases)
    result = sync_entity_registry(db_path=args.db, aliases_path=args.aliases)
    print(f"[OK] entity_registry synced={result.synced} updated={result.updated} events_normalized={norm}")


if __name__ == "__main__":
    main()
