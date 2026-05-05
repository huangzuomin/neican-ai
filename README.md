# neican.ai MVP Workspace

neican.ai 是面向 AI 行业的知识生产与发布工作区。第一阶段 MVP 聚焦可信信息采集、事件建模、编辑决策、Memory Wiki 知识资产维护，以及 Hugo 内容导出。

## 双 Agent 架构

- `neican-editor`：主 Agent，负责编辑决策、知识资产、内容生成、审核协调与发布控制。
- `sandbox-fetcher`：低权限子 Agent，负责 RSS/网页抓取、正文清洗和结构化抽取。

外部不可信内容必须先经过 `sandbox-fetcher` 清洗和结构化后，才供 `neican-editor` 消费。

## 初始化

```bash
python3 scripts/init_db.py
```

重复运行应保持幂等，并输出：

```text
[OK] neican.sqlite initialized with 7 tables
```

## 目录

- `config/`：来源、分类、编辑、SEO、风险与 Hugo 路径配置。
- `db/`：SQLite schema 与本地数据库。
- `scripts/`：初始化和后续流水线脚本。
- `schemas/`：结构化输入输出 JSON Schema。
- `flows/`：采集与发布流程边界。
- `memory-wiki/`：内部知识资产，格式与 Hugo Front Matter 一致。
- `hugo-site/`：静态站点内容与 Hugo 配置。
- `sandbox-fetcher/`：低权限抓取子 Agent 工作区。
- `tests/`：验收与回归测试。

## 当前阶段

Round 0 建立项目骨架、双 Agent 工作区、配置、SQLite schema 和初始化脚本。后续 Round 会在此基础上继续实现抓取、清洗、事件建模、编辑决策与 Hugo 导出。

## 主流水线

可以直接运行一键流水线：

```bash
python3 scripts/pipeline.py --date 2026-05-01 --full-text
```

Heartbeat/定时触发入口：

```bash
python3 scripts/heartbeat_pipeline.py --json --full-text
```

`heartbeat_pipeline.py` 会先检查是否存在待处理 raw_items / modeled events / pending decisions，或是否已经超过抓取间隔；只有需要时才继续调用 `pipeline.py`。

## 发布方式

Hugo 公开站点的发布目标是 GitHub 仓库：

```text
https://github.com/huangzuomin/AInews
```

发布流程为 Hugo build 校验通过并审批后，提交并 push 到该仓库；Vercel 监听 GitHub 更新后自动同步部署。项目脚本不直接调用 Vercel deploy。
