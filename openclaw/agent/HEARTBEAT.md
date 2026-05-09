```markdown
# neican-editor heartbeat

目标：让 neican-editor 在 heartbeat 唤醒时，优先推进知识生产主流水线，而不是只做空检查。

## 默认动作

heartbeat 触发后，优先执行：

```bash
python3 scripts/heartbeat_pipeline.py --json --full-text --min-fetch-interval 240
```

该脚本会先判断是否需要跑主流水线：

- `raw_items.status='new'` 存在 → 继续跑
- `events.status='modeled'` 但还没 decision → 继续跑
- `decisions.status='pending'` 存在 → 继续跑
- 距离上次 `fetch_sources` 已超过默认 240 分钟 → 继续跑
- 否则跳过，并保持安静

## 运行原则

1. 优先用真实流水线，不要只做口头检查。
2. 默认带 `--full-text`，尽量抓全文而不是只吃 RSS summary。
3. 用户没有特别要求时，不要 `--force`。
4. 如果 heartbeat 结果是 `ran=false` 且无新进展，不要打扰用户。
5. 只有在以下情况才主动汇报：
   - 新生成了日报或 insight
   - 出现明确失败或阻塞
   - 需要用户审批/决策

## 可选参数

- 快速试跑：`python3 scripts/heartbeat_pipeline.py --json --mock`
- 强制跑一次：`python3 scripts/heartbeat_pipeline.py --json --force --full-text`
- 改抓取间隔：`python3 scripts/heartbeat_pipeline.py --json --min-fetch-interval 60`
```

## Related

- [Heartbeat config](/gateway/config-agents)
