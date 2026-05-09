---
name: knowledge-asset-update
description: Use when neican.ai events should update Memory Wiki assets
---

# knowledge_asset_update

## 目标

把非 D 级事件沉淀到 Memory Wiki 的实体、主题、概念和时间线中。

## 触发条件

- decision_grade 为 A/B/C。
- event 含可追溯 source。

## 输入

```json
{
  "event": {},
  "decision": {},
  "claims": [],
  "entities": [],
  "topics": []
}
```

## 处理步骤

1. 定位相关 Memory Wiki 页面。
2. 按 `config/entity_allowlist.yaml` 与启发式规则判定 `entity_role` 和 `entity_quality`。
3. 只有 approved 且属于 core_actor/product_or_model/infrastructure/regulator 的实体可以进入公开实体页。
4. source_media、mentioned_context、noise 只进入来源、上下文或审核数据，不默认建档。
5. 追加事件卡片和来源。
6. 新实体创建候选页。
7. 更新时间线。
8. 大改动进入 review_queue。

## 输出

```json
{
  "updated_paths": [],
  "created_paths": [],
  "review_required": false
}
```

## 禁止事项

- 不无来源新增 claim。
- 不大段覆盖已有资产。
- 不写 Hugo public content。

## 失败处理

写入失败保留原文件，记录 error_message。

## 是否需要人工审核

新实体、大段修改、高风险 claim 需要审核。
