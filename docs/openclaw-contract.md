# OpenClaw Contract: neican-editor

## Artifact Type

OpenClaw sub-agent workspace.

The deployable runtime package is `openclaw/agent/` from the development repository. This project is not a standalone OpenClaw Skill project, although the sub-agent workspace may contain agent-local Skills under `openclaw/agent/skills/`.

## Development Repository Boundary

Development happens in:

```text
/home/ai/projects/openclaw-apps/neican-editor-dev
```

Codex must make source changes in this development repository. The repository was created from:

```text
/home/ai/projects/openclaw-app-template
```

## Runtime Boundary

The OpenClaw runtime workspace is:

```text
~/.openclaw/workspace-neican-editor
```

Codex must not directly edit, delete, move, or manually copy files into the runtime workspace. Runtime synchronization must happen only through the documented deployment command after explicit user approval.

## Source Paths

```text
docs/
openclaw/agent/
scripts/
```

Key deployable source path:

```text
openclaw/agent/
```

Key project document path:

```text
docs/
```

## Runtime Target Paths

```text
~/.openclaw/workspace-neican-editor
```

The source path `openclaw/agent/` maps to the runtime workspace only through:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

## Allowed File Changes

- Update `docs/` to improve project documentation, test plans, decision records, and manifests.
- Update `openclaw/agent/` to change the deployable sub-agent workspace.
- Update `scripts/validate.sh` only when validation requirements genuinely change.
- Update tests under `openclaw/agent/tests/` when behavior changes.

## Forbidden File Changes

- Do not directly edit `~/.openclaw/workspace-neican-editor`.
- Do not manually copy files into `~/.openclaw/`.
- Do not write secrets, API keys, cookies, SSH keys, tokens, credentials, logs, or caches into docs or deployable source.
- Do not overwrite migration conflicts without first reviewing the runtime and development versions.
- Do not treat generated Hugo output, caches, or logs as source unless a task explicitly requires it.

## Allowed Commands

```bash
bash scripts/validate.sh
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
git status
git diff
```

`AGENT_NAME=neican-editor bash scripts/deploy-agent.sh` is allowed only when the user explicitly requests deployment.

## Forbidden Commands and Actions

- Do not invent OpenClaw CLI commands, flags, subcommands, configuration keys, runtime tests, or file locations.
- Do not deploy unless explicitly requested.
- Do not claim validation passed unless the exact command was run.
- Do not run manual runtime validation unless the command is explicitly documented and requested.
- Do not use destructive file or git commands without explicit user approval.

## Validation Requirements

Required static validation:

```bash
bash scripts/validate.sh
```

Expected result:

```text
Validation passed.
```

Static validation includes the local tests wired into `scripts/validate.sh`, including MVP quality gates for AI relevance, daily brief dedupe, public metadata hiding behavior, valid insight dates, Topic Hub generation, and Hugo internal link checking.

When requested, run:

```bash
git status
```

Any additional local functional tests must be explicitly selected from existing scripts/tests and reported by exact command. Do not silently redefine validation.

## Deployment Requirements

Deployment is not part of normal documentation or development tasks.

When the user explicitly asks to deploy, use only:

```bash
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

After deployment, runtime validation still requires an exact command to be defined. No OpenClaw CLI runtime test is currently specified.

## Manual Runtime Test Command

To be confirmed.

No OpenClaw CLI command is documented as a manual runtime test yet.

## Open Questions

- What exact runtime validation command should be used after deployment?
- Should local functional validation include `pytest openclaw/agent/tests` or specific script-level commands?
- Should migrated runtime identity conflicts replace the initialized development identity files?
- Should deploy approval require a generated public-site link-check artifact, or is the current build-time link-check failure sufficient?
