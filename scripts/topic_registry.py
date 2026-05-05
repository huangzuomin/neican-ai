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
TAXONOMY_PATH = ROOT / "config" / "taxonomy.yaml"


@dataclass(frozen=True)
class TopicRegistryResult:
    synced: int = 0
    updated: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS topic_registry (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          slug TEXT NOT NULL UNIQUE,
          canonical_name TEXT NOT NULL,
          aliases_json TEXT,
          parent_slug TEXT,
          description TEXT,
          public INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


# Known acronyms that .title() mangles — applied after title-casing.
_ACRONYM_FIXES = [
    (r"\bAi\b", "AI"),
    (r"\bLlm\b", "LLM"),
    (r"\bMcp\b", "MCP"),
    (r"\bRag\b", "RAG"),
    (r"\bGpu\b", "GPU"),
    (r"\bApi\b", "API"),
    (r"\bSdk\b", "SDK"),
    (r"\bIpo\b", "IPO"),
    (r"\bVla\b", "VLA"),
    (r"\bVlm\b", "VLM"),
]


def fix_acronyms(name: str) -> str:
    """Fix .title()-mangled acronyms: 'Ai Agents' -> 'AI Agents', 'Llm' -> 'LLM'."""
    for pattern, replacement in _ACRONYM_FIXES:
        name = re.sub(pattern, replacement, name)
    return name


def load_taxonomy(taxonomy_path: Path = TAXONOMY_PATH) -> dict[str, Any]:
    if not taxonomy_path.exists():
        return {}
    return yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}


def build_topic_alias_map(taxonomy: dict[str, Any]) -> dict[str, tuple[str, str, str | None, str]]:
    """Build reverse lookup: lowercase alias -> (slug, canonical_name, parent_slug, description).

    Currently taxonomy.yaml only has flat topic_slugs list, so we create entries from those.
    In future, taxonomy can include richer topic definitions with aliases, parents, descriptions.
    """
    mapping: dict[str, tuple[str, str, str | None, str]] = {}
    topic_slugs = taxonomy.get("topic_slugs") or []
    for slug in topic_slugs:
        canonical_name = fix_acronyms(str(slug).replace("-", " ").title())
        mapping[str(slug).lower()] = (str(slug), canonical_name, None, "")

    # Support richer topic_definitions if present
    topic_defs = taxonomy.get("topic_definitions") or []
    for defn in topic_defs:
        if isinstance(defn, dict):
            slug = str(defn.get("slug") or slugify(str(defn.get("name") or "")))
            canonical = str(defn.get("name") or fix_acronyms(slug.replace("-", " ").title()))
            parent = defn.get("parent")
            desc = str(defn.get("description") or "")
            aliases = defn.get("aliases") or []
            mapping[slug.lower()] = (slug, canonical, parent, desc)
            for alias in aliases:
                mapping[str(alias).lower().strip()] = (slug, canonical, parent, desc)
    return mapping


def normalize_topic_name(
    value: str,
    taxonomy: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Normalize a topic name to (slug, canonical_name)."""
    if taxonomy is None:
        taxonomy = load_taxonomy()
    alias_map = build_topic_alias_map(taxonomy)
    key = value.lower().strip().replace(" ", "-")
    if key in alias_map:
        slug, canonical, _parent, _desc = alias_map[key]
        return slug, canonical
    # Try without hyphen replacement
    key2 = value.lower().strip()
    if key2 in alias_map:
        slug, canonical, _parent, _desc = alias_map[key2]
        return slug, canonical
    # Fallback: slugify
    slug = slugify(value)
    return slug, value.strip()


def sync_topic_registry(
    db_path: Path = DB_PATH,
    taxonomy_path: Path = TAXONOMY_PATH,
) -> TopicRegistryResult:
    """Sync topic_registry from taxonomy.yaml."""
    taxonomy = load_taxonomy(taxonomy_path)
    topic_slugs = taxonomy.get("topic_slugs") or []
    topic_defs = taxonomy.get("topic_definitions") or []

    with get_conn(db_path) as conn:
        ensure_schema(conn)

        synced = 0
        updated = 0
        skipped = 0

        # Process flat topic_slugs
        for slug in topic_slugs:
            canonical_name = fix_acronyms(str(slug).replace("-", " ").title())
            _upsert_topic(conn, slug, canonical_name, None, "", [], synced, updated)
            # Check if insert or update
            synced += 1

        # Process richer topic_definitions
        for defn in topic_defs:
            if not isinstance(defn, dict):
                continue
            slug = str(defn.get("slug") or slugify(str(defn.get("name") or "")))
            canonical = str(defn.get("name") or fix_acronyms(slug.replace("-", " ").title()))
            parent = defn.get("parent")
            desc = str(defn.get("description") or "")
            aliases = defn.get("aliases") or []
            _upsert_topic(conn, slug, canonical, parent, desc, aliases, 0, 0)
            synced += 1

        conn.commit()

        result = TopicRegistryResult(synced=synced, updated=updated, skipped=skipped)
        conn.execute(
            """
            INSERT INTO runs (run_type, status, output_json, finished_at)
            VALUES ('topic_registry', 'success', ?, CURRENT_TIMESTAMP)
            """,
            (json.dumps(result.to_dict(), ensure_ascii=False),),
        )
        conn.commit()
        return result


def _upsert_topic(
    conn, slug: str, canonical_name: str, parent_slug: str | None,
    description: str, aliases: list[str], _synced: int, _updated: int,
) -> None:
    aliases_json = json.dumps(aliases, ensure_ascii=False)
    existing = conn.execute("SELECT id FROM topic_registry WHERE slug = ?", (slug,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE topic_registry
               SET canonical_name = ?, aliases_json = ?, parent_slug = ?, description = ?, updated_at = CURRENT_TIMESTAMP
               WHERE slug = ?""",
            (canonical_name, aliases_json, parent_slug, description, slug),
        )
    else:
        conn.execute(
            """INSERT INTO topic_registry (slug, canonical_name, aliases_json, parent_slug, description)
               VALUES (?, ?, ?, ?, ?)""",
            (slug, canonical_name, aliases_json, parent_slug, description),
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sync topic registry from taxonomy config.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH)
    args = parser.parse_args()
    result = sync_topic_registry(db_path=args.db, taxonomy_path=args.taxonomy)
    print(f"[OK] topic_registry synced={result.synced} updated={result.updated}")


if __name__ == "__main__":
    main()
