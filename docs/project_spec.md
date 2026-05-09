# Project Spec: neican-editor

## Goal

`neican-editor` is the OpenClaw sub-agent workspace for the neican.ai knowledge engine. Its job is to turn selected AI industry information into durable knowledge assets and controlled publishing outputs: raw item records, modeled events, editorial decisions, Memory Wiki pages, daily briefs, insight drafts, entity pages, topic pages, timelines, and Hugo-ready Markdown.

The development repository is `/home/ai/projects/openclaw-apps/neican-editor-dev`. The runtime workspace is `~/.openclaw/workspace-neican-editor`. Codex must work in the development repository and must not directly edit the runtime workspace.

## Artifact Type

OpenClaw sub-agent workspace.

Justification: the project is a persistent role with its own identity, runtime files, skills, scripts, memory assets, editorial policy, tool boundaries, and deployment target. The migrated workspace also contains agent-local Skills, but the deployable artifact is the full sub-agent workspace under `openclaw/agent/`.

## Recommended Architecture

Development happens in the Git repository at `/home/ai/projects/openclaw-apps/neican-editor-dev`. The deployable agent source lives under `openclaw/agent/` and is deployed to `~/.openclaw/workspace-neican-editor` only through:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

The migrated workspace has these major parts:

- Agent identity and operating files: `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`.
- Low-permission fetcher workspace: `sandbox-fetcher/`.
- Reusable local Skills: `skills/`.
- Project rules and reference docs: `docs/`.
- Source configuration: `config/`.
- SQLite schema and runtime ledger path: `db/`.
- Processing scripts: `scripts/`.
- Structured schemas: `schemas/`.
- Workflow notes: `flows/`.
- Knowledge assets: `memory-wiki/`.
- Static publishing output source: `hugo-site/`.
- Tests and fixtures: `tests/`.

## Target User

- The project owner operating neican.ai.
- Codex or another coding agent maintaining the development repository.
- The `neican-editor` OpenClaw runtime agent after approved deployment.

## User Scenario

A maintainer asks Codex to improve or validate part of the neican.ai knowledge engine. Codex reads these project documents and the migrated runtime files, edits only the development repository, validates with `bash scripts/validate.sh`, and reports whether deployment is ready. Deployment is a separate explicit step.

## Input

- AI industry sources configured under `openclaw/agent/config/`.
- RSS or web content fetched by the sandboxed fetcher path.
- Raw items, events, editorial decisions, and review queues represented in SQLite.
- Existing Memory Wiki content under `openclaw/agent/memory-wiki/`.
- Hugo content and layout files under `openclaw/agent/hugo-site/`.
- User requests for development, migration, validation, or documentation work.

## Output

- Updated sub-agent workspace files under `openclaw/agent/`.
- Structured knowledge assets in `memory-wiki/`.
- Hugo Markdown and static-site source files in `hugo-site/`.
- Validated scripts, schemas, and tests.
- Clear reports of files changed, validation results, assumptions, and anything not validated.

## Workflow

1. Read `docs/project_spec.md`, `docs/openclaw-contract.md`, `docs/test_plan.md`, and `docs/project_manifest.md`.
2. Read the relevant migrated runtime docs under `openclaw/agent/docs/`.
3. Make changes only in `/home/ai/projects/openclaw-apps/neican-editor-dev`.
4. Keep deployable runtime content under `openclaw/agent/`.
5. Do not directly edit `~/.openclaw/workspace-neican-editor`.
6. Do not invent OpenClaw CLI commands, flags, runtime tests, paths, or config keys.
7. Validate with `bash scripts/validate.sh`.
8. Run `git status` when requested or before handoff.
9. Deploy only after an explicit user request with `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.

## Core Capabilities

### Capability: MVP Quality Gates

Description:
Protect the public product from raw knowledge-engine artifacts by applying AI relevance, event-level dedupe, source quality, entity quality, public rendering, and link integrity gates before output is trusted as a user-facing AI industry intelligence product.

Acceptance Criteria:

- Given a raw item with weak or no AI industry relevance, when event modeling runs, then the item is marked ignored and does not enter events, daily briefs, timelines, entity pages, topic pages, or public Hugo output.
- Given multiple records for the same event, source URL, or normalized title, when a daily brief, topic page, timeline, or tracking line is generated, then the event appears at most once per page.
- Given public Hugo pages, when rendered, then internal fields such as `draft`, `needs_review`, `event_id`, `decision_id`, and `generated_by` are not shown to end users.
- Given a Hugo build, when internal links on the home page, navigation, or generated content are broken, then the build check reports failure before deployment.

### Capability: Runtime Workspace Development

Description:
Maintain the migrated OpenClaw sub-agent workspace as source-controlled development content.

Acceptance Criteria:

- Given a development task, when Codex edits files, then edits are made under `/home/ai/projects/openclaw-apps/neican-editor-dev`.
- Given a file under `~/.openclaw/workspace-neican-editor`, when Codex needs to change runtime behavior, then Codex updates the corresponding source file under `openclaw/agent/` instead of editing the runtime workspace directly.

### Capability: Source Ingestion and Extraction

Description:
Use configured sources and sandboxed extraction paths to collect raw AI industry information before modeling it.

Acceptance Criteria:

- Given configured RSS or web sources, when ingestion scripts are run by an approved workflow, then raw items are deduplicated and recorded in the SQLite ledger.
- Given untrusted external web content, when it is fetched, then it is handled through the sandbox-fetcher boundary and does not directly write Memory Wiki or Hugo content.

### Capability: Event Modeling and Editorial Decision

Description:
Transform raw items into events, classify editorial value, and route work according to A/B/C/D editorial decisions.

Acceptance Criteria:

- Given a raw item, when event modeling starts, then AI relevance is evaluated before event creation.
- Given processed raw items, when event modeling runs, then events are produced according to the project schemas.
- Given modeled events, when editorial decision logic runs, then decisions are recorded and high-value or high-risk items enter the appropriate review path.
- Given policy, safety, legal, dispute, financial, or other high-risk A-grade candidates, when editorial decisions run, then weak single-source evidence is routed to review instead of automatically treated as high-confidence A-grade output.

### Capability: Knowledge Asset Maintenance

Description:
Update Memory Wiki entities, topics, concepts, timelines, claims, drafts, reports, and syntheses as durable knowledge assets.

Acceptance Criteria:

- Given a validated event with entities and topics, when knowledge asset update logic runs, then relevant Memory Wiki pages are updated without overwriting important existing content blindly.
- Given missing or uncertain source data, when content is generated, then uncertainty is preserved instead of being invented.
- Given extracted entities, when public entity pages are generated, then only approved or core AI-relevant entities are exposed; source media and incidental mentions remain source/context metadata unless deliberately promoted.
- Given entity registry/profile sync, when entities are classified, then `entity_role` and `entity_quality` determine whether they can become public entity pages.

### Capability: Hugo Export and Build Readiness

Description:
Generate Hugo-ready Markdown and keep static publishing files buildable.

Acceptance Criteria:

- Given approved daily brief or insight content, when Hugo export runs, then generated front matter follows `openclaw/agent/docs/FRONTMATTER_SPEC.md`.
- Given generated Hugo content, when validation or build checks run, then failures are reported with enough detail for follow-up work.
- Given generated insight content, when it is exported, then it has a valid non-zero date and a clear thesis-oriented article structure.
- Given generated topic content, when it is exported, then the page behaves as a Topic Hub with definition, current judgment, recent changes, key entities, representative events, and next observations.

### Capability: Deployment Boundary

Description:
Keep development and runtime deployment separate.

Acceptance Criteria:

- Given a completed development change, when validation passes, then the report recommends deployment only as a separate explicit step.
- Given no deployment request, when Codex finishes the task, then it does not run `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.

## Non-goals

- Do not directly edit `~/.openclaw/workspace-neican-editor`.
- Do not manually copy files into `~/.openclaw/`.
- Do not deploy unless the user explicitly asks.
- Do not invent OpenClaw CLI commands or runtime validation commands.
- Do not introduce unapproved workflow systems, databases, CMS products, or agent hierarchies.
- Do not store secrets, tokens, cookies, credentials, logs, or caches in project docs.

## Acceptance Criteria

- Given the repository path `/home/ai/projects/openclaw-apps/neican-editor-dev`, when a coding agent starts work, then it can identify the development repository, runtime workspace, validation command, and deployment command from docs alone.
- Given the runtime path `~/.openclaw/workspace-neican-editor`, when a coding agent needs to modify the sub-agent, then docs clearly instruct it not to edit the runtime workspace directly.
- Given a completed documentation or development change, when `bash scripts/validate.sh` is run, then validation passes before the agent claims readiness.
- Given any proposed OpenClaw command, when it is not explicitly documented or verified, then it is treated as forbidden.

## Risks and Mitigations

- Risk: Runtime identity files in the migration conflicted with initialized development files. Mitigation: conflicts were recorded in `docs/runtime_migration_report.md`; review and merge them deliberately before deployment.
- Risk: Generated site output or caches may be mistaken for source. Mitigation: generated/cache-like paths are excluded or removed during migration and should remain out of source unless intentionally committed.
- Risk: OpenClaw command assumptions could break runtime behavior. Mitigation: do not add OpenClaw CLI commands unless verified and recorded.
- Risk: SQLite files may contain runtime state. Mitigation: treat `openclaw/agent/db/neican.sqlite` as migrated state; prefer schema and scripts for reproducible behavior.

## Dependencies

- Template source: `/home/ai/projects/openclaw-app-template`.
- Development repository: `/home/ai/projects/openclaw-apps/neican-editor-dev`.
- Runtime workspace: `~/.openclaw/workspace-neican-editor`.
- Python scripts and tests under `openclaw/agent/scripts/` and `openclaw/agent/tests/`.
- Hugo project files under `openclaw/agent/hugo-site/`.
- Validation script: `scripts/validate.sh`.

## Assumptions

- `neican-editor` remains an OpenClaw sub-agent workspace, not a standalone Skill project.
- Deployment is intentionally separate from documentation and validation tasks.
- Runtime validation requires a future explicit command; no OpenClaw runtime test command is defined in this document set.
- Existing migrated docs under `openclaw/agent/docs/` are treated as domain source material.

## Open Questions

- Should the migrated runtime versions of `AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `USER.md`, and `TOOLS.md` replace or be merged with the initialized development versions?
- Which local functional tests should be considered required beyond `bash scripts/validate.sh`?
- Should `db/neican.sqlite` remain in the development repository or be regenerated from `db/schema.sql` during setup?
- What exact manual runtime validation command should be used after deployment?
- What source trust tier taxonomy should be canonical: numeric `trust_level` 1-5, S/A/B/C labels, or both?
- Which entities should be pre-approved as public core entities before the entity quality gate suppresses noisy generated pages?

## Implementation Hints for Codex

Recommended task sequence:

1. Read `docs/openclaw-contract.md` and `docs/runtime_migration_report.md`.
2. Review unresolved migration conflicts in the five root agent identity files.
3. Compare migrated docs under `openclaw/agent/docs/` with current project behavior.
4. Make scoped changes under `openclaw/agent/` or `docs/`.
5. Run `bash scripts/validate.sh`.
6. Run `git status`.
7. Report files changed, validation result, and anything not validated.

Complexity:

- Medium

Dependencies:

- Existing migrated runtime files.
- Template deployment and validation scripts.
- Project docs and schema files.

Suggested first task:

- Review and intentionally merge the five non-overwritten runtime identity conflicts before deployment.

## Notes for Codex

- Read these files first: `docs/project_spec.md`, `docs/openclaw-contract.md`, `docs/test_plan.md`, `docs/project_manifest.md`, `docs/runtime_migration_report.md`.
- Edit these files: project docs, `openclaw/agent/`, tests, schemas, scripts, and config as required by the user task.
- Do not edit these files: anything under `~/.openclaw/workspace-neican-editor` unless the user explicitly changes the boundary.
- Code writing allowed: Yes, when the user asks for implementation work.
- Deployment allowed: No, unless explicitly requested.
- Validation commands: `bash scripts/validate.sh`.
