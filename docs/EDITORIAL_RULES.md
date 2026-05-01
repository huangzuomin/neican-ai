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

event_modeling 输出以下分数：

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
```

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
