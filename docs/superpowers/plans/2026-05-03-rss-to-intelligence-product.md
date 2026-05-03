# RSS To Intelligence Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn RSS-derived information into the final reader-facing neican.ai product through six prioritized modules: Event Store, Entity Registry, Topic Registry, Timeline Builder, Daily Brief, and Insight.

**Architecture:** Treat Event as the system atom. RSS items are cleaned, deduplicated, modeled into structured events, normalized against entity/topic registries, routed into timeline tracks, summarized into daily briefs, and eventually synthesized into insights. Each iteration must leave auditable SQLite rows, generated Markdown/Hugo output where applicable, and tests proving the module can be trusted by OpenClaw.

**Tech Stack:** Python scripts, SQLite, YAML config, JSON fields, project Skills under `skills/`, pytest, Hugo Markdown/front matter, OpenClaw/Codex execution.

---

## Operating Contract For OpenClaw

OpenClaw may execute this plan module by module without waiting for human decisions. Each module must finish with:

- Passing tests for the module and affected pipeline behavior.
- A `runs` row or equivalent SQLite evidence when the module has runtime behavior.
- Generated sample output when the module affects Hugo pages.
- A commit with a focused message.
- An audit note in the final response listing changed files, verification commands, and known residual risks.

The iteration result can be handed back to Codex for audit. Codex audit should check:

- Whether the implementation still follows Event-first architecture.
- Whether generated public content can be traced back to event IDs, source URLs, and claims.
- Whether entity/topic/track names are stable and normalized.
- Whether tests prove behavior rather than only implementation details.
- Whether generated Hugo pages match the reader-facing demo direction.

## Current Baseline

Already present:

- RSS ingestion: `scripts/fetch_sources.py`
- Content extraction: `scripts/extract_content.py`
- Event modeling: `scripts/event_modeling.py`
- Editorial decisioning: `scripts/editorial_decision.py`
- Entity product output: `scripts/entity_product.py`
- Event catalog output: `scripts/event_product.py`
- Track-aware timeline output: `scripts/timeline_product.py`
- Candidate track discovery and automatic review: `scripts/candidate_tracks.py`, `scripts/track_review.py`, `skills/track-review/SKILL.md`
- Content export for daily briefs and single-event insights: `scripts/export_hugo.py`

Known gaps:

- Event Store still lacks source merge groups and event-level deduplication across multiple RSS items.
- Entity Registry is generated from events, but alias normalization is still config-heavy and does not have a registry table.
- Topic Registry exists mostly as taxonomy config and Memory Wiki output, not a productized registry.
- Timeline Builder has track assignment, but automatic approved candidate tracks do not yet update public track config.
- Daily Brief is generated, but not yet track-aware or reader-demo polished from real event clusters.
- Insight generation is event-based, not yet triggered by accumulated timeline-track structure changes.

## Iteration 1: Event Store

**Purpose:** Ensure every RSS item becomes either a clean raw item, duplicate, merged source for an existing event, or a new structured event.

**Files:**
- Modify: `db/schema.sql`
- Modify: `scripts/event_modeling.py`
- Create: `scripts/event_store.py`
- Test: `tests/test_event_store.py`
- Update: `scripts/pipeline.py`

**Target behavior:**

```text
raw_items
  -> source-level dedupe by content_hash
  -> event-level matching by canonical title/entities/date
  -> events
  -> event_sources join evidence
```

- [ ] **Step 1: Write event merge tests**

Create `tests/test_event_store.py` with tests for:

```python
def test_event_store_merges_two_raw_items_about_same_event(tmp_path):
    # Insert two raw_items from different sources with similar titles,
    # same date, same entities, and same topics.
    # Run event_store.merge_modeled_events().
    # Assert one canonical event remains public and event_sources has two source rows.
```

```python
def test_event_store_keeps_distinct_events_separate(tmp_path):
    # Insert two modeled events with different event_date or dominant entity.
    # Assert they remain separate canonical events.
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_event_store.py -q
```

Expected: fails because `scripts/event_store.py` and `event_sources` do not exist.

- [ ] **Step 3: Add schema**

Add:

```sql
CREATE TABLE IF NOT EXISTS event_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  raw_item_id INTEGER NOT NULL UNIQUE,
  source_url TEXT,
  source_title TEXT,
  source_name TEXT,
  published_at TEXT,
  confidence REAL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (event_id) REFERENCES events(id),
  FOREIGN KEY (raw_item_id) REFERENCES raw_items(id)
);

CREATE INDEX IF NOT EXISTS idx_event_sources_event ON event_sources(event_id);
```

- [ ] **Step 4: Implement `scripts/event_store.py`**

Required public function:

```python
def merge_modeled_events(db_path: Path = DB_PATH) -> EventStoreResult:
    ...
```

Result shape:

```python
@dataclass(frozen=True)
class EventStoreResult:
    canonical_events: int
    merged_events: int
    event_sources: int
```

Merge key:

```text
normalized event_title first 80 chars + event_date first 10 chars + first entity slug
```

- [ ] **Step 5: Wire pipeline**

Call `merge_modeled_events()` after `model_events()` and before `make_decisions()`. Add `event_store` to `PipelineResult`.

- [ ] **Step 6: Verify**

Run:

```bash
python3 -m pytest tests/test_event_store.py tests/test_pipeline.py tests/test_init_db.py -q
```

Expected: pass.

- [ ] **Step 7: Audit checkpoint**

Codex audit should confirm source traceability: every public event must have at least one `event_sources` row or a documented reason why legacy events are exempt.

## Iteration 2: Minimal Entity Registry

**Purpose:** Normalize entity names before timeline/entity/topic products consume them.

**Files:**
- Modify: `db/schema.sql`
- Modify: `config/entity_aliases.yaml`
- Create: `scripts/entity_registry.py`
- Test: `tests/test_entity_registry.py`
- Update: `scripts/event_modeling.py`
- Update: `scripts/entity_product.py`

**Target behavior:**

```text
OpenAI / openai / Open AI / ChatGPT maker
  -> entity_registry.slug = openai
```

- [ ] **Step 1: Write normalization tests**

Create `tests/test_entity_registry.py` with:

```python
def test_entity_registry_normalizes_aliases_to_one_slug(tmp_path):
    # Given aliases OpenAI, openai, Open AI.
    # normalize_entity("Open AI") returns {"slug": "openai", "name": "OpenAI"}.
```

```python
def test_entity_registry_upserts_entities_from_events(tmp_path):
    # Insert events mentioning alias variants.
    # Run sync_entity_registry().
    # Assert one row exists for openai and aliases_json includes variants.
```

- [ ] **Step 2: Add schema**

Add:

```sql
CREATE TABLE IF NOT EXISTS entity_registry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  canonical_name TEXT NOT NULL,
  entity_type TEXT NOT NULL DEFAULT 'organization',
  aliases_json TEXT,
  confidence REAL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 3: Implement `scripts/entity_registry.py`**

Required functions:

```python
def normalize_entity_name(value: str, aliases: dict[str, list[str]]) -> tuple[str, str]:
    ...

def sync_entity_registry(db_path: Path = DB_PATH, aliases_path: Path = ENTITY_ALIASES_PATH) -> EntityRegistryResult:
    ...
```

- [ ] **Step 4: Apply registry during event modeling**

After LLM/rule extraction, normalize each entity before writing `entities_json`.

- [ ] **Step 5: Update entity product**

Make `entity_product.py` prefer `entity_registry.canonical_name` and `entity_registry.entity_type` when available.

- [ ] **Step 6: Verify**

Run:

```bash
python3 -m pytest tests/test_entity_registry.py tests/test_event_modeling.py tests/test_entity_product.py tests/test_pipeline.py -q
```

Expected: pass. If `tests/test_entity_product.py` does not exist yet, create it before modifying `entity_product.py`.

- [ ] **Step 7: Audit checkpoint**

Codex audit should sample generated `hugo-site/content/entities/openai/_index.md` and verify it aggregates all alias variants under one slug.

## Iteration 3: Topic Registry

**Purpose:** Convert topic slugs from loose taxonomy into stable product objects that support topic pages, timeline tracks, and daily brief grouping.

**Files:**
- Modify: `db/schema.sql`
- Modify: `config/taxonomy.yaml`
- Create: `scripts/topic_registry.py`
- Create: `scripts/topic_product.py`
- Test: `tests/test_topic_registry.py`
- Test: `tests/test_topic_product.py`
- Update: `scripts/pipeline.py`

**Target behavior:**

```text
ai-agents
  canonical_name: AI Agents
  aliases: agentic workflow, autonomous agents
  parent: enterprise-ai
  public: true
```

- [ ] **Step 1: Write registry tests**

Create tests proving:

```python
def test_topic_registry_syncs_taxonomy_to_sqlite(tmp_path):
    # taxonomy.yaml topic slugs become topic_registry rows.
```

```python
def test_topic_registry_normalizes_topic_aliases(tmp_path):
    # "Agentic Workflow" normalizes to ai-agents.
```

- [ ] **Step 2: Add schema**

Add:

```sql
CREATE TABLE IF NOT EXISTS topic_registry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  canonical_name TEXT NOT NULL,
  aliases_json TEXT,
  parent_slug TEXT,
  description TEXT,
  public INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 3: Implement `scripts/topic_registry.py`**

Required function:

```python
def sync_topic_registry(db_path: Path = DB_PATH, taxonomy_path: Path = TAXONOMY_PATH) -> TopicRegistryResult:
    ...
```

- [ ] **Step 4: Implement `scripts/topic_product.py`**

Generate:

```text
hugo-site/content/topics/_index.md
hugo-site/content/topics/{topic_slug}/_index.md
```

Each topic page must include related events, related entities, related tracks, and source count.

- [ ] **Step 5: Wire pipeline**

Run topic registry sync before candidate track discovery and topic product export after timeline product.

- [ ] **Step 6: Verify**

Run:

```bash
python3 -m pytest tests/test_topic_registry.py tests/test_topic_product.py tests/test_pipeline.py -q
npm run build
```

- [ ] **Step 7: Audit checkpoint**

Codex audit should check whether topic pages are reader-facing and not internal dumps.

## Iteration 4: Timeline Builder

**Purpose:** Make timeline tracks the structural map of the site, fed by A/B events and governed by automatic candidate-track review.

**Files:**
- Modify: `scripts/timeline_product.py`
- Modify: `scripts/candidate_tracks.py`
- Modify: `scripts/track_review.py`
- Modify: `config/timeline_tracks.yaml`
- Test: `tests/test_timeline_product.py`
- Test: `tests/test_track_review.py`

**Target behavior:**

```text
A/B events
  -> timeline_nodes
  -> assigned public tracks
  -> candidate tracks
  -> track-review skill decision
  -> generated /timeline/ and /timeline/{track}/
```

- [ ] **Step 1: Expand tests for approved candidates**

Add:

```python
def test_track_review_approves_distinct_candidate_track(tmp_path):
    # Candidate has 5 events, multiple entities, no overlap with existing tracks.
    # Assert decision approved.
```

- [ ] **Step 2: Implement approved-track materialization**

When `track_review_decisions.decision = 'approved'`, write or update a controlled generated section in `config/timeline_tracks.yaml`:

```yaml
# generated_tracks:
#   managed_by: track_review
```

Do not overwrite manually curated tracks.

- [ ] **Step 3: Add merge evidence to timeline nodes**

For merged candidates, preserve candidate ID in track metadata or node metadata so audits can see which candidate strengthened which public track.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_track_review.py tests/test_timeline_product.py tests/test_pipeline.py -q
npm run build
```

- [ ] **Step 5: Audit checkpoint**

Codex audit should verify that public track count remains sane, generated tracks have evidence event IDs, and no raw RSS text leaks into public pages.

## Iteration 5: Daily Brief

**Purpose:** Generate a reader-facing daily brief from Event Store and Timeline Tracks, not just a list of B/C decisions.

**Files:**
- Modify: `scripts/export_hugo.py`
- Create or modify: `scripts/daily_brief_product.py`
- Test: `tests/test_daily_brief_product.py`
- Update: `hugo-site/layouts/briefs/single.html`

**Target behavior:**

Daily brief contains:

- 今日判断
- 按追踪线组织的事件
- A/B/C 事件分层
- 新增候选追踪线/自动审核摘要
- 值得继续观察
- 来源索引

- [ ] **Step 1: Write tests**

Create:

```python
def test_daily_brief_groups_events_by_timeline_track(tmp_path):
    # Insert events across two tracks.
    # Generate daily brief.
    # Assert headings include track titles and event links.
```

```python
def test_daily_brief_includes_track_review_summary(tmp_path):
    # Insert one merged candidate track review decision.
    # Assert brief mentions automatic merge/watch decision.
```

- [ ] **Step 2: Implement product script**

Required function:

```python
def generate_daily_brief(db_path: Path, site_dir: Path, date: str) -> DailyBriefResult:
    ...
```

- [ ] **Step 3: Replace or wrap current daily export**

`export_hugo.py` may call `generate_daily_brief()` instead of owning all daily brief construction.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_daily_brief_product.py tests/test_export_hugo.py tests/test_pipeline.py -q
npm run build
```

- [ ] **Step 5: Audit checkpoint**

Codex audit should check whether a reader can understand the day without knowing internal table names.

## Iteration 6: Insight

**Purpose:** Generate deep insights only when a timeline track accumulates enough structural evidence.

**Files:**
- Modify: `db/schema.sql`
- Create: `scripts/insight_candidates.py`
- Create: `scripts/insight_product.py`
- Modify: `scripts/export_hugo.py`
- Test: `tests/test_insight_candidates.py`
- Test: `tests/test_insight_product.py`

**Target behavior:**

```text
timeline track has repeated A/B events
  -> insight_candidate
  -> evidence bundle
  -> generated insight draft
  -> review_status=draft
```

- [ ] **Step 1: Add schema**

Add:

```sql
CREATE TABLE IF NOT EXISTS insight_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track_slug TEXT NOT NULL,
  proposed_title TEXT NOT NULL,
  thesis TEXT,
  evidence_event_ids_json TEXT,
  entity_slugs_json TEXT,
  topic_slugs_json TEXT,
  confidence REAL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'proposed',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 2: Write candidate tests**

Create:

```python
def test_insight_candidate_created_from_track_with_three_a_grade_events(tmp_path):
    # Insert timeline nodes for one track with three A-grade events.
    # Assert one insight candidate is created with evidence_event_ids.
```

- [ ] **Step 3: Implement insight candidate detection**

Rules:

```text
candidate if track has >= 3 A events in 30 days
candidate if track has >= 6 A/B events and candidate track review is approved/merged
skip if existing insight covers same evidence_event_ids
```

- [ ] **Step 4: Implement insight product**

Generate `hugo-site/content/insights/{slug}.md` with:

- 核心判断
- 证据链
- 结构变化
- 关键实体
- 后续观察点
- 来源

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m pytest tests/test_insight_candidates.py tests/test_insight_product.py tests/test_export_hugo.py tests/test_pipeline.py -q
npm run build
```

- [ ] **Step 6: Audit checkpoint**

Codex audit should ensure insights are not single-event rewrites. Each insight must cite multiple event IDs and sources.

## Final Integration

- [ ] **Step 1: Full pipeline dry run**

Run:

```bash
python3 scripts/pipeline.py --date 2026-05-03 --mock --limit 5
```

Expected JSON includes:

```json
{
  "fetch": {},
  "extract": {},
  "model": {},
  "event_store": {},
  "decide": {},
  "assets": {},
  "candidate_tracks": {},
  "track_review": {},
  "timeline": {},
  "entities": {},
  "events": {},
  "export": {}
}
```

- [ ] **Step 2: Build public site**

Run:

```bash
cd hugo-site
npm run build
```

Expected: Hugo exits 0 and generated pages include `/timeline/`, `/entities/`, `/topics/`, `/briefs/daily/`, and `/insights/`.

- [ ] **Step 3: Full regression**

Run:

```bash
python3 -m pytest tests -q
```

Expected: all tests under `tests/` pass.

- [ ] **Step 4: Prepare audit package**

OpenClaw final response must include:

```text
Branch:
Commits:
Modules completed:
Verification commands:
Generated public pages:
Database tables changed:
Known limitations:
Suggested Codex audit focus:
```

## Audit Handoff To Codex

After each iteration, ask Codex to audit using this prompt:

```text
请审计当前迭代是否符合 RSS → Event Store → Entity Registry → Topic Registry → Timeline Builder → Daily Brief → Insight 的模块优先级。

重点检查：
1. 是否仍然以 Event 为系统原子。
2. 是否所有公开内容都能追溯到 event_id/raw_item/source_url。
3. 是否实体、主题、追踪线命名稳定，不会因 RSS 噪音漂移。
4. 是否测试覆盖真实行为。
5. 是否 Hugo 输出符合 reader-facing demo 的最终形态。

请按严重程度列出 findings，并给出是否可以进入下一迭代的结论。
```
