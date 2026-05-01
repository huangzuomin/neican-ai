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
2. 生成带判断的正文草稿。
3. 保留 sources、entities、topics、claims。
4. 输出给 hugo_export 或 Memory Wiki draft。

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

## 失败处理

缺少来源或关键字段时停止生成并写 runs。

## 是否需要人工审核

A 级文章草稿需要人工审核。
