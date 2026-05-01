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
- 人工已明确批准发布。
- 发布目标是 `https://github.com/huangzuomin/AInews`。

## 输入

```json
{
  "content_paths": [],
  "approval_id": "",
  "deploy_target": "https://github.com/huangzuomin/AInews"
}
```

## 处理步骤

1. 运行 Hugo build。
2. build 失败则停止并写日志。
3. 生成 diff 摘要。
4. 确认 approval gate。
5. git add/commit/push 到 GitHub 发布仓库。
6. 写 publish_log。
7. 等待或提示 Vercel 自动同步部署。
8. 通知 Gateway/IM。

## 输出

```json
{
  "status": "published",
  "git_commit": "",
  "message": ""
}
```

## 禁止事项

- 未审批不得 commit 或 push。
- build 失败不得 commit。
- 不直接调用 Vercel deploy；Vercel 由 GitHub push 自动同步。
- 不隐藏错误日志。

## 失败处理

停止后续副作用，写 publish_log 或 runs，并通知失败原因。

## 是否需要人工审核

必须人工审核。
