# ITERATION-01 Content Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 neican.ai 公开页面从“数据库导出”升级为可阅读、无内部字段泄漏、可随数据自动更新的知识产品。

**Architecture:** 本迭代只做模板化编辑升级，不引入新的 LLM 生成链路。内容质量改造集中在 `timeline_product.py`、`entity_product.py`、`topic_product.py`、`export_hugo.py` 和 Hugo 模板，先用确定性规则重写页面结构，再用单元测试和 Hugo 构建验证公开页面输出。

**Tech Stack:** Python 3、SQLite、PyYAML、pytest、Hugo templates。

---

## File Structure

- Modify: `openclaw/agent/scripts/timeline_product.py`
  - Move event internal fields into `neican`.
  - Replace event body sections with reader-facing editorial sections.
  - Stop rendering claims as a repeated body list.
- Modify: `openclaw/agent/scripts/entity_product.py`
  - Improve `build_signal()`.
  - Add entity intro text.
  - Remove confidence percentage from entity body.
  - Include event type and summary in entity event cards.
- Modify: `openclaw/agent/scripts/topic_product.py`
  - Generate topic judgment from actual event grades and summaries.
  - Remove duplicated key-entity body section.
  - Enrich event list entries.
- Modify: `openclaw/agent/scripts/export_hugo.py`
  - Include A/B/C events in daily brief rows.
  - Adjust fallback and LLM prompt language for A-grade summary plus link behavior.
- Modify: `openclaw/agent/hugo-site/layouts/index.html`
  - Replace hard-coded homepage content with Hugo queries over actual content sections.
- Modify: `openclaw/agent/hugo-site/layouts/event/single.html`
  - Hide internal badges/metrics.
  - Make entity and topic chips clickable.
- Modify: `openclaw/agent/hugo-site/layouts/_default/single.html`
  - Stop rendering `decision_grade` and claims box for public pages.
- Modify tests:
  - `openclaw/agent/tests/test_timeline_product.py`
  - `openclaw/agent/tests/test_entity_product.py`
  - `openclaw/agent/tests/test_topic_product.py`
  - `openclaw/agent/tests/test_export_hugo.py`

---

### Task 1: Event Frontmatter And Internal Field Cleanup

**Files:**
- Modify: `openclaw/agent/scripts/timeline_product.py:278-321`
- Modify: `openclaw/agent/hugo-site/layouts/event/single.html`
- Modify: `openclaw/agent/hugo-site/layouts/_default/single.html`
- Test: `openclaw/agent/tests/test_timeline_product.py`

- [ ] **Step 1: Write failing timeline frontmatter test**

Add this test to `openclaw/agent/tests/test_timeline_product.py`:

```python
def test_event_page_moves_internal_fields_under_neican_and_body_hides_internal_terms(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    tracks_path = write_tracks(tmp_path)
    insert_decided_event(
        db_path,
        "OpenAI agent runtime becomes enterprise control plane",
        "A",
        topics=[{"slug": "ai-agents", "name": "AI Agents"}],
        entities=[{"name": "OpenAI", "slug": "openai", "type": "company"}],
    )

    run(db_path=db_path, site_dir=site_dir, tracks_path=tracks_path)

    event_path = next((site_dir / "content" / "events").glob("*.md"))
    text = event_path.read_text(encoding="utf-8")
    fm = read_frontmatter(event_path)
    body = text.split("---", 2)[2]

    assert "event_id" not in fm
    assert "decision_grade" not in fm
    assert "importance_score" not in fm
    assert "confidence" not in fm
    assert fm["neican"]["event_id"] == 1
    assert fm["neican"]["grade"] == "A"
    assert "时间线判断" not in body
    assert "结构化声明" not in body
    assert "编辑判断为" not in body
    assert "发生了什么" in body
    assert "为什么重要" in body
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_timeline_product.py::test_event_page_moves_internal_fields_under_neican_and_body_hides_internal_terms -q
```

Expected: FAIL because `decision_grade`, `importance_score`, and `confidence` are still top-level frontmatter fields and body still contains internal headings.

- [ ] **Step 3: Move event internal fields under `neican`**

In `write_event_page()`, replace the frontmatter block with:

```python
    fm = {
        "title": row["title"],
        "date": f"{row['date']}T09:00:00+08:00",
        "slug": row["slug"],
        "type": "event",
        "event_type": row["event_type"],
        "entities": entities,
        "topics": topics,
        "tracks": tracks,
        "claims": claims,
        "sources": sources,
        "timeline": {"date": row["date"], "year": row["year"], "month": row["month"], "tracks": tracks},
        "neican": {
            "event_id": row["event_id"],
            "grade": row["grade"],
            "importance_score": row["importance_score"],
            "confidence": row["confidence"],
            "generated_by": "timeline_product",
            "review_status": row["review_status"],
        },
    }
```

- [ ] **Step 4: Remove public internal field rendering from event and default templates**

In `openclaw/agent/hugo-site/layouts/event/single.html`, remove rendering of `.Params.decision_grade`, `.Params.confidence`, and `.Params.importance_score`. Keep `.Params.event_type` because it is a public taxonomy field.

In `openclaw/agent/hugo-site/layouts/_default/single.html`, remove the grade badge and the `claims-box` block. Keep `.Params.event_type`, `.Params.entities`, `.Params.topics`, and `.Params.sources`.

- [ ] **Step 5: Run focused test**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_timeline_product.py::test_event_page_moves_internal_fields_under_neican_and_body_hides_internal_terms -q
```

Expected: PASS after Task 2 body changes are also present; if only frontmatter is complete, the test may still fail on body assertions.

---

### Task 2: Event Editorial Body Rewrite And Claim Deduplication

**Files:**
- Modify: `openclaw/agent/scripts/timeline_product.py:159-190`
- Modify: `openclaw/agent/scripts/timeline_product.py:278-321`
- Test: `openclaw/agent/tests/test_timeline_product.py`

- [ ] **Step 1: Add deterministic body helper tests**

Add imports and tests to `openclaw/agent/tests/test_timeline_product.py`:

```python
from timeline_product import editorial_event_body


def test_editorial_event_body_uses_reader_facing_sections():
    body = "\n".join(editorial_event_body(
        "AI 视频 Agent 产品面临大厂竞争",
        "字节跳动和快手的视频模型正在高频迭代，创业公司需要重新判断产品窗口。",
        "该事件具备后续跟踪价值。",
        [{"claim_text": "字节跳动的 Seedance 正在高频迭代。"}],
        [{"name": "字节跳动"}],
        [{"name": "AI Video"}],
    ))

    assert "## 发生了什么" in body
    assert "## 为什么重要" in body
    assert "## 关键细节" in body
    assert "## 值得关注的信号" in body
    assert "时间线判断" not in body
    assert "结构化声明" not in body
    assert "- 字节跳动的 Seedance" not in body
```

- [ ] **Step 2: Run helper test and verify it fails**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_timeline_product.py::test_editorial_event_body_uses_reader_facing_sections -q
```

Expected: FAIL because `editorial_event_body` does not exist.

- [ ] **Step 3: Add reader-facing helpers in `timeline_product.py`**

Add these helpers after `_claim_text()`:

```python
def _clean_internal_judgment(text: str) -> str:
    cleaned = re.sub(r"编辑判断为\s*[A-D]\s*级[，,]?", "", text or "")
    cleaned = cleaned.replace("适合作为独立洞察与长期时间线节点", "值得继续跟踪其对行业结构的影响")
    cleaned = cleaned.replace("适合进入日报并沉淀为趋势信号", "值得作为趋势信号持续观察")
    cleaned = re.sub(r"已抽取\s*\d+\s*条结构化声明[。；;]?", "", cleaned)
    cleaned = cleaned.replace("；。", "。").strip("；; ")
    return cleaned or "这件事值得关注，因为它可能影响相关产品路线、竞争节奏或行业判断。"


def editorial_event_body(
    title: str,
    summary: str,
    importance: str,
    claims: list[Any],
    entities: list[Any],
    topics: list[Any],
) -> list[str]:
    valid_claims = [_claim_text(c) for c in claims if _claim_text(c)]
    entity_names = [name for name in (_entity_name(e) for e in entities) if name]
    topic_names = [name for name in (_topic_name(t) for t in topics) if name]
    context = "、".join(topic_names[:2] or entity_names[:2]) or "AI 行业"
    detail = "；".join(valid_claims[:2]) if valid_claims else (summary or "目前公开信息仍有限。")
    watch_target = "、".join(entity_names[:2]) if entity_names else context
    return [
        f"# {title}",
        "",
        "## 发生了什么",
        "",
        summary or "目前已捕捉到一条值得跟踪的行业事件，事件摘要仍在补充。",
        "",
        "## 为什么重要",
        "",
        _clean_internal_judgment(importance),
        "",
        "## 关键细节",
        "",
        f"围绕 {context}，当前可确认的关键细节是：{detail}",
        "",
        "## 值得关注的信号",
        "",
        f"接下来应观察 {watch_target} 是否出现后续产品动作、生态反馈、商业化进展或监管与市场反应。",
        "",
    ]
```

- [ ] **Step 4: Use helper in `write_event_page()`**

Replace the manual body list and `valid_claims` block with:

```python
    body = editorial_event_body(
        row["title"],
        row["summary"] or "",
        row["why_it_matters"] or "",
        claims,
        entities,
        topics,
    )
```

Keep the existing source section append.

- [ ] **Step 5: Run focused timeline tests**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_timeline_product.py -q
```

Expected: PASS.

---

### Task 3: Entity Page Context And Signal Upgrade

**Files:**
- Modify: `openclaw/agent/scripts/entity_product.py:248-252`
- Modify: `openclaw/agent/scripts/entity_product.py:376-423`
- Test: `openclaw/agent/tests/test_entity_product.py`

- [ ] **Step 1: Write failing entity body test**

Add this test to `openclaw/agent/tests/test_entity_product.py`:

```python
def test_entity_page_adds_context_and_hides_claim_confidence(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    seed_event_with_core_and_noise_entities(db_path)

    with get_conn(db_path) as conn:
        generate_from_db(conn)
        conn.execute(
            "UPDATE entity_profiles SET claims_json = ? WHERE slug = 'openai'",
            (json.dumps([{"text": "OpenAI 发布面向 Agent 工作流的工具。", "confidence": 0.95}], ensure_ascii=False),),
        )
        export_hugo(conn, site_dir=site_dir)

    text = (site_dir / "content" / "entities" / "openai" / "_index.md").read_text(encoding="utf-8")
    assert "OpenAI 是 neican.ai 追踪的 AI 行业公司。" in text
    assert "tool_launch" in text
    assert "OpenAI 发布面向 Agent 工作流的工具。" in text
    assert "95%" not in text
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_entity_product.py::test_entity_page_adds_context_and_hides_claim_confidence -q
```

Expected: FAIL because the intro sentence and event type are absent, and claim confidence is rendered.

- [ ] **Step 3: Replace `build_signal()`**

Use this implementation:

```python
def build_signal(name: str, entity_type_value: str, events: list[dict[str, Any]], topics: list[str]) -> str:
    if not events:
        return f"{name} 已进入实体档案，等待更多事件沉淀。"
    recent = events[0]
    topic_text = "、".join(topics[:3]) or "AI 行业"
    event_title = recent.get("title") or "最近事件"
    event_type = recent.get("type") or "event"
    return f"{name} 最近出现在“{event_title}”中，事件类型为 {event_type}；当前主要关联 {topic_text}，已沉淀 {len(events)} 个相关事件。"
```

- [ ] **Step 4: Add intro and improve event cards in `write_entity_page()`**

Add `type_labels` before `body`:

```python
    type_labels = {
        "company": "公司",
        "tool": "AI 产品/工具",
        "model": "AI 模型",
        "organization": "组织/机构",
        "person": "人物",
    }
    type_label = type_labels.get(row["entity_type"], "行业参与者")
    intro = f"{row['name']} 是 neican.ai 追踪的 AI 行业{type_label}。"
```

Replace the page lead line with:

```python
        f"<p class=\"page-lead\">{intro}</p>",
```

Replace event card append with:

```python
            event_type = ev.get("type") or "event"
            summary = ev.get("summary") or ""
            link = f"<a href=\"{url}\">{title}</a>" if url else title
            body.append(f"<article><time>{date}</time><span class=\"chip\">{event_type}</span><h3>{link}</h3><p>{summary}</p></article>")
```

Replace claim rendering with:

```python
        for c in valid_claims[:12]:
            body.append(f"<p><span>{c.get('text')}</span></p>")
```

- [ ] **Step 5: Run focused entity tests**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_entity_product.py -q
```

Expected: PASS.

---

### Task 4: Homepage Dynamic Data

**Files:**
- Modify: `openclaw/agent/hugo-site/layouts/index.html`

- [ ] **Step 1: Replace hard-coded homepage with Hugo data queries**

Use these top-level queries at the start of the template:

```html
{{ define "main" }}
{{ $events := where .Site.RegularPages "Section" "events" }}
{{ $briefs := where (where .Site.RegularPages "Section" "briefs") "Params.type" "daily_brief" }}
{{ $entities := where .Site.RegularPages "Section" "entities" }}
{{ $topics := where .Site.RegularPages "Section" "topics" }}
{{ $timeline := where .Site.RegularPages "Section" "timeline" }}
{{ $latestEvent := index (first 1 $events.ByDate.Reverse) 0 }}
{{ $latestBrief := index (first 1 $briefs.ByDate.Reverse) 0 }}
```

Keep the existing classes `front-page`, `front-grid`, `lead-story`, `brief-panel`, `reader-section`, `article-row`, `watch-list`, `theme-stack`, and `timeline-preview`, but replace literal links such as `/topics/ai-agents/`, `/entities/openai/`, and `/briefs/daily/2026-05-03/` with ranges over the page collections.

- [ ] **Step 2: Implement safe empty states**

Use `{{ with $latestEvent }}` and `{{ else }}` blocks so homepage builds when content is empty. Empty state copy should be public-facing:

```html
<p>新的事件洞察正在生成中。</p>
```

- [ ] **Step 3: Run Hugo build**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent/hugo-site
hugo
```

Expected: build completes without template errors.

- [ ] **Step 4: Verify no stale homepage references**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
grep -R "2026-05-03\\|OpenAI\\|Anthropic\\|Microsoft\\|Cursor" hugo-site/layouts/index.html && exit 1 || echo "PASS"
```

Expected: `PASS`.

---

### Task 5: Topic Page Editorial Synthesis

**Files:**
- Modify: `openclaw/agent/scripts/topic_product.py:69-95`
- Modify: `openclaw/agent/scripts/topic_product.py:239-256`
- Test: `openclaw/agent/tests/test_topic_product.py`

- [ ] **Step 1: Write failing topic synthesis test**

Add this test to `openclaw/agent/tests/test_topic_product.py`:

```python
from topic_product import topic_hub_sections


def test_topic_hub_sections_generate_data_based_judgment_and_event_summaries():
    sections = "\n".join(topic_hub_sections(
        "AI Agents",
        "Agent 相关主题。",
        ["OpenAI"],
        [
            {"title": "OpenAI 发布 Agent 工具", "summary": "工具进入企业工作流。", "date": "2026-05-01", "type": "tool_launch", "grade": "A"},
            {"title": "千问更新语音能力", "summary": "语音入口继续增强。", "date": "2026-05-02", "type": "model_update", "grade": "B"},
        ],
    ))

    assert "近期有 1 个高优先级事件" in sections
    assert "工具进入企业工作流。" in sections
    assert "页面优先服务于理解主线" not in sections
    assert "## 关键实体" not in sections
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_topic_product.py::test_topic_hub_sections_generate_data_based_judgment_and_event_summaries -q
```

Expected: FAIL because current judgment is fixed copy and event summaries are absent.

- [ ] **Step 3: Replace `topic_hub_sections()`**

Use this implementation:

```python
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
```

- [ ] **Step 4: Remove duplicated key entity section after related events**

Delete the body block that appends:

```python
        body += [
            "## 关键实体",
            "",
            ", ".join(top_entities),
            "",
        ]
```

- [ ] **Step 5: Run topic tests**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_topic_product.py -q
```

Expected: PASS.

---

### Task 6: Daily Brief Coverage Repair

**Files:**
- Modify: `openclaw/agent/scripts/export_hugo.py:191-216`
- Modify: `openclaw/agent/scripts/export_hugo.py:273-310`
- Modify: `openclaw/agent/scripts/export_hugo.py:409-419`
- Test: `openclaw/agent/tests/test_export_hugo.py`

- [ ] **Step 1: Write failing daily coverage test**

Add a test that seeds one A, one B, and one C event for the same date and asserts all are covered:

```python
def test_daily_brief_includes_a_b_c_events(tmp_path):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    memory_dir = tmp_path / "memory"
    seed_decision_event(db_path, "A 级视频 Agent 事件", "A", "2026-05-07")
    seed_decision_event(db_path, "B 级千问语音事件", "B", "2026-05-07")
    seed_decision_event(db_path, "C 级论文事件", "C", "2026-05-07")

    result = export_hugo(db_path=db_path, site_dir=site_dir, memory_dir=memory_dir, date="2026-05-07", mock=True)

    text = (site_dir / "content" / "briefs" / "daily" / "2026-05-07.md").read_text(encoding="utf-8")
    assert result.daily_briefs == 1
    assert "A 级视频 Agent 事件" in text
    assert "B 级千问语音事件" in text
    assert "C 级论文事件" in text
```

If `seed_decision_event()` does not exist in the file, add it using the existing test fixture style: insert one `sources` row, one `raw_items` row, one `events` row, and one `decisions` row with `status='pending'`.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_export_hugo.py::test_daily_brief_includes_a_b_c_events -q
```

Expected: FAIL because daily export currently fetches only B/C rows.

- [ ] **Step 3: Fetch A/B/C rows for daily**

Change:

```python
        daily_rows = fetch_rows(conn, date, ("B", "C"))
```

to:

```python
        daily_rows = fetch_rows(conn, date, ("A", "B", "C"))
```

- [ ] **Step 4: Improve fallback daily copy**

Change the fallback judgment text to:

```python
    key_judgment = f"今日共跟踪 {len(rows)} 条 A/B/C 级事件，重点集中在 " + "、".join(list(grouped)[:3]) + "。"
```

When listing rows, include grade and link hint for A-grade events:

```python
            grade = row["decision_grade"]
            summary = (row["event_summary"] or row["event_title"] or "").strip()
            suffix = "，已生成独立洞察，可从洞察页继续阅读" if grade == "A" else ""
            sections.append(f"- **[{grade}] {row['event_title']}**：{summary}{suffix}")
```

- [ ] **Step 5: Adjust LLM daily prompt**

Replace the system prompt with:

```python
"你是 neican.ai 的日报编辑。返回 JSON：{body_markdown:string}。正文必须包含“今日关键判断”“值得跟踪”“来源索引”等二级标题，不要编造事实。A 级事件已有独立洞察，日报中简短提及并提示读者继续阅读独立文章；B/C 级事件保留摘要。"
```

- [ ] **Step 6: Run export tests**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest tests/test_export_hugo.py -q
```

Expected: PASS.

---

### Task 7: Event Cross-Page Navigation

**Files:**
- Modify: `openclaw/agent/hugo-site/layouts/event/single.html`

- [ ] **Step 1: Make entity chips links**

Replace entity chip spans with anchors:

```html
<a href="/entities/{{ $slug }}/" class="entity-chip"><span class="chip-type">{{ .type | default "entity" }}</span>{{ .name | default $slug }}</a>
```

For string entities:

```html
<a href="/entities/{{ $slug }}/" class="entity-chip"><span class="chip-type">entity</span>{{ . }}</a>
```

- [ ] **Step 2: Make topic tags links**

Replace topic spans with anchors:

```html
<a href="/topics/{{ $slug }}/">#{{ .name | default $slug }}</a>
```

For string topics:

```html
<a href="/topics/{{ $slug }}/">#{{ . }}</a>
```

- [ ] **Step 3: Verify template contains links**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
grep -n 'href="/entities/{{ \\$slug }}/"\\|href="/topics/{{ \\$slug }}/"' hugo-site/layouts/event/single.html
```

Expected: at least one entity link and one topic link are printed.

---

### Task 8: Full Regression And Public Output Audit

**Files:**
- Validate all modified files.

- [ ] **Step 1: Run Python tests**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Hugo build**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent/hugo-site
hugo
```

Expected: build completes without errors.

- [ ] **Step 3: Run public leakage scan**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent
grep -R "编辑判断为\\|时间线判断\\|结构化声明\\|generated_by\\|review_status\\|decision_grade\\|importance_score\\|置信度" hugo-site/public/events/ hugo-site/public/entities/ hugo-site/public/topics/ && exit 1 || echo "PASS"
```

Expected: `PASS`.

- [ ] **Step 4: Run repository validation**

Run:

```bash
cd /home/ai/projects/openclaw-apps/neican-editor-dev
bash scripts/validate.sh
```

Expected: validation completes successfully.

---

## Iteration Slices

1. **Day 1: Public Leakage Baseline**
   - Complete Tasks 1 and 2.
   - Commit: `fix: clean event public output`

2. **Day 2: Entity And Topic Reading Quality**
   - Complete Tasks 3 and 5.
   - Commit: `feat: improve entity and topic pages`

3. **Day 3: Homepage And Daily Coverage**
   - Complete Tasks 4 and 6.
   - Commit: `feat: make homepage and daily brief data-driven`

4. **Day 4: Navigation And Release Gate**
   - Complete Tasks 7 and 8.
   - Commit: `chore: verify content quality iteration`

---

## Acceptance Map

- 需求 1: Task 2 covers event body rewrite.
- 需求 2: Task 1 and Task 8 cover internal field cleanup and leakage scans.
- 需求 3: Task 4 covers homepage dynamic data.
- 需求 4: Task 3 covers entity content upgrade.
- 需求 5: Task 5 covers topic editorial synthesis.
- 需求 6: Task 6 covers daily brief A/B/C coverage.
- 需求 7: Task 2 covers claim deduplication.
- 需求 8: Task 3 covers entity context.
- 需求 9: Task 7 covers cross-page navigation.

## Self-Review

- Spec coverage: all nine requirements in `docs/ITERATION-01-content-quality.md` map to at least one task above.
- Placeholder scan: every code-changing step includes concrete snippets or exact replacement guidance.
- Type consistency: helper names are consistent across tests and implementation snippets: `editorial_event_body`, `_clean_internal_judgment`, `build_signal`, and `topic_hub_sections`.
