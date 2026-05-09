from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"


@dataclass(frozen=True)
class EventProductResult:
    generated: int = 0
    exported: int = 0
    source: str = "timeline_nodes"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_catalog (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id INTEGER,
          slug TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          date TEXT,
          summary TEXT,
          event_type TEXT,
          grade TEXT,
          importance_score REAL DEFAULT 0,
          confidence REAL DEFAULT 0,
          entities_json TEXT,
          topics_json TEXT,
          claims_json TEXT,
          sources_json TEXT,
          url TEXT,
          status TEXT NOT NULL DEFAULT 'public',
          review_status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_catalog_date ON event_catalog(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_catalog_grade ON event_catalog(grade)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_catalog_type ON event_catalog(event_type)")


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def upsert(conn, item: dict[str, Any]) -> None:
    cols = list(item)
    conn.execute(
        f"""
        INSERT INTO event_catalog ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})
        ON CONFLICT(slug) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols if c != 'slug')}, updated_at=CURRENT_TIMESTAMP
        """,
        tuple(item[c] for c in cols),
    )


def generate_from_timeline_nodes(conn) -> int:
    ensure_schema(conn)
    rows = conn.execute("SELECT * FROM timeline_nodes WHERE status='public' ORDER BY date DESC, id DESC").fetchall()
    for row in rows:
        upsert(conn, {
            "event_id": row["event_id"],
            "slug": row["slug"],
            "title": row["title"],
            "date": row["date"],
            "summary": row["summary"] or row["why_it_matters"] or "",
            "event_type": row["event_type"],
            "grade": row["grade"],
            "importance_score": row["importance_score"],
            "confidence": row["confidence"],
            "entities_json": row["entities_json"],
            "topics_json": row["topics_json"],
            "claims_json": row["claims_json"],
            "sources_json": row["sources_json"],
            "url": f"/events/{row['slug']}/",
            "status": "public",
            "review_status": row["review_status"],
        })
    conn.commit()
    return len(rows)


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        try:
            _blank, fm, body = text.split("---", 2)
            return yaml.safe_load(fm) or {}, body.strip()
        except Exception:
            pass
    return {}, text


def generate_from_hugo_events(conn, site_dir: Path = SITE_DIR) -> int:
    ensure_schema(conn)
    files = sorted((site_dir / "content" / "events").glob("*.md"))
    count = 0
    for path in files:
        if path.name == "_index.md":
            continue
        fm, body = read_frontmatter(path)
        slug = str(fm.get("slug") or path.stem)
        summary = ""
        for paragraph in body.split("\n\n"):
            p = paragraph.strip()
            if p and not p.startswith("#") and "<" not in p:
                summary = p[:320]
                break
        upsert(conn, {
            "event_id": fm.get("event_id"),
            "slug": slug,
            "title": str(fm.get("title") or slug),
            "date": str(fm.get("timeline", {}).get("date") or fm.get("date") or "")[:10],
            "summary": summary,
            "event_type": str(fm.get("event_type") or "event"),
            "grade": str(fm.get("decision_grade") or ""),
            "importance_score": float(fm.get("importance_score") or 0),
            "confidence": float(fm.get("confidence") or 0),
            "entities_json": json.dumps(fm.get("entities") or [], ensure_ascii=False),
            "topics_json": json.dumps(fm.get("topics") or [], ensure_ascii=False),
            "claims_json": json.dumps(fm.get("claims") or [], ensure_ascii=False),
            "sources_json": json.dumps(fm.get("sources") or [], ensure_ascii=False),
            "url": f"/events/{slug}/",
            "status": "public",
            "review_status": (fm.get("neican") or {}).get("review_status", "draft"),
        })
        count += 1
    conn.commit()
    return count


def frontmatter(data: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("slug") or "")
    return str(value)


def export_index(conn, site_dir: Path = SITE_DIR) -> int:
    ensure_schema(conn)
    rows = conn.execute("SELECT * FROM event_catalog WHERE status='public' ORDER BY date DESC, importance_score DESC, id DESC").fetchall()
    grades = Counter(row["grade"] or "未分级" for row in rows)
    types = Counter(row["event_type"] or "event" for row in rows)
    source_count = 0
    claim_count = 0
    entity_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    for row in rows:
        sources = json_list(row["sources_json"])
        claims = json_list(row["claims_json"])
        source_count += len(sources)
        claim_count += len(claims)
        for e in json_list(row["entities_json"]):
            name = _name(e)
            if name:
                entity_counter[name] += 1
        for t in json_list(row["topics_json"]):
            name = _name(t)
            if name:
                topic_counter[name] += 1

    body = [
        "<div class=\"event-product-page\">",
        "<p class=\"eyebrow\">Event Library MVP</p>",
        "<h1>事件库：把 RSS 资讯变成可检索、可审计、可复用的行业事件</h1>",
        "<p class=\"page-lead\">事件库是 neican.ai 的核心产品层。每个事件都连接日期、类型、实体、主题、关键信息和来源；时间线、实体档案、日报与洞察都从这里派生。</p>",
        "<div class=\"event-kpis\">",
        f"<div><strong>{len(rows)}</strong><span>公开事件</span></div>",
        f"<div><strong>{grades.get('A', 0)}</strong><span>A 级事件</span></div>",
        f"<div><strong>{claim_count}</strong><span>关键信息</span></div>",
        f"<div><strong>{source_count}</strong><span>来源链接</span></div>",
        "</div>",
        "<section class=\"event-method\"><h2>从 RSS 到事件库的产品链路</h2><div class=\"schema-strip\"><span>RSS</span><i></i><span>Raw Item</span><i></i><span>Event</span><i></i><span>Decision</span><i></i><span>Timeline / Entity / Article</span></div></section>",
        "<section class=\"event-facets\"><div><h2>事件类型</h2>",
    ]
    for name, count in types.most_common(8):
        body.append(f"<p><b>{name}</b><span>{count}</span></p>")
    body.append("</div><div><h2>高频实体</h2>")
    for name, count in entity_counter.most_common(8):
        body.append(f"<p><b>{name}</b><span>{count}</span></p>")
    body.append("</div><div><h2>高频主题</h2>")
    for name, count in topic_counter.most_common(8):
        body.append(f"<p><b>{name}</b><span>{count}</span></p>")
    body.append("</div></section>")
    body.append("<section class=\"event-library-list\"><h2>事件列表</h2>")
    for row in rows:
        entities = "、".join(_name(e) for e in json_list(row["entities_json"])[:3] if _name(e))
        topics = "、".join(_name(t) for t in json_list(row["topics_json"])[:3] if _name(t))
        body.append(
            f"<article class=\"event-library-card grade-{str(row['grade']).lower()}\">"
            f"<div class=\"event-card-date\"><time>{row['date'] or ''}</time><span class=\"badge\">{row['grade'] or '—'}</span></div>"
            f"<div><p><span class=\"chip\">{row['event_type'] or 'event'}</span></p>"
            f"<h3><a href=\"{row['url']}\">{row['title']}</a></h3>"
            f"<p>{row['summary'] or ''}</p>"
            f"<small>{'实体：' + entities if entities else ''}{' · 主题：' + topics if topics else ''}</small></div></article>"
        )
    body += ["</section>", "</div>"]
    fm = {"title": "事件库", "type": "event_index", "event_count": len(rows), "seo": {"description": "neican.ai 自动生成的结构化 AI 行业事件库。"}}
    path = site_dir / "content" / "events" / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")
    return len(rows)


def run(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR) -> EventProductResult:
    with get_conn(db_path) as conn:
        generated = generate_from_timeline_nodes(conn)
        source = "timeline_nodes"
        if generated == 0:
            generated = generate_from_hugo_events(conn, site_dir=site_dir)
            source = "hugo-events"
        exported = export_index(conn, site_dir=site_dir)
    return EventProductResult(generated=generated, exported=exported, source=source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate event_catalog and export event library index.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
