# 项目目录结构规范

## 1. 目录总览

Codex 必须严格按以下结构创建和维护项目文件：

```text
neican-ai/
  PROJECT_BRIEF.md
  ARCHITECTURE.md
  DATA_MODEL.md
  DIRECTORY_STRUCTURE.md
  SKILL_SPEC.md
  FRONTMATTER_SPEC.md
  EDITORIAL_RULES.md
  CODEX_TASKS.md

  AGENTS.md
  sandbox-fetcher/
    AGENTS.md

  SOUL.md
  IDENTITY.md
  TOOLS.md
  HEARTBEAT.md

  config/
    sources.yaml
    taxonomy.yaml
    entity_aliases.yaml
    editorial_rules.yaml
    seo_rules.yaml
    hugo_paths.yaml
    risk_rules.yaml

  db/
    schema.sql
    neican.sqlite

  scripts/
    init_db.py
    sqlite_ops.py
    hash_utils.py
    fetch_sources.py
    extract_content.py
    event_modeling.py
    editorial_decision.py
    generate_article.py
    generate_brief.py
    export_hugo.py
    build_hugo.py
    deploy.py

  skills/
    fetch_and_extract/
      SKILL.md
    ingest_raw_item/
      SKILL.md
    event_modeling/
      SKILL.md
    entity_topic_archiving/
      SKILL.md
    editorial_decision/
      SKILL.md
    content_generation/
      SKILL.md
    seo_quality_check/
      SKILL.md
    knowledge_asset_update/
      SKILL.md
    hugo_export/
      SKILL.md
    deploy_and_notify/
      SKILL.md

  schemas/
    raw_item.schema.json
    event.schema.json
    decision.schema.json
    article.schema.json
    claim.schema.json
    frontmatter.schema.json

  flows/
    ingest-flow.md
    deploy-flow.md

  hooks/
    gateway_startup_check.md
    publish_after_log.md
    session_compact_archive.md

  memory-wiki/
    sources/
    entities/
      companies/
      models/
      tools/
      people/
      organizations/
    concepts/
    topics/
    timeline/
    syntheses/
    drafts/
    reports/

  hugo-site/
    content/
      insights/
      briefs/
        daily/
        weekly/
      topics/
      entities/
        companies/
        models/
        tools/
        people/
      concepts/
      timeline/
    layouts/
    static/
    config.toml

  logs/
    runs/
    build/
    publish/

  tests/
    fixtures/
    test_db.py
    test_fetch_sources.py
    test_export_hugo.py
```

---

## 2. 根目录文档

根目录的 8 份前置文档用于约束 Codex 编码行为。

```text
PROJECT_BRIEF.md
ARCHITECTURE.md
DATA_MODEL.md
DIRECTORY_STRUCTURE.md
SKILL_SPEC.md
FRONTMATTER_SPEC.md
EDITORIAL_RULES.md
CODEX_TASKS.md
```

Codex 在每次开始新阶段任务前，必须优先阅读这些文档。

---

## 3. OpenClaw 配置文件与 Agent 工作区

```text
AGENTS.md
sandbox-fetcher/AGENTS.md
SOUL.md
IDENTITY.md
TOOLS.md
HEARTBEAT.md
```

这些文件用于定义 OpenClaw 工作区行为。

`AGENTS.md` 定义 `neican-editor` 主 Agent：编辑决策、知识资产维护、内容生成、审核协调和发布控制。

`sandbox-fetcher/AGENTS.md` 定义低权限抓取子 Agent：RSS 抓取、网页抓取、正文清洗和结构化抽取。该子工作区不得写入 `memory-wiki/`、`hugo-site/`，不得修改 `config/`，不得 deploy 或 git commit。

---

## 4. config/

配置文件目录。

### sources.yaml

保存信源列表。

### taxonomy.yaml

保存主题、实体类型、事件类型等分类体系。

### entity_aliases.yaml

保存实体别名映射，例如：

```yaml
OpenAI:
  - ChatGPT
  - Open AI
```

### editorial_rules.yaml

机器可读编辑规则。

### seo_rules.yaml

SEO 检查规则。

### hugo_paths.yaml

Hugo 导出路径配置。

### risk_rules.yaml

高风险内容判断规则。

---

## 5. db/

数据库目录。

```text
db/schema.sql
db/neican.sqlite
```

`neican.sqlite` 是运行时生成文件，不应手动编辑。

---

## 6. scripts/

Python 脚本目录。

所有脚本必须满足：

1. 可单独运行。
2. 有清晰命令行参数。
3. 出错时返回非零退出码。
4. 重要操作写入 runs 表或 logs。
5. 不擅自调用未批准的外部服务。

---

## 7. skills/

OpenClaw Skill 目录。

每个 Skill 单独一个目录，内含 `SKILL.md`。

不要把所有 Skill 都塞进 `AGENTS.md`。

`AGENTS.md` 只保存总规则和 Skill 索引。

---

## 8. schemas/

JSON Schema 目录。

用于约束 LLM 结构化输出。

第一阶段至少包括：

```text
event.schema.json
decision.schema.json
claim.schema.json
frontmatter.schema.json
```

---

## 9. flows/

OpenClaw Task Flow 说明目录。

第一阶段只保留：

```text
ingest-flow.md
deploy-flow.md
```

其中 deploy-flow 是严格发布流程，必须带审批门。

---

## 10. memory-wiki/

内部知识资产层。

不要把 Memory Wiki 当 Hugo content 使用。

Memory Wiki 可以更细、更内部、更有证据链。

公开页面由 export_hugo 脚本导出到 Hugo。

---

## 11. hugo-site/

公开网站工程。

Codex 不得在未经过 `export_hugo.py` 的情况下随意写入生产内容。

第一阶段允许写入：

```text
hugo-site/content/briefs/daily/
hugo-site/content/insights/
```

---

## 12. logs/

日志目录。

构建日志、发布日志、运行日志都放这里，便于审计。

---

## 13. tests/

测试目录。

第一阶段最低测试：

1. 数据库初始化测试。
2. RSS 抓取模拟测试。
3. Hugo Front Matter 导出测试。
