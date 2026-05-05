# 编辑决策规则

## 1. 总原则

neican.ai 不追求资讯数量，而追求信息密度、知识沉淀价值和长期 SEO 资产。

系统必须避免大规模生成低价值 AI 内容。

核心规则：

> 不是所有资讯都值得生成独立 URL。

---

## 2. 内容分级

## 2.1 A 级：独立洞察文章

### 条件

满足以下多数条件：

1. 涉及重要 AI 公司、模型、工具、平台或政策变化。
2. 有明确行业影响。
3. 有长期搜索价值。
4. 来源可靠。
5. 能形成判断，而不是简单复述。
6. 能更新实体页、主题页或时间线。
7. 不是重复报道。

### 示例

```text
重要模型发布
关键平台能力变化
大公司 AI 战略调整
AI 编程工具重大更新
AI Agent 重要产品化事件
政策/监管变化
基础设施价格、算力、芯片重大变化
```

### 动作

```text
生成 insight 文章草稿
更新 Memory Wiki
更新相关 topic/entity/concept
进入日报重点
写入 review_queue
需要人工审核
```

---

## 2.2 B 级：日报事件

### 条件

1. 有行业信息价值。
2. 但不足以形成独立文章。
3. 信息较短或影响有限。
4. 适合放入日报。

### 动作

```text
进入 daily brief
更新 Memory Wiki 简要记录
不单独生成 insight URL
```

---

## 2.3 C 级：补充来源

### 条件

1. 是已有事件的补充来源。
2. 可以提高某条 claim 的置信度。
3. 没有独立信息增量。

### 动作

```text
不发文
作为 source/evidence 追加到已有 event 或 claim
可能更新 confidence
```

---

## 2.4 D 级：忽略

### 条件

1. 营销稿。
2. 重复报道。
3. 来源弱。
4. 无新增信息。
5. 标题党但事实不足。
6. 与 AI 行业无关。
7. 无法提取可靠来源。

### 动作

```text
标记 ignored
不生成页面
不进入日报
```

---

## 3. 评分规则

event_modeling 先输出并执行 AI 相关性闸门，再输出以下分数：

```text
ai_relevance_score
```

AI relevance 低于 `config/editorial_rules.yaml` 中 `ai_relevance_gate.threshold` 的 raw item 必须标记为 D/ignored，不进入事件、日报、时间线、实体或公开页面。宁可漏掉边缘泛科技/财经新闻，也不要污染 AI 行业主线。

直接相关范围：

```text
AI 模型
AI 产品/工具
AI 公司/研究机构
AI 芯片/算力/基础设施
AI 应用/workflow
AI 政策/安全/研究
与既有 AI 主题线存在明确关系的产业事件
```

排除范围：

```text
泛财经
宏观市场
交通物流
电影票房
普通消费/社会新闻
仅因标题中出现科技公司但缺少 AI 关系的报道
```

通过 relevance gate 后，event_modeling 输出以下分数：

```text
importance_score
seo_value_score
knowledge_value_score
risk_score
confidence
```

建议范围：

```text
0-100
```

### A 级参考阈值

```text
importance_score >= 75
seo_value_score >= 60
knowledge_value_score >= 70
confidence >= 0.75
risk_score < 70
```

### B 级参考阈值

```text
importance_score >= 45
knowledge_value_score >= 40
confidence >= 0.65
```

### C 级参考阈值

```text
importance_score < 45
但与已有 event/claim 有关联
```

### D 级参考阈值

```text
confidence < 0.5
或明显重复/营销/无关
或 ai_relevance_score < 0.65
```

## 3.1 事件级去重

事件去重不能只依赖 URL/hash。生成日报、时间线、主题页和追踪线时必须至少检查：

```text
event_id
source_url
title_normalized
event_fingerprint（主体实体 + 核心动作 + 事件日期 + event_type）
```

同一个 event_id 在同一公开页面最多出现一次。同一个 source_url 和 normalized title 在同一日报中最多出现一次。

## 3.2 实体质量闸门

新实体默认不是公开知识资产。实体必须先经过角色和质量判定：

```text
core_actor / approved: 核心 AI 公司、关键长期参与者。
product_or_model / approved: AI 模型、工具、平台、基础设施产品。
regulator / candidate: 政策监管主体，默认待审核。
source_media / suppressed: 媒体源和聚合站。
mentioned_context / candidate: 投资方、客户、财经/社会/行业上下文对象。
noise / suppressed: 偶然出现且无长期追踪价值的对象。
```

公开实体页只导出 approved 且属于核心角色的实体。媒体源如 36氪、MacRumors 应进入来源说明，不默认成为实体档案。

---

## 4. 人工审核规则

以下情况必须进入 review_queue：

```text
A 级独立文章
新实体创建
高风险内容
来源冲突
claim confidence < 0.7
risk_score >= 70
大段修改知识资产
首页推荐
deploy 发布
```

---

## 5. 高风险内容

高风险包括：

```text
政策监管
安全漏洞
公司负面争议
法律诉讼
未经证实的爆料
财务数据
人物指控
政治敏感内容
```

处理原则：

1. 不自动发布。
2. 不使用夸张标题。
3. 必须保留来源。
4. 低置信度只写“据称”“尚未证实”，或不写。
5. 优先进入人工审核。
6. 政策、安全、争议类 A 级候选必须至少有一个高可信来源或多源确认；只有单一行业媒体/聚合源时，不得自动作为高置信 A 级洞察公开。

## 5.1 来源分级

Source Trust 建议同时保留数值 `trust_level` 和编辑标签：

```text
S: 官方公告、公司博客、论文、监管文件、GitHub 原始发布。
A: 权威科技媒体、主流财经媒体。
B: 行业媒体、聚合站。
C: 社交平台爆料、二次转述。
```

当前来源分级配置在 `config/source_trust.yaml`：

```text
S: trust_level >= 5
A: trust_level >= 4
B: trust_level >= 3
C: trust_level >= 1
```

政策、安全等高风险 A 级候选必须达到 `min_a_grade_tier`。弱来源高风险候选会降为待审核，不自动生成 A 级洞察。

---

## 6. SEO 质量规则

独立文章必须满足：

1. 标题具体，不空泛。
2. slug 语义化。
3. 第一段直接给出判断。
4. 有 SEO 信息卡。
5. 至少关联 1 个 entity。
6. 至少关联 1 个 topic。
7. 至少有 1 个可靠 source。
8. 不包含无来源 claims。
9. 不是纯翻译、纯摘要、纯搬运。
10. 不批量制造低价值 URL。

---

## 7. 标题规则

避免：

```text
震惊
杀疯了
炸裂
遥遥领先
最强
彻底改变世界
```

除非正文有足够事实支撑。

建议标题结构：

```text
[主体] + [动作] + [行业意义]
```

示例：

```text
Gemini 进入 Mac 桌面端，AI 助手开始争夺系统入口
```

---

## 8. 日报规则

日报不是垃圾桶。

日报应包含：

1. 今日关键判断。
2. A 级事件摘要。
3. B 级事件分类聚合。
4. 值得继续跟踪的线索。
5. 来源索引。

低质量 D 级内容不进入日报。

---

## 9. Memory Wiki 更新规则

更新知识资产时：

1. 只追加有来源的信息。
2. 不自动大段覆盖旧内容。
3. 新 claim 必须带 source 和 confidence。
4. 与旧 claim 冲突时，标记 disputed。
5. 大段改写进入审核队列。

---

## 10. 发布规则

部署前必须：

1. Hugo build 成功。
2. 没有 pending_review 内容混入公开页面。
3. 生成发布 diff 摘要。
4. A 级文章已审核。
5. publish_log 可写入。
