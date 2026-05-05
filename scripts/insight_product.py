from __future__ import annotations

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


@dataclass(frozen=True)
class InsightProductResult:
    generated: int = 0
    exported: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "insight"


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _entity_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("name") or entity.get("slug") or "")
    return str(entity)


def _slug_to_name(slug: str) -> str:
    """Convert a kebab-case slug to a human-readable name using topic_registry."""
    try:
        from topic_registry import fix_acronyms
        name = slug.replace("-", " ").title()
        return fix_acronyms(name)
    except Exception:
        return slug.replace("-", " ").title()


def _claim_text(claim: Any) -> str:
    if not isinstance(claim, dict):
        return ""
    return str(claim.get("statement") or claim.get("claim_text") or claim.get("text") or "").strip()


def _valid_date(value: str) -> str:
    text = (value or "")[:10]
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return ""
    if parsed.year <= 1900:
        return ""
    return text


def _insight_date(events: list[Any]) -> str:
    dates = [_valid_date(str(event["event_date"] or "")) for event in events]
    dates = [date for date in dates if date]
    return f"{max(dates)}T09:00:00+08:00" if dates else datetime.now().strftime("%Y-%m-%dT09:00:00+08:00")


def frontmatter(data: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def generate_insight_pages(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR) -> InsightProductResult:
    with get_conn(db_path) as conn:
        candidates = conn.execute("SELECT * FROM insight_candidates WHERE status = 'proposed' ORDER BY confidence DESC").fetchall()
        if not candidates:
            return InsightProductResult()
        generated = exported = 0
        for candidate in candidates:
            event_ids = json_list(candidate["evidence_event_ids_json"])
            entity_slugs = json_list(candidate["entity_slugs_json"])
            topic_slugs = json_list(candidate["topic_slugs_json"])
            if not event_ids:
                continue
            placeholders = ",".join("?" for _ in event_ids)
            events = conn.execute(
                f"SELECT e.*, d.decision_grade, r.source_url, r.title AS source_title, s.name AS source_name "
                f"FROM events e LEFT JOIN decisions d ON d.event_id = e.id "
                f"LEFT JOIN raw_items r ON r.id = e.raw_item_id LEFT JOIN sources s ON s.id = r.source_id "
                f"WHERE e.id IN ({placeholders}) ORDER BY e.event_date DESC",
                tuple(event_ids),
            ).fetchall()
            if not events:
                continue
            slug = slugify(f"{candidate['track_slug']}-insight-{candidate['id']}")
            title = candidate["proposed_title"]
            thesis = candidate["thesis"] or ""
            insight_date = _insight_date(list(events))
            all_entity_objs: list[dict[str, str]] = []
            all_entity_slugs_seen: set[str] = set()
            all_sources: list[dict[str, str]] = []
            all_claims: list[dict[str, Any]] = []
            for event in events:
                for ent in json_list(event["entities_json"]):
                    if not isinstance(ent, dict):
                        continue
                    ent_slug = str(ent.get("slug") or "")
                    if ent_slug and ent_slug not in all_entity_slugs_seen:
                        all_entity_slugs_seen.add(ent_slug)
                        all_entity_objs.append({
                            "slug": ent_slug,
                            "name": str(ent.get("name") or ent_slug),
                            "type": str(ent.get("type") or "entity"),
                        })
                source = {"url": event["source_url"] or "", "title": event["source_title"] or event["event_title"], "publisher": event["source_name"] or ""}
                if source["url"] and source["url"] not in [s["url"] for s in all_sources]:
                    all_sources.append(source)
                for claim in json_list(event["claims_json"]):
                    text = _claim_text(claim)
                    if text:
                        all_claims.append({"text": text, "confidence": claim.get("confidence", 0) if isinstance(claim, dict) else 0})

            topic_objs = [{"slug": s, "name": _slug_to_name(s)} for s in topic_slugs]

            fm = {
                "title": title, "date": insight_date, "type": "insight", "track_slug": candidate["track_slug"],
                "evidence_event_ids": event_ids, "entities": all_entity_objs[:10], "topics": topic_objs,
                "claims": all_claims[:10], "sources": all_sources[:10], "confidence": candidate["confidence"],
                "seo": {"title": title[:60], "description": thesis[:150], "structured_data": "Article"},
                "neican": {"generated_by": "insight_product", "review_status": "draft", "candidate_id": candidate["id"]},
            }
            top_events = list(events)[:5]
            body = [
                f"# {title}", "",
                "## 核心判断", "",
                thesis or "这组事件显示相关 AI 主题正在出现值得持续跟踪的结构性变化。", "",
                "## 发生了什么", "",
            ]
            for event in top_events:
                grade = event["decision_grade"] or ""
                date = (event["event_date"] or "")[:10]
                body.append(f"- **[{grade}]** ({date}) {event['event_title']}")
                if event["event_summary"]:
                    body.append(f"  {event['event_summary'][:200]}")
            entity_names = [e["name"] for e in all_entity_objs[:8]]
            body += ["", "## 为什么重要", "",
                      "这些事件的共同价值不在于单条新闻本身，而在于它们指向同一条可追踪的产业变化线。编辑判断应优先解释结构变化、受影响对象和后续验证信号，而不是堆叠全部证据。", ""]
            if entity_names:
                body += ["## 影响谁", "", "、".join(entity_names), ""]
            body += [
                "## 证据链",
                "",
                f"本洞察压缩展示 {len(top_events)} 个关键事件；其余证据保留在结构化事件和来源中，避免把文章写成全量聚合清单。",
                "",
            ]
            if all_claims:
                for c in all_claims[:8]:
                    conf = round(float(c.get("confidence", 0)) * 100)
                    body.append(f"- {c['text']}（{conf}%）")
                body.append("")
            body += ["## 反向信号", "",
                      "- 后续关键实体没有产品、客户、生态或政策层面的连续动作。",
                      "- 新来源显示这些事件只是短期发布节奏，而不是结构变化。",
                      "- 高可信来源否定或削弱了核心事实链。", "",
                      "## 下一步观察", "",
                      f"- 观察「{candidate['track_slug']}」追踪线是否持续产生新证据。",
                      "- 关注关键实体是否有后续产品、策略或市场变化。",
                      "- 如有新 A 级事件，考虑更新本洞察。", ""]
            if all_sources:
                body += ["## 来源", ""]
                for s in all_sources:
                    pub = f" · {s['publisher']}" if s.get("publisher") else ""
                    body.append(f"- [{s['title']}]({s['url']}){pub}")

            path = site_dir / "content" / "insights" / f"{slug}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(frontmatter(fm, "\n".join(body)), encoding="utf-8")
            conn.execute("UPDATE insight_candidates SET status = 'draft', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (candidate["id"],))
            generated += 1
            exported += 1
        conn.commit()
        return InsightProductResult(generated=generated, exported=exported)


def run(db_path: Path = DB_PATH, site_dir: Path = SITE_DIR) -> InsightProductResult:
    return generate_insight_pages(db_path=db_path, site_dir=site_dir)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    r = run()
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(r)


if __name__ == "__main__":
    main()
