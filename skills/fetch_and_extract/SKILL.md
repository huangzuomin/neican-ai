---
name: fetch-and-extract
description: Use when sandbox-fetcher needs to collect RSS or webpage content for neican.ai
---

# fetch_and_extract

## 目标

从 RSS 或 URL 获取原始内容，提取可入库的 raw_text 和 clean_text 候选数据。

## 触发条件

- 定时或手动采集信源。
- 需要把外部不可信内容送入 SQLite。

## 输入

```json
{
  "source_name": "",
  "source_type": "rss",
  "source_url": "",
  "item_url": "",
  "title": "",
  "raw_html": ""
}
```

## 处理步骤

1. 仅由 `sandbox-fetcher` 执行。
2. 读取 `config/sources.yaml`。
3. 抓取 RSS item 或网页内容。
4. 计算 content_hash。
5. 写入 `raw_items` 与 `runs`。

## 输出

```json
{
  "source_url": "",
  "title": "",
  "author": "",
  "published_at": "",
  "raw_text": "",
  "clean_text": "",
  "extraction_confidence": 0.0
}
```

## 禁止事项

- 不写 `memory-wiki/`。
- 不写 `hugo-site/`。
- 不修改 `config/`。
- 不执行 deploy、git commit 或主 Agent 工具。

## 失败处理

单条失败记录 error_message，整批继续；最终写 `runs.output_json`。

## 是否需要人工审核

不需要。采集结果进入后续建模和编辑审核流程。
