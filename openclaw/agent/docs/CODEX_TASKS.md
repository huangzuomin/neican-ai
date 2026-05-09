# Codex 实施任务清单

## 1. 使用原则

Codex 是施工队，不是架构师。

每次任务必须：

1. 只完成当前阶段。
2. 不引入未批准框架。
3. 不跨阶段实现功能。
4. 输出修改文件列表。
5. 输出运行和验证方式。
6. 保证代码可回滚。
7. 优先写可测试、可单独运行的小脚本。

---

## 2. 阶段 0：项目初始化

### 目标

创建项目基础目录、配置文件、SQLite schema 和初始化脚本。

### 任务

1. 创建 `DIRECTORY_STRUCTURE.md` 中定义的目录结构。
2. 改写主工作区 `AGENTS.md` 为 `neican-editor` 业务专用版本。
3. 创建 `sandbox-fetcher/AGENTS.md`，写清低权限抓取子 Agent 的权限边界。
4. 创建 config 示例文件：
   - `sources.yaml`
   - `taxonomy.yaml`
   - `entity_aliases.yaml`
   - `editorial_rules.yaml`
   - `seo_rules.yaml`
   - `hugo_paths.yaml`
   - `risk_rules.yaml`
5. 创建 `db/schema.sql`。
6. 创建 `scripts/init_db.py`。
7. 创建 `scripts/sqlite_ops.py`。
8. 创建 `README.md`。

### 禁止事项

```text
不实现 RSS 抓取
不调用 LLM
不生成文章
不导出 Hugo
不实现 Web Admin
不引入 PostgreSQL
不引入 n8n
不让 sandbox-fetcher 写 Memory Wiki 或 Hugo content
```

### 验收标准

```bash
python scripts/init_db.py
```

必须：

1. 创建 `db/neican.sqlite`。
2. 成功创建所有表。
3. 可重复运行不报错。
4. 输出初始化成功信息。

---

## 3. 阶段 1：信源抓取与 raw_items 入库

### 目标

支持从 RSS 信源抓取内容并写入 raw_items。

### 任务

1. 实现 `scripts/fetch_sources.py`。
2. 读取 `config/sources.yaml`。
3. 支持 RSS feed。
4. 生成 content_hash。
5. 去重写入 raw_items。
6. 写入 runs 记录。

### 推荐依赖

如需依赖，应优先使用：

```text
feedparser
requests
beautifulsoup4
pyyaml
```

### 验收标准

```bash
python scripts/fetch_sources.py --limit 5
```

必须：

1. 能抓取测试 RSS。
2. raw_items 中生成记录。
3. 重复运行不会重复入库。
4. 失败有错误日志。

---

## 4. 阶段 2：内容清洗与抽取

### 目标

把 raw_items 的 raw_text 或网页内容变成 clean_text。

### 任务

1. 实现 `scripts/extract_content.py`。
2. 支持基础 HTML 清洗。
3. 保存 clean_text。
4. 标记 extraction confidence。
5. 不接触 Memory Wiki 和 Hugo。

### 验收标准

```bash
python scripts/extract_content.py --raw-item-id 1
```

必须：

1. clean_text 非空。
2. 不执行危险操作。
3. 失败写入 error_message。

---

## 5. 阶段 3：事件建模 Mock 版

### 目标

先不用真实 LLM，使用 mock 规则把 raw_items 转换为 events，跑通数据库流程。

### 任务

1. 实现 `scripts/event_modeling.py`。
2. 读取 raw_items status=new。
3. 生成 mock event。
4. 写入 events。
5. raw_items status 改为 processed。

### 验收标准

```bash
python scripts/event_modeling.py --mock --limit 5
```

必须：

1. events 表有记录。
2. raw_items 状态更新。
3. events 字段结构符合 DATA_MODEL.md。

---

## 6. 阶段 4：编辑决策规则版

### 目标

不用 LLM，先用规则对 events 分级。

### 任务

1. 实现 `scripts/editorial_decision.py`。
2. 根据 importance_score、seo_value_score、knowledge_value_score、risk_score、confidence 生成 A/B/C/D。
3. 写入 decisions。
4. A 级或高风险写入 review_queue。

### 验收标准

```bash
python scripts/editorial_decision.py --limit 10
```

必须：

1. decisions 表有记录。
2. A 级进入 review_queue。
3. D 级 action=ignore。

---

## 7. 阶段 5：Hugo 导出 Mock 版

### 目标

根据 events + decisions 生成 Hugo Markdown 草稿。

### 任务

1. 实现 `scripts/export_hugo.py`。
2. 生成 daily brief。
3. 为 A 级事件生成 insight draft。
4. Front Matter 符合 `FRONTMATTER_SPEC.md`。
5. 输出到 `hugo-site/content/`。

### 验收标准

```bash
python scripts/export_hugo.py --date 2026-05-01 --mock
```

必须：

1. 生成 `hugo-site/content/briefs/daily/<date>.md`。
2. A 级事件生成 `hugo-site/content/insights/*.md`。
3. Front Matter 可被 Hugo 读取。
4. 文件内容包含 sources、entities、topics、claims。

---

## 8. 阶段 6：Hugo build

### 目标

支持本地构建校验。

### 任务

1. 实现 `scripts/build_hugo.py`。
2. 执行 `hugo --gc` 或项目配置命令。
3. 保存 build 日志到 `logs/build/`。
4. 构建失败时返回非零退出码。

### 验收标准

```bash
python scripts/build_hugo.py
```

必须：

1. 成功时输出 build 成功。
2. 失败时保存错误日志。
3. 不自动 git commit。

---

## 9. 阶段 7：OpenClaw Skill 文档

### 目标

创建所有核心 Skill 的 `SKILL.md`。

### 任务

1. 创建 `skills/fetch_and_extract/SKILL.md`。
2. 创建 `skills/ingest_raw_item/SKILL.md`。
3. 创建 `skills/event_modeling/SKILL.md`。
4. 创建 `skills/editorial_decision/SKILL.md`。
5. 创建 `skills/content_generation/SKILL.md`。
6. 创建 `skills/knowledge_asset_update/SKILL.md`。
7. 创建 `skills/hugo_export/SKILL.md`。
8. 创建 `skills/deploy_and_notify/SKILL.md`。

### 验收标准

每个 Skill 文档必须包含：

```text
目标
输入
处理步骤
输出
禁止事项
失败处理
```

---

## 10. 阶段 8：接入真实 LLM / OpenClaw llm-task

### 目标

在 Mock 版跑通后，把 event_modeling 和 editorial_decision 切换为结构化 LLM 输出。

### 任务

1. 根据 `schemas/event.schema.json` 约束 event_modeling。
2. 根据 `schemas/decision.schema.json` 约束 editorial_decision。
3. 失败允许重试 1 次。
4. 输出校验失败则写入 failed 状态。

### 禁止事项

```text
不得绕过 JSON Schema
不得让 LLM 直接写 Hugo 文件
不得让 LLM 直接部署
```

---

## 11. 阶段 9：Memory Wiki 更新

### 目标

把非 D 级事件沉淀到 Memory Wiki。

### 任务

1. 更新 entities。
2. 更新 topics。
3. 更新 concepts。
4. 更新时间线。
5. 写入 claims。
6. 新实体进入 review_queue。

### 验收标准

1. Memory Wiki 有新增或更新页面。
2. 每个新增 claim 都有 source。
3. 大段修改不会自动覆盖。

---

## 12. 阶段 10：deploy-flow

### 目标

实现发布前校验和 Git 提交流程。

### 任务

1. build 成功后生成 diff 摘要。
2. push 到 GitHub 发布仓库前进入审批。
3. 审批通过后 git add/commit/push 到 `https://github.com/huangzuomin/neican-ai`。
4. 写 publish_log。
5. 失败通知。

### 验收标准

1. 未审批不提交、不 push。
2. build 失败不提交。
3. publish_log 记录 commit hash。
4. 不直接调用 Vercel deploy；Vercel 由 GitHub push 自动同步。

---

## 13. 给 Codex 的第一条提示词

正式编码前，先让 Codex 对齐：

```text
请先阅读本项目根目录下的以下文档：

- PROJECT_BRIEF.md
- ARCHITECTURE.md
- DATA_MODEL.md
- DIRECTORY_STRUCTURE.md
- SKILL_SPEC.md
- FRONTMATTER_SPEC.md
- EDITORIAL_RULES.md
- CODEX_TASKS.md

不要立即写代码。

请先完成三件事：

1. 用你自己的话复述本项目第一阶段 MVP 的目标。
2. 检查这些文档之间是否存在冲突、遗漏或不清楚的地方。
3. 按 CODEX_TASKS.md 给出你建议的第一轮实现计划，要求每一步都能独立运行和测试。

注意：
- 不要引入 n8n、Temporal、LangGraph、PostgreSQL、Neo4j、Next.js。
- 不要创建 Web Admin。
- 不要扩展为多 Agent 大组织；第一阶段只允许 `neican-editor` + `sandbox-fetcher`。
- 第一阶段只围绕 OpenClaw + SQLite + Memory Wiki + Hugo。
- 任何写文件、发布、覆盖内容的动作都必须可审计、可回滚。
```

---

## 14. 第一轮编码提示词

```text
现在开始执行阶段 0：项目初始化。

请严格按照 DIRECTORY_STRUCTURE.md 和 CODEX_TASKS.md 实施。

本轮只允许完成以下事项：

1. 创建项目目录结构。
2. 创建 config 示例文件：
   - sources.yaml
   - taxonomy.yaml
   - entity_aliases.yaml
   - editorial_rules.yaml
   - seo_rules.yaml
   - hugo_paths.yaml
   - risk_rules.yaml
3. 创建 db/schema.sql。
4. 创建 scripts/init_db.py。
5. 创建 scripts/sqlite_ops.py 的基础连接和执行函数。
6. 创建 README.md，说明如何初始化数据库。
7. 创建 `sandbox-fetcher/AGENTS.md`，写清抓取子 Agent 的禁止事项和输出契约。

禁止事项：

- 不要实现 RSS 抓取。
- 不要实现 LLM 调用。
- 不要实现 Hugo 导出。
- 不要引入 Web Admin。
- 不要引入额外数据库。
- 不要写与阶段 0 无关的代码。

完成后请输出：
1. 修改文件列表。
2. 每个文件作用。
3. 如何运行初始化。
4. 如何验证结果。
```
