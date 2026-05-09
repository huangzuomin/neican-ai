# Ingest Flow

## 边界

`sandbox-fetcher` 负责外部不可信内容：

1. 读取 `config/sources.yaml`。
2. 抓取 RSS 或网页。
3. 提取 `raw_text` 与 `clean_text`。
4. 计算内容哈希。
5. 写入 `db/neican.sqlite` 的 `sources`、`raw_items`、`runs`。
6. 写入 `logs/runs/`。

`neican-editor` 负责可信结构化消费：

1. 读取 `raw_items.clean_text`。
2. 建模事件、实体、主题和 claims。
3. 执行编辑决策。
4. 更新 `memory-wiki/` 与 `hugo-site/`。

## 红线

- `neican-editor` 不直接抓取或清洗网页正文。
- `sandbox-fetcher` 不写入 `memory-wiki/`、`hugo-site/` 或编辑决策表。
- 低置信抽取必须保留 `extraction_confidence`，由主 Agent 决定后续处理。
