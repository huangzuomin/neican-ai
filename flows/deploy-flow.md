# Deploy Flow

## 流程

1. `neican-editor` 生成或更新 Hugo 内容。
2. 运行 Hugo build 校验。
3. 检查 SEO、来源、风险和未溯源 claim。
4. 需要审批的内容进入 `review_queue`。
5. 获得明确审批后，才允许 commit 并 push 到 GitHub 发布仓库。
6. GitHub 仓库更新后，由 Vercel 自动同步部署。
7. 发布结果写入 `publish_log` 与 `logs/publish/`。

## 发布前质量闸门

部署前必须先完成本开发仓库的静态验证：

```bash
bash scripts/validate.sh
```

Hugo build 成功不等于站内链接正确。构建检查必须阻断以下问题：

```text
首页、导航或内容页内部链接指向不存在页面。
公开页面渲染 draft / needs_review / event_id / generated_by 等内部字段。
洞察页缺少有效日期或显示 0001-01-01。
日报出现重复 event_id、source_url 或 normalized title。
日报、时间线、实体页、主题页混入低 AI relevance 内容。
```

未通过上述质量闸门时，不得部署。

## 发布目标

Hugo 公开站点发布仓库：

```text
https://github.com/huangzuomin/AInews
```

部署链路：

```text
hugo-site/content/
→ Hugo build 校验
→ 人工审批
→ git commit
→ git push github.com/huangzuomin/AInews
→ Vercel 自动同步部署
```

脚本不得直接调用 Vercel deploy。Vercel 是 GitHub push 后的自动发布层。

## 审批门

以下动作必须先获得人工审批：

- A 级文章发布。
- 风险分数大于等于 70 的内容处理。
- 新实体创建后的公开发布。
- 任何 git commit、git push、Vercel 触发发布或外部通知。

未审批时不得 commit，不得 push 到发布仓库，不得触发 Vercel 自动发布，不得触发外部通知。
