# neican-editor OpenClaw 运行策略

状态：active
适用阶段：测试工作流阶段
更新时间：2026-05-07

## 目标

让 OpenClaw 在 neican-editor 部署后自动推进知识生产、审核和 GitHub 发布，同时保持抓取路由、质量闸门和发布副作用可审计。

## 调度策略

### knowledge-production-cycle

频率：每 4 小时运行一次。

执行入口：

```bash
python3 scripts/heartbeat_pipeline.py --json --full-text --min-fetch-interval 240
```

执行规则：

1. RSS 解析、去重、raw_items 入库由 neican-editor 本地脚本执行。
2. 如 heartbeat 输出 `需要抓取：...`，OpenClaw 主 agent（璇玑）负责调度 info-fetcher，neican-editor 不直接 spawn info-fetcher。
3. 有 `raw_items.status='new'`、未决事件、待决策项或待全文抓取请求时继续推进流水线。
4. 无新进展、无失败、无审批结果时保持静默。

## 测试工作流发布策略

测试工作流阶段允许用审核 skill 代替人工审核。审核通过后，才允许把生成结果推送到 GitHub 发布仓库。

### auto-review-and-publish

触发条件：

1. `knowledge-production-cycle` 生成或更新 Hugo 内容。
2. 存在新的日报、事件页、主题页、实体页、时间线或 insight 输出。
3. `bash scripts/validate.sh` 通过。
4. 审核 skill 给出 `approved` 或等价通过结论。

执行步骤：

1. 运行本地质量闸门：

```bash
bash scripts/validate.sh
```

2. 调用审核 skill，检查：

- 公开页面不暴露 `draft`、`needs_review`、`event_id`、`generated_by` 等内部字段。
- 日报、时间线、实体页、主题页未混入低 AI relevance 内容。
- 高风险、低置信、弱来源内容未被直接作为高置信 A 级发布。
- 新增 timeline track 或候选 track 已通过 `track-review` 规则。
- 生成内容有来源、日期、实体/主题关系和可解释的编辑分级。

3. 审核 skill 通过后，调用 `deploy_and_notify` 发布流程。
4. `deploy_and_notify` 必须再次执行 Hugo build、站内链接检查、diff 摘要和公开字段检查。
5. 通过后 git commit 并 push 到 GitHub 发布仓库：

```text
https://github.com/huangzuomin/neican-ai
```

6. Vercel 由 GitHub push 自动同步部署。脚本不得直接调用 Vercel deploy。
7. 发布结果写入 `publish_log`，并向 Gateway/IM 报告 commit、变更摘要和失败原因。

## 阻断条件

出现以下任一情况时，不得 push 到 GitHub：

- `bash scripts/validate.sh` 失败。
- 审核 skill 未通过、返回不确定、要求人工复核或无结构化结论。
- heartbeat 或 pipeline 出现失败。
- 存在未处理的 `需要抓取：...` 且相关内容依赖全文证据。
- Hugo build 或站内链接检查失败。
- 公开页面泄露内部工作流字段。
- 发布目标不是 `https://github.com/huangzuomin/neican-ai`。

## 人工审核保留边界

测试工作流阶段可以用审核 skill 代替人工审核。进入生产阶段后，以下动作仍应恢复人工审核：

- A 级洞察正式发布。
- 高风险内容发布。
- 大范围实体、主题或时间线结构调整。
- 发布策略、目标仓库或外部通知策略变更。

## OpenClaw 执行摘要

```yaml
agent: neican-editor
stage: test_workflow
timezone: Asia/Shanghai
jobs:
  - id: knowledge-production-cycle
    schedule: "every 4 hours"
    command: "python3 scripts/heartbeat_pipeline.py --json --full-text --min-fetch-interval 240"
    on_info_fetch_request: "route_to_main_agent"
    quiet_when_no_progress: true

  - id: auto-review-and-publish
    trigger: "after knowledge-production-cycle updates Hugo content"
    quality_gate: "bash scripts/validate.sh"
    review: "call review skill; require approved verdict"
    publish: "call deploy_and_notify; commit and push to github.com/huangzuomin/neican-ai"
    block_on:
      - validation_failed
      - review_not_approved
      - pending_info_fetch_dependency
      - hugo_build_failed
      - internal_field_leak
      - wrong_publish_target
```
