# neican-editor Development Repository

This repository is the source-controlled development workspace for the OpenClaw sub-agent `neican-editor`, the neican.ai AI industry knowledge engine.

The development repository is separate from the OpenClaw runtime workspace:

```text
/home/ai/projects/openclaw-apps/neican-editor-dev
~/.openclaw/workspace-neican-editor
```

Work happens in this repository. Do not directly edit, copy, move, or delete files under `~/.openclaw/workspace-neican-editor`.

## Artifact

Primary artifact: OpenClaw sub-agent workspace.

Deployable source package:

```text
openclaw/agent/
```

The top-level `openclaw/skill/` directory is inactive template residue for this agent-only project and is not the deployable artifact.

## Validate

Run the default validation command before reporting readiness:

```bash
bash scripts/validate.sh
```

This checks the required OpenClaw project files and runs the agent regression suite plus release gate tests.

## Deploy

Deployment is not automatic. Deploy only after the user explicitly requests it:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

The deployment script syncs `openclaw/agent/` to `~/.openclaw/workspace-neican-editor`, creates a timestamped backup when the target already exists and is non-empty, and excludes generated/runtime state such as logs, caches, SQLite WAL/SHM files, and Hugo build output.

## Important Files

- `docs/project_spec.md` — project goal, artifact type, capabilities, non-goals, and success criteria.
- `docs/openclaw-contract.md` — development/runtime boundary and allowed commands.
- `docs/deploy_manifest.md` — deployment package, exclusions, backup rule, rollback, and deployment record.
- `docs/test_plan.md` — validation expectations and regression checklist.
- `docs/decision_log.md` — design decisions and assumptions.
- `docs/handoff.md` — current continuation notes.
- `openclaw/agent/` — deployable sub-agent workspace source.
- `scripts/validate.sh` — required validation command.
- `scripts/deploy-agent.sh` — only approved runtime sync command after explicit deployment approval.
