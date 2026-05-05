# Hugo Front Matter 标准

## 1. 总原则

所有由 OpenClaw 导出的 Hugo Markdown，必须包含标准 Front Matter。

Front Matter 用于：

1. Hugo 页面渲染。
2. SEO 元数据。
3. 结构化数据生成。
4. 内链生成。
5. OpenClaw 回溯。
6. 发布审计。

不得随意新增不兼容字段。确需新增字段时，应先更新本文件。

---

## 2. Insight 文章页

适用于：

```text
content/insights/*.md
```

标准格式：

```yaml
---
title: ""
date: "2026-05-01T10:00:00+08:00"
slug: ""
type: "insight"
decision_grade: "A"
event_type: ""

entities:
  - slug: ""
    name: ""
    type: "company"

topics:
  - slug: ""
    name: ""

sources:
  - url: ""
    title: ""
    publisher: ""
    date: ""

claims:
  - statement: ""
    confidence: 0.0
    sources:
      - ""
    status: "active"

seo:
  title: ""
  description: ""
  structured_data: "NewsArticle"
  noindex: false

neican:
  event_id: ""
  decision_id: ""
  generated_by: "openclaw"
  review_status: "draft"
---
```

字段说明：

| 字段 | 说明 |
|---|---|
| decision_grade | A/B/C/D |
| event_type | model_release/product_update 等 |
| entities | 关联实体 |
| topics | 关联主题 |
| sources | 来源列表 |
| claims | 结构化声明 |
| seo | SEO 信息 |
| neican | 内部回溯信息 |

`neican`、`event_id`、`decision_id`、`generated_by`、`review_status` 等字段是内部审计字段。它们可以保留在 Front Matter 或 HTML comment 中，但不得在公开页面直接渲染为 `draft`、`needs_review`、`event_26` 等用户不可理解的状态。

---

## 3. Daily Brief 页面

适用于：

```text
content/briefs/daily/*.md
```

标准格式：

```yaml
---
title: "AI 内参日报：2026-05-01"
date: "2026-05-01T18:00:00+08:00"
slug: "2026-05-01"
type: "daily_brief"

covered_events:
  - "evt_20260501_001"
  - "evt_20260501_002"

seo:
  title: "AI 内参日报 2026-05-01"
  description: ""
  structured_data: "Article"
  noindex: false

neican:
  generated_by: "openclaw"
  review_status: "draft"
---
```

正文结构建议：

```markdown
# AI 内参日报：YYYY-MM-DD

## 今日关键判断

## A 级事件

## 行业动态

## 研究与开源

## 值得跟踪

## 来源索引
```

同一个 `covered_events` 条目、`source_url` 或 normalized title 在同一日报中最多出现一次。`covered_events` 是内部回溯字段，不作为公开 chip 列表渲染。

---

## 4. Topic 页面

适用于：

```text
content/topics/<topic-slug>/_index.md
```

标准格式：

```yaml
---
title: ""
slug: ""
type: "topic"
description: ""
last_updated: "2026-05-01T18:00:00+08:00"

related_entities:
  - slug: ""
    name: ""

related_topics:
  - slug: ""
    name: ""

claims:
  - statement: ""
    confidence: 0.0
    sources:
      - ""
    status: "active"

seo:
  title: ""
  description: ""
  structured_data: "Article"
  noindex: false

neican:
  source_memory_path: ""
  generated_by: "openclaw"
  review_status: "approved"
---
```

正文结构必须包含 Topic Hub 头部：

```markdown
## 一句话定义
## 当前判断
## 最近 30 天变化
## 关键实体
## 代表事件
## 下一步观察
```

主题页不是事件列表页；它必须先帮助用户理解主题边界、当前判断和下一步阅读路径。

---

## 5. Entity 页面

适用于：

```text
content/entities/companies/<slug>/_index.md
content/entities/models/<slug>/_index.md
content/entities/tools/<slug>/_index.md
```

标准格式：

```yaml
---
title: ""
slug: ""
type: "entity"
entity_type: "company"
description: ""
official_url: ""
last_updated: "2026-05-01T18:00:00+08:00"

aliases:
  - ""

related_topics:
  - slug: ""
    name: ""

claims:
  - statement: ""
    confidence: 0.0
    sources:
      - ""
    status: "active"

seo:
  title: ""
  description: ""
  structured_data: "Organization"
  noindex: false

neican:
  source_memory_path: ""
  generated_by: "openclaw"
  review_status: "approved"
---
```

entity_type 可选：

```text
company
model
tool
person
organization
```

---

## 6. Concept 页面

适用于：

```text
content/concepts/*.md
```

标准格式：

```yaml
---
title: ""
slug: ""
type: "concept"
description: ""
last_updated: ""

related_topics: []
related_entities: []

claims: []

seo:
  title: ""
  description: ""
  structured_data: "Article"
  noindex: false

neican:
  source_memory_path: ""
  generated_by: "openclaw"
  review_status: "approved"
---
```

---

## 7. Timeline 页面

适用于：

```text
content/timeline/<year>/_index.md
```

标准格式：

```yaml
---
title: "AI 行业时间线：2026"
slug: "2026"
type: "timeline"
year: 2026
last_updated: ""

seo:
  title: "AI 行业时间线 2026"
  description: ""
  structured_data: "Article"
  noindex: false

neican:
  generated_by: "openclaw"
  review_status: "approved"
---
```

---

## 8. SEO 字段规则

### seo.title

建议长度：

```text
20-60 个中文字符
```

### seo.description

建议长度：

```text
60-150 个中文字符
```

### seo.structured_data

可选：

```text
Article
NewsArticle
Organization
FAQPage
BreadcrumbList
```

### seo.noindex

低价值聚合页可设为 true。

默认 false。

---

## 9. Claims 规则

每个 claim 必须包含：

```yaml
statement: ""
confidence: 0.0
sources: []
status: "active"
```

confidence 范围：

```text
0.0 - 1.0
```

status 可选：

```text
active
disputed
outdated
unverified
```

禁止无来源 claim 进入公开页面。

---

## 10. neican 字段规则

`neican` 字段用于内部回溯，不直接展示。

必备：

```yaml
generated_by: "openclaw"
review_status: "draft"
```

review_status 可选：

```text
draft
pending_review
approved
rejected
published
```
