# SQLite 数据模型

## 1. 设计原则

SQLite 只作为运行账本，不作为 CMS，也不保存长期知识正文。

SQLite 保存：

- 原始资讯索引。
- 去重 hash。
- 事件建模结果。
- 编辑决策。
- 审核队列。
- 发布日志。
- 运行日志。

长期知识资产保存到 Memory Wiki。

---

## 2. 表清单

```text
sources
raw_items
events
decisions
review_queue
publish_log
runs
```

---

## 3. sources

保存信源配置。

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
```

字段说明：

| 字段 | 说明 |
|---|---|
| name | 信源名称 |
| type | rss / webpage / github / arxiv / manual |
| url | 信源 URL |
| enabled | 是否启用 |
| trust_level | 可信度，1-5 |
| language | 语言 |
| fetch_interval_minutes | 抓取间隔 |

---

## 4. raw_items

保存抓取到的原始资讯。

```sql
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
```

status 可选值：

```text
new
duplicate
processed
ignored
failed
```

字段说明：

| 字段 | 说明 |
|---|---|
| raw_text | 原始抓取文本或 HTML 转文本结果 |
| clean_text | 经 sandbox-fetcher 清洗后的正文 |
| content_hash | 用于去重的内容哈希 |
| extraction_confidence | 正文抽取置信度，0-1；未抽取时为 NULL |
| status | raw item 当前处理状态 |

---

## 5. events

保存事件建模结果。

```sql
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
```

event_type 建议枚举：

```text
model_release
product_update
company_strategy
research_paper
policy
tool_launch
funding
safety_issue
market_signal
industry_trend
other
```

---

## 6. decisions

保存编辑决策。

```sql
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
```

action 可选值：

```text
publish_article
daily_brief_only
update_assets_only
ignore
review_required
```

decision_grade 可选值：

```text
A
B
C
D
```

status 可选值：

```text
pending
approved
rejected
executed
skipped
failed
```

---

## 7. review_queue

保存人工审核项。

```sql
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
```

review_type 可选值：

```text
new_entity
a_grade_article
high_risk_content
source_conflict
low_confidence_claim
major_asset_update
deploy_approval
```

status 可选值：

```text
pending
approved
rejected
skipped
```

---

## 8. publish_log

保存发布记录。

```sql
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
```

status 可选值：

```text
success
failed
skipped
```

---

## 9. runs

保存脚本和任务执行记录。

```sql
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

run_type 示例：

```text
fetch_sources
event_modeling
editorial_decision
generate_brief
hugo_export
hugo_build
deploy
```

---

## 10. JSON 字段规范

SQLite 第一阶段可以用 JSON 文本字段保存半结构化数据：

- entities_json
- topics_json
- claims_json
- context_json
- input_json
- output_json

代码中必须使用 JSON parse/stringify，不允许拼接字符串。

---

## 11. 初始化要求

Codex 需要生成：

```text
db/schema.sql
scripts/init_db.py
scripts/sqlite_ops.py
```

验收标准：

```bash
python scripts/init_db.py
```

运行后：

1. 创建 `db/neican.sqlite`。
2. 成功创建所有表。
3. 可重复运行，不报错。
