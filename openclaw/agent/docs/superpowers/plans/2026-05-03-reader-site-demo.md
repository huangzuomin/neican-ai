# Reader Site Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished Hugo demo that presents neican.ai as a real AI industry intelligence site for readers.

**Architecture:** Keep the existing Hugo static site and replace the current system-demo presentation with a coherent reader-facing content universe. Use Hugo Markdown content for polished sample pages, existing layouts where sufficient, and a refreshed CSS layer for an editorial, high-trust reading experience.

**Tech Stack:** Hugo, Markdown with YAML front matter, Hugo templates, static CSS, Git, Vercel build script.

---

## File Structure

- Modify `hugo-site/config.toml`: update menu and site description for the reader product.
- Modify `hugo-site/layouts/index.html`: rebuild the home page as the public intelligence front page.
- Modify `hugo-site/layouts/_default/list.html`: make section indexes reader-facing for insights, briefs, entities, topics, and timeline.
- Modify `hugo-site/layouts/_default/single.html`: support source, claim, entity, topic, and next-watch sections in article-style pages.
- Modify `hugo-site/layouts/partials/card.html`: make cards compact, editorial, and robust for Chinese content.
- Modify `hugo-site/static/css/custom.css`: replace the dark internal demo styling with a light editorial design system.
- Modify `hugo-site/content/_index.md`: home metadata and editorial positioning.
- Modify `hugo-site/content/briefs/_index.md`: brief section copy.
- Create `hugo-site/content/briefs/daily/2026-05-03.md`: one polished daily brief.
- Modify `hugo-site/content/insights/_index.md`: insight section copy.
- Replace insight samples under `hugo-site/content/insights/` with three coherent AI-agent-focused insight pages.
- Modify `hugo-site/content/entities/_index.md`: entity section copy.
- Replace selected entity pages under `hugo-site/content/entities/` with polished dossiers for OpenAI, Anthropic, Microsoft, Google DeepMind, Nvidia, and Cursor.
- Modify `hugo-site/content/topics/_index.md`: topic section copy.
- Create topic pages under `hugo-site/content/topics/ai-agents/`, `enterprise-ai-governance/`, and `mcp/`.
- Modify `hugo-site/content/timeline/_index.md`: timeline section as structural change narrative.
- Modify or replace `hugo-site/content/about.md`: concise reader-facing about page.

## Tasks

### Task 1: Clean Site Navigation And Metadata

**Files:**
- Modify: `hugo-site/config.toml`
- Modify: `hugo-site/content/_index.md`
- Modify: `hugo-site/content/about.md`

- [ ] **Step 1: Update site description and menu**

Set `params.description` to:

```toml
description = "面向 AI 行业的低噪音情报、深度洞察与长期知识资产。"
```

Set main menu items to:

```toml
[[menus.main]]
name = "首页"
url = "/"
weight = 10

[[menus.main]]
name = "日报"
url = "/briefs/daily/"
weight = 20

[[menus.main]]
name = "洞察"
url = "/insights/"
weight = 30

[[menus.main]]
name = "实体"
url = "/entities/"
weight = 40

[[menus.main]]
name = "主题"
url = "/topics/"
weight = 50

[[menus.main]]
name = "时间线"
url = "/timeline/"
weight = 60

[[menus.main]]
name = "关于"
url = "/about/"
weight = 70
```

- [ ] **Step 2: Update home front matter**

Use:

```markdown
---
title: AI内参
seo:
  description: 面向 AI 行业的低噪音情报、深度洞察与长期知识资产。
---
```

- [ ] **Step 3: Rewrite about page**

Use a concise reader-facing page explaining that neican.ai filters AI industry noise into daily briefs, insights, entity dossiers, topics, and timelines.

- [ ] **Step 4: Verify metadata and menu**

Run:

```bash
rg -n "日报|洞察|实体|主题|时间线|关于|低噪音" hugo-site/config.toml hugo-site/content/_index.md hugo-site/content/about.md
```

Expected: each menu label and the new description appear.

- [ ] **Step 5: Commit**

```bash
git add hugo-site/config.toml hugo-site/content/_index.md hugo-site/content/about.md
git commit -m "feat: align reader site navigation"
```

### Task 2: Build The Reader-Facing Home Page

**Files:**
- Modify: `hugo-site/layouts/index.html`

- [ ] **Step 1: Replace internal workflow hero**

Rewrite the template with sections:

```html
<section class="front-page">
  <div class="front-kicker">AI 行业情报台 · 2026-05-03</div>
  <h1>今日判断：Agent 产品正在从效率工具转向企业治理基础设施。</h1>
  <p class="front-lead">neican.ai 每天从模型、Agent、算力、政策与应用信号中筛出真正值得跟踪的变化，并沉淀为日报、洞察、实体档案、主题页和时间线。</p>
</section>
```

Include modules for lead insight, daily brief, rising themes, entity watchlist, and timeline excerpt.

- [ ] **Step 2: Link every module to a real page**

Use these target URLs:

```text
/insights/agent-runtime-becomes-enterprise-control-plane/
/briefs/daily/2026-05-03/
/topics/ai-agents/
/entities/openai/
/timeline/
```

- [ ] **Step 3: Verify no internal workflow language dominates**

Run:

```bash
rg -n "Raw Item|SQLite|OpenClaw|workflow|demo navigation|Signal → Knowledge" hugo-site/layouts/index.html
```

Expected: no matches, except `OpenClaw` is acceptable only if hidden in a small implementation note. Prefer no matches.

- [ ] **Step 4: Commit**

```bash
git add hugo-site/layouts/index.html
git commit -m "feat: build reader-facing home page"
```

### Task 3: Create Coherent Daily Brief Content

**Files:**
- Modify: `hugo-site/content/briefs/_index.md`
- Modify: `hugo-site/content/briefs/daily/_index.md`
- Create: `hugo-site/content/briefs/daily/2026-05-03.md`

- [ ] **Step 1: Update section pages**

Set `briefs/_index.md` title to `简报` with copy describing briefings as structured daily signal summaries.

Set `briefs/daily/_index.md` title to `日报` with copy describing five-lane daily coverage.

- [ ] **Step 2: Add polished daily brief**

Create `2026-05-03.md` with front matter:

```yaml
---
title: AI 内参日报：Agent 工作流进入企业治理阶段
date: 2026-05-03T08:30:00+08:00
type: daily_brief
topics: ["ai-agents", "enterprise-ai-governance", "mcp"]
entities: ["OpenAI", "Anthropic", "Microsoft", "Google DeepMind", "Nvidia", "Cursor"]
seo:
  description: 2026-05-03 AI 内参日报，聚焦 Agent 工作流、企业治理、MCP、模型能力与算力约束。
neican:
  generated_by: reader_demo
  review_status: demo
---
```

Body structure:

```markdown
## 今日判断

Agent 产品的竞争焦点正在从“能替用户完成任务”转向“能否在企业权限、审计、数据边界和失败恢复中稳定运行”。

## 模型
...

## Agent
...

## 基础设施
...

## 政策与治理
...

## 应用
...

## 明日观察
...
```

- [ ] **Step 3: Verify daily brief exists and has required fields**

Run:

```bash
rg -n "title:|topics:|entities:|今日判断|明日观察" hugo-site/content/briefs/daily/2026-05-03.md
```

Expected: all required fields and headings appear.

- [ ] **Step 4: Commit**

```bash
git add hugo-site/content/briefs
git commit -m "feat: add reader demo daily brief"
```

### Task 4: Replace Insight Samples With Three High-Quality Articles

**Files:**
- Modify: `hugo-site/content/insights/_index.md`
- Create or replace:
  - `hugo-site/content/insights/agent-runtime-becomes-enterprise-control-plane.md`
  - `hugo-site/content/insights/mcp-turns-agent-integration-into-platform-layer.md`
  - `hugo-site/content/insights/evals-become-agent-adoption-bottleneck.md`
- Quarantine or remove mismatched old sample content from visible indexes by setting `draft: true` on files that are outside the coherent sample universe.

- [ ] **Step 1: Update insight index**

Describe insights as scarce A-grade analysis, not a bulk archive.

- [ ] **Step 2: Add article front matter**

Each article must include:

```yaml
type: insight
decision_grade: A
topics:
  - ai-agents
entities:
  - name: OpenAI
    slug: openai
    type: company
claims:
  - statement: Agent 竞争正在从能力演示转向运行时治理。
    confidence: 0.86
    status: active
sources:
  - title: OpenAI product updates
    url: https://openai.com/news/
    publisher: OpenAI
seo:
  structured_data: NewsArticle
neican:
  generated_by: reader_demo
  review_status: demo
```

- [ ] **Step 3: Add article body structure**

Every article should contain:

```markdown
## 为什么重要
## 发生了什么
## 影响谁
## 证据与约束
## 后续观察
```

- [ ] **Step 4: Hide mismatched samples**

Add `draft: true` to old or incoherent samples such as `hugo-site/content/insights/5.md` and any mock-only Round 6 sample that should not appear in the reader demo.

- [ ] **Step 5: Verify insights**

Run:

```bash
rg -n "为什么重要|发生了什么|影响谁|证据与约束|后续观察|draft: true" hugo-site/content/insights
```

Expected: the three reader-demo insight files contain all required headings; quarantined files show `draft: true`.

- [ ] **Step 6: Commit**

```bash
git add hugo-site/content/insights
git commit -m "feat: add reader demo insights"
```

### Task 5: Create Entity Dossiers

**Files:**
- Modify: `hugo-site/content/entities/_index.md`
- Create or replace:
  - `hugo-site/content/entities/openai/_index.md`
  - `hugo-site/content/entities/anthropic/_index.md`
  - `hugo-site/content/entities/microsoft/_index.md`
  - `hugo-site/content/entities/google-deepmind/_index.md`
  - `hugo-site/content/entities/nvidia/_index.md`
  - `hugo-site/content/entities/cursor/_index.md`

- [ ] **Step 1: Update entity index**

Write the entity index as a directory of living industry dossiers.

- [ ] **Step 2: Add dossier front matter**

Each entity page should use:

```yaml
---
title: OpenAI
type: entity_profile
entity_type: company
topics: ["ai-agents", "enterprise-ai-governance"]
neican:
  generated_by: reader_demo
  review_status: demo
---
```

- [ ] **Step 3: Add dossier body structure**

Every entity page should contain:

```markdown
## 当前信号
## 为什么值得跟踪
## 相关主题
## 关键判断
## 后续观察
```

- [ ] **Step 4: Verify entity dossiers**

Run:

```bash
rg -n "当前信号|为什么值得跟踪|相关主题|关键判断|后续观察" hugo-site/content/entities
```

Expected: the six reader-demo entity pages contain all required headings.

- [ ] **Step 5: Commit**

```bash
git add hugo-site/content/entities
git commit -m "feat: add reader demo entity dossiers"
```

### Task 6: Create Topic Research Indexes And Timeline

**Files:**
- Modify: `hugo-site/content/topics/_index.md`
- Create:
  - `hugo-site/content/topics/ai-agents/_index.md`
  - `hugo-site/content/topics/enterprise-ai-governance/_index.md`
  - `hugo-site/content/topics/mcp/_index.md`
- Modify: `hugo-site/content/timeline/_index.md`

- [ ] **Step 1: Update topic index**

Describe topics as research indexes that connect events, entities, claims, and insights.

- [ ] **Step 2: Add topic front matter**

Each topic page should use:

```yaml
---
title: AI Agents
type: topic_index
topics: ["ai-agents"]
neican:
  generated_by: reader_demo
  review_status: demo
---
```

- [ ] **Step 3: Add topic body structure**

Each topic page should contain:

```markdown
## 当前命题
## 最新变化
## 关键实体
## 重要声明
## 推荐阅读
## 时间线
```

- [ ] **Step 4: Rewrite timeline**

Make `timeline/_index.md` a structural narrative with dated entries for AI agents moving from demos to governed enterprise workflows.

- [ ] **Step 5: Verify topics and timeline**

Run:

```bash
rg -n "当前命题|最新变化|关键实体|重要声明|推荐阅读|时间线|企业治理" hugo-site/content/topics hugo-site/content/timeline/_index.md
```

Expected: all required topic sections and the timeline narrative appear.

- [ ] **Step 6: Commit**

```bash
git add hugo-site/content/topics hugo-site/content/timeline/_index.md
git commit -m "feat: add reader demo topic indexes"
```

### Task 7: Refresh Editorial Templates And Styling

**Files:**
- Modify: `hugo-site/layouts/_default/list.html`
- Modify: `hugo-site/layouts/_default/single.html`
- Modify: `hugo-site/layouts/partials/card.html`
- Modify: `hugo-site/layouts/partials/site_header.html`
- Modify: `hugo-site/layouts/partials/site_footer.html`
- Modify: `hugo-site/static/css/custom.css`

- [ ] **Step 1: Make list templates work for reader sections**

Ensure list pages render `.Content`, followed by `.Pages` cards when available.

- [ ] **Step 2: Make single pages show structured context**

Render content first, then optional claims and sources from front matter.

- [ ] **Step 3: Replace dark system CSS**

Use a light editorial palette:

```css
:root {
  --bg: #f7f5ef;
  --paper: #fffdf8;
  --ink: #171717;
  --muted: #6f6b63;
  --line: #ded8cc;
  --accent: #0f766e;
  --accent-2: #9a3412;
  --soft: #ece7dc;
}
```

Use dense editorial components: front page grid, brief lanes, article cards, dossier blocks, topic tables, timeline entries.

- [ ] **Step 4: Verify CSS no longer reads as dark AI demo**

Run:

```bash
rg -n "#0b1020|#111831|a78bfa|demo-hero|signal-console|workflow-panel" hugo-site/static/css/custom.css hugo-site/layouts
```

Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add hugo-site/layouts hugo-site/static/css/custom.css
git commit -m "feat: refresh reader site templates"
```

### Task 8: Build, Inspect, And Prepare For Vercel

**Files:**
- Modify only if needed: `hugo-site/vercel-build.sh`, `hugo-site/vercel.json`

- [ ] **Step 1: Check Hugo availability**

Run:

```bash
command -v hugo
```

Expected: path to Hugo if installed; empty output if unavailable.

- [ ] **Step 2: Run local build path**

If Hugo is installed, run:

```bash
cd hugo-site
hugo --gc --minify
```

Expected: build completes and `public/index.html` exists.

If Hugo is not installed, run:

```bash
cd hugo-site
bash -n vercel-build.sh
test -f vercel.json
```

Expected: shell syntax passes and Vercel config exists.

- [ ] **Step 3: Verify required generated routes or source routes**

Run:

```bash
test -f hugo-site/content/briefs/daily/2026-05-03.md
test -f hugo-site/content/insights/agent-runtime-becomes-enterprise-control-plane.md
test -f hugo-site/content/entities/openai/_index.md
test -f hugo-site/content/topics/ai-agents/_index.md
test -f hugo-site/content/timeline/_index.md
```

Expected: all tests exit successfully.

- [ ] **Step 4: Commit verification fixes if any**

```bash
git add hugo-site/vercel-build.sh hugo-site/vercel.json
git commit -m "chore: verify reader demo build path"
```

Only commit if files changed.

### Task 9: Push Demo To GitHub For Vercel

**Files:**
- No source edits expected.

- [ ] **Step 1: Inspect remote**

Run:

```bash
git remote -v
```

Expected: a GitHub remote is configured for the repository that Vercel watches.

- [ ] **Step 2: Inspect current branch**

Run:

```bash
git branch --show-current
```

Expected: branch name appears. If the branch is `main`, confirm it is the intended Vercel deployment branch before pushing.

- [ ] **Step 3: Push**

Run:

```bash
git push
```

Expected: push succeeds and Vercel can build from GitHub.

- [ ] **Step 4: Report result**

Report pushed branch, latest commit hash, and any local build limitation.

## Self-Review Notes

- Spec coverage: Home, daily brief, insights, entities, topics, timeline, content quality, visual direction, and Vercel readiness are each mapped to tasks.
- Scope: The plan keeps the first implementation inside the existing Hugo site and does not introduce a new framework.
- Known risk: local Hugo may be unavailable. Task 8 includes a fallback syntax and route verification path, while Vercel can still run `vercel-build.sh`.
