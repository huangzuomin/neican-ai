---
name: deploy-and-notify
description: Use when approved neican.ai Hugo output is ready for build, commit, deploy, or notification
---

# deploy_and_notify

## 目标

在审批后执行 Hugo build、git 提交、推送 GitHub 发布仓库，并等待 Vercel 自动同步。

## 触发条件

- Hugo 内容已生成。
- build 准备就绪。
- 生产阶段：人工已明确批准发布。
- 测试工作流阶段：审核 skill 已明确给出通过结论。
- 发布目标是 `https://github.com/huangzuomin/neican-ai`。

## 输入

```json
{
  "content_paths": [],
  "approval_id": "",
  "deploy_target": "https://github.com/huangzuomin/neican-ai"
}
```

## 处理步骤

1. 运行 Hugo build 和站内链接检查。
2. build 或内部链接检查失败则停止并写日志。
3. 确认公开页面没有渲染 `draft`、`needs_review`、`event_id`、`generated_by` 等内部字段。
4. 生成 diff 摘要。
5. 确认 approval gate：生产阶段要求人工审批；测试工作流阶段允许审核 skill 通过结论代替人工审批。
6. git add/commit/push 到 GitHub 发布仓库。
7. 写 publish_log。
8. 等待或提示 Vercel 自动同步部署。
9. 通知 Gateway/IM。

## 输出

```json
{
  "status": "published",
  "git_commit": "",
  "message": ""
}
```

## 禁止事项

- 未审批不得 commit 或 push；测试工作流阶段的审核 skill 通过结论视为测试审批。
- build 失败不得 commit。
- 站内链接检查失败不得 commit。
- 不直接调用 Vercel deploy；Vercel 由 GitHub push 自动同步。
- 不隐藏错误日志。

## 失败处理

停止后续副作用，写 publish_log 或 runs，并通知失败原因。

## 是否需要人工审核

生产阶段必须人工审核。测试工作流阶段可由审核 skill 代替人工审核，审核未通过或结论不确定时必须停止。
