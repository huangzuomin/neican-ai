# neican.ai Reader Site Demo Design

## Purpose

Build a Hugo demo that shows the future public-facing neican.ai reader experience. The demo is for the project owner first: it should make the desired final website concrete enough to reason backward into OpenClaw skills, data objects, Memory Wiki outputs, and Hugo export templates.

The demo should feel like a real AI industry intelligence product, not an internal workflow diagram, a generic blog, or a marketing landing page.

## Audience

Primary audience:

- Project owner evaluating the final product shape and implementation path.

Secondary audience:

- Future readers who want a low-noise AI industry briefing.
- Collaborators who need to understand what OpenClaw should produce.

## Product Positioning

The public website should present neican.ai as an AI industry knowledge product with these promises:

- It filters noisy AI news into editorially ranked signals.
- It publishes concise daily briefings for medium-value signals.
- It reserves standalone insight articles for high-value events.
- It maintains long-lived entity, topic, concept, claim, and timeline assets.
- It avoids generating separate public URLs for low-value or duplicate items.

The reader should experience the site as a trustworthy industry desk, while the project owner can still see how each page maps back to structured objects.

## Demo Scope

The first reader-site demo will focus on a coherent sample universe rather than broad coverage.

Core narrative:

- AI agents are moving from productivity assistants into enterprise workflow infrastructure.

Included sections:

- Home page.
- Daily brief index and one polished daily brief.
- Insights index and three high-quality insight examples.
- Entity index and four polished entity pages.
- Topic index and three polished topic pages.
- Timeline page showing the narrative over time.

Sample entities:

- OpenAI.
- Anthropic.
- Microsoft.
- Google DeepMind.
- Nvidia.
- Cursor.

Sample topics and concepts:

- AI Agents.
- Enterprise AI Governance.
- MCP.
- Computer Use.
- Agent Runtime.
- Evals.

Out of scope for this demo pass:

- Admin UI.
- User accounts.
- Search backend.
- Personalization.
- Full old-site migration.
- Large-scale generated archives.
- New frontend framework adoption.

## Information Architecture

### Home

The home page should behave like a reader-facing intelligence front page.

It should open with a specific editorial judgment, not a generic hero slogan. Example:

`今日判断：Agent 产品正在从效率工具转向企业治理基础设施。`

Primary modules:

- Lead insight: one A-grade story with a clear "why it matters" summary.
- Today's brief: five concise B-grade signals grouped by sector.
- Rising themes: topics gaining importance.
- Entity watchlist: key companies, labs, tools, and infrastructure providers.
- Timeline excerpt: recent events placed into longer context.

The page may hint at structured production through labels such as entity, topic, source, confidence, and grade, but should not foreground internal workflow language.

### Daily Brief

The daily brief should read like a compact industry memo, not a news feed.

Structure:

- Date and one-line editorial readout.
- Five sections: Models, Agents, Infrastructure, Policy, Applications.
- Each item includes signal, why it matters, related entities, and next watch point.
- Low-value duplicated or promotional items are absent.

### Insights

Insights are sparse and high-value.

Each insight should include:

- A sharp headline.
- Why it matters.
- What changed.
- Who is affected.
- Evidence and sources.
- Related entities and topics.
- What to watch next.

The index should make scarcity visible: this is not a bulk article archive.

### Entities

Entity pages are living dossiers, not encyclopedia entries.

Each entity page should answer:

- What is the current signal around this entity?
- Which recent events matter?
- Which topics does it influence?
- Which claims are worth tracking?
- What should readers watch next?

### Topics

Topic pages are research indexes.

Each topic page should connect:

- Current thesis.
- Recent events.
- Key entities.
- Important claims.
- Related insights.
- Timeline notes.

### Timeline

The timeline should show structural change over time.

It should group events by theme when helpful, not merely list dates.

## Visual Direction

The site should feel like a modern intelligence desk:

- Calm white or very light neutral background.
- Strong editorial typography.
- Dense but breathable information layout.
- Thin dividers, tables, lists, and annotations over decorative cards.
- Minimal gradients and no generic AI glow aesthetic.
- Chinese-first reading experience.
- Clear content hierarchy for mobile and desktop.

Avoid:

- Oversized marketing hero sections.
- Purple/blue AI gradients as the main visual identity.
- Generic SaaS dashboard styling.
- Decorative visuals that obscure the actual content product.

## Content Quality Bar

Demo content should be internally coherent and AI-industry focused.

Every public sample article or brief item should have:

- Entities.
- Topics.
- At least one source reference.
- A claim or judgment.
- A reason it appears on the site.

Remove or quarantine sample content that does not match the AI industry scope or has empty claims.

## OpenClaw Backward Mapping

Although the reader site should not explain the implementation, each public module should map cleanly back to system outputs:

- Home lead insight maps to A-grade event decision and insight export.
- Daily brief maps to B-grade decisions and daily brief generation.
- Entity pages map to Memory Wiki entity assets.
- Topic pages map to Memory Wiki topic assets.
- Timeline maps to event chronology and topic clustering.
- Source and evidence blocks map to raw item, extraction, and claim records.

This mapping is the reason the demo is useful for planning OpenClaw implementation.

## Implementation Strategy

Use the existing Hugo site.

Primary work:

- Rewrite homepage layout and content around the reader experience.
- Replace scattered sample content with a coherent AI-agent sample universe.
- Add or polish section templates only where necessary.
- Keep Hugo content and front matter compatible with the current project.
- Do not introduce a new frontend framework.

Verification:

- Confirm generated public pages exist for home, briefs, insights, entities, topics, and timeline.
- Run Hugo build if the executable is available.
- If Hugo is unavailable locally, verify the build script and document the limitation.

## Success Criteria

The demo is successful when:

- A first-time reader can understand what neican.ai is within one screen.
- The site feels like a real AI industry intelligence product.
- Daily brief, insight, entity, topic, and timeline pages form a coherent reading loop.
- The project owner can point to each visible module and identify which OpenClaw output should generate it.
- The demo can be pushed to GitHub for Vercel to build.
