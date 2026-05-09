# Deploy Manifest

## Project

neican-editor

## Artifact Type

OpenClaw sub-agent workspace

## Development Repository

```text
/home/ai/projects/openclaw-apps/neican-editor-dev
```

## Source Package

```text
openclaw/agent/
```

## Runtime Target

```text
~/.openclaw/workspace-neican-editor
```

## Deployment Mode

```text
agent_workspace_sync
```

## Deployment Command

Deployment is allowed only after an explicit user request:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

Do not invent OpenClaw CLI commands. Do not manually copy files into `~/.openclaw/`.

## Pre-deployment Requirements

- Delivery audit must be PASS.
- If audit result is PASS_WITH_WARNINGS, the user must explicitly approve deployment.
- `bash scripts/validate.sh` must pass.
- Runtime target must be confirmed as `~/.openclaw/workspace-neican-editor`.
- Backup must be created before deployment.
- Migration conflicts recorded in `docs/runtime_migration_report.md` must be reviewed before deployment.
- Because the approved deployment script uses `rsync --delete`, the user must explicitly approve deployment knowing target files not present in `openclaw/agent/` may be removed.

## Files Allowed to Deploy

The deployable package is the contents of `openclaw/agent/`, including:

- `AGENTS.md`
- `IDENTITY.md`
- `SOUL.md`
- `USER.md`
- `TOOLS.md`
- `HEARTBEAT.md`
- `sandbox-fetcher/`
- `skills/`
- `docs/`
- `config/`
- `db/schema.sql`
- `flows/`
- `hugo-site/`
- `memory-wiki/`
- `schemas/`
- `scripts/`
- `tests/`
- `package.json`
- `requirements.txt`
- `vercel.json`

If additional files or directories are added under `openclaw/agent/`, they may be deployed only when they are intentional runtime workspace source files and do not match the forbidden list below.

## Files Never Deploy

- `.git/`
- `.env`
- `.env.*`
- `credentials/`
- `secrets/`
- `*.pem`
- `*.key`
- `node_modules/`
- `__pycache__/`
- `.pytest_cache/`
- `logs/`
- `*.log`
- `.hugo_build.lock`
- `hugo-site/public/`
- `hugo-site/resources/`
- `docs/` from the development repository root
- `src/`
- `tests/` from the development repository root
- `scripts/` from the development repository root
- `data/`
- `raw/`
- `tmp/`
- `cache/`
- `*.sqlite-wal`
- `*.sqlite-shm`

## Backup Rule

Before deployment, the approved deployment script must create a timestamped backup when the runtime target exists and is non-empty:

```text
~/.openclaw/workspace-neican-editor.backup.<timestamp>
```

## Deployment Strategy

Use the approved repository deployment script only:

- Source: `openclaw/agent/`
- Target: `~/.openclaw/workspace-neican-editor`
- Backup existing non-empty target before sync.
- Sync the source package into the runtime workspace.
- The current script uses delete sync behavior; target-only files may be removed.
- Do not directly edit, copy, move, or delete files under `~/.openclaw/`.

## Post-deployment Validation

```text
To be confirmed.
```

No exact OpenClaw runtime validation command is currently documented. Do not invent one. After deployment, report that runtime validation is not complete until an approved command is defined and run.

## Rollback

If deployment fails, restore from the backup created during this deployment:

```text
~/.openclaw/workspace-neican-editor.backup.<timestamp>
```

Rollback must preserve the failed deployment state long enough to inspect the cause unless the user explicitly requests immediate restoration.

## Deployment Record

Append deployment result to:

```text
docs/deploy_log.md
```

Each record should include:

- Timestamp.
- Source repository path.
- Source package.
- Runtime target.
- Deployment command used.
- Validation command result.
- Runtime validation result or reason not run.
- Backup path.
- Files or directories intentionally excluded.
- Operator notes.

## Open Questions

- What exact manual runtime validation command should be used after deployment?
- Should the deployment script keep `rsync --delete`, or should delete sync require a separate deployment mode?
- Should local functional validation include all tests under `openclaw/agent/tests/` in addition to `bash scripts/validate.sh`?
