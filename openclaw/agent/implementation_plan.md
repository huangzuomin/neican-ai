# neican.ai 第一阶段 MVP 实施计划

## 已确认的设计决策

| 决策项 | 确认结果 |
|---|---|
| sandbox-fetcher 形态 | **独立 OpenClaw 子 Agent 工作区**（有自己的 AGENTS.md + 权限约束） |
| sources.yaml 同步方式 | **每次运行 fetch_sources.py 时 upsert** sources 表 |
| Memory Wiki 内部格式 | **与 Hugo Front Matter 相同**（YAML Front Matter + Markdown 正文） |
| hugo-site 初始化方式 | **从零初始化**，不兼容旧站 |
| Hugo 发布方式 | **push 到 GitHub 仓库 `https://github.com/huangzuomin/neican-ai`，由 Vercel 自动同步部署** |

---

## 当前状态（活计划）

```text
workspace-neican-editor/   ← neican-editor 主 Agent 工作区（已存在）
  .git/
  .openclaw/workspace-state.json
  AGENTS.md               ← 已改写为 neican-editor 业务专用
  BOOTSTRAP.md
  HEARTBEAT.md
  IDENTITY.md / SOUL.md / TOOLS.md / USER.md
  docs/                   ← 8 份项目约束文档（已存在）
  config/ db/ scripts/ schemas/ flows/ hooks/
  memory-wiki/ hugo-site/ logs/ tests/
  sandbox-fetcher/        ← 低权限抓取子 Agent 工作区（已存在）
  项目目标.md              ← 意图声明文档（已存在）
```

### 已完成

- **Round 0 已完成**：项目骨架、双 Agent 工作区、配置、SQLite schema、初始化脚本、JSON Schema、Flow 文档、Hugo 骨架、README。
- **Round 1 已完成**：6 份 docs 已按「项目目标.md」更新，双 Agent 安全隔离与 `extraction_confidence` 已同步到约束文档。
- **Round 2 已完成**：RSS 采集入口、sources upsert、raw_items hash 去重、runs 审计。
- **Round 3 已完成**：raw_text 清洗为 clean_text，写入 extraction_confidence，成功后保持 status=new。
- **Round 4 已完成**：Mock 事件建模，写 events，并将 raw_items 标记为 processed。
- **Round 5 已完成**：规则版编辑决策，写 decisions 和 review_queue。
- **Round 6 已完成**：Hugo Daily Brief / Insight mock 导出，同步 Memory Wiki draft。
- **Round 7 已完成实现**：Hugo build 校验脚本已实现；当前机器缺少 Hugo，可验证失败日志路径。
- **Round 8 已完成**：8 个核心 Skill 文档和测试 fixture 已补齐。

### 已验证

```bash
python3 scripts/init_db.py
python3 scripts/init_db.py
python3 -m pytest tests/test_init_db.py
python3 -m pytest tests/ -v
```

> 当前环境默认使用 `python3`。若后续虚拟环境中 `python` 指向正确解释器，也可等价使用 `python`。

### 下一步

第一阶段 Round 0-8 已跑通。下一步进入阶段二前，建议先补齐环境依赖中的 Hugo 可执行文件，再决定是否推进 Round 9（真实 LLM）或先处理 Round 7 的真实 build 成功路径。

---

## 已迭代的前置文档

> [!IMPORTANT]
> 以下文档已在 Round 1 更新完毕；Codex 后续编码施工以更新后版本为准。

| 文档 | 变更内容 |
|---|---|
| `docs/PROJECT_BRIEF.md` | 顶部加「最终版项目目标」标准段落；非目标补"不做旧站迁移/全站改版" |
| `docs/ARCHITECTURE.md` | 2.2节改为双Agent安全隔离架构（neican-editor + sandbox-fetcher） |
| `docs/DATA_MODEL.md` | raw_items 表加 `extraction_confidence REAL DEFAULT NULL` 字段 |
| `docs/DIRECTORY_STRUCTURE.md` | 新增 sandbox-fetcher/ 子工作区目录定义 |
| `docs/SKILL_SPEC.md` | fetch_and_extract 执行者改为 sandbox-fetcher 子 Agent |
| `docs/CODEX_TASKS.md` | 阶段0新增 sandbox-fetcher/AGENTS.md 初始化任务 |

---

## 实施计划总览

```
Round 0  项目骨架与双 Agent 初始化          ✅ 已完成
Round 1  文档迭代（6份docs更新）            ✅ 已完成
Round 2  沙箱采集层：RSS 抓取 + raw_items 入库 ✅ 已完成
Round 3  沙箱清洗层：HTML 清洗 + clean_text 提取 ✅ 已完成
Round 4  事件建模 Mock 版                   ✅ 已完成
Round 5  编辑决策规则版                     ✅ 已完成
Round 6  Hugo 导出 Mock 版                  ✅ 已完成
Round 7  Hugo Build 校验                    ✅ 已实现；本机缺 Hugo，真实 build 失败日志已验证
Round 8  Skill 文档 + 测试文件              ✅ 已完成
```

---

## Round 0 — 项目骨架与双 Agent 初始化

**目标**：创建所有目录、配置、SQLite schema、初始化脚本，建立双 Agent 工作区。

### 0-A：neican-editor 主工作区改写

#### [MODIFY] `AGENTS.md`
改写为 neican-editor 业务专用版本，替换通用 OpenClaw 模板内容：
- 身份：neican-editor，AI 行业知识生产主 Agent
- 职责：编辑决策 / 知识资产维护 / 内容生成 / 审核协调 / 发布控制
- Skill 索引：指向 skills/ 各目录
- 红线：不直接处理外部不可信网页内容；所有 deploy 需审批

### 0-B：sandbox-fetcher 子 Agent 工作区

#### [NEW] `sandbox-fetcher/AGENTS.md`
```markdown
# sandbox-fetcher

低权限抓取子 Agent。负责 RSS 抓取、网页抓取、正文清洗、结构化抽取。

## 权限约束（Red Lines）

禁止：
- 写入 memory-wiki/
- 写入 hugo-site/
- 修改 config/
- 读取 db/neican.sqlite 之外的敏感文件
- 执行 deploy 或 git commit
- 调用主 Agent 工具

允许：
- 读取 config/sources.yaml
- 写入 db/neican.sqlite（仅 raw_items、runs 两张表）
- 写入 logs/runs/

## 输出契约

所有输出必须经过 clean_text 提取，以结构化 JSON 形式
写入 SQLite，供 neican-editor 读取消费。
```

### 0-C：目录结构创建

按 DIRECTORY_STRUCTURE.md（更新后）创建：

```text
config/
db/
scripts/
skills/
  fetch_and_extract/
  ingest_raw_item/
  event_modeling/
  editorial_decision/
  content_generation/
  knowledge_asset_update/
  hugo_export/
  deploy_and_notify/
schemas/
flows/
hooks/
memory-wiki/
  sources/ entities/companies/ entities/models/
  entities/tools/ entities/people/ entities/organizations/
  concepts/ topics/ timeline/ syntheses/ drafts/ reports/
hugo-site/
  content/insights/ content/briefs/daily/ content/briefs/weekly/
  content/topics/ content/entities/ content/concepts/ content/timeline/
  layouts/ static/
logs/
  runs/ build/ publish/
tests/
  fixtures/
sandbox-fetcher/
```

### 0-D：配置文件骨架

#### [NEW] `config/sources.yaml`
```yaml
sources:
  - name: "OpenAI Blog"
    type: rss
    url: "https://openai.com/blog/rss.xml"
    enabled: true
    trust_level: 5
    language: en
    fetch_interval_minutes: 120

  - name: "Anthropic News"
    type: rss
    url: "https://www.anthropic.com/news/rss"
    enabled: true
    trust_level: 5
    language: en
    fetch_interval_minutes: 120

  - name: "Google DeepMind Blog"
    type: rss
    url: "https://deepmind.google/blog/rss.xml"
    enabled: true
    trust_level: 5
    language: en
    fetch_interval_minutes: 120

  - name: "MIT Technology Review AI"
    type: rss
    url: "https://www.technologyreview.com/feed/"
    enabled: true
    trust_level: 4
    language: en
    fetch_interval_minutes: 180

  - name: "The Verge AI"
    type: rss
    url: "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"
    enabled: true
    trust_level: 3
    language: en
    fetch_interval_minutes: 120
```

#### [NEW] `config/editorial_rules.yaml`
```yaml
grades:
  A:
    importance_score_min: 75
    seo_value_score_min: 60
    knowledge_value_score_min: 70
    confidence_min: 0.75
    risk_score_max: 69
    action: publish_article
    need_review: true

  B:
    importance_score_min: 45
    knowledge_value_score_min: 40
    confidence_min: 0.65
    action: daily_brief_only
    need_review: false

  C:
    has_related_event: true
    action: update_assets_only
    need_review: false

  D:
    action: ignore
    need_review: false

review_triggers:
  - a_grade_article
  - new_entity_created
  - risk_score_gte: 70
  - event_confidence_lt: 0.70
  - claim_confidence_lt: 0.70
  - major_asset_update
  - deploy_approval
```

#### [NEW] `config/taxonomy.yaml`
```yaml
event_types:
  - model_release
  - product_update
  - company_strategy
  - research_paper
  - policy
  - tool_launch
  - funding
  - safety_issue
  - market_signal
  - industry_trend
  - other

entity_types:
  - company
  - model
  - tool
  - person
  - organization

topic_slugs:
  - ai-agents
  - vibe-coding
  - rag
  - mcp
  - ai-search
  - embodied-ai
  - llm
  - multimodal
  - ai-safety
  - ai-policy
```

#### [NEW] `config/risk_rules.yaml`
```yaml
high_risk_keywords:
  - 安全漏洞
  - 法律诉讼
  - 人物指控
  - 财务数据
  - 未经证实
  - 政治
  - 监管处罚

risk_score_threshold: 70
auto_publish_blocked_above: 70
```

#### [NEW] `config/entity_aliases.yaml`
```yaml
OpenAI:
  - Open AI
  - ChatGPT maker

Anthropic:
  - Claude maker

Google DeepMind:
  - DeepMind
  - Google AI

Meta AI:
  - Meta Platforms AI
  - FAIR
```

#### [NEW] `config/seo_rules.yaml`
```yaml
title:
  min_chars: 10
  max_chars: 60

description:
  min_chars: 60
  max_chars: 150

requirements:
  min_entities: 1
  min_topics: 1
  min_sources: 1
  no_unsourced_claims: true
  no_pure_translation: true
```

#### [NEW] `config/hugo_paths.yaml`
```yaml
base_dir: hugo-site/content

paths:
  insight: insights/{slug}.md
  daily_brief: briefs/daily/{date}.md
  weekly_brief: briefs/weekly/{date}.md
  topic: topics/{slug}/_index.md
  entity: entities/{entity_type}/{slug}/_index.md
  concept: concepts/{slug}.md
  timeline: timeline/{year}/_index.md
```

### 0-E：SQLite Schema

#### [NEW] `db/schema.sql`
```sql
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  trust_level INTEGER NOT NULL DEFAULT 3,
  language TEXT DEFAULT 'en',
  fetch_interval_minutes INTEGER DEFAULT 120,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER,
  source_url TEXT NOT NULL,
  title TEXT,
  author TEXT,
  published_at TEXT,
  fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  raw_text TEXT,
  clean_text TEXT,
  content_hash TEXT NOT NULL UNIQUE,
  extraction_confidence REAL DEFAULT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  duplicate_of INTEGER,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_item_id INTEGER NOT NULL,
  event_title TEXT NOT NULL,
  event_summary TEXT,
  event_type TEXT,
  event_date TEXT,
  entities_json TEXT,
  topics_json TEXT,
  claims_json TEXT,
  importance_score REAL DEFAULT 0,
  seo_value_score REAL DEFAULT 0,
  knowledge_value_score REAL DEFAULT 0,
  risk_score REAL DEFAULT 0,
  confidence REAL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'modeled',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (raw_item_id) REFERENCES raw_items(id)
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  decision_grade TEXT NOT NULL,
  reason TEXT,
  need_review INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS review_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_type TEXT NOT NULL,
  target_id INTEGER NOT NULL,
  review_type TEXT NOT NULL,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  context_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content_type TEXT NOT NULL,
  slug TEXT,
  file_path TEXT,
  git_commit TEXT,
  published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL,
  message TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT,
  output_json TEXT,
  error_message TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
```

### 0-F：初始化脚本

#### [NEW] `scripts/sqlite_ops.py`
提供：`get_conn(db_path)`, `execute(conn, sql, params)`, `fetchall(conn, sql, params)`, `fetchone(conn, sql, params)`, `upsert(conn, table, data, conflict_col)`

#### [NEW] `scripts/init_db.py`
- 读取 `db/schema.sql`
- 创建 `db/neican.sqlite`
- 幂等运行（IF NOT EXISTS）
- 输出 `[OK] neican.sqlite initialized with 7 tables`

### 0-G：JSON Schema 骨架

#### [NEW] `schemas/event.schema.json`
#### [NEW] `schemas/decision.schema.json`
#### [NEW] `schemas/claim.schema.json`
#### [NEW] `schemas/frontmatter.schema.json`
#### [NEW] `schemas/raw_item.schema.json`
#### [NEW] `schemas/article.schema.json`

### 0-H：Flow 文档骨架

#### [NEW] `flows/ingest-flow.md`
说明采集流程，标注 sandbox-fetcher / neican-editor 各自的边界。

#### [NEW] `flows/deploy-flow.md`
说明发布流程，标注审批门位置，说明未审批不得 commit。

### 0-I：Hugo 骨架

#### [NEW] `hugo-site/config.toml`
```toml
baseURL = "https://neican.ai/"
languageCode = "zh-cn"
title = "neican.ai"
theme = ""
```

### 0-J：README

#### [NEW] `README.md`
说明项目定位、双 Agent 架构、初始化步骤、运行方式。

**Round 0 验收**：
```bash
python3 scripts/init_db.py
# → [OK] neican.sqlite initialized with 7 tables
# 重复运行不报错
```

---

## Round 1 — 文档迭代（6份 docs 更新）

**目标**：根据「项目目标.md」更新6份存在偏差的文档，确保 Codex 后续编码基准正确。

| 文件 | 变更摘要 |
|---|---|
| `docs/PROJECT_BRIEF.md` | 顶部加最终版项目目标段落；非目标补2条 |
| `docs/ARCHITECTURE.md` | 2.2节改为双Agent安全隔离描述 |
| `docs/DATA_MODEL.md` | raw_items 表加 extraction_confidence 字段 |
| `docs/DIRECTORY_STRUCTURE.md` | 新增 sandbox-fetcher/ 目录定义 |
| `docs/SKILL_SPEC.md` | fetch_and_extract 执行者标注为 sandbox-fetcher |
| `docs/CODEX_TASKS.md` | 阶段0任务加 sandbox-fetcher/AGENTS.md 初始化 |

**Round 1 验收**：6份文档更新完毕，无内部矛盾。

---

## Round 2 — 沙箱采集层（sandbox-fetcher 职责）

**目标**：从 sources.yaml 抓取 RSS，hash 去重写入 raw_items。

### 涉及文件

#### [NEW] `scripts/hash_utils.py`
```python
# SHA256(title + source_url + published_at)
def compute_content_hash(title, source_url, published_at): ...
```

#### [NEW] `scripts/fetch_sources.py`
```
CLI: python3 scripts/fetch_sources.py [--limit N] [--source NAME] [--dry-run]

流程：
1. 读取 config/sources.yaml
2. upsert sources 表（以 url 为唯一键）
3. 对每个 enabled source，用 feedparser 抓取
4. 每条 item：计算 content_hash
5. 查 raw_items.content_hash：
   - 已存在 → 不新增 raw_items 记录，计入 skipped_duplicate_count
   - 不存在 → 写入 raw_items，status=new
6. 写 runs 表记录（run_type=fetch_sources），output_json 至少包含：
   - inserted_count
   - skipped_duplicate_count
   - failed_count
7. 失败单条记录 error_message，不中断整批
```

#### [NEW] `requirements.txt`
```text
feedparser
requests
beautifulsoup4
lxml
pyyaml
jsonschema
pytest
```

安装：
```bash
python3 -m pip install -r requirements.txt
```

**Round 2 验收**：
```bash
python3 scripts/fetch_sources.py --limit 5
# raw_items 有新记录 status=new
# 重复运行不新增重复记录
# runs 表有记录，output_json 含 inserted_count / skipped_duplicate_count / failed_count
```

---

## Round 3 — 沙箱清洗层（sandbox-fetcher 职责）

**目标**：把 raw_items 的 raw_text 清洗为 clean_text。

#### [NEW] `scripts/extract_content.py`
```
CLI: python3 scripts/extract_content.py [--raw-item-id N] [--batch N] [--dry-run]

流程：
1. 读取 raw_items.status='new' AND clean_text IS NULL
2. raw_text 可以来自 RSS summary/content，也可以是网页 HTML 转文本来源
3. 仅当 raw_text 看起来像 HTML 时，用 BeautifulSoup 清洗（去脚本、广告、导航）；否则做基础空白规整
4. 保存 clean_text
5. 设置 extraction_confidence（0.0-1.0，基于正文长度和结构完整度估算）
6. 成功后保持 status='new'，不在本轮标记 processed
7. 失败写 error_message，status=failed
8. 写 runs 表记录
```

禁止：不写 Memory Wiki、不写 Hugo、不调用 LLM。

**Round 3 验收**：
```bash
python3 scripts/extract_content.py --raw-item-id 1
# raw_items.clean_text 非空
# raw_items.extraction_confidence 有值 (0.0-1.0)
# 成功清洗后 raw_items.status 仍为 new
```

---

## Round 4 — 事件建模 Mock 版（neican-editor 职责开始）

**目标**：用规则（不调用 LLM）把 raw_items 转换为 events。

#### [NEW] `scripts/event_modeling.py`
```
CLI: python3 scripts/event_modeling.py [--mock] [--limit N] [--raw-item-id N]

Mock 规则：
- event_title：直接使用 raw_item.title
- event_type：关键词匹配（含"model/GPT/Claude"→model_release，含"funding/raise"→funding 等）
- importance_score：source.trust_level × 20（上限100）
- seo_value_score：60（mock 默认）
- knowledge_value_score：55（mock 默认）
- risk_score：risk_rules.yaml 关键词命中数 × 15
- confidence：0.60（mock 默认）
- entities_json：从 entity_aliases.yaml 匹配 title/clean_text
- topics_json：从 taxonomy.yaml 关键词匹配

流程：
1. 读 raw_items.status='new' AND clean_text IS NOT NULL
2. 生成 mock event，写 events 表
3. raw_items.status → processed
4. 写 runs 表
```

**Round 4 验收**：
```bash
python3 scripts/event_modeling.py --mock --limit 5
# events 表有记录
# entities_json / topics_json 是合法 JSON
# raw_items.status = processed
```

---

## Round 5 — 编辑决策规则版

**目标**：按 editorial_rules.yaml 阈值对 events 分级，写 decisions 和 review_queue。

#### [NEW] `scripts/editorial_decision.py`
```
CLI: python3 scripts/editorial_decision.py [--limit N] [--event-id N] [--dry-run]

规则（按顺序）：
1. confidence < 0.5 → D
2. risk_score >= 70 → need_review=true，进入 review_queue(review_type=high_risk_content)
3. A级条件全满足 → A，action=publish_article，need_review=true
4. B级条件满足 → B，action=daily_brief_only
5. Mock 版 C 级替代规则：非 A/B，confidence >= 0.5，且 entities_json 或 topics_json 非空 → C，action=update_assets_only
6. 其余 → D，action=ignore

写 decisions 表，A级/高风险写 review_queue
写 runs 表
```

说明：`editorial_rules.yaml` 中的 `has_related_event` 保留为后续真实关联事件能力字段；Round 5 Mock 版不读取该字段，使用上面的确定性 C 级替代规则。

**Round 5 验收**：
```bash
python3 scripts/editorial_decision.py --limit 10
# decisions 表有记录，decision_grade/action 符合规则
# 若测试 fixture 明确构造 A/B/C/D 场景，则应覆盖全部等级
# A级在 review_queue，review_type=a_grade_article
# D级 action=ignore
```

---

## Round 6 — Hugo 导出 Mock 版

**目标**：生成符合 FRONTMATTER_SPEC.md 的 Hugo Markdown，`neican.review_status=draft`，不自动发布。

#### [NEW] `scripts/export_hugo.py`
```
CLI: python3 scripts/export_hugo.py --date YYYY-MM-DD [--mock] [--dry-run]

生成内容：
1. Daily Brief（当日所有 B/C 级事件）
   → hugo-site/content/briefs/daily/{date}.md
   → Front Matter: 按 FRONTMATTER_SPEC.md 的 Daily Brief 标准字段生成，包含 type=daily_brief、covered_events、seo、neican.review_status=draft

2. A级 Insight 草稿（每个 A 级 decision，decision.status=pending 时生成草稿）
   → hugo-site/content/insights/{slug}.md
   → Front Matter: 按 FRONTMATTER_SPEC.md 的 Insight 标准字段生成，包含完整 sources/entities/topics/claims/seo/neican，且 neican.review_status=draft

禁止：不自动 git commit；不修改 neican.review_status=approved 的文件
```

Memory Wiki 草稿同步写入（同格式，路径 memory-wiki/drafts/），不得覆盖已 approved 内容。

**Round 6 验收**：
```bash
python3 scripts/export_hugo.py --date 2026-05-01 --mock
# 生成 hugo-site/content/briefs/daily/2026-05-01.md
# Front Matter 含 covered_events / seo / neican
# A级事件生成 hugo-site/content/insights/*.md
# 所有文件 neican.review_status=draft
```

---

## Round 7 — Hugo Build 校验

**目标**：本地 build 验证，失败日志可查，不自动 commit。

#### [NEW] `scripts/build_hugo.py`
```
CLI: python3 scripts/build_hugo.py [--site-dir PATH]

流程：
1. subprocess.run(['hugo', '--gc', '--minify'], cwd=hugo-site/)
2. 成功：输出 [OK] Hugo build succeeded，写 runs
3. 失败：保存 logs/build/{timestamp}.log，返回退出码 1
4. 不执行 git 操作
```

**Round 7 验收**：
```bash
python3 scripts/build_hugo.py
# 成功：[OK] Hugo build succeeded
# 失败：logs/build/ 有时间戳日志，退出码非零
```

---

## Round 8 — Skill 文档 + 测试文件

### 8-A：Skill 文档

为 8 个核心 Skill 创建 SKILL.md，每份包含：目标、触发条件、输入、处理步骤、输出、禁止事项、失败处理、是否需要人工审核。

`skills/fetch_and_extract/SKILL.md` 特别标注：执行者为 sandbox-fetcher 子 Agent。

### 8-B：测试文件

#### [NEW] `tests/fixtures/sample_rss.xml` — 测试用 RSS fixture
#### [NEW] `tests/fixtures/sample_raw_item.json` — mock raw_item
#### [MODIFY/KEEP] `tests/test_init_db.py` — 保留或扩展现有数据库初始化、7张表存在、幂等测试，避免另建重复的 `tests/test_db.py`
#### [NEW] `tests/test_fetch_sources.py` — hash 去重逻辑
#### [NEW] `tests/test_export_hugo.py` — Front Matter 字段完整性

**Round 8 验收**：
```bash
python3 -m pytest tests/ -v
# 全部通过
```

---

## 完整文件清单

```text
[Round 0]
sandbox-fetcher/AGENTS.md                   ← 子Agent约束
AGENTS.md                                    ← 主Agent改写
config/sources.yaml
config/taxonomy.yaml
config/entity_aliases.yaml
config/editorial_rules.yaml
config/seo_rules.yaml
config/hugo_paths.yaml
config/risk_rules.yaml
db/schema.sql
scripts/sqlite_ops.py
scripts/init_db.py
schemas/{event,decision,claim,frontmatter,raw_item,article}.schema.json
flows/ingest-flow.md
flows/deploy-flow.md
hugo-site/config.toml
README.md
（所有目录结构）

[Round 1]
docs/PROJECT_BRIEF.md（修改）
docs/ARCHITECTURE.md（修改）
docs/DATA_MODEL.md（修改）
docs/DIRECTORY_STRUCTURE.md（修改）
docs/SKILL_SPEC.md（修改）
docs/CODEX_TASKS.md（修改）

[Round 2]
requirements.txt
scripts/hash_utils.py
scripts/fetch_sources.py

[Round 3]
scripts/extract_content.py

[Round 4]
scripts/event_modeling.py

[Round 5]
scripts/editorial_decision.py

[Round 6]
scripts/export_hugo.py

[Round 7]
scripts/build_hugo.py

[Round 8]
skills/*/SKILL.md（8个）
tests/fixtures/sample_rss.xml
tests/fixtures/sample_raw_item.json
tests/test_init_db.py（保留或扩展现有测试）
tests/test_fetch_sources.py
tests/test_export_hugo.py
```

---

## 依赖清单

```text
feedparser      ← RSS 解析
requests        ← HTTP 抓取
beautifulsoup4  ← HTML 清洗
lxml            ← BS4 解析器
pyyaml          ← 配置读取
jsonschema      ← Schema 校验
pytest          ← 测试运行
```

安装：
```bash
python3 -m pip install -r requirements.txt
```

---

## 阶段二（第一阶段跑通后）

以下内容不在本次范围，待 Mock 版稳定运行后推进：

```text
Round 9：接入真实 LLM（event_modeling + editorial_decision 切换为结构化输出）
Round 10：Memory Wiki 知识资产更新（实体/主题/概念/时间线/claims）
Round 11：deploy-flow（build成功→diff摘要→审批门→git commit/push 到 GitHub 发布仓库→Vercel 自动同步→publish_log）
Round 12：OpenClaw Cron 接入（定时采集 + 定时日报）
```
