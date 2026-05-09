from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
MEMORY_DIR = ROOT / "memory-wiki"
ENTITY_ALLOWLIST_PATH = ROOT / "config" / "entity_allowlist.yaml"


@dataclass(frozen=True)
class EntityResult:
    generated: int = 0
    exported: int = 0
    source: str = "db"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          slug TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          entity_type TEXT NOT NULL DEFAULT 'organization',
          entity_role TEXT NOT NULL DEFAULT 'mentioned_context',
          entity_quality TEXT NOT NULL DEFAULT 'candidate',
          summary TEXT,
          signal TEXT,
          related_events INTEGER DEFAULT 0,
          related_topics_json TEXT,
          timeline_nodes_json TEXT,
          claims_json TEXT,
          sources_json TEXT,
          status TEXT NOT NULL DEFAULT 'public',
          review_status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_profiles_type ON entity_profiles(entity_type)")
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(entity_profiles)").fetchall()}
    if "entity_role" not in existing_cols:
        conn.execute("ALTER TABLE entity_profiles ADD COLUMN entity_role TEXT NOT NULL DEFAULT 'mentioned_context'")
    if "entity_quality" not in existing_cols:
        conn.execute("ALTER TABLE entity_profiles ADD COLUMN entity_quality TEXT NOT NULL DEFAULT 'candidate'")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entity"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def entity_slug(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("slug") or slugify(str(entity.get("name") or "")))
    return slugify(str(entity))


def entity_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("name") or entity.get("slug") or "").strip()
    return str(entity).strip()


def entity_type(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("type") or entity.get("entity_type") or "organization")
    return "organization"


def load_entity_policy(path: Path = ENTITY_ALLOWLIST_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policy: dict[str, dict[str, str]] = {}
    for section, status in (("approved_entities", "public"), ("suppressed_entities", "suppressed")):
        for item in data.get(section, []) or []:
            if not isinstance(item, dict) or not item.get("slug"):
                continue
            slug = str(item["slug"])
            policy[slug] = {
                "entity_type": str(item.get("entity_type") or ""),
                "entity_role": str(item.get("entity_role") or "mentioned_context"),
                "entity_quality": str(item.get("entity_quality") or ("approved" if status == "public" else "suppressed")),
                "status": status,
            }
    return policy


def classify_entity(
    name: str,
    slug: str,
    entity_type_value: str,
    source_name: str = "",
    entity_policy: dict[str, dict[str, str]] | None = None,
) -> tuple[str, str, str, str]:
    policy = (entity_policy or {}).get(slug)
    if policy:
        return (
            policy.get("entity_type") or entity_type_value,
            policy["entity_role"],
            policy["entity_quality"],
            policy["status"],
        )
    source_markers = {"36kr", "36氪", "macrumors", "the verge", "mit technology review"}
    context_markers = {"hkex", "港交所", "香港交易所", "kospi", "wsbk", "央视新闻"}
    lowered = f"{name} {slug}".lower()
    source_lowered = source_name.lower()

    if any(marker.lower() in lowered for marker in source_markers) or (source_name and name.lower() in source_lowered):
        return entity_type_value, "source_media", "suppressed", "suppressed"
    if slug in context_markers or name in context_markers:
        return entity_type_value, "mentioned_context", "candidate", "suppressed"
    if entity_type_value in {"company", "model", "tool"}:
        role = "product_or_model" if entity_type_value in {"model", "tool"} else "core_actor"
        return entity_type_value, role, "approved", "public"
    if entity_type_value == "person":
        return entity_type_value, "core_actor", "candidate", "suppressed"
    if entity_type_value == "organization":
        regulator_markers = {"白宫", "监管", "政府", "ministry", "commission", "regulator"}
        if any(marker.lower() in lowered for marker in regulator_markers):
            return entity_type_value, "regulator", "candidate", "suppressed"
    return entity_type_value, "mentioned_context", "candidate", "suppressed"


def topic_slug(topic: Any) -> str:
    if isinstance(topic, dict):
        return str(topic.get("slug") or slugify(str(topic.get("name") or "")))
    return slugify(str(topic))


def claim_text(claim: Any) -> str:
    if not isinstance(claim, dict):
        return ""
    return str(claim.get("statement") or claim.get("claim_text") or claim.get("text") or "").strip()


def generate_from_db(conn) -> int:
    ensure_schema(conn)
    entity_policy = load_entity_policy()
    rows = conn.execute(
        """
        SELECT
          events.id AS event_id,
          events.event_title,
          events.event_summary,
          events.event_date,
          events.event_type,
          events.entities_json,
          events.topics_json,
          events.claims_json,
          decisions.decision_grade,
          raw_items.source_url,
          raw_items.title AS source_title,
          sources.name AS source_name,
          timeline_nodes.slug AS timeline_slug
        FROM events
        LEFT JOIN decisions ON decisions.event_id = events.id
        LEFT JOIN raw_items ON raw_items.id = events.raw_item_id
        LEFT JOIN sources ON sources.id = raw_items.source_id
        LEFT JOIN timeline_nodes ON timeline_nodes.event_id = events.id
        WHERE events.entities_json IS NOT NULL AND events.entities_json != '[]'
        """
    ).fetchall()
    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        entities = json_list(row["entities_json"])
        topics = json_list(row["topics_json"])
        claims = json_list(row["claims_json"])
        for ent in entities:
            slug = entity_slug(ent)
            name = entity_name(ent) or slug
            profile = profiles.setdefault(slug, {
                "slug": slug,
                "name": name,
                "entity_type": entity_type(ent),
                "entity_role": "",
                "entity_quality": "",
                "status": "",
                "events": [],
                "topics": Counter(),
                "claims": [],
                "sources": [],
            })
            classified_type, role, quality, status = classify_entity(
                name, slug, profile["entity_type"], row["source_name"] or "", entity_policy,
            )
            profile["entity_type"] = classified_type or profile["entity_type"]
            profile["entity_role"] = profile["entity_role"] or role
            profile["entity_quality"] = profile["entity_quality"] or quality
            profile["status"] = profile["status"] or status
            event = {
                "id": row["event_id"],
                "title": row["event_title"],
                "summary": row["event_summary"] or "",
                "date": (row["event_date"] or "")[:10],
                "type": row["event_type"] or "event",
                "grade": row["decision_grade"] or "",
                "url": f"/events/{row['timeline_slug']}/" if row["timeline_slug"] else "",
            }
            profile["events"].append(event)
            for topic in topics:
                ts = topic_slug(topic)
                if ts:
                    profile["topics"][ts] += 1
            for claim in claims:
                text = claim_text(claim)
                if text and text not in {c["text"] for c in profile["claims"]}:
                    profile["claims"].append({"text": text, "confidence": claim.get("confidence", 0.0) if isinstance(claim, dict) else 0.0})
            if row["source_url"]:
                profile["sources"].append({"url": row["source_url"], "title": row["source_title"] or row["event_title"], "publisher": row["source_name"] or ""})

    for profile in profiles.values():
        top_topics = [topic for topic, _count in profile["topics"].most_common(8)]
        recent_events = sorted(profile["events"], key=lambda e: e.get("date") or "", reverse=True)[:20]
        signal = build_signal(profile["name"], profile["entity_type"], recent_events, top_topics)
        upsert_profile(conn, profile, top_topics, recent_events, signal)
    conn.commit()
    return len(profiles)


def build_signal(name: str, entity_type_value: str, events: list[dict[str, Any]], topics: list[str]) -> str:
    if not events:
        return f"{name} 已进入实体档案，等待更多事件沉淀。"
    recent = events[0]
    topic_text = "、".join(topics[:3]) or "AI 行业"
    event_title = recent.get("title") or "最近事件"
    event_type_value = recent.get("type") or "event"
    return f"{name} 最近出现在“{event_title}”中，事件类型为 {event_type_value}；当前主要关联 {topic_text}，已沉淀 {len(events)} 个相关事件。"


def upsert_profile(conn, profile: dict[str, Any], topics: list[str], events: list[dict[str, Any]], signal: str) -> None:
    data = {
        "slug": profile["slug"],
        "name": profile["name"],
        "entity_type": profile["entity_type"],
        "entity_role": profile["entity_role"],
        "entity_quality": profile["entity_quality"],
        "summary": f"{profile['name']} 的实体档案由 neican.ai 从结构化事件、时间线节点和声明库自动生成。",
        "signal": signal,
        "related_events": len(profile["events"]),
        "related_topics_json": json.dumps(topics, ensure_ascii=False),
        "timeline_nodes_json": json.dumps(events, ensure_ascii=False),
        "claims_json": json.dumps(profile["claims"][:20], ensure_ascii=False),
        "sources_json": json.dumps(profile["sources"][:20], ensure_ascii=False),
        "status": profile.get("status") or "suppressed",
        "review_status": "draft",
    }
    cols = list(data)
    conn.execute(
        f"""
        INSERT INTO entity_profiles ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})
        ON CONFLICT(slug) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols if c != 'slug')}, updated_at=CURRENT_TIMESTAMP
        """,
        tuple(data[c] for c in cols),
    )


def read_yaml_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        try:
            _blank, fm, body = text.split("---", 2)
            return yaml.safe_load(fm) or {}, body.strip()
        except Exception:
            pass
    return {}, text


def generate_from_memory(conn, memory_dir: Path = MEMORY_DIR) -> int:
    ensure_schema(conn)
    files = list((memory_dir / "entities").glob("*/*/_index.md"))
    count = 0
    for path in files:
        fm, body = read_yaml_page(path)
        slug = str(fm.get("slug") or path.parent.name)
        name = str(fm.get("title") or slug)
        etype = str(fm.get("entity_type") or path.parent.parent.name.rstrip("s") or "organization")
        claims = fm.get("claims") if isinstance(fm.get("claims"), list) else []
        event_lines = [line.strip("- ") for line in body.splitlines() if line.strip().startswith("- ")][:20]
        events = [{"title": line, "date": line[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", line) else "", "url": ""} for line in event_lines]
        profile = {
            "slug": slug,
            "name": name,
            "entity_type": etype,
            "entity_role": "mentioned_context",
            "entity_quality": "candidate",
            "status": "suppressed",
            "events": events,
            "topics": Counter(),
            "claims": [{"text": c.get("text") or c.get("statement") or "", "confidence": c.get("confidence", 0)} for c in claims if isinstance(c, dict)],
            "sources": [],
        }
        signal = build_signal(name, etype, events, [])
        upsert_profile(conn, profile, [], events, signal)
        count += 1
    conn.commit()
    return count


def frontmatter(data: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def export_hugo(conn, site_dir: Path = SITE_DIR) -> int:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT * FROM entity_profiles
        WHERE status='public'
          AND entity_quality='approved'
          AND entity_role IN ('core_actor', 'product_or_model', 'infrastructure', 'regulator')
        ORDER BY related_events DESC, name
        """
    ).fetchall()
    base = site_dir / "content" / "entities"
    base.mkdir(parents=True, exist_ok=True)
    for child in base.iterdir():
        if child.is_dir() and (child / "_index.md").exists():
            # Replace generated/demo entity profiles; keep root _index and .gitkeep.
            (child / "_index.md").unlink()
            try:
                child.rmdir()
            except OSError:
                pass
    write_index(base, rows)
    for row in rows:
        write_entity_page(base, row)
    return len(rows)


def write_index(base: Path, rows: list[Any]) -> None:
    types = Counter(row["entity_type"] for row in rows)
    body = [
        "<div class=\"entity-product-page\">",
        "<p class=\"eyebrow\">Entity Files MVP</p>",
        "<h1>实体档案库：把公司、人物、模型和工具变成长期知识资产</h1>",
        "<p class=\"page-lead\">实体档案不是百科词条，而是由事件、时间线、声明和来源持续更新的行业对象。它回答：这个对象最近参与了什么变化？关联哪些主题？有哪些可追溯判断？</p>",
        "<div class=\"entity-kpis\">",
        f"<div><strong>{len(rows)}</strong><span>实体档案</span></div>",
        f"<div><strong>{types.get('company', 0)}</strong><span>公司</span></div>",
        f"<div><strong>{types.get('person', 0)}</strong><span>人物</span></div>",
        f"<div><strong>{types.get('organization', 0) + types.get('organizations', 0)}</strong><span>组织/机构</span></div>",
        "</div><div class=\"entity-profile-grid\">",
    ]
    for row in rows[:48]:
        body.append(f"<a href=\"/entities/{row['slug']}/\"><b>{row['name']}</b><small>{row['entity_type']}</small><span>{row['signal'] or row['summary'] or ''}</span></a>")
    body += ["</div>", "</div>"]
    fm = {"title": "实体档案", "type": "entity_index", "entity_count": len(rows), "seo": {"description": "neican.ai 自动生成的 AI 行业实体档案库。"}}
    (base / "_index.md").write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")


def write_entity_page(base: Path, row) -> None:
    topics = json_list(row["related_topics_json"])
    events = json_list(row["timeline_nodes_json"])
    claims = json_list(row["claims_json"])
    sources = json_list(row["sources_json"])
    fm = {
        "title": row["name"],
        "type": "entity_profile",
        "entity_type": row["entity_type"],
        "entity_role": row["entity_role"],
        "entity_quality": row["entity_quality"],
        "related_events": row["related_events"],
        "topics": topics,
        "claims": claims,
        "sources": sources,
        "neican": {"generated_by": "entity_product", "review_status": row["review_status"]},
    }
    type_labels = {
        "company": "公司",
        "tool": "AI 产品/工具",
        "model": "AI 模型",
        "organization": "组织/机构",
        "person": "人物",
    }
    type_label = type_labels.get(row["entity_type"], "行业参与者")
    intro = f"{row['name']} 是 neican.ai 追踪的 AI 行业{type_label}。"
    body = [
        "<div class=\"entity-profile-page\">",
        f"<p class=\"eyebrow\">{row['entity_type']} File</p>",
        f"<h1>{row['name']}</h1>",
        f"<p class=\"page-lead\">{intro}</p>",
        "<section class=\"entity-signal\"><h2>当前信号</h2>",
        f"<p>{row['signal'] or '该实体仍在积累更多事件。'}</p></section>",
    ]
    if topics:
        body.append("<section><h2>关联主题</h2><div class=\"entity-topic-chips\">" + "".join(f"<a href=\"/topics/{slug}/\">#{slug}</a>" for slug in topics[:12]) + "</div></section>")
    if events:
        body.append("<section><h2>相关时间线/事件</h2><div class=\"entity-event-list\">")
        for ev in events[:20]:
            url = ev.get("url") or ""
            title = ev.get("title") or "事件"
            date = ev.get("date") or ""
            event_type_value = ev.get("type") or "event"
            summary = ev.get("summary") or ""
            link = f"<a href=\"{url}\">{title}</a>" if url else title
            body.append(f"<article><time>{date}</time><span class=\"chip\">{event_type_value}</span><h3>{link}</h3><p>{summary}</p></article>")
        body.append("</div></section>")
    valid_claims = [c for c in claims if c.get("text")]
    if valid_claims:
        body.append("<section><h2>关键信息</h2><div class=\"entity-claims\">")
        for c in valid_claims[:12]:
            body.append(f"<p><span>{c.get('text')}</span></p>")
        body.append("</div></section>")
    if sources:
        body.append("<section><h2>来源</h2><ul class=\"entity-sources\">" + "".join(f"<li><a href=\"{s.get('url')}\">{s.get('title') or s.get('url')}</a></li>" for s in sources if s.get("url")) + "</ul></section>")
    body.append("</div>")
    path = base / row["slug"] / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")


def run(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR, memory_dir: Path = MEMORY_DIR) -> EntityResult:
    with get_conn(db_path) as conn:
        generated = generate_from_db(conn)
        source = "db"
        if generated == 0:
            generated = generate_from_memory(conn, memory_dir=memory_dir)
            source = "memory-wiki"
        exported = export_hugo(conn, site_dir=site_dir)
    return EntityResult(generated=generated, exported=exported, source=source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate entity_profiles and export entity Hugo pages.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
