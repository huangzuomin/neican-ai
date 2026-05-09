# ITERATION-01：内容阅读质量提升

> 状态：Draft
> 创建：2026-05-08
> 目标：让 neican.ai 公开页面从"数据库导出"升级为"可阅读的知识产品"

---

## 背景

流水线已通：RSS → raw_items → events → entities/topics/timeline → Hugo 页面 → 构建成功（95 页）。

但从最终读者视角审视，当前输出存在系统性的质量问题。本文档将诊断结论转化为可执行的迭代需求。

## 问题总览

| # | 问题 | 严重度 | 影响范围 | 修复复杂度 |
|---|------|--------|----------|-----------|
| 1 | 事件页正文是内部状态报告，不是文章 | 🔴 高 | 所有事件页 | 中 |
| 2 | 实体页是声明置信度的堆砌 | 🔴 高 | 所有实体页 | 中 |
| 3 | 首页硬编码，与实际数据脱节 | 🔴 高 | 首页 | 低 |
| 4 | 内部工作流字段泄漏到公开页面 | 🔴 高 | 全站 | 低 |
| 5 | 主题页缺少编辑综合 | 🟡 中 | 所有主题页 | 中 |
| 6 | 日报与当日事件脱节 | 🟡 中 | 日报页 | 中 |
| 7 | 声明在正文和 frontmatter 中重复 | 🟡 中 | 事件页 | 低 |
| 8 | 实体页缺少上下文介绍 | 🟡 中 | 实体页 | 中 |
| 9 | 缺少跨页面导航和关联 | 🟢 低 | 全站 | 高 |

---

## 需求 1：事件页正文重写

### 问题

`timeline_product.py` 的 `write_event_page()` 生成的事件页正文由三个机械模块组成：

1. **"时间线判断"** — 写的是"涉及 X、Y、Z 等关键实体；关联 A、B 主题；编辑判断为 A 级…"
   - 这是内部状态报告，不是读者该看的内容
2. **"事件摘要"** — 单段密集事实压缩，没有分析和上下文
3. **"结构化声明"** — 与摘要完全重复的 bullet list

### 当前代码位置

- 正文生成：`scripts/timeline_product.py` → `write_event_page()` 函数（约 L210-L240）
- 模板渲染：`hugo-site/layouts/event/single.html`（整个正文通过 `{{ .Content }}` 渲染）

### 需求

将事件页正文从"数据搬运"改为"编辑叙事"。正文结构改为：

```markdown
# {标题}

## 发生了什么
[2-3 句话讲清楚事件本身，面向非专业读者]

## 为什么重要
[编辑判断：这件事在行业里的意义，对谁有影响，为什么值得跟踪]

## 关键细节
[读者需要知道的具体数据点，融入叙述而不是罗列]

## 值得关注的信号
[接下来该观察什么，面向未来]
```

### 实现路径

**方案 A（推荐）：修改 `write_event_page()` 的 body 拼接逻辑**

在 `timeline_product.py` 的 `write_event_page()` 中：
1. 移除"时间线判断"段落（`why_it_matters` 字段仍保留在 frontmatter 供系统使用）
2. 移除"结构化声明"列表（claims 仍保留在 frontmatter 供系统使用）
3. 将 `summary` 拆分为"发生了什么"段落
4. 新增"为什么重要"段落 — 可以从 `why_it_matters` 字段重构，但需要去掉内部术语
5. 新增"关键细节"段落 — 从 claims 中提取关键数据点，融入叙述句
6. 新增"值得关注的信号"段落 — 可以是通用模板或基于事件类型生成

**方案 B（更高质量但需要 LLM 调用）：在 timeline_product 中增加 LLM 编辑步骤**

对于 A 级事件，在 `write_event_page()` 之前调用 LLM，基于 summary + claims + entities 生成编辑叙事。B 级事件使用方案 A 的模板化生成。

### 验收标准

- [ ] 事件页正文不再出现"时间线判断""结构化声明"等内部标签
- [ ] 事件页正文包含"发生了什么""为什么重要"两个核心段落
- [ ] claims 数据仍保留在 frontmatter 中（供系统使用），但不在正文中重复罗列
- [ ] 已有事件页在重新跑 pipeline 后自动升级为新格式

---

## 需求 2：清理公开页面中的内部字段

### 问题

frontmatter 和正文中暴露了大量内部工作流字段：

**frontmatter 泄漏**（在 Hugo 构建的 HTML 中可能被模板或 SEO 工具读取）：
- `event_id`、`decision_grade`、`importance_score`、`confidence`
- `neican.generated_by`（值如 `timeline_product`、`entity_product`）
- `neican.review_status`（值如 `draft`、`needs_review`）

**正文泄漏**：
- "编辑判断为 A 级" — A/B/C/D 是内部编辑分级，不应对读者暴露
- "适合作为独立洞察与长期时间线节点" — 内部决策逻辑
- "已抽取 5 条结构化声明" — 系统实现细节

### 当前代码位置

- frontmatter 生成：`scripts/timeline_product.py` → `write_event_page()` L215-L235
- 正文生成：同上 → body 拼接部分
- 实体页：`scripts/entity_product.py` → `write_entity_page()` L195-L220
- 主题页：`scripts/topic_product.py` → frontmatter 构建部分

### 需求

1. **frontmatter 分层**：保留内部字段用于系统逻辑，但加 `neican_` 前缀或移至单独的 `neican` 命名空间下，确保 Hugo 模板不渲染它们
2. **正文清理**：移除所有内部术语表述
3. **模板层过滤**：在 Hugo 模板中不渲染 `event_id`、`decision_grade`、`importance_score`、`confidence`、`generated_by`、`review_status`

### 具体修改

**`timeline_product.py` 的 `write_event_page()`：**

```python
# 当前
fm = {
    ...
    "event_id": row["event_id"],
    "decision_grade": row["grade"],
    "importance_score": row["importance_score"],
    "confidence": row["confidence"],
    ...
    "neican": {"generated_by": "timeline_product", "review_status": row["review_status"]},
}

# 改为
fm = {
    ...
    # 公开字段
    "event_type": row["event_type"],
    "entities": entities,
    "topics": topics,
    "sources": sources,
    "timeline": {...},
    # 内部字段移入 neican 命名空间
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

**`event/single.html` 模板：**

```html
<!-- 移除这些字段的渲染 -->
<!-- 当前有： -->
{{ with .Params.decision_grade }}<span class="badge">{{ . }}</span>{{ end }}

<!-- 改为不渲染，或仅在 neican 命名空间下渲染（仅供开发/debug） -->
```

### 验收标准

- [ ] 公开页面 HTML 中不出现 `event_id`、`decision_grade`、`importance_score`、`generated_by`、`review_status`
- [ ] 正文中不出现"A 级""B 级""编辑判断为"等内部术语
- [ ] 内部字段仍保留在 frontmatter 的 `neican` 命名空间下，供系统逻辑使用
- [ ] `hugo` 构建正常，无报错

---

## 需求 3：首页动态化

### 问题

`layouts/index.html` 是完全硬编码的静态 HTML：
- 日期写死为 `2026-05-03`
- 引用的实体（OpenAI、Anthropic、Microsoft、Cursor）在实际数据中不存在
- 5 月 7 日生成的 3 个事件完全没有出现在首页
- 日报链接指向 `2026-05-03`，而不是最新日报

### 当前代码位置

- `hugo-site/layouts/index.html` — 全部硬编码

### 需求

将首页改为从实际数据动态生成：

1. **今日主洞察**：从 events section 取最新 A 级事件（`range` + `where`）
2. **今日日报**：从 briefs/daily 取最新日报
3. **深度洞察**：从 events section 取最新 3 个事件
4. **实体观察**：从 entities section 取实体列表
5. **主题追踪**：从 topics section 取主题列表
6. **时间线预览**：从 timeline section 取最新节点

### 实现方案

使用 Hugo 的 `.Site.RegularPages` 和 `range` + `where` 从各 section 取数据。保留当前的视觉设计框架，但数据源改为动态。

```html
<!-- 示例：今日主洞察 -->
{{ $events := where .Site.RegularPages "Section" "events" }}
{{ $latest := index (first 1 $events) 0 }}
{{ with $latest }}
<section class="front-grid">
  <article class="lead-story">
    <p class="section-label">最新洞察</p>
    <h2><a href="{{ .RelPermalink }}">{{ .Title }}</a></h2>
    <p>{{ .Summary }}</p>
  </article>
</section>
{{ end }}
```

### 验收标准

- [ ] 首页显示的数据来自实际 content 目录中的内容
- [ ] 新增事件后重新 hugo 构建，首页自动更新
- [ ] 不引用不存在的实体
- [ ] 视觉设计框架保持不变（front-page、front-grid 等 CSS class 保留）

---

## 需求 4：实体页内容升级

### 问题

当前实体页（如千问）的内容是：
- "当前信号"段落：一段模板化的"近期主要出现在 X 等主题下"套话
- "结构化声明"列表：每条 claim 后面跟一个置信度百分比（95%、90%…）
- 缺少：这个实体是什么、为什么值得关注、在行业里的位置

### 当前代码位置

- `scripts/entity_product.py` → `write_entity_page()` L195-L230
- `scripts/entity_product.py` → `build_signal()` L165-L170

### 需求

1. **增加实体简介**：在页面顶部增加一段实体介绍，说明这个公司/产品/模型是什么
2. **移除面向读者的置信度**：claims 列表中不显示置信度百分比（保留在 frontmatter 供系统使用）
3. **改善"当前信号"**：从模板套话改为基于实际事件的具体判断
4. **改善事件列表格式**：当前事件列表只显示标题和日期，增加事件类型和摘要

### 具体修改

**`build_signal()` 改进：**

```python
# 当前
def build_signal(name, entity_type_value, events, topics):
    if not events:
        return f"{name} 已进入实体档案，等待更多事件沉淀。"
    topic_text = "、".join(topics[:3]) or "AI 行业"
    return f"{name} 近期主要出现在 {topic_text} 等主题下；已关联 {len(events)} 个事件，适合持续跟踪其产品路线、生态位置和风险信号。"

# 改为：基于实际事件生成具体判断
def build_signal(name, entity_type_value, events, topics):
    if not events:
        return f"{name} 已进入实体档案，等待更多事件沉淀。"
    recent = events[0]  # 最近的事件
    topic_text = "、".join(topics[:3]) or "AI 行业"
    grade_text = ""
    if recent.get("grade") in ("A", "B"):
        grade_text = f"最近一次出现在 {recent.get('date', '')} 的 {recent.get('grade', '')} 级事件中。"
    return f"{name} 是 {entity_type_value} 类型的行业参与者，活跃于 {topic_text} 领域。{grade_text}已关联 {len(events)} 个事件。"
```

**实体页面 claims 渲染：**

```python
# 当前
for c in valid_claims[:12]:
    conf = c.get("confidence", 0)
    body.append(f"<p><span>{c.get('text')}</span><b>{round(float(conf or 0) * 100)}%</b></p>")

# 改为：不显示置信度
for c in valid_claims[:12]:
    body.append(f"<p><span>{c.get('text')}</span></p>")
```

### 验收标准

- [ ] 实体页不再显示置信度百分比
- [ ] 实体页"当前信号"段落基于实际事件生成，不再是模板套话
- [ ] claims 数据仍保留在 frontmatter 中
- [ ] 实体页事件列表包含事件类型和摘要

---

## 需求 5：主题页增加编辑综合

### 问题

主题页（如 AI Agents）的内容结构：
- "一句话定义"：从 description 字段复制
- "当前判断"：固定模板"优先服务于理解主线，而不是罗列所有命中的事件"
- "最近 30 天变化"：事件标题列表
- 缺少：主题级别的综合分析、趋势判断

### 当前代码位置

- `scripts/topic_product.py` → `topic_hub_sections()` L70-L95

### 需求

1. **改善"当前判断"**：基于实际事件生成具体判断，而非固定模板
2. **改善事件列表**：每个事件增加摘要和编辑判断
3. **移除冗余的"关键实体"段落**：实体已在页面其他位置展示

### 具体修改

**`topic_hub_sections()` 改进：**

```python
def topic_hub_sections(canonical, description, top_entities, events):
    recent_events = sorted(events, key=lambda e: e.get("date") or "", reverse=True)[:5]
    entity_text = " / ".join(top_entities[:5]) if top_entities else "待从高质量事件中确认"

    # 基于实际事件生成判断
    a_count = sum(1 for e in events if e.get("grade") == "A")
    b_count = sum(1 for e in events if e.get("grade") == "B")

    if a_count > 0:
        judgment = f"近期有 {a_count} 个 A 级事件进入该主题，表明 {canonical} 正处于活跃变化期。"
    elif b_count > 0:
        judgment = f"该主题下有 {b_count} 个 B 级事件，值得持续观察但尚未出现结构性变化。"
    else:
        judgment = f"{canonical} 目前以 C 级信号为主，仍在积累观察素材。"

    return [
        "## 当前判断",
        "",
        judgment,
        "",
        "## 最近事件",
        "",
        *(f"1. {event['title']}" for idx, event in enumerate(recent_events[:3], start=1)),
        "",
        "## 关键实体",
        "",
        entity_text,
        "",
    ]
```

### 验收标准

- [ ] 主题页"当前判断"基于实际事件数据生成
- [ ] 主题页不再显示固定的模板套话
- [ ] 事件列表格式清晰，包含关键信息

---

## 需求 6：日报覆盖修复

### 问题

`export_hugo.py` 的 `fetch_rows()` 只查询 `decisions.decision_grade IN ('B', 'C')` 的事件。如果当天的 A 级事件已经通过 `build_insight()` 生成了独立洞察文章，它们不会出现在日报中。

但实际的 5 月 7 日日报只包含 2 条 C 级 arxiv 论文，而当天最重要的 3 个事件（A 级视频 Agent、A 级途见科技融资、B 级千问语音）完全没有出现在日报中。

### 当前代码位置

- `scripts/export_hugo.py` → `fetch_rows()` L85-L115
- `scripts/export_hugo.py` → `export_hugo()` L190-L230

### 需求

1. **日报应包含当天所有 A/B 级事件**，不仅限于 B/C 级
2. A 级事件在日报中以简短摘要+链接形式出现（链接到独立洞察文章）
3. B 级事件在日报中以完整摘要形式出现

### 具体修改

修改 `export_hugo()` 函数：

```python
# 当前：日报只取 B/C 级
daily_rows = fetch_rows(conn, date, ("B", "C"))

# 改为：日报取 A/B/C 级
daily_rows = fetch_rows(conn, date, ("A", "B", "C"))
```

同时修改 `build_daily()` 的 LLM prompt，让它知道 A 级事件已有独立文章，日报中只需简要提及并链接。

### 验收标准

- [ ] 日报包含当天所有有事件的 A/B/C 级条目
- [ ] A 级事件在日报中以简短摘要 + 链接到独立洞察的形式出现
- [ ] 日报不再出现"今日共跟踪 0 条事件"而当天实际有事件的情况

---

## 需求 7：声明去重

### 问题

事件页正文中"结构化声明"段落与"事件摘要"段落高度重复。例如《AI视频Agent产品面临大厂竞争》：

- 事件摘要提到"字节跳动的Seedance和快手的可灵正在进行一周一小版、两月一大版的高频迭代"
- 结构化声明又列出"字节跳动的Seedance和快手的可灵正在进行一周一小版、两月一大版的高频迭代"

### 当前代码位置

- `scripts/timeline_product.py` → `write_event_page()` L230-L235

### 需求

- 事件页正文不重复罗列 claims（需求 1 已覆盖）
- claims 保留在 frontmatter 供系统使用
- 如果未来需要在页面展示 claims，应与正文叙述融合，而非独立列表

### 验收标准

- [ ] 事件页正文中不出现与摘要重复的声明列表
- [ ] claims 数据仍保留在 frontmatter 的 `claims` 字段中

---

## 需求 8：实体页增加上下文

### 问题

实体页缺少对实体本身的介绍。千问的页面直接从"当前信号"开始，读者不知道千问是什么产品。

### 当前代码位置

- `scripts/entity_product.py` → `write_entity_page()` L195-L210

### 需求

在实体页标题下方增加一段实体介绍，包含：
- 实体类型（公司/产品/模型/组织）的自然语言描述
- 简短的一句话介绍（如果有数据的话）

### 具体修改

在 `write_entity_page()` 中：

```python
# 在 <h1> 之后增加介绍段落
type_labels = {
    "company": "公司",
    "tool": "AI 产品/工具",
    "model": "AI 模型",
    "organization": "组织/机构",
    "person": "人物",
}
type_label = type_labels.get(row["entity_type"], "行业参与者")
intro = f"{row['name']} 是 neican.ai 追踪的 AI 行业{type_label}。"
if row.get("signal"):
    intro += f" {row['signal']}"
```

### 验收标准

- [ ] 实体页标题下方有实体类型和简介
- [ ] 读者打开实体页能立即理解这是什么

---

## 需求 9（低优先级）：跨页面导航

### 问题

事件页、实体页、主题页之间缺少直接的导航链接。读者看完一个事件，不知道如何跳转到相关实体或主题。

### 需求

1. 事件页的实体 chips 可点击，链接到实体页
2. 事件页的主题 chips 可点击，链接到主题页
3. 实体页的事件列表包含事件类型标签

### 当前代码位置

- `hugo-site/layouts/event/single.html` — entity chips 部分

### 具体修改

在 `event/single.html` 中，将实体 chips 改为可点击链接：

```html
<!-- 当前 -->
<span class="entity-chip"><span class="chip-type">{{ .type }}</span>{{ .name }}</span>

<!-- 改为 -->
<a href="/entities/{{ .slug }}/" class="entity-chip"><span class="chip-type">{{ .type }}</span>{{ .name }}</a>
```

### 验收标准

- [ ] 事件页的实体名称可点击跳转到实体页
- [ ] 事件页的主题标签可点击跳转到主题页

---

## 实现顺序

按影响力和依赖关系排序：

| 顺序 | 需求 | 预计工作量 | 依赖 |
|------|------|-----------|------|
| 1 | 需求 2：清理内部字段 | 低（改模板 + 改 frontmatter 构建） | 无 |
| 2 | 需求 1：事件页正文重写 | 中（改 write_event_page 逻辑） | 无 |
| 3 | 需求 7：声明去重 | 低（已被需求 1 覆盖） | 需求 1 |
| 4 | 需求 4：实体页内容升级 | 中（改 entity_product 逻辑） | 无 |
| 5 | 需求 3：首页动态化 | 低（改 Hugo 模板） | 无 |
| 6 | 需求 8：实体页增加上下文 | 低（改 write_entity_page） | 需求 4 |
| 7 | 需求 5：主题页编辑综合 | 中（改 topic_hub_sections） | 无 |
| 8 | 需求 6：日报覆盖修复 | 中（改 export_hugo 逻辑） | 无 |
| 9 | 需求 9：跨页面导航 | 低（改 Hugo 模板） | 需求 2 |

---

## 验证方法

完成所有需求后，执行以下验证：

1. **构建验证**：`cd hugo-site && hugo` — 无报错
2. **内容验证**：检查生成的 HTML 文件中不出现内部术语
   ```bash
   grep -r "编辑判断为\|时间线判断\|结构化声明\|generated_by\|review_status" hugo-site/public/events/ || echo "PASS"
   ```
3. **页面抽样检查**：打开 3 个事件页、2 个实体页、1 个主题页、首页，人工检查阅读体验
4. **日报覆盖验证**：检查最新日报是否包含当天所有 A/B 级事件
5. **链接验证**：检查实体 chips 和主题标签的链接是否可点击且指向正确页面

---

## 不在本次迭代范围内

- LLM 驱动的深度编辑综合（作为需求 1 的方案 B 备选，后续迭代）
- 全站搜索功能
- 实体页的自动生成介绍（基于 LLM 总结实体历史）
- 移动端响应式优化（CSS 已有基础响应式支持）
- 评论系统、推荐系统等交互功能
