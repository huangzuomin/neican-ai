---
name: neican_editor_inactive_skill_template
description: Do not use; this repository is initialized as an OpenClaw sub-agent project, not a Skill project.
---

# Inactive Skill Template

## When to use

Do not use this Skill in normal work. The active artifact for this repository is the `neican-editor` sub-agent workspace under `openclaw/agent/`.

This file remains only because the standard template includes a Skill package and the static validator checks `SKILL.md` when it exists.

## Inputs

No Skill inputs are defined for this agent-only initialization.

## Workflow

1. Use `openclaw/agent/` as the deployable package for this project.
2. Update the project contract before turning this repository into a Skill or combined artifact.
3. Do not deploy this Skill file as a runtime deliverable unless the project scope changes.

## Output Standard

- Report that this Skill is inactive for the current project contract.
- Point maintainers to `docs/openclaw-contract.md` and `openclaw/agent/`.

## Safety

Do not execute shell commands built from raw user input.

Do not read files outside the declared workspace unless the user explicitly provides the path and the task requires it.

Do not expose secrets, credentials, cookies, SSH keys, tokens, or private config values.

## Validation

Validation for this project is:

```bash
bash scripts/validate.sh
```
