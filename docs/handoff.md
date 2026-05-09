# Handoff

## Current Status

`neican-editor-dev` is an OpenClaw sub-agent development repository for the neican.ai AI industry knowledge engine.

The primary deployable artifact is:

```text
openclaw/agent/
```

The runtime target is:

```text
~/.openclaw/workspace-neican-editor
```

Do not edit the runtime workspace directly. Deployment is allowed only after explicit user approval.

## Latest Iteration

The delivery-audit follow-up focused on release gate convergence:

- Root `README.md` now describes the actual agent-only project instead of the generic template workflow.
- `scripts/validate.sh` runs the agent pytest suite and release gate tests.
- `scripts/deploy-agent.sh` excludes generated/runtime state when syncing the agent workspace.
- `docs/project_manifest.md` no longer points at already-resolved identity conflicts as the next step.
- `docs/deploy_log.md` exists as the deployment record target.

## Validation

Default validation:

```bash
bash scripts/validate.sh
```

The validation command is expected to check required files and run:

```bash
pytest openclaw/agent/tests tests
```

## Deployment

Only approved deployment command:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

The deployment script uses `rsync --delete` and excludes caches, logs, SQLite WAL/SHM files, Hugo generated output, and Hugo build locks. Because delete sync can remove target-only files, the user must explicitly approve deployment.

## Open Questions

- What exact OpenClaw runtime validation command should be used after deployment?
- Should `openclaw/agent/db/neican.sqlite` remain deployable migrated state, or should runtime setup regenerate it from `db/schema.sql`?
- Should local functional validation eventually include a Hugo build command in addition to pytest?

## Recommended Next Step

Run a fresh delivery audit after validation passes. If the audit is `PASS` or `PASS_WITH_WARNINGS`, ask the user whether to deploy.
