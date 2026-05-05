---
name: content-generation
description: Use when neican.ai decisions need article or brief draft content
---

# content_generation

## 目标

为 A 级事件生成洞察文章草稿，为 B/C 级事件生成日报内容块。

## 触发条件

- decision.action 为 `publish_article` 或 `daily_brief_only`。
- 来源、entities、topics 和 claims 可追溯。

## 输入

```json
{
  "event": {},
  "decision": {},
  "related_memory": {},
  "sources": []
}
```

## 处理步骤

1. 读取事件和决策。
2. 洞察文章必须先形成明确 thesis，标题要像编辑判断，不像实体/主题聚合结果。
3. 洞察正文使用固定结构：核心判断、发生了什么、为什么重要、影响谁、证据链、反向信号、下一步观察。
4. 日报、主题页和实体页不得渲染 `draft`、`needs_review`、`event_id`、`generated_by` 等内部字段。
5. 保留 sources、entities、topics、claims。
6. 输出给 hugo_export 或 Memory Wiki draft。

## 输出

```json
{
  "title": "",
  "slug": "",
  "summary": "",
  "body_markdown": "",
  "frontmatter": {}
}
```

## 禁止事项

- 不编造 claim。
- 不生成无来源事实。
- 不自动把草稿标为 approved。
- 不把证据数量、实体数量、主题数量当作洞察正文的主要结论。

## 失败处理

缺少来源或关键字段时停止生成并写 runs。

## 是否需要人工审核

A 级文章草稿需要人工审核。
