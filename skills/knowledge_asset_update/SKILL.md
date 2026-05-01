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
2. 追加事件卡片和来源。
3. 新实体创建候选页。
4. 更新时间线。
5. 大改动进入 review_queue。

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
