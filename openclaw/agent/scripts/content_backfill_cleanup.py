from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "hugo-site"
ALLOWLIST_PATH = ROOT / "config" / "entity_allowlist.yaml"
EDITORIAL_RULES_PATH = ROOT / "config" / "editorial_rules.yaml"


@dataclass(frozen=True)
class CleanupResult:
    removed_entities: int = 0
    filtered_daily_lines: int = 0
    removed_insights: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---"):
        try:
            _blank, fm, body = text.split("---", 2)
            return yaml.safe_load(fm) or {}, body.lstrip()
        except ValueError:
            return {}, text
    return {}, text


def frontmatter_block(frontmatter: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def approved_entity_slugs(allowlist_path: Path) -> dict[str, str]:
    data = load_yaml(allowlist_path)
    approved: dict[str, str] = {}
    for item in data.get("approved_entities", []) or []:
        if isinstance(item, dict) and item.get("slug"):
            approved[str(item["slug"])] = str(item.get("name") or item["slug"])
    return approved


def blocked_keywords(editorial_rules_path: Path) -> list[str]:
    rules = load_yaml(editorial_rules_path)
    gate = rules.get("ai_relevance_gate") or {}
    words = [str(word) for word in gate.get("exclusion_keywords", []) or []]
    words += [
        "港交所", "黄金期货", "电影票房", "汽车滚装船", "环球音乐", "威马汽车",
        "KOSPI", "美联储", "五一", "五一假期", "五一档", "英派药业",
        "Yotta", "IPO", "Bitcoin", "比特币", "伊利股份", "陈发树",
        "白宫拟在AI模型发布前实施审查", "模型发布前实施审查",
        "马斯克就推特", "美证监会", "诉讼", "红果短剧", "短剧收费",
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        key = word.lower()
        if key not in seen:
            seen.add(key)
            unique.append(word)
    return unique


def contains_blocked(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def title_key(line: str) -> str:
    text = re.sub(r"\[[A-D]\]", "", line)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())).strip()


def clean_entities(site_dir: Path, allowlist_path: Path, keywords: list[str]) -> int:
    approved = approved_entity_slugs(allowlist_path)
    entities_dir = site_dir / "content" / "entities"
    if not entities_dir.exists():
        return 0
    removed = 0
    for child in entities_dir.iterdir():
        if not child.is_dir():
            continue
        if not (child / "_index.md").exists():
            continue
        if child.name not in approved:
            shutil.rmtree(child)
            removed += 1
        else:
            rewrite_entity_page(child / "_index.md", keywords)

    index_body = [
        "<div class=\"entity-product-page\">",
        "<p class=\"eyebrow\">Entity Files</p>",
        "<h1>实体档案库</h1>",
        "<p class=\"page-lead\">这里只展示经过 allowlist 或质量闸门确认的核心 AI 行业实体。</p>",
        "<div class=\"entity-profile-grid\">",
    ]
    entity_count = 0
    for slug, name in sorted(approved.items(), key=lambda item: item[1].lower()):
        if (entities_dir / slug / "_index.md").exists():
            index_body.append(f"<a href=\"/entities/{slug}/\"><b>{name}</b><small>approved</small></a>")
            entity_count += 1
    index_body += ["</div>", "</div>"]
    (entities_dir / "_index.md").write_text(
        frontmatter_block(
            {"title": "实体档案", "type": "entity_index", "entity_count": entity_count},
            "\n".join(index_body),
        ),
        encoding="utf-8",
    )
    return removed


def clean_daily_briefs(site_dir: Path, keywords: list[str]) -> int:
    daily_dir = site_dir / "content" / "briefs" / "daily"
    if not daily_dir.exists():
        return 0
    filtered = 0
    for path in sorted(daily_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
        kept: list[str] = []
        seen_titles: set[str] = set()
        skip_continuation = False
        allow_continuation = False
        continuation_count = 0
        for line in body.splitlines():
            is_continuation = line.startswith("  ") or line.startswith("\t")
            if is_continuation and line.strip():
                continuation_count += 1
                if continuation_count > 1:
                    filtered += 1
                    continue
            if skip_continuation and is_continuation and line.strip():
                filtered += 1
                continue
            if is_continuation and line.strip() and not allow_continuation:
                filtered += 1
                continue
            if not is_continuation:
                skip_continuation = False
                allow_continuation = False
                continuation_count = 0
            if contains_blocked(line, keywords):
                filtered += 1
                if line.lstrip().startswith("-"):
                    skip_continuation = True
                continue
            if line.startswith("## "):
                seen_titles = set()
            if line.lstrip().startswith("-"):
                key = title_key(line)
                if key and key in seen_titles:
                    filtered += 1
                    skip_continuation = True
                    continue
                if key:
                    seen_titles.add(key)
                allow_continuation = True
                continuation_count = 0
            kept.append(line)
        path.write_text(frontmatter_block(fm, "\n".join(kept)), encoding="utf-8")
    return filtered


def clean_markdown_file(path: Path, keywords: list[str]) -> int:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    kept: list[str] = []
    removed = 0
    for line in body.splitlines():
        if contains_blocked(line, keywords):
            removed += 1
            continue
        kept.append(line)
    path.write_text(frontmatter_block(fm, "\n".join(kept)), encoding="utf-8")
    return removed


def list_without_blocked(items: Any, keywords: list[str]) -> list[Any]:
    if not isinstance(items, list):
        return []
    kept: list[Any] = []
    for item in items:
        rendered = yaml.safe_dump(item, allow_unicode=True, sort_keys=False)
        if not contains_blocked(rendered, keywords):
            kept.append(item)
    return kept


def rewrite_entity_page(path: Path, keywords: list[str]) -> None:
    fm, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    title = str(fm.get("title") or path.parent.name)
    topics = list_without_blocked(fm.get("topics"), keywords)
    claims = [
        claim for claim in list_without_blocked(fm.get("claims"), keywords)
        if title.lower() in yaml.safe_dump(claim, allow_unicode=True, sort_keys=False).lower()
    ]
    sources = list_without_blocked(fm.get("sources"), keywords)
    fm["topics"] = topics
    fm["claims"] = claims
    fm["sources"] = sources

    body = [
        "<div class=\"entity-profile-page\">",
        f"<p class=\"eyebrow\">{fm.get('entity_type', 'entity')} File</p>",
        f"<h1>{title}</h1>",
        "<p class=\"page-lead\">该实体已通过质量闸门保留为核心 AI 行业实体。页面内容已移除低相关事件和噪声来源。</p>",
    ]
    if topics:
        body.append("<section><h2>关联主题</h2><div class=\"entity-topic-chips\">")
        for topic in topics[:12]:
            slug = str(topic.get("slug") if isinstance(topic, dict) else topic)
            body.append(f"<a href=\"/topics/{slug}/\">#{slug}</a>")
        body.append("</div></section>")
    if claims:
        body.append("<section><h2>结构化声明</h2><div class=\"entity-claims\">")
        for claim in claims[:12]:
            if not isinstance(claim, dict):
                continue
            text = str(claim.get("text") or claim.get("statement") or "").strip()
            if text:
                conf = round(float(claim.get("confidence") or 0) * 100)
                body.append(f"<p><span>{text}</span><b>{conf}%</b></p>")
        body.append("</div></section>")
    if sources:
        body.append("<section><h2>来源</h2><ul class=\"entity-sources\">")
        for source in sources[:12]:
            if not isinstance(source, dict) or not source.get("url"):
                continue
            body.append(f"<li><a href=\"{source.get('url')}\">{source.get('title') or source.get('url')}</a></li>")
        body.append("</ul></section>")
    body.append("</div>")
    path.write_text(frontmatter_block(fm, "\n".join(body)), encoding="utf-8")


def clean_insights(site_dir: Path, keywords: list[str]) -> int:
    insights_dir = site_dir / "content" / "insights"
    if not insights_dir.exists():
        return 0
    removed = 0
    for path in sorted(insights_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if contains_blocked(text, keywords):
            path.unlink()
            removed += 1
    return removed


def cleanup_hugo_content(
    site_dir: Path = SITE_DIR,
    allowlist_path: Path = ALLOWLIST_PATH,
    editorial_rules_path: Path = EDITORIAL_RULES_PATH,
) -> CleanupResult:
    site_dir = Path(site_dir)
    keywords = blocked_keywords(Path(editorial_rules_path))
    return CleanupResult(
        removed_entities=clean_entities(site_dir, Path(allowlist_path), keywords),
        filtered_daily_lines=clean_daily_briefs(site_dir, keywords),
        removed_insights=clean_insights(site_dir, keywords),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill and clean generated Hugo content through quality gates.")
    parser.add_argument("--site-dir", type=Path, default=SITE_DIR)
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST_PATH)
    parser.add_argument("--editorial-rules", type=Path, default=EDITORIAL_RULES_PATH)
    args = parser.parse_args()
    result = cleanup_hugo_content(
        site_dir=args.site_dir,
        allowlist_path=args.allowlist,
        editorial_rules_path=args.editorial_rules,
    )
    print(yaml.safe_dump(result.to_dict(), allow_unicode=True, sort_keys=True).strip())


if __name__ == "__main__":
    main()
