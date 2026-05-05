from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
MEMORY_DIR = ROOT / "memory-wiki"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class ExportResult:
    daily_briefs: int = 0
    insights: int = 0
    skipped_approved: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "daily_briefs": self.daily_briefs,
            "failed_count": self.failed_count,
            "insights": self.insights,
            "skipped_approved": self.skipped_approved,
        }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def normalize_topics(topics: list[Any]) -> list[dict[str, str]]:
    normalized = []
    for topic in topics:
        if isinstance(topic, dict):
            slug = topic.get("slug") or slugify(str(topic.get("name", "")))
            name = topic.get("name") or slug
        else:
            slug = str(topic)
            name = slug.replace("-", " ")
        normalized.append({"slug": slug, "name": name})
    return normalized


def normalize_claims(claims: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        statement = (claim.get("statement") or claim.get("text") or claim.get("claim_text") or "").strip()
        sources = claim.get("sources") or ([claim.get("source_url")] if claim.get("source_url") else [])
        if not statement or not sources:
            continue
        normalized.append(
            {
                "statement": statement,
                "confidence": float(claim.get("confidence", 0.0)),
                "sources": sources,
                "status": claim.get("status", "active"),
            }
        )
    return normalized


def frontmatter_block(frontmatter: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_text}---\n\n{body.strip()}\n"


def approved_file(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    try:
        _blank, frontmatter, _body = text.split("---", 2)
        data = yaml.safe_load(frontmatter) or {}
    except ValueError:
        return False
    return (data.get("neican") or {}).get("review_status") == "approved"


def fetch_rows(conn, date: str, grades: tuple[str, ...]):
    """Fetch decisions for events matching date. Handles both ISO and RSS date formats."""
    placeholders = ", ".join("?" for _ in grades)
    # Try matching both ISO format (2026-05-01...) and RSS format (...01 May 2026...)
    # We parse the target date and match the day portion
    iso_prefix = f"{date}%"
    # Also try matching the month-day pattern in RSS format (e.g. "30 Apr 2026")
    from datetime import datetime as _dt
    try:
        target = _dt.strptime(date, "%Y-%m-%d")
        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        rss_pattern = f"%{target.day:02d} {month_names[target.month-1]} {target.year}%"
    except Exception:
        rss_pattern = None

    sql = f"""
        SELECT
          decisions.id AS decision_id,
          decisions.decision_grade,
          decisions.action,
          decisions.status AS decision_status,
          events.*,
          raw_items.source_url,
          raw_items.title AS source_title,
          raw_items.published_at AS source_date,
          sources.name AS source_name
        FROM decisions
        JOIN events ON events.id = decisions.event_id
        JOIN raw_items ON raw_items.id = events.raw_item_id
        LEFT JOIN sources ON sources.id = raw_items.source_id
        WHERE decisions.status = 'pending'
          AND decisions.decision_grade IN ({placeholders})
          AND (
            events.event_date LIKE ?
            {f'OR events.event_date LIKE ?' if rss_pattern else ''}
          )
        ORDER BY events.id
        """
    params = list(grades) + [iso_prefix]
    if rss_pattern:
        params.append(rss_pattern)
    return conn.execute(sql, tuple(params)).fetchall()


def source_from_row(row) -> dict[str, str]:
    return {
        "url": row["source_url"] or "",
        "title": row["source_title"] or row["event_title"],
        "publisher": row["source_name"] or "",
        "date": row["source_date"] or row["event_date"] or "",
    }


def _get_llm_client() -> tuple[OpenAI, str] | None:
    api_key = os.getenv("LLM_API_KEY_CONTENT") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL_CONTENT") or os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL_CONTENT") or os.getenv("LLM_MODEL")
    if not api_key or not base_url or not model:
        return None
    return OpenAI(api_key=api_key, base_url=base_url), model


def _topic_name(topic: dict[str, str]) -> str:
    return topic.get("name", "").replace("-", " ").upper() if topic.get("slug") == "llm" else topic.get("name", "")


def _claims_markdown(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "- 当前结构化 claim 仍在补充，暂以事件摘要与来源为准。"
    lines = []
    for claim in claims[:5]:
        conf = round(float(claim.get("confidence", 0.0)) * 100)
        lines.append(f"- {claim['statement']}（置信度 {conf}%）")
    return "\n".join(lines)


def _source_markdown(sources: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- [{source['title']}]({source['url']})"
        + (f" · {source['publisher']}" if source.get("publisher") else "")
        for source in sources
        if source.get("url")
    ) or "- 暂无来源索引"


def _fallback_daily_body(date: str, rows: list[Any]) -> str:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        topics = normalize_topics(json_list(row["topics_json"]))
        key = topics[0]["name"] if topics else "未分类"
        grouped.setdefault(key, []).append(row)

    key_judgment = f"今日共跟踪 {len(rows)} 条 B/C 级事件，重点集中在 " + "、".join(list(grouped)[:3]) + "。"
    sections = [f"# AI 内参日报：{date}", "", "## 今日关键判断", "", key_judgment, ""]
    for topic_name, topic_rows in grouped.items():
        sections.extend([f"## {topic_name}", ""])
        for row in topic_rows:
            summary = (row["event_summary"] or row["event_title"] or "").strip()
            sections.append(f"- **{row['event_title']}**：{summary}")
        sections.append("")

    sections.extend([
        "## 值得跟踪",
        "",
        *[f"- 持续观察 **{row['event_title']}** 后续是否带来产品、生态或竞争格局变化。" for row in rows[:3]],
        "",
        "## 来源索引",
        "",
        *[f"- [{row['source_title'] or row['event_title']}]({row['source_url']})" for row in rows if row['source_url']],
    ])
    return "\n".join(sections).strip() + "\n"


def _fallback_insight_body(title: str, summary: str, entities: list[dict[str, Any]], topics: list[dict[str, str]], claims: list[dict[str, Any]], sources: list[dict[str, str]]) -> str:
    entity_names = "、".join(entity.get("name", "") for entity in entities[:3] if entity.get("name")) or "相关参与方"
    topic_names = "、".join(_topic_name(topic) for topic in topics[:3] if topic.get("name")) or "AI 行业"
    sections = [
        f"# {title}",
        "",
        "## 核心判断",
        "",
        f"这条事件不只是单点更新，它更像是 **{entity_names}** 在 **{topic_names}** 方向上的一次明确信号。{summary or '当前已知信息显示，该变化值得继续跟踪。'}",
        "",
        "## 事件摘要",
        "",
        summary or "当前事件摘要仍在补充。",
        "",
        "## 为什么值得关注",
        "",
        f"- 事件涉及 {entity_names}，具备持续跟踪价值。\n- 其影响不止于功能更新，还可能反映产品路线、竞争格局或市场节奏变化。\n- 从 neican.ai 的编辑标准看，这类事件适合沉淀为后续主题页、实体页和时间线素材。",
        "",
        "## 关键信号",
        "",
        _claims_markdown(claims),
        "",
        "## 后续观察点",
        "",
        f"- 观察 {entity_names} 是否继续释放更完整的产品、商业化或生态信息。\n- 观察该事件是否引发同类厂商跟进。\n- 观察其是否需要同步更新相关 topic / entity 资产。",
        "",
        "## 来源",
        "",
        _source_markdown(sources),
    ]
    return "\n".join(sections).strip() + "\n"


def _llm_generate_json(prompt: str, system_prompt: str, llm: tuple[OpenAI, str] | None) -> dict[str, Any] | None:
    if not llm:
        return None
    client, model = llm
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=int(os.getenv("LLM_MAX_TOKENS_CONTENT", os.getenv("LLM_MAX_TOKENS", "2048"))),
            temperature=float(os.getenv("LLM_TEMPERATURE_CONTENT", os.getenv("LLM_TEMPERATURE", "0.4"))),
            timeout=int(os.getenv("LLM_TIMEOUT_CONTENT", os.getenv("LLM_TIMEOUT", "60"))),
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None


def build_daily(date: str, rows, llm: tuple[OpenAI, str] | None = None) -> tuple[dict[str, Any], str]:
    title = f"AI 内参日报：{date}"
    frontmatter = {
        "title": title,
        "date": f"{date}T18:00:00+08:00",
        "slug": date,
        "type": "daily_brief",
        "covered_events": [f"event_{row['id']}" for row in rows],
        "seo": {
            "title": f"AI 内参日报 {date}",
            "description": f"{date} AI 行业关键事件摘要与编辑判断。",
            "structured_data": "Article",
            "noindex": False,
        },
        "neican": {
            "generated_by": "openclaw",
            "review_status": "draft",
        },
    }
    prompt_rows = [
        {
            "title": row["event_title"],
            "summary": row["event_summary"],
            "topics": normalize_topics(json_list(row["topics_json"])),
            "source_url": row["source_url"],
        }
        for row in rows
    ]
    prompt = json.dumps({"date": date, "events": prompt_rows}, ensure_ascii=False)
    generated = _llm_generate_json(
        prompt,
        "你是 neican.ai 的日报编辑。返回 JSON：{body_markdown:string}。正文必须包含“今日关键判断”“值得跟踪”“来源索引”等二级标题，不要编造事实。",
        llm,
    )
    body = generated.get("body_markdown") if isinstance(generated, dict) else None
    if not body:
        body = _fallback_daily_body(date, list(rows))
    return frontmatter, body


def build_insight(row, llm: tuple[OpenAI, str] | None = None) -> tuple[str, dict[str, Any], str]:
    slug = slugify(row["event_title"])
    entities = json_list(row["entities_json"])
    topics = normalize_topics(json_list(row["topics_json"]))
    claims = normalize_claims(json_list(row["claims_json"]))
    title = row["event_title"]
    sources = [source_from_row(row)]
    frontmatter = {
        "title": title,
        "date": f"{(row['event_date'] or '2026-05-01')[:10]}T10:00:00+08:00",
        "slug": slug,
        "type": "insight",
        "decision_grade": row["decision_grade"],
        "event_type": row["event_type"] or "other",
        "entities": entities,
        "topics": topics,
        "sources": sources,
        "claims": claims,
        "seo": {
            "title": title[:60],
            "description": (row["event_summary"] or title)[:150],
            "structured_data": "NewsArticle",
            "noindex": False,
        },
        "neican": {
            "event_id": str(row["id"]),
            "decision_id": str(row["decision_id"]),
            "generated_by": "openclaw",
            "review_status": "draft",
        },
    }
    prompt = json.dumps(
        {
            "title": title,
            "summary": row["event_summary"],
            "entities": entities,
            "topics": topics,
            "claims": claims,
            "sources": sources,
        },
        ensure_ascii=False,
    )
    generated = _llm_generate_json(
        prompt,
        "你是 neican.ai 的洞察编辑。返回 JSON：{body_markdown:string}。正文必须包含“核心判断”“事件摘要”“为什么值得关注”“关键信号”“后续观察点”“来源”等二级标题。不要编造事实，判断必须建立在输入来源上。",
        llm,
    )
    body = generated.get("body_markdown") if isinstance(generated, dict) else None
    if not body:
        body = _fallback_insight_body(title, row["event_summary"] or "", entities, topics, claims, sources)
    return slug, frontmatter, body


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_run(conn, status: str, result: ExportResult, errors: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('hugo_export', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            "\n".join(errors) if errors else None,
        ),
    )


def export_hugo(
    db_path: Path = DB_PATH,
    site_dir: Path = SITE_DIR,
    memory_dir: Path = MEMORY_DIR,
    date: str | None = None,
    mock: bool = False,
    dry_run: bool = False,
) -> ExportResult:
    if date is None:
        raise SystemExit("--date is required")
    db_path = Path(db_path)
    site_dir = Path(site_dir)
    memory_dir = Path(memory_dir)
    if not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    daily_briefs = 0
    insights = 0
    skipped_approved = 0
    failed_count = 0
    errors: list[str] = []

    llm = None if mock else _get_llm_client()

    with get_conn(db_path) as conn:
        daily_rows = fetch_rows(conn, date, ("B", "C"))
        if daily_rows:
            frontmatter, body = build_daily(date, daily_rows, llm=llm)
            content = frontmatter_block(frontmatter, body)
            daily_path = site_dir / "content" / "briefs" / "daily" / f"{date}.md"
            if not dry_run:
                write_file(daily_path, content)
            daily_briefs = 1

        for row in fetch_rows(conn, date, ("A",)):
            try:
                slug, frontmatter, body = build_insight(row, llm=llm)
                content = frontmatter_block(frontmatter, body)
                insight_path = site_dir / "content" / "insights" / f"{slug}.md"
                memory_path = memory_dir / "drafts" / f"{slug}.md"
                if approved_file(insight_path):
                    skipped_approved += 1
                    continue
                if not dry_run:
                    write_file(insight_path, content)
                    write_file(memory_path, content)
                insights += 1
            except Exception as exc:
                failed_count += 1
                errors.append(f"decision_id={row['decision_id']}: {exc}")

        result = ExportResult(daily_briefs, insights, skipped_approved, failed_count)
        if not dry_run:
            if failed_count and daily_briefs == 0 and insights == 0:
                status = "failed"
            elif failed_count:
                status = "partial_failed"
            else:
                status = "success"
            write_run(conn, status, result, errors)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Hugo Markdown content.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--mock", action="store_true", help="Legacy flag, now ignored")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = export_hugo(date=args.date, mock=args.mock, dry_run=args.dry_run)
    print(
        "[OK] export_hugo "
        f"daily_briefs={result.daily_briefs} "
        f"insights={result.insights} "
        f"skipped_approved={result.skipped_approved} "
        f"failed={result.failed_count}"
    )


if __name__ == "__main__":
    main()
