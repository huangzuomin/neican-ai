"""Knowledge asset maintenance: auto-create/update entity, topic, timeline pages in memory-wiki."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
MEMORY_DIR = ROOT / "memory-wiki"


@dataclass(frozen=True)
class AssetUpdateResult:
    entities_created: int = 0
    entities_updated: int = 0
    topics_created: int = 0
    topics_updated: int = 0
    timeline_entries: int = 0
    claims_written: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _slugify(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _read_frontmatter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    try:
        _, fm, _ = text.split("---", 2)
        return yaml.safe_load(fm) or {}
    except Exception:
        return {}


def _write_asset(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{yaml_text}---\n\n{body.strip()}\n", encoding="utf-8")


def _entity_dir(entity_type: str) -> Path:
    type_map = {
        "company": "companies",
        "organization": "organizations",
        "person": "people",
        "model": "models",
        "tool": "tools",
    }
    return MEMORY_DIR / "entities" / type_map.get(entity_type, "organizations")


def update_entities(conn, result: AssetUpdateResult) -> AssetUpdateResult:
    """Create/update entity pages from all events in DB."""
    rows = conn.execute(
        """
        SELECT events.entities_json, events.event_title, events.event_date, events.claims_json
        FROM events
        WHERE status = 'modeled'
        ORDER BY id DESC
        """
    ).fetchall()

    # Collect all entities across events
    entity_map: dict[str, dict[str, Any]] = {}  # slug -> {name, type, role, events, claims}

    for row in rows:
        entities = json.loads(row["entities_json"] or "[]")
        claims = json.loads(row["claims_json"] or "[]")
        for e in entities:
            if not isinstance(e, dict):
                continue
            slug = e.get("slug") or _slugify(str(e.get("name", "")))
            if not slug:
                continue
            if slug not in entity_map:
                entity_map[slug] = {
                    "name": e.get("name", slug),
                    "slug": slug,
                    "type": e.get("type", "organization"),
                    "role": e.get("role", ""),
                    "events": [],
                    "claims": [],
                }
            entity_map[slug]["events"].append({
                "title": row["event_title"],
                "date": row["event_date"],
            })
            for c in claims:
                if isinstance(c, dict) and c.get("claim_text"):
                    entity_map[slug]["claims"].append({
                        "text": c["claim_text"],
                        "confidence": c.get("confidence", 0.5),
                        "date": row["event_date"],
                    })

    entities_created = 0
    entities_updated = 0
    claims_written = 0

    for slug, data in entity_map.items():
        entity_path = _entity_dir(data["type"]) / slug / "_index.md"

        existing_fm = _read_frontmatter(entity_path)
        existing_claims = existing_fm.get("claims", [])

        # Merge claims: add new ones
        existing_texts = {c.get("text") for c in existing_claims}
        for c in data["claims"]:
            if c["text"] not in existing_texts:
                existing_claims.append(c)
                claims_written += 1

        frontmatter = {
            "title": data["name"],
            "slug": slug,
            "type": "entity",
            "entity_type": data["type"],
            "role": data.get("role", ""),
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "related_events": len(data["events"]),
            "claims": existing_claims,
        }

        # Build body
        body_parts = [f"# {data['name']}", ""]
        if data.get("role"):
            body_parts.append(f"**角色**: {data['role']}")
            body_parts.append("")

        body_parts.append(f"## 关联事件 ({len(data['events'])})")
        body_parts.append("")
        for ev in data["events"][:20]:
            date_str = (ev["date"] or "")[:10]
            body_parts.append(f"- {date_str}: {ev['title']}")

        if existing_claims:
            body_parts.append("")
            body_parts.append(f"## 结构化声明 ({len(existing_claims)})")
            body_parts.append("")
            for c in existing_claims[:20]:
                conf = round(c.get("confidence", 0) * 100)
                body_parts.append(f"- {c['text']}（{conf}%）")

        body = "\n".join(body_parts)
        _write_asset(entity_path, frontmatter, body)

        if existing_fm:
            entities_updated += 1
        else:
            entities_created += 1

    return AssetUpdateResult(
        entities_created=entities_created,
        entities_updated=entities_updated,
        claims_written=claims_written,
        topics_created=result.topics_created,
        topics_updated=result.topics_updated,
        timeline_entries=result.timeline_entries,
    )


def update_topics(conn, result: AssetUpdateResult) -> AssetUpdateResult:
    """Create/update topic pages from all events."""
    rows = conn.execute(
        """
        SELECT events.topics_json, events.event_title, events.event_date,
               events.entities_json, events.importance_score
        FROM events
        WHERE status = 'modeled'
        ORDER BY id DESC
        """
    ).fetchall()

    topic_map: dict[str, dict[str, Any]] = {}

    for row in rows:
        topics = json.loads(row["topics_json"] or "[]")
        entities = json.loads(row["entities_json"] or "[]")
        for t in topics:
            if isinstance(t, dict):
                slug = t.get("slug") or _slugify(str(t.get("name", "")))
                name = t.get("name") or slug
            else:
                slug = str(t)
                name = slug.replace("-", " ")
            if not slug:
                continue
            if slug not in topic_map:
                topic_map[slug] = {"name": name, "slug": slug, "events": [], "entities": set()}
            topic_map[slug]["events"].append({
                "title": row["event_title"],
                "date": row["event_date"],
                "importance": row["importance_score"],
            })
            for e in entities:
                if isinstance(e, dict) and e.get("slug"):
                    topic_map[slug]["entities"].add(e["slug"])

    topics_created = 0
    topics_updated = 0

    for slug, data in topic_map.items():
        topic_path = MEMORY_DIR / "topics" / slug / "_index.md"
        existing_fm = _read_frontmatter(topic_path)

        frontmatter = {
            "title": data["name"],
            "slug": slug,
            "type": "topic",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "related_events": len(data["events"]),
            "related_entities": sorted(data["entities"]),
        }

        body_parts = [f"# {data['name']}", ""]
        body_parts.append(f"## 事件时间线 ({len(data['events'])})")
        body_parts.append("")
        for ev in sorted(data["events"], key=lambda x: x.get("date", ""), reverse=True)[:20]:
            date_str = (ev["date"] or "")[:10]
            body_parts.append(f"- {date_str}: {ev['title']}")

        if data["entities"]:
            body_parts.append("")
            body_parts.append(f"## 相关实体 ({len(data['entities'])})")
            body_parts.append("")
            for e_slug in sorted(data["entities"])[:20]:
                body_parts.append(f"- [[{e_slug}]]")

        body = "\n".join(body_parts)
        _write_asset(topic_path, frontmatter, body)

        if existing_fm:
            topics_updated += 1
        else:
            topics_created += 1

    return AssetUpdateResult(
        entities_created=result.entities_created,
        entities_updated=result.entities_updated,
        topics_created=topics_created,
        topics_updated=topics_updated,
        timeline_entries=result.timeline_entries,
        claims_written=result.claims_written,
    )


def update_timeline(conn, result: AssetUpdateResult) -> AssetUpdateResult:
    """Create/update timeline pages by year."""
    rows = conn.execute(
        """
        SELECT events.event_date, events.event_title, events.event_type,
               events.importance_score, events.entities_json
        FROM events
        WHERE status = 'modeled' AND event_date IS NOT NULL
        ORDER BY event_date
        """
    ).fetchall()

    year_map: dict[str, list[dict]] = {}
    timeline_entries = 0

    for row in rows:
        date_str = (row["event_date"] or "")[:10]
        if not date_str or len(date_str) < 4:
            continue
        year = date_str[:4]
        entities = json.loads(row["entities_json"] or "[]")
        entity_names = [e.get("name", "") for e in entities if isinstance(e, dict)]
        year_map.setdefault(year, []).append({
            "date": date_str,
            "title": row["event_title"],
            "type": row["event_type"],
            "importance": row["importance_score"],
            "entities": entity_names,
        })
        timeline_entries += 1

    for year, entries in year_map.items():
        tl_path = MEMORY_DIR / "timeline" / year / "_index.md"
        frontmatter = {
            "title": f"{year} 年时间线",
            "type": "timeline",
            "year": year,
            "event_count": len(entries),
        }

        body_parts = [f"# {year} 年 AI 行业时间线", ""]
        for e in entries:
            entity_str = ", ".join(e["entities"][:3])
            body_parts.append(f"- **{e['date']}** — {e['title']} [{e['type']}]")
            if entity_str:
                body_parts[-1] += f" · {entity_str}"

        body = "\n".join(body_parts)
        _write_asset(tl_path, frontmatter, body)

    return AssetUpdateResult(
        entities_created=result.entities_created,
        entities_updated=result.entities_updated,
        topics_created=result.topics_created,
        topics_updated=result.topics_updated,
        timeline_entries=timeline_entries,
        claims_written=result.claims_written,
    )


def update_knowledge_assets(
    db_path: Path = DB_PATH,
    memory_dir: Path = MEMORY_DIR,
) -> AssetUpdateResult:
    db_path = Path(db_path)
    memory_dir = Path(memory_dir)
    if not db_path.exists():
        raise SystemExit("Database not found")

    global MEMORY_DIR
    MEMORY_DIR = memory_dir

    with get_conn(db_path) as conn:
        result = AssetUpdateResult()
        result = update_entities(conn, result)
        result = update_topics(conn, result)
        result = update_timeline(conn, result)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Update knowledge assets from events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = update_knowledge_assets()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
