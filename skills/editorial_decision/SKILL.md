---
name: editorial-decision
description: Use when modeled neican.ai events need A/B/C/D editorial decisions
---

# editorial_decision

## 目标

按编辑规则把事件分为 A/B/C/D，并写入 decisions 与 review_queue。

## 触发条件

- events 已建模。
- 尚无对应 decision。

## 输入

```json
{
  "event_id": 0,
  "importance_score": 0,
  "seo_value_score": 0,
  "knowledge_value_score": 0,
  "risk_score": 0,
  "confidence": 0.0
}
```

## 处理步骤

1. 读取 `config/editorial_rules.yaml`。
2. 已被 AI relevance gate 标记为无关的内容不得升级为 A/B/C。
3. confidence < 0.5 评为 D。
4. 高风险进入 review_queue。
5. 按 `config/source_trust.yaml` 计算 source trust tier。
6. 政策、安全、争议等高风险 A 级候选必须有 S/A 级或多源证据，否则降级为 review_required。
7. 满足 A/B 阈值则输出对应等级。
8. Mock C 级使用 entity/topic 存在性判断。
9. 写 decisions、review_queue 和 runs。

## 输出

```json
{
  "decision_id": 0,
  "decision_grade": "A",
  "action": "publish_article",
  "need_review": true
}
```

## 禁止事项

- 不生成文章。
- 不写 Hugo。
- 不自动发布。

## 失败处理

单事件失败写 runs；不得影响其他事件决策。

## 是否需要人工审核

A 级、高风险、deploy 等触发项需要人工审核。
