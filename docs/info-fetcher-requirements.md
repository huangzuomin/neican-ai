# neican-editor 调用 info-fetcher 集成需求说明

> 状态：Draft
> 创建：2026-05-07
> 更新：2026-05-07
> 作者：neican-editor
> 目标：明确 neican-editor 如何通过主 agent 路由调用已有的 info-fetcher 子智能体

---

## 1. 背景

### 1.1 现状

OpenClaw 系统中已存在独立的 `info-fetcher` 子智能体，具备完整的外部信息采集能力（RSS、网页抓取、动态页面、社媒、视频字幕等）。

当前 neican-editor 的信息采集有两条路径：

1. **RSS 解析**：`scripts/fetch_sources.py` 在本地直接运行，用 feedparser 抓 RSS feed 写入 `raw_items`。
2. **全文抓取**：通过主 agent（璇玑）路由到 info-fetcher 执行。

### 1.2 问题

- `fetch_sources.py` 能力局限于 RSS，不支持网页全文、社媒、动态页面。
- 全文抓取的路由规则散落在各处，缺乏统一的集成文档。
- neican-editor 的 AGENTS.md 和 IDENTITY.md 中对路由描述不够精确。

### 1.3 目标

明确 neican-editor 与 info-fetcher 的集成方式：neican-editor 不直接 spawn info-fetcher，而是通过主 agent（璇玑）路由调度。

---

## 2. 架构与调用链

### 2.1 核心原则

**info-fetcher 只有一个调用者：主 agent（璇玑）。**

其他子 agent 需要信息抓取时，走主 agent 路由，不得直接 spawn info-fetcher。

### 2.2 调用链

```
neican-editor 需要抓取外部信息
    │
    │ 向主 agent（璇玑）发送消息：
    │ "需要抓取：<具体任务描述>"
    ▼
主 agent（璇玑）
    │
    │ sessions_spawn(
    │   task="<具体抓取任务描述>",
    │   cwd="/home/ai/.openclaw/workspace-info-fetcher",
    │   context="isolated",
    │   model="zai/glm-5.1"
    │ )
    ▼
info-fetcher 执行抓取
    │
    │ 结果回传给璇玑
    ▼
璇玑将结果转发给 neican-editor
    │
    ▼
neican-editor 消费结果，继续建模/决策流程
```

### 2.3 为什么不直接 spawn

| 风险 | 说明 |
|------|------|
| 超时失控 | 子 agent 嵌套调度，外层超时难以传递 |
| token 爆炸 | 嵌套上下文累积，token 用量不可控 |
| 错误传播 | 内层失败不易被外层正确处理 |
| 调度复杂度 | 多层嵌套让状态追踪和调试变得困难 |

### 2.4 实际场景

| 场景 | 触发者 | 执行者 |
|------|--------|--------|
| 用户说"帮我抓这个网页" | 璇玑 | 璇玑 → info-fetcher |
| neican-editor heartbeat 需要抓取 | neican-editor → 璇玑 | 璇玑 → info-fetcher |
| neican-editor 建模时需要全文 | neican-editor → 璇玑 | 璇玑 → info-fetcher |
| Cron 定时采集 | Cron → 璇玑 | 璇玑 → info-fetcher |

---

## 3. neican-editor 端集成需求

### 3.1 AGENTS.md 路由规则

在 neican-editor 的 `AGENTS.md` 中，需要明确写入：

```markdown
## 信息抓取路由

neican-editor 不直接 spawn 或调用 info-fetcher。需要外部信息抓取时，
向主 agent（璇玑）返回消息：`需要抓取：<具体任务描述>`，由主 agent
调度 info-fetcher 执行。

RSS 解析等确定性逻辑保留在本 agent 内部脚本 `fetch_sources.py` 中。
```

### 3.2 本地能力边界

neican-editor 本地保留的能力：

| 能力 | 实现 | 说明 |
|------|------|------|
| RSS 解析 | `fetch_sources.py` | feedparser + requests，确定性逻辑 |
| 内容清洗 | `extract_content.py` | 本地 HTML → clean_text |
| 去重 | `hash_utils.py` + SQLite | content_hash 比对 |

需要路由给 info-fetcher 的能力：

| 能力 | 触发条件 | 说明 |
|------|----------|------|
| 网页全文抓取 | RSS 中只有摘要，需要全文 | 静态/动态网页 |
| 社媒内容 | 需要抓取 Twitter/X、Reddit 等 | 平台限制多 |
| 视频字幕 | 需要 YouTube 视频字幕 | |
| 搜索发现 | 需要基于关键词发现新内容 | web_search 扩展 |
| 动态页面 | JS 渲染的 SPA 页面 | 需要浏览器自动化 |
| 批量站点抓取 | 需要抓取整个站点或栏目 | |

### 3.3 heartbeat_pipeline.py 集成

当前 `heartbeat_pipeline.py` 调用 `fetch_sources.py` 做 RSS 采集。改造后：

1. RSS 采集仍由本地 `fetch_sources.py` 执行（确定性逻辑，不需要 LLM）。
2. 如果发现 RSS 条目只有摘要没有全文，且 `full_text=True`，则：
   - 不在本地直接抓取全文
   - 收集需要全文抓取的 URL 列表
   - 向璇玑发送批量抓取请求

```python
# 伪代码
if need_full_text and urls_to_fetch:
    # 向主 agent 发送抓取请求
    route_to_main_agent(f"需要抓取以下 URL 的全文：{urls_to_fetch}")
    # 不等待结果，由后续 heartbeat 或回调处理
```

### 3.4 event_modeling 集成

事件建模阶段，如果发现 raw_items 的 clean_text 不完整或 extraction_confidence 过低：

1. 标记该 raw_item 为 `needs_refetch`
2. 在下一次 heartbeat 中，将这些 URL 路由给璇玑 → info-fetcher 重新抓取

### 3.5 结果消费

info-fetcher 的抓取结果如何回到 neican-editor：

**方式 A：通过璇玑转发（推荐）**

璇玑将 info-fetcher 的结果通过 `sessions_send` 转发给 neican-editor，neican-editor 解析后写入 `raw_items`。

**方式 B：info-fetcher 直接写入共享 SQLite**

如果 info-fetcher 有写入 `raw_items` 表的权限，结果可以直接落库，neican-editor 在下一次查询时自动消费。这需要在 info-fetcher 的权限配置中开放 `raw_items` 写入。

---

## 4. 需要修改的文件

### 4.1 neican-editor 工作区

| 文件 | 改动 |
|------|------|
| `AGENTS.md` | 添加信息抓取路由规则 |
| `IDENTITY.md` | 更新 info-fetcher 相关描述 |
| `TOOLS.md` | 添加 info-fetcher 调用说明 |
| `scripts/heartbeat_pipeline.py` | 增加全文抓取路由逻辑 |
| `scripts/fetch_sources.py` | 保留 RSS 能力，移除本地全文抓取 |

### 4.2 开发仓库

| 文件 | 改动 |
|------|------|
| `docs/info-fetcher-requirements.md` | 重写为集成需求（本文件） |
| `docs/ARCHITECTURE.md` | 更新架构图，标注路由关系 |

---

## 5. 给 Codex 的迭代指南

### 5.1 第一步：对齐

```text
请先阅读以下文档：

- docs/info-fetcher-requirements.md（本文件）
- docs/ARCHITECTURE.md
- docs/SKILL_SPEC.md
- scripts/fetch_sources.py
- scripts/heartbeat_pipeline.py

不要立即写代码。

请先完成：
1. 复述 neican-editor 与 info-fetcher 的调用关系。
2. 确认哪些抓取能力在本地（fetch_sources.py），哪些需要路由。
3. 给出你的实现计划。
```

### 5.2 第二步：AGENTS.md 和路由规则

```text
1. 修改 neican-editor 的 AGENTS.md，添加信息抓取路由规则。
2. 修改 IDENTITY.md，更新 info-fetcher 相关描述。
3. 修改 TOOLS.md，添加调用说明。
```

### 5.3 第三步：heartbeat 集成

```text
1. 修改 heartbeat_pipeline.py，增加全文抓取路由逻辑。
2. RSS 采集保持本地执行。
3. 需要全文时，收集 URL 列表，输出到 stdout 或写入待抓取队列。
4. 不直接调用 info-fetcher，而是输出"需要抓取"信号。
```

### 5.4 第四步：结果消费

```text
1. 实现 neican-editor 接收抓取结果的逻辑。
2. 结果写入 raw_items（如果 info-fetcher 未直接写入）。
3. 更新 raw_items 状态。
```

---

## 6. 开放问题

1. **结果回传方式**：info-fetcher 的结果是通过璇玑转发，还是直接写入共享 SQLite？需要确认 info-fetcher 的输出契约。
2. **队列机制**：neican-editor 积累的待抓取 URL 列表如何持久化？写入 SQLite 临时表还是文件？
3. **抓取优先级**：批量抓取任务如何传递优先级？是否需要支持"立即抓取"和"下次 heartbeat 时抓取"两种模式？
4. **info-fetcher 输出格式**：info-fetcher 返回的结构化数据格式是什么？需要查阅 info-fetcher 的 AGENTS.md 或 SKILL.md。
