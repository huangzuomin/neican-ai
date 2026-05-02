from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"

PUBLIC_GRADES = {"A", "B"}
INTERNAL_GRADES = {"C"}


@dataclass(frozen=True)
class TimelineResult:
    generated: int = 0
    exported_events: int = 0
    exported_years: int = 0
    skipped: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_nodes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id INTEGER NOT NULL UNIQUE,
          date TEXT NOT NULL,
          year TEXT NOT NULL,
          month TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          summary TEXT,
          why_it_matters TEXT,
          event_type TEXT,
          grade TEXT NOT NULL,
          importance_score REAL DEFAULT 0,
          confidence REAL DEFAULT 0,
          risk_score REAL DEFAULT 0,
          entities_json TEXT,
          topics_json TEXT,
          claims_json TEXT,
          sources_json TEXT,
          status TEXT NOT NULL DEFAULT 'public',
          review_status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_nodes_date ON timeline_nodes(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_nodes_year ON timeline_nodes(year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_nodes_grade ON timeline_nodes(grade)")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80].strip("-") or "event"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    # RSS style: Fri, 01 May 2026 12:34:56 GMT
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%d %b %Y %H:%M:%S %Z", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    match = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", value)
    if match:
        try:
            return datetime.strptime(" ".join(match.groups()), "%d %b %Y").strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def _topic_name(topic: Any) -> str:
    if isinstance(topic, dict):
        return str(topic.get("name") or topic.get("slug") or "").strip()
    return str(topic).strip()


def _entity_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("name") or entity.get("slug") or "").strip()
    return str(entity).strip()


def _claim_text(claim: Any) -> str:
    if not isinstance(claim, dict):
        return ""
    return str(claim.get("statement") or claim.get("claim_text") or claim.get("text") or "").strip()


def source_from_row(row) -> dict[str, str]:
    return {
        "url": row["source_url"] or "",
        "title": row["source_title"] or row["event_title"] or "",
        "publisher": row["source_name"] or "",
        "date": row["source_date"] or row["event_date"] or "",
    }


def why_it_matters(row, entities: list[Any], topics: list[Any], claims: list[Any]) -> str:
    entity_names = [name for name in (_entity_name(e) for e in entities) if name]
    topic_names = [name for name in (_topic_name(t) for t in topics) if name]
    parts = []
    if entity_names:
        parts.append(f"涉及 {'、'.join(entity_names[:3])} 等关键实体")
    if topic_names:
        parts.append(f"关联 {'、'.join(topic_names[:3])} 主题")
    if row["decision_grade"] == "A":
        parts.append("编辑判断为 A 级，适合作为独立洞察与长期时间线节点")
    elif row["decision_grade"] == "B":
        parts.append("编辑判断为 B 级，适合进入日报并沉淀为趋势信号")
    if claims:
        valid_claims = [_claim_text(c) for c in claims if _claim_text(c)]
        if valid_claims:
            parts.append(f"已抽取 {len(valid_claims)} 条结构化声明")
    return "；".join(parts) + "。" if parts else "该事件具备后续跟踪价值，已进入 neican.ai 时间线。"


def fetch_timeline_candidates(conn, include_internal: bool = False) -> list[Any]:
    grades = sorted(PUBLIC_GRADES | (INTERNAL_GRADES if include_internal else set()))
    placeholders = ",".join("?" for _ in grades)
    return conn.execute(
        f"""
        SELECT
          events.*,
          decisions.decision_grade,
          decisions.need_review,
          decisions.reason,
          raw_items.source_url,
          raw_items.title AS source_title,
          raw_items.published_at AS source_date,
          sources.name AS source_name
        FROM decisions
        JOIN events ON events.id = decisions.event_id
        JOIN raw_items ON raw_items.id = events.raw_item_id
        LEFT JOIN sources ON sources.id = raw_items.source_id
        WHERE decisions.decision_grade IN ({placeholders})
          AND events.event_date IS NOT NULL
        ORDER BY events.event_date DESC, events.id DESC
        """,
        tuple(grades),
    ).fetchall()


def generate_nodes(conn, include_internal: bool = False) -> tuple[int, int]:
    ensure_schema(conn)
    generated = 0
    skipped = 0
    for row in fetch_timeline_candidates(conn, include_internal=include_internal):
        date = normalize_date(row["event_date"] or row["source_date"])
        if not date:
            skipped += 1
            continue
        grade = row["decision_grade"]
        status = "public" if grade in PUBLIC_GRADES else "internal"
        entities = json_list(row["entities_json"])
        topics = json_list(row["topics_json"])
        claims = json_list(row["claims_json"])
        source = source_from_row(row)
        slug = f"{date}-{slugify(row['event_title'])}-{row['id']}"
        node = {
            "event_id": row["id"],
            "date": date,
            "year": date[:4],
            "month": date[:7],
            "slug": slug,
            "title": row["event_title"],
            "summary": row["event_summary"] or "",
            "why_it_matters": why_it_matters(row, entities, topics, claims),
            "event_type": row["event_type"] or "event",
            "grade": grade,
            "importance_score": float(row["importance_score"] or 0),
            "confidence": float(row["confidence"] or 0),
            "risk_score": float(row["risk_score"] or 0),
            "entities_json": json.dumps(entities, ensure_ascii=False),
            "topics_json": json.dumps(topics, ensure_ascii=False),
            "claims_json": json.dumps(claims, ensure_ascii=False),
            "sources_json": json.dumps([source] if source.get("url") else [], ensure_ascii=False),
            "status": status,
            "review_status": "needs_review" if row["need_review"] else "draft",
        }
        cols = list(node)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "event_id") + ", updated_at=CURRENT_TIMESTAMP"
        conn.execute(
            f"""
            INSERT INTO timeline_nodes ({', '.join(cols)})
            VALUES ({', '.join('?' for _ in cols)})
            ON CONFLICT(event_id) DO UPDATE SET {updates}
            """,
            tuple(node[c] for c in cols),
        )
        generated += 1
    conn.commit()
    return generated, skipped


def frontmatter(data: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def write_event_page(site_dir: Path, row) -> None:
    entities = json_list(row["entities_json"])
    topics = json_list(row["topics_json"])
    claims = json_list(row["claims_json"])
    sources = json_list(row["sources_json"])
    fm = {
        "title": row["title"],
        "date": f"{row['date']}T09:00:00+08:00",
        "slug": row["slug"],
        "type": "event",
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "decision_grade": row["grade"],
        "importance_score": row["importance_score"],
        "confidence": row["confidence"],
        "entities": entities,
        "topics": topics,
        "claims": claims,
        "sources": sources,
        "timeline": {"date": row["date"], "year": row["year"], "month": row["month"]},
        "neican": {"generated_by": "timeline_product", "review_status": row["review_status"]},
    }
    body = [
        f"# {row['title']}",
        "",
        "## 时间线判断",
        "",
        row["why_it_matters"] or "该事件已进入 neican.ai 时间线。",
        "",
        "## 事件摘要",
        "",
        row["summary"] or "事件摘要仍在补充。",
        "",
    ]
    valid_claims = [_claim_text(c) for c in claims if _claim_text(c)]
    if valid_claims:
        body += ["## 结构化声明", ""] + [f"- {text}" for text in valid_claims[:8]] + [""]
    if sources:
        body += ["## 来源", ""] + [f"- [{s.get('title') or s.get('url')}]({s.get('url')})" for s in sources if s.get("url")]
    path = site_dir / "content" / "events" / f"{row['slug']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")


def write_year_page(site_dir: Path, year: str, rows: list[Any]) -> None:
    months: dict[str, list[Any]] = {}
    for row in rows:
        months.setdefault(row["month"], []).append(row)
    fm = {
        "title": f"{year} 年 AI 行业时间线",
        "type": "timeline_year",
        "year": year,
        "event_count": len(rows),
        "seo": {"description": f"{year} 年 AI 行业关键事件、实体、主题与结构化声明时间线。"},
    }
    body = [
        "<div class=\"timeline-product-page\">",
        f"<p class=\"eyebrow\">{year} Timeline</p>",
        f"<h1>{year} 年 AI 行业时间线</h1>",
        f"<p class=\"page-lead\">本页由 neican.ai 从结构化事件库自动生成，共收录 {len(rows)} 个 A/B 级时间线节点。</p>",
        "<div class=\"timeline-node-list\">",
    ]
    for month in sorted(months, reverse=True):
        body.append(f"<h2>{month}</h2>")
        for row in months[month]:
            body.append(
                f"<article class=\"timeline-node grade-{row['grade'].lower()}\">"
                f"<time>{row['date']}</time><div><p><span class=\"badge\">{row['grade']}</span> <span class=\"chip\">{row['event_type']}</span></p>"
                f"<h3><a href=\"/events/{row['slug']}/\">{row['title']}</a></h3>"
                f"<p>{row['why_it_matters'] or row['summary'] or ''}</p></div></article>"
            )
    body += ["</div>", "</div>"]
    path = site_dir / "content" / "timeline" / year / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")


def write_index_page(site_dir: Path, rows: list[Any]) -> None:
    years = sorted({row["year"] for row in rows}, reverse=True)
    grade_counts = {"A": 0, "B": 0}
    for row in rows:
        grade_counts[row["grade"]] = grade_counts.get(row["grade"], 0) + 1
    fm = {
        "title": "AI 行业时间线",
        "type": "timeline",
        "event_count": len(rows),
        "seo": {"description": "neican.ai 从 RSS 到结构化事件自动生成的 AI 行业关键事件时间线。"},
    }
    body = [
        "<div class=\"timeline-product-page\">",
        "<p class=\"eyebrow\">Timeline Product MVP</p>",
        "<h1>从资讯噪音到 AI 行业演化地图</h1>",
        "<p class=\"page-lead\">这不是静态专题页，而是由 RSS → Event → Decision → Timeline Node 自动生成的时间线产品。公开页只展示 A/B 级节点，C/D 级不会制造噪音。</p>",
        "<div class=\"timeline-kpis\">",
        f"<div><strong>{len(rows)}</strong><span>公开节点</span></div>",
        f"<div><strong>{grade_counts.get('A', 0)}</strong><span>A 级关键事件</span></div>",
        f"<div><strong>{grade_counts.get('B', 0)}</strong><span>B 级趋势信号</span></div>",
        f"<div><strong>{len(years)}</strong><span>覆盖年份</span></div>",
        "</div>",
        "<section class=\"timeline-years\"><h2>按年份浏览</h2><div>",
    ]
    for year in years:
        count = sum(1 for row in rows if row["year"] == year)
        body.append(f"<a href=\"/timeline/{year}/\"><b>{year}</b><span>{count} 个节点</span></a>")
    body += ["</div></section>", "<section class=\"timeline-node-list\"><h2>最新节点</h2>"]
    for row in rows[:24]:
        body.append(
            f"<article class=\"timeline-node grade-{row['grade'].lower()}\">"
            f"<time>{row['date']}</time><div><p><span class=\"badge\">{row['grade']}</span> <span class=\"chip\">{row['event_type']}</span></p>"
            f"<h3><a href=\"/events/{row['slug']}/\">{row['title']}</a></h3>"
            f"<p>{row['why_it_matters'] or row['summary'] or ''}</p></div></article>"
        )
    body += ["</section>", "</div>"]
    path = site_dir / "content" / "timeline" / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")


def export_hugo(conn, site_dir: Path = SITE_DIR) -> tuple[int, int]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT * FROM timeline_nodes
        WHERE status = 'public'
        ORDER BY date DESC, importance_score DESC, id DESC
        """
    ).fetchall()
    events_dir = site_dir / "content" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    for old in events_dir.glob("*.md"):
        if old.name != "_index.md":
            old.unlink()
    for row in rows:
        write_event_page(site_dir, row)
    by_year: dict[str, list[Any]] = {}
    for row in rows:
        by_year.setdefault(row["year"], []).append(row)
    for year, year_rows in by_year.items():
        write_year_page(site_dir, year, year_rows)
    write_index_page(site_dir, rows)
    return len(rows), len(by_year)


def run(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR, include_internal: bool = False) -> TimelineResult:
    with get_conn(db_path) as conn:
        generated, skipped = generate_nodes(conn, include_internal=include_internal)
        exported_events, exported_years = export_hugo(conn, site_dir=site_dir)
    return TimelineResult(generated=generated, exported_events=exported_events, exported_years=exported_years, skipped=skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate timeline_nodes and export timeline/event Hugo pages.")
    parser.add_argument("--include-internal", action="store_true", help="Also create internal C-grade nodes, not exported publicly.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(include_internal=args.include_internal)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
