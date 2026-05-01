# Deploy Flow

## 流程

1. `neican-editor` 生成或更新 Hugo 内容。
2. 运行 Hugo build 校验。
3. 检查 SEO、来源、风险和未溯源 claim。
4. 需要审批的内容进入 `review_queue`。
5. 获得明确审批后，才允许 commit 并 push 到 GitHub 发布仓库。
6. GitHub 仓库更新后，由 Vercel 自动同步部署。
7. 发布结果写入 `publish_log` 与 `logs/publish/`。

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
