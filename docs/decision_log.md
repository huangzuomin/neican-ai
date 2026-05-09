# Decision Log

## 2026-05-05: Initialize Development Repository

### Observation

The user requested a development repository for the existing `neican-editor` OpenClaw sub-agent, with no edits to `~/.openclaw/workspace-neican-editor` and no runtime workspace file copy during initialization.

### Decision

Initialize `neican-editor-dev` as an agent-only project copied from `/home/ai/projects/openclaw-app-template`.

### Reason

The OpenClaw development workflow requires work to happen in a separate repository and runtime paths to be documented only as deployment targets until deployment is explicitly requested.

### Impact

Runtime files under `~/.openclaw/` were not modified during initialization. The deployable project source lives under `/home/ai/projects/openclaw-apps/neican-editor-dev/openclaw/agent/`.

## 2026-05-05: Runtime Migration

### Observation

The existing `neican-editor` runtime workspace contained real agent files, scripts, schemas, Hugo site assets, Memory Wiki content, tests, and development docs. The initialized development repository already had placeholder agent identity files with the same names as runtime files.

### Decision

Copy non-conflicting runtime files into `openclaw/agent/`, copy runtime development documentation into `docs/runtime-workspace-docs/`, and preserve conflicts without overwriting them.

### Reason

The migration rules required source workspace safety, no secrets/logs/caches/env/git copying, and conflict reporting before overwrite.

### Impact

Runtime source files are present in the development repository, except for skipped policy paths and five non-overwritten conflicts: `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md`, and `USER.md`.

## 2026-05-05: Rebuild Clean Development Documents

### Observation

The migrated runtime files show that `neican-editor` is not only a generic editing agent; it is the OpenClaw sub-agent workspace for the neican.ai AI industry knowledge engine, with ingestion, event modeling, editorial decisions, Memory Wiki assets, Hugo publishing source, schemas, scripts, and tests.

### Decision

Regenerate the primary development document set for an OpenClaw sub-agent workspace:

- `docs/project_spec.md`
- `docs/openclaw-contract.md`
- `docs/test_plan.md`
- `docs/decision_log.md`
- `docs/project_manifest.md`

### Reason

Future Codex sessions need clean documents that reflect the migrated project rather than initialization placeholders. The documents must keep the development repository and runtime workspace separate, document the exact validation and deployment commands, and prohibit invented OpenClaw CLI commands.

### Impact

Future work should start from `docs/project_spec.md` and `docs/openclaw-contract.md`, edit only `/home/ai/projects/openclaw-apps/neican-editor-dev`, validate with `bash scripts/validate.sh`, and deploy only when explicitly requested with `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.

## 2026-05-05: MVP Quality Gate Sprint 01 Scope

### Observation

`docs/mvp反馈.md` says the MVP has the right product direction but exposes too much semi-finished knowledge-engine output: weak AI relevance items, duplicate events, noisy entities, database-like insight titles, invalid `0001-01-01` dates, homepage 404 links, internal review states on public pages, weak source trust controls, and topic pages that behave like event lists instead of Topic Hubs.

### Decision

Treat the feedback as a quality-gate sprint instead of a broad feature expansion. Implement and document the smallest concrete gates now:

- AI relevance gate before event modeling.
- Daily brief dedupe by event ID, source URL, and normalized title.
- Valid dates and thesis-oriented structure for generated insight pages.
- Topic Hub header sections for generated topic pages.
- Public template removal of `draft`, `needs_review`, `event_id`, and `generated_by` style metadata.
- Homepage link correction and build-time internal link checking.
- Runtime identity and Skill instructions updated to emphasize editorial judgment over raw aggregation.

### Reason

These changes directly address P0 credibility failures while preserving the OpenClaw development/runtime boundary and avoiding unrelated architecture changes.

### Impact

The agent should now bias toward fewer, cleaner public outputs. Some marginal AI-adjacent items may be ignored until the relevance gate is tuned. Future work can add richer schema fields such as `ai_relevance_score`, `event_fingerprint`, `entity_role`, `entity_quality`, and formal S/A/B/C source trust labels.

### Assumption

Because the feedback did not provide a finalized taxonomy for source trust or entity approval, this sprint records those as future schema/config work instead of inventing a full migration.

### Open Questions

- Should the canonical source trust model use the existing numeric `trust_level` values, S/A/B/C labels, or both?
- Which entities should be pre-approved as public core entities before suppressing candidate/noise entities?
- Should link checking scan only generated `public/` HTML, or should it also inspect raw Markdown before Hugo renders links?

## 2026-05-05: Entity Quality Gate Implementation

### Observation

The MVP feedback called out entity-library pollution: source media, generic finance/social organizations, and incidental mentions were being promoted into public entity files.

### Decision

Add `entity_role` and `entity_quality` to `entity_registry` and `entity_profiles`, and filter `entity_product` public export to approved core roles only.

### Reason

This keeps SQLite auditability while preventing NER-like extraction output from becoming public knowledge assets.

### Impact

Core companies, models, and tools can publish as public entity pages. Source media and context entities remain recorded but are suppressed from Hugo export by default. People and regulators are currently conservative candidates unless explicitly promoted later.

### Assumption

The first pass uses deterministic rules from entity type/name/source markers rather than a manually curated approval list. A curated core-entity allowlist can replace or refine this later.

## 2026-05-05: Source Trust and Entity Allowlist

### Observation

After the entity quality gate, the next risk was that weak single-source policy/safety items could still meet A thresholds, while important organization-type AI infrastructure entities needed explicit approval instead of relying only on entity type heuristics.

### Decision

Add `config/source_trust.yaml` with S/A/B/C tiers mapped from numeric `trust_level`, and require high-risk A candidates such as policy or safety events to meet the configured minimum trust tier. Add `config/entity_allowlist.yaml` for explicit approved and suppressed entities.

### Reason

Source credibility and public entity eligibility should be configurable editorial policy, not hidden code behavior.

### Impact

Weak-source policy/safety events are routed to review instead of becoming automatic A-grade insights. Approved allowlisted entities such as NVIDIA GEAR Lab can publish even if they are typed as organization; suppressed media entities remain out of public entity export.

### Assumption

The initial source tier mapping uses existing `trust_level` values to avoid a database migration. Future source configs can add explicit `trust_tier` labels if needed.

## 2026-05-05: Generated Content Backfill Cleanup

### Observation

The SQLite runtime ledger in the development repository was empty, but `hugo-site/content` already contained generated public Markdown with noisy entity pages, duplicate/low-relevance daily brief items, and weak-source high-risk insight content.

### Decision

Add `scripts/content_backfill_cleanup.py` to clean existing Hugo Markdown directly inside the development repository. The cleanup removes non-allowlisted entity pages, rewrites retained entity pages through the quality gate, filters low-relevance daily brief lines and orphan summaries, removes weak-source/noisy insight pages, and updates public links so Hugo link checking passes.

### Reason

The generated content was already present as source files, so waiting for DB regeneration would not remove public product defects. A repeatable cleanup script keeps the backfill auditable and testable.

### Impact

The public entity set is reduced to allowlisted core pages currently present in content (`OpenAI`, `Anthropic`). The noisy generated insight pages were removed, leaving the insights index for future regenerated thesis-grade content. Event pages no longer link directly to entity/topic chips, avoiding broken links when noisy entities are suppressed.

### Assumption

Until the runtime ledger is repopulated under the new gates, existing generated content should be cleaned conservatively rather than expanded.

## 2026-05-05: Merge Runtime Identity Files

### Observation

The migration had preserved five non-overwritten conflicts: `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md`, and `USER.md` under `openclaw/agent/`. The dev versions (from the template) were English and concise; the runtime versions (from `~/.openclaw/workspace-neican-editor`) were the actual production agent identity files with the exception of `TOOLS.md` and `USER.md`, which were generic placeholders never customized for neican-editor.

### Decision

Merge each file based on quality, not on source:

- `AGENTS.md`: Runtime version as base (Chinese, operational, with skill index and red lines). Added quality-gate working principles from dev version (AI relevance, dedupe, public-field hiding, uncertainty preservation).
- `IDENTITY.md`: Runtime version as base (Chinese, comprehensive — 12 responsibilities, core objects, tech stack, child agent definition, publishing boundary). Added quality-gate success criteria from dev version.
- `SOUL.md`: Runtime version as base (Chinese, definitive — A/B/C/D grading, core principles, must-avoid behaviors). Added uncertainty transparency and tone notes from dev version.
- `TOOLS.md`: Dev version kept; runtime version was a generic camera/SSH/TTS placeholder. Expanded with available Skills list and key config files.
- `USER.md`: Dev version kept; runtime version was an empty generic template. Already properly contextualized.

### Reason

The runtime versions of `AGENTS.md`, `IDENTITY.md`, and `SOUL.md` were the real agent identity — rich, domain-specific, and operationally proven. The runtime versions of `TOOLS.md` and `USER.md` had never been customized and were less useful than the template-derived dev versions.

### Impact

The five root identity conflicts are resolved. The agent now has a consistent identity document set: Chinese for the editorial soul and identity, English for tool/user documentation. All operational references (skills, config files, workflows) are preserved and verified to match the current project structure.

### Assumption

The identity files may need further tuning after deployment and runtime testing, but the merge is complete enough to pass static validation and support the next development step.

### Open Questions

- Should `TOOLS.md` include additional runtime-specific tool notes from the actual OpenClaw environment?
- Should `USER.md` be expanded with specific user preferences after deployment feedback?
