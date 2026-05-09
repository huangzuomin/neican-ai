---
title: 声明库
draft: true
date: 2026-05-02T09:20:00+08:00
seo:
  description: neican.ai 的结构化声明库示范，展示事实、判断、来源和置信度如何被追踪。
---

<div class="demo-page rich-page">
  <p class="eyebrow">Claim Ledger</p>
  <h1>每个重要判断，都应该能追溯到声明与来源</h1>
  <p class="page-lead">声明库不是给读者堆元数据，而是让编辑判断可审计：哪些是事实、哪些是推断、哪些仍需等待更多来源。</p>

  <div class="claim-ledger">
    <div class="claim-row head"><span>声明</span><span>类型</span><span>置信度</span><span>处理</span></div>
    <div class="claim-row"><span>模型产品正在从“对话界面”转向“任务执行系统”。</span><span>趋势判断</span><strong>82%</strong><em>进入洞察</em></div>
    <div class="claim-row"><span>企业采用 Agent 的关键障碍包括权限、审计、私有数据连接和失败恢复。</span><span>结构化判断</span><strong>88%</strong><em>更新主题页</em></div>
    <div class="claim-row"><span>推理成本将影响模型 API 商业化与应用形态。</span><span>背景判断</span><strong>84%</strong><em>进入日报</em></div>
    <div class="claim-row"><span>单一厂商发布的 benchmark 不能直接作为横向结论。</span><span>风险规则</span><strong>91%</strong><em>需交叉来源</em></div>
  </div>

  <aside class="source-note">Demo 提示：正式生产中，claim 会绑定 sources、event_id、entity_id、confidence、status 和 review_status；低置信或无来源 claim 不进入公开内容。</aside>
</div>
