---
name: ingest-raw-item
description: Use when raw source items need to be inserted into neican.ai SQLite tables
---

# ingest_raw_item

## 目标

把采集得到的 source item 幂等写入 `raw_items`。

## 触发条件

- RSS item 已解析。
- 手动 URL 内容已提取元数据。

## 输入

```json
{
  "source_id": 1,
  "source_url": "",
  "title": "",
  "author": "",
  "published_at": "",
  "raw_text": "",
  "clean_text": ""
}
```

## 处理步骤

1. 计算 `content_hash`。
2. 查询 `raw_items.content_hash`。
3. 已存在则跳过插入。
4. 不存在则插入 `status='new'`。
5. 写入 `runs` 审计计数。

## 输出

```json
{
  "raw_item_id": 0,
  "status": "new",
  "skipped_duplicate": false
}
```

## 禁止事项

- 不写 events、decisions、Memory Wiki 或 Hugo。
- 不把重复 item 作为新 raw_item 写入。

## 失败处理

字段缺失或数据库错误写入 runs；批处理不得因单条失败整体中断。

## 是否需要人工审核

不需要。
