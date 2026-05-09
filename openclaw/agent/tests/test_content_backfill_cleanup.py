import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from content_backfill_cleanup import cleanup_hugo_content


def write_page(path: Path, frontmatter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n\n" + body,
        encoding="utf-8",
    )


def write_policy(tmp_path: Path) -> tuple[Path, Path]:
    allowlist = tmp_path / "entity_allowlist.yaml"
    allowlist.write_text(
        yaml.safe_dump(
            {
                "approved_entities": [
                    {"slug": "openai", "name": "OpenAI", "entity_role": "core_actor", "entity_quality": "approved"}
                ],
                "suppressed_entities": [
                    {"slug": "36kr", "entity_role": "source_media", "entity_quality": "suppressed"}
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    editorial = tmp_path / "editorial_rules.yaml"
    editorial.write_text(
        yaml.safe_dump(
            {"ai_relevance_gate": {"exclusion_keywords": ["黄金期货", "电影票房", "环球音乐"]}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return allowlist, editorial


def test_cleanup_removes_non_allowlisted_entities_and_rewrites_index(tmp_path):
    site_dir = tmp_path / "hugo-site"
    allowlist, editorial = write_policy(tmp_path)
    write_page(site_dir / "content/entities/openai/_index.md", {"title": "OpenAI"}, "OpenAI")
    write_page(site_dir / "content/entities/36kr/_index.md", {"title": "36氪"}, "36氪")
    write_page(site_dir / "content/entities/hkex/_index.md", {"title": "港交所"}, "港交所")
    write_page(site_dir / "content/entities/_index.md", {"title": "实体档案"}, "old index")

    result = cleanup_hugo_content(site_dir=site_dir, allowlist_path=allowlist, editorial_rules_path=editorial)

    assert result.removed_entities == 2
    assert (site_dir / "content/entities/openai/_index.md").exists()
    assert not (site_dir / "content/entities/36kr/_index.md").exists()
    assert not (site_dir / "content/entities/hkex/_index.md").exists()
    index_text = (site_dir / "content/entities/_index.md").read_text(encoding="utf-8")
    assert "OpenAI" in index_text
    assert "36氪" not in index_text


def test_cleanup_filters_noise_inside_allowlisted_entity_page(tmp_path):
    site_dir = tmp_path / "hugo-site"
    allowlist, editorial = write_policy(tmp_path)
    write_page(
        site_dir / "content/entities/openai/_index.md",
        {
            "title": "OpenAI",
            "claims": [
                {"text": "OpenAI 发布 Agent Runtime", "confidence": 0.9},
                {"text": "某算力独角兽提交上市辅导", "confidence": 0.5},
            ],
        },
        "\n".join(
            [
                "<article><h3>OpenAI 发布 Agent Runtime</h3></article>",
                "<article><h3>又一算力独角兽，冲击IPO</h3></article>",
                "<p><span>IPO辅导完成</span><b>50%</b></p>",
            ]
        ),
    )
    write_page(site_dir / "content/entities/_index.md", {"title": "实体档案"}, "old index")

    cleanup_hugo_content(site_dir=site_dir, allowlist_path=allowlist, editorial_rules_path=editorial)

    text = (site_dir / "content/entities/openai/_index.md").read_text(encoding="utf-8")
    assert "OpenAI" in text
    assert "质量闸门" in text
    assert "OpenAI 发布 Agent Runtime" in text
    assert "算力独角兽" not in text
    assert "IPO" not in text


def test_cleanup_dedupes_and_filters_daily_brief(tmp_path):
    site_dir = tmp_path / "hugo-site"
    allowlist, editorial = write_policy(tmp_path)
    brief = site_dir / "content/briefs/daily/2026-05-04.md"
    write_page(
        brief,
        {"title": "AI 内参日报：2026-05-04"},
        "\n".join(
            [
                "# AI 内参日报：2026-05-04",
                "",
                "- **[B]** 豆包发布 AI Agent",
                "- **[B]** 港交所拟重启黄金期货交易",
                "  港交所计划重启黄金期货交易。",
                "- **[B]** 港交所拟重启黄金期货交易",
                "- **[C]** 2026年五一档电影票房突破6亿元",
                "- **[C]** Bitcoin briefly breaks $80,000",
                "  Bitcoin price moved higher.",
                "",
                "  orphan summary without a bullet",
                "## 来源索引",
                "- [豆包发布 AI Agent](https://example.com/ai)",
                "- [港交所拟重启黄金期货交易](https://example.com/gold)",
            ]
        ),
    )

    result = cleanup_hugo_content(site_dir=site_dir, allowlist_path=allowlist, editorial_rules_path=editorial)

    text = brief.read_text(encoding="utf-8")
    assert result.filtered_daily_lines >= 5
    assert "豆包发布 AI Agent" in text
    assert "黄金期货" not in text
    assert "港交所计划" not in text
    assert "电影票房" not in text
    assert "Bitcoin" not in text
    assert "orphan summary" not in text


def test_cleanup_removes_noisy_insight_pages(tmp_path):
    site_dir = tmp_path / "hugo-site"
    allowlist, editorial = write_policy(tmp_path)
    clean = site_dir / "content/insights/agent.md"
    noisy = site_dir / "content/insights/music.md"
    write_page(clean, {"title": "Agent 治理"}, "OpenAI Agent Runtime")
    write_page(noisy, {"title": "模型竞争"}, "潘兴广场计划以640亿美元收购环球音乐")

    result = cleanup_hugo_content(site_dir=site_dir, allowlist_path=allowlist, editorial_rules_path=editorial)

    assert result.removed_insights == 1
    assert clean.exists()
    assert not noisy.exists()
