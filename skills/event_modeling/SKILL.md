---
name: event-modeling
description: Use when clean raw_items need to become structured neican.ai events
---

# event_modeling

## 目标

把 `raw_items.clean_text` 转换为 `events` 表中的结构化事件。

## 触发条件

- `raw_items.status='new'`。
- `clean_text IS NOT NULL`。

## 输入

```json
{
  "raw_item_id": 0,
  "title": "",
  "clean_text": "",
  "source_url": ""
}
```

## 处理步骤

1. 读取待建模 raw_items。
2. 先按 `config/editorial_rules.yaml` 的 `ai_relevance_gate` 计算 AI 相关性。
3. 低于阈值的 raw item 标记为 `ignored`，不写 events，不进入日报/时间线/实体。
4. Mock 版用关键词规则生成 event_type。
5. 从配置匹配 entities 和 topics。
6. 计算 mock 分数、AI relevance 和 confidence。
7. 写入 events。
8. 将 raw_item 标记为 `processed`。
9. 写 runs。

## 输出

```json
{
  "event_id": 0,
  "event_title": "",
  "event_type": "",
  "confidence": 0.6
}
```

## 禁止事项

- Round 4 不调用真实 LLM。
- 不写 Memory Wiki、Hugo 或 decisions。
- 不把泛财经、社会、宏观、交通、文娱等弱 AI 相关内容强行建模为 AI 行业事件。

## 失败处理

单条失败写 runs error_message；已成功事件保留。

## 是否需要人工审核

不需要。审核由 editorial_decision 触发。
