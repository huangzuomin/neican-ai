# Runtime Migration Report

## Date

2026-05-05

## Source

`~/.openclaw/workspace-neican-editor`

## Target

`/home/ai/projects/openclaw-apps/neican-editor-dev`

## Agent Package Target

`openclaw/agent/`

## Docs Target

`docs/runtime-workspace-docs/`

## Copy Strategy

Runtime files were copied with `rsync --ignore-existing` so existing development repository files were not overwritten.

## Conflicts Not Overwritten

- `openclaw/agent/AGENTS.md`
- `openclaw/agent/IDENTITY.md`
- `openclaw/agent/SOUL.md`
- `openclaw/agent/TOOLS.md`
- `openclaw/agent/USER.md`

## Files Skipped By Policy

- `.env`
- `.git/`
- `.openclaw/`
- `.pytest_cache/`
- `__pycache__/`
- `logs/`
- `*.log`
- `.hugo_build.lock`
- `node_modules/`
- `.cache/`
- paths matching `*secret*`, `*credential*`, or `*token*`

## Removed From Target After Copy

These generated or tool/cache-like directories were removed from the development repository after the initial copy:

- `openclaw/agent/.superpowers/`
- `openclaw/agent/.tools/`
- `openclaw/agent/hugo-site/public/`
- `openclaw/agent/hugo-site/resources/`
- `openclaw/agent/memory/.dreams/`

## Validation

```text
Validating OpenClaw project...
Checking Skill package...
Checking agent workspace package...
Validation passed.
```
