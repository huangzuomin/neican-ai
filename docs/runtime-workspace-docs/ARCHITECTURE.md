# neican.ai 技术架构说明

## 1. 总体架构

第一阶段采用 OpenClaw 原生架构：

```text
信息源
RSS / 官网博客 / GitHub / arXiv / 手动投递 URL
        ↓
OpenClaw Gateway / Cron
        ↓
sandbox-fetcher 子 Agent
fetch_and_extract Skill / 低权限抓取与沙箱清洗
        ↓
SQLite raw_items
去重、记录、状态管理
        ↓
event_modeling Skill
资讯 → 事件 Event
        ↓
editorial_decision Skill
A/B/C/D 分级与动作决策
        ↓
Memory Wiki
实体、主题、概念、声明、草稿、报告
        ↓
hugo_export Skill
Markdown + Front Matter
        ↓
Hugo Build
        ↓
Git Commit / Deploy
        ↓
neican.ai
```

---

## 2. 架构原则

### 2.1 OpenClaw 是唯一中枢

所有智能处理、任务调度、编辑判断、知识资产维护、发布审批，均围绕 OpenClaw 完成。

禁止第一阶段引入：

```text
n8n
Temporal
LangGraph
自建工作流平台
复杂 Web Admin
```

### 2.2 双 Agent 安全隔离，多 Skill

第一阶段采用两个边界清楚的 Agent 工作区：

```text
neican-editor：主业务 Agent
sandbox-fetcher：低权限抓取子 Agent
```

`neican-editor` 负责编辑判断、知识资产维护、Codex 协作、内容生成、审核协调和发布控制。

`sandbox-fetcher` 负责 RSS 抓取、网页抓取、正文清洗、结构化抽取和隔离外部不可信内容。

第一阶段不扩展为采集 Agent、编辑 Agent、SEO Agent、发布 Agent 等多 Agent 大组织。除 `neican-editor` 与 `sandbox-fetcher` 之外，复杂角色拆分必须留到后续阶段。

外部网页内容不可信，必须先进 `sandbox-fetcher`。知识写入和发布动作必须由 `neican-editor` 控制。

### 2.3 事件优先，文章后置

资讯进入系统后，先建模为 Event，再决定是否生成 Article。

文章不是系统原子，事件才是系统原子。

### 2.4 Knowledge Asset 优先

长期价值来自主题页、实体页、概念页、时间线、结构化声明，而不是单篇快讯。

### 2.5 公开页面与内部知识分离

Memory Wiki 是内部知识资产层。

Hugo 是公开页面输出层。

两者不等价。

---

## 3. 核心组件职责

## 3.0 Agent 工作区

### neican-editor

职责：

- 编辑决策。
- 知识资产维护。
- 内容生成。
- 审核协调。
- 发布控制。

### sandbox-fetcher

职责：

- RSS 抓取。
- 网页抓取。
- 正文清洗。
- 结构化抽取。
- 隔离外部不可信内容。

禁止：

- 写入 Memory Wiki。
- 写入 Hugo content。
- 修改配置。
- 执行 deploy 或 git commit。

## 3.1 OpenClaw Gateway

职责：

- 接收人工指令。
- 支持 IM/CUI 审核入口。
- 展示任务结果。
- 通知发布成功或失败。
- 管理长期运行会话。

## 3.2 OpenClaw Cron

职责：

- 定时抓取信源。
- 定时生成日报。
- 定时检查审核队列。
- 定时触发发布准备。

建议 Cron：

```text
每 2 小时：collect-and-model
每天 18:00：daily-brief-generation
每天 19:00：deploy-preview
每周一 09:00：weekly-synthesis
```

## 3.3 OpenClaw Skills

职责：

- 把采集、清洗、建模、决策、导出、发布等操作封装为可复用工艺。
- 每个 Skill 必须有输入、输出、禁止事项和失败处理。

## 3.4 OpenClaw llm-task

职责：

- 执行结构化 LLM 输出。
- 用 JSON Schema 校验事件建模、编辑决策、SEO 检查结果。
- 避免自由文本污染流程。

## 3.5 OpenClaw Lobster

职责：

- 用于有副作用或需要审批的多步骤操作。
- 特别是 Hugo 导出、build、commit、deploy。
- 支持 approval gate。

## 3.6 Memory Wiki

职责：

长期知识资产：

```text
sources/
entities/
concepts/
topics/
timeline/
syntheses/
drafts/
reports/
```

每个核心页面应尽量包含结构化 claims。

## 3.7 SQLite

职责：

运行账本：

```text
sources
raw_items
events
decisions
review_queue
publish_log
runs
```

SQLite 不存知识正文，不做 CMS。

## 3.8 Hugo

职责：

- 生成公开静态页面。
- 渲染 content 目录。
- 输出 sitemap、RSS、HTML。
- 根据 Front Matter 输出结构化数据。

---

## 4. 关键流程

## 4.1 资讯入库流程

```text
Cron / 手动 URL
→ fetch_and_extract
→ hash_check
→ raw_items 入库
→ event_modeling
→ events 入库
→ editorial_decision
→ decisions 入库
```

## 4.2 内容生成流程

```text
decision = publish_article
→ content_generation
→ SEO quality check
→ drafts 写入 Memory Wiki
→ review_queue 如需审核
```

## 4.3 知识资产更新流程

```text
non-drop event
→ knowledge_asset_update
→ 更新 entities/topics/concepts/timeline
→ 添加 claims
→ 记录 sources
```

## 4.4 日报流程

```text
读取当日 B/C 级事件
→ 生成日报草稿
→ 写入 Memory Wiki reports/drafts
→ 导出 Hugo briefs/daily
```

## 4.5 发布流程

```text
hugo_export
→ local_build_check
→ approval_gate
→ git commit
→ git push GitHub 发布仓库
→ Vercel 自动同步部署
→ post_deploy_verify
→ publish_log
→ notify
```

Hugo 公开站点发布仓库为：

```text
https://github.com/huangzuomin/neican-ai
```

第一阶段后续 deploy-flow 不直接调用 Vercel API；发布动作是把 Hugo 生成内容提交并推送到该 GitHub 仓库，由 Vercel 自动同步。

---

## 5. 安全边界

外部网页内容必须先进入低权限抓取清洗层，不得直接进入主 Agent 可信上下文。

`fetch_and_extract` 禁止：

```text
写 Memory Wiki
写 Hugo content
执行 deploy
修改 config
读取敏感文件
```

发布类 Skill 必须通过 preview 或 approval gate。

---

## 6. 后续可演进组件

仅当真实需求出现时，再考虑：

```text
PostgreSQL：当 SQLite 查询和并发不足时
Meilisearch：当站内搜索体验不足时
Neo4j：当实体关系查询复杂到 Memory Wiki 无法承担时
Next.js Admin：当审核量大到 CUI 不够用时
```
