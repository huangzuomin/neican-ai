# TOOLS.md

## Tool Notes

This file documents how `neican-editor` should think about tools that are already available in the runtime environment.

This file does not grant tool access. It only documents how the agent should use tools that are already available in the runtime environment.

## Rules

- Do not invent tools.
- Do not invent command flags.
- Do not run destructive commands without explicit permission.
- Prefer documented scripts over ad-hoc shell commands.
- Do not claim runtime validation unless the exact documented runtime test command was actually run.

## Available Capabilities

The agent has access to these local Skills for domain-specific workflows:

- `skills/fetch_and_extract/` — delegated to sandbox-fetcher
- `skills/ingest_raw_item/` — raw item ingestion
- `skills/event_modeling/` — event, entity, topic, and claim modeling
- `skills/editorial_decision/` — A/B/C/D grading and review triggers
- `skills/content_generation/` — articles, briefs, and index content
- `skills/knowledge_asset_update/` — Memory Wiki asset maintenance
- `skills/hugo_export/` — Hugo content export
- `skills/deploy_and_notify/` — approved publish and notify

Use Skills only when the task matches their scope.

## info-fetcher Route（强制规则）

**绝对约束：**

1. neican-editor **禁止**直接 spawn、调用或调度 info-fetcher agent。
2. neican-editor **禁止**自行编写 HTTP 抓取脚本（requests、urllib、curl 等）抓取外部网页全文。
3. neican-editor **禁止**使用 web_fetch、web_search 等工具直接抓取外部 URL 全文。
4. neican-editor **禁止**在 tmux、nohup 或任何后台进程中运行外部网页抓取。
5. 所有外部信息抓取必须通过路由：neican-editor 输出 `需要抓取：<具体任务描述>` → 主 agent（璇玑）调度 info-fetcher → 结果转发回 neican-editor。
6. 当路由链不通（主 agent 未在线）时，neican-editor 应等待并提示用户启动主 agent，不得自行越权抓取。

**违反以上规则属于越权行为。**

路由信号格式：
```text
需要抓取：<具体任务描述>
```

主 agent（璇玑）负责调度 info-fetcher 并转发结果。本地脚本仅保留确定性 RSS 逻辑：

- `scripts/fetch_sources.py` 解析 RSS、去重、写入 `raw_items`、记录全文需求到 `info_fetch_requests`
- `scripts/heartbeat_pipeline.py` 打印待处理的 `需要抓取：...` 信号
- `scripts/info_fetch_requests.py` 管理请求队列和消费转发回来的结果

## Development Repository Commands

```bash
bash scripts/validate.sh
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

Deployment must only happen after the user explicitly requests it.

## Key Config Files

- `config/source_trust.yaml` — S/A/B/C source trust tiers
- `config/entity_allowlist.yaml` — approved and suppressed entities
- `config/editorial_rules.yaml` — editorial decision policy
- `config/risk_rules.yaml` — high-risk content routing
- `config/sources.yaml` — configured information sources
