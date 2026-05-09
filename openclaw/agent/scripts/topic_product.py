from __future__ import annotations

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


@dataclass(frozen=True)
class TopicProductResult:
    generated: int = 0
    exported: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


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


def dedupe_by_event_id(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for event in events:
        event_id = int(event.get("id") or 0)
        if event_id and event_id in seen:
            continue
        if event_id:
            seen.add(event_id)
        unique.append(event)
    return unique


def topic_hub_sections(canonical: str, description: str, top_entities: list[str], events: list[dict[str, Any]]) -> list[str]:
    recent_events = sorted(events, key=lambda e: e.get("date") or "", reverse=True)[:5]
    a_count = sum(1 for e in events if e.get("grade") == "A")
    b_count = sum(1 for e in events if e.get("grade") == "B")
    if a_count:
        judgment = f"近期有 {a_count} 个高优先级事件进入该主题，说明 {canonical} 正处在值得密切跟踪的变化期。"
    elif b_count:
        judgment = f"该主题近期有 {b_count} 个趋势事件，暂未形成结构性结论，但已经值得持续观察。"
    else:
        judgment = f"{canonical} 目前仍以弱信号积累为主，需要等待更多高质量事件确认方向。"
    event_lines = []
    for idx, event in enumerate(recent_events[:3], start=1):
        summary = event.get("summary") or "摘要仍在补充。"
        event_type = event.get("type") or "event"
        event_lines.append(f"{idx}. **{event['title']}**（{event_type}）：{summary}")
    if not event_lines:
        event_lines = ["1. 暂无可公开展示的近期事件。"]
    return [
        "## 一句话定义",
        "",
        description or f"{canonical} 是 neican.ai 用来追踪 AI 行业结构变化的长期主题。",
        "",
        "## 当前判断",
        "",
        judgment,
        "",
        "## 最近事件",
        "",
        *event_lines,
        "",
        "## 下一步观察",
        "",
        "- 是否出现连续的高优先级事件。",
        "- 核心实体是否推出产品、政策、研究或平台能力变化。",
        "- 来源可信度是否足以支撑更强判断。",
        "",
    ]


def frontmatter(data: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def generate_topic_pages(
    db_path: Path = DB_PATH,
    site_dir: Path = SITE_DIR,
) -> TopicProductResult:
    """Generate topic pages from topic_registry + events."""
    with get_conn(db_path) as conn:
        # Get all topic_registry rows
        topics = conn.execute(
            "SELECT * FROM topic_registry WHERE public = 1 ORDER BY slug"
        ).fetchall()

        if not topics:
            return TopicProductResult()

        # Get all events with topics
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
              sources.name AS source_name
            FROM events
            LEFT JOIN decisions ON decisions.event_id = events.id
            LEFT JOIN raw_items ON raw_items.id = events.raw_item_id
            LEFT JOIN sources ON sources.id = raw_items.source_id
            WHERE events.topics_json IS NOT NULL AND events.topics_json != '[]'
            """
        ).fetchall()

        # Group events by topic slug
        topic_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        topic_entities: dict[str, Counter] = defaultdict(Counter)
        topic_sources: dict[str, list[dict[str, str]]] = defaultdict(list)
        topic_tracks: dict[str, Counter] = defaultdict(Counter)

        for row in rows:
            topics_json = json_list(row["topics_json"])
            entities = json_list(row["entities_json"])
            for topic in topics_json:
                ts = _slug(topic)
                if ts:
                    topic_events[ts].append({
                        "id": row["event_id"],
                        "title": row["event_title"],
                        "summary": row["event_summary"] or "",
                        "date": (row["event_date"] or "")[:10],
                        "type": row["event_type"] or "event",
                        "grade": row["decision_grade"] or "",
                    })
                    for ent in entities:
                        name = _name(ent)
                        if name:
                            topic_entities[ts][name] += 1
                    if row["source_url"]:
                        topic_sources[ts].append({
                            "url": row["source_url"],
                            "publisher": row["source_name"] or "",
                        })

        track_rows = conn.execute(
            """
            SELECT topics_json, tracks_json
            FROM timeline_nodes
            WHERE status = 'public'
              AND topics_json IS NOT NULL AND topics_json != '[]'
              AND tracks_json IS NOT NULL AND tracks_json != '[]'
            """
        ).fetchall()
        for row in track_rows:
            for topic in json_list(row["topics_json"]):
                ts = _slug(topic)
                if not ts:
                    continue
                for track_slug in json_list(row["tracks_json"]):
                    track_slug = str(track_slug).strip()
                    if track_slug:
                        topic_tracks[ts][track_slug] += 1

        generated = 0
        exported = 0

        topics_dir = site_dir / "content" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)

        for topic in topics:
            slug = topic["slug"]
            canonical = topic["canonical_name"]
            events = dedupe_by_event_id(topic_events.get(slug, []))
            entities = topic_entities.get(slug, Counter())
            sources = topic_sources.get(slug, [])
            aliases = json_list(topic["aliases_json"])
            related_tracks = [track_slug for track_slug, _count in topic_tracks.get(slug, Counter()).most_common(8)]

            top_entities = [name for name, _count in entities.most_common(8)]

            # Build frontmatter
            fm = {
                "title": canonical,
                "type": "topic",
                "slug": slug,
                "aliases": aliases,
                "parent": topic["parent_slug"] or None,
                "description": topic["description"] or f"{canonical} 主题下的 AI 行业事件、实体和趋势。",
                "event_count": len(events),
                "entity_count": len(entities),
                "source_count": len(sources),
                "related_tracks": related_tracks,
                "seo": {
                    "title": f"{canonical} - neican.ai",
                    "description": f"AI 行业 {canonical} 相关事件、实体和趋势分析。",
                },
                "neican": {
                    "generated_by": "topic_product",
                    "review_status": "draft",
                },
            }

            # Build body
            body = [
                f"# {canonical}",
                "",
                *topic_hub_sections(
                    canonical,
                    topic["description"] or f"{canonical} 主题下的 AI 行业事件、实体和趋势。",
                    top_entities,
                    events,
                ),
            ]

            if events:
                body += [
                    "## 相关事件",
                    "",
                ]
                for ev in sorted(events, key=lambda e: e.get("date") or "", reverse=True)[:20]:
                    grade = ev.get("grade", "")
                    grade_badge = f"**[{grade}]** " if grade else ""
                    body.append(f"- {grade_badge}({ev['date']}) {ev['title']}")
                body.append("")

            if related_tracks:
                body += [
                    "## 相关追踪线",
                    "",
                ]
                for track_slug in related_tracks:
                    body.append(f"- [{track_slug}](/timeline/{track_slug}/)")
                body.append("")

            if sources:
                body += [
                    "## 来源统计",
                    "",
                    f"共 {len(sources)} 个来源。",
                    "",
                ]

            if aliases:
                body += [
                    "## 相关搜索词",
                    "",
                    ", ".join(aliases),
                    "",
                ]

            path = topics_dir / slug / "_index.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")
            generated += 1
            exported += 1

        # Write topics index
        index_fm = {
            "title": "主题索引",
            "type": "topic_index",
            "topic_count": len(topics),
            "seo": {"description": "neican.ai AI 行业主题索引页。"},
        }
        index_body = [
            "<div class=\"topic-index-page\">",
            "<h1>主题索引</h1>",
            "<p>按主题组织的 AI 行业事件、实体和趋势。</p>",
            "<div class=\"topic-grid\">",
        ]
        for topic in topics:
            slug = topic["slug"]
            canonical = topic["canonical_name"]
            count = len(topic_events.get(slug, []))
            index_body.append(
                f"<a href=\"/topics/{slug}/\"><b>{canonical}</b><span>{count} 事件</span></a>"
            )
        index_body += ["</div>", "</div>"]
        (topics_dir / "_index.md").write_text(
            frontmatter(index_fm, "\n".join(index_body)), encoding="utf-8"
        )

        return TopicProductResult(generated=generated, exported=exported)


def run(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR) -> TopicProductResult:
    return generate_topic_pages(db_path=db_path, site_dir=site_dir)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate topic pages from topic_registry.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
