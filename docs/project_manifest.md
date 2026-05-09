# Project Manifest

## Project Name

neican-editor

## Artifact Type

OpenClaw sub-agent workspace

## Development Repository

`/home/ai/projects/openclaw-apps/neican-editor-dev`

This is the only place Codex should edit project source during normal development.

## Runtime Workspace

`~/.openclaw/workspace-neican-editor`

Codex must not directly edit this runtime workspace.

## Created From Template

Yes

## Template Source

`/home/ai/projects/openclaw-app-template`

## Deployable Source Path

`openclaw/agent/`

## Runtime Target

`~/.openclaw/workspace-neican-editor`

## Skill Name

Not applicable as the primary artifact. The workspace contains agent-local Skills under `openclaw/agent/skills/`.

## Agent Name

neican-editor

## Key Files

- `docs/project_spec.md`
- `docs/openclaw-contract.md`
- `docs/test_plan.md`
- `docs/decision_log.md`
- `docs/project_manifest.md`
- `docs/runtime_migration_report.md`
- `docs/runtime-workspace-docs/`
- `openclaw/agent/AGENTS.md`
- `openclaw/agent/IDENTITY.md`
- `openclaw/agent/SOUL.md`
- `openclaw/agent/USER.md`
- `openclaw/agent/TOOLS.md`
- `openclaw/agent/HEARTBEAT.md`
- `openclaw/agent/config/`
- `openclaw/agent/db/schema.sql`
- `openclaw/agent/docs/`
- `openclaw/agent/flows/`
- `openclaw/agent/hugo-site/`
- `openclaw/agent/memory-wiki/`
- `openclaw/agent/sandbox-fetcher/`
- `openclaw/agent/schemas/`
- `openclaw/agent/scripts/`
- `openclaw/agent/skills/`
- `openclaw/agent/tests/`
- `scripts/deploy-agent.sh`
- `scripts/validate.sh`

## Validation Command

```bash
bash scripts/validate.sh
```

## Deployment Command

Deployment is not automatic. Deploy only after explicit user request:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

## Manual Runtime Test Command

To be confirmed.

No OpenClaw CLI runtime test command is currently documented. Do not invent one.

## Migration Summary

Runtime workspace contents were migrated from `~/.openclaw/workspace-neican-editor` into `openclaw/agent/` with policy exclusions for secrets, logs, caches, `.env`, credentials, and `.git` directories.

Runtime development docs were copied into `docs/runtime-workspace-docs/`.

Unresolved migration conflicts are recorded in `docs/runtime_migration_report.md`.

## Development Notes

- The migrated project implements a neican.ai AI industry knowledge engine.
- The first priority is preserving the development/runtime boundary.
- The current product priority is MVP Quality Gate Sprint 01: AI relevance, event dedupe, source trust, entity quality, public metadata hiding, valid insight dates, Topic Hub structure, and internal link integrity.
- Source trust is configured in `openclaw/agent/config/source_trust.yaml`.
- Entity allowlist/suppression policy is configured in `openclaw/agent/config/entity_allowlist.yaml`.
- The five root agent identity conflicts were reviewed and merged. The next likely development step is deployment readiness review after validation and packaging hygiene checks pass.
- Validation must use `bash scripts/validate.sh`.
- OpenClaw CLI commands must not be invented.
