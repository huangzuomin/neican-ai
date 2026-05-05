---
name: hugo-export
description: Use when neican.ai drafts or decisions need Hugo Markdown output
---

# hugo_export

## 目标

把日报、洞察文章或知识资产导出为 Hugo Markdown。

## 触发条件

- Daily Brief 需要生成。
- A 级 decision 需要 insight 草稿。
- Memory Wiki 草稿需要公开页面候选。

## 输入

```json
{
  "content_type": "insight",
  "source_id": "",
  "draft_path": "",
  "event_id": ""
}
```

## 处理步骤

1. 读取 events、decisions、sources。
2. 生成符合 FRONTMATTER_SPEC.md 的 Front Matter。
3. 确保 insight/date、daily/date、topic/last_updated 等公开日期不是空值或 `0001-01-01`。
4. 对公开正文使用用户可理解标签，不渲染内部 workflow 字段。
5. 写入 `hugo-site/content/`。
6. 同步 insight 草稿到 `memory-wiki/drafts/`。
7. 写 runs。

## 输出

```json
{
  "file_path": "",
  "frontmatter": {},
  "markdown": "",
  "build_required": true
}
```

## 禁止事项

- 不覆盖 `neican.review_status=approved` 文件。
- 不执行 git commit。
- 不部署。

## 失败处理

单文件失败记录 runs，其他文件继续。

## 是否需要人工审核

导出的 draft 需要后续审核或 build 校验。
