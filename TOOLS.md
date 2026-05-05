# TOOLS.md

## Tool Notes

This file documents how `neican-editor` should think about tools that are already available in the runtime environment.

This file does not grant tool access. It only documents how the agent should use tools that are already available in the runtime environment.

## Rules

- Do not invent tools.
- Do not invent command flags.
- Do not run destructive commands without explicit permission.
- Prefer documented scripts over ad-hoc shell commands.
- Do not claim runtime validation unless the exact documented runtime test command was actually run.

## Available Capabilities

The agent has access to these local Skills for domain-specific workflows:

- `skills/fetch_and_extract/` — delegated to sandbox-fetcher
- `skills/ingest_raw_item/` — raw item ingestion
- `skills/event_modeling/` — event, entity, topic, and claim modeling
- `skills/editorial_decision/` — A/B/C/D grading and review triggers
- `skills/content_generation/` — articles, briefs, and index content
- `skills/knowledge_asset_update/` — Memory Wiki asset maintenance
- `skills/hugo_export/` — Hugo content export
- `skills/deploy_and_notify/` — approved publish and notify

Use Skills only when the task matches their scope.

## Development Repository Commands

```bash
bash scripts/validate.sh
AGENT_NAME=neican-editor bash scripts/deploy-agent.sh
```

Deployment must only happen after the user explicitly requests it.

## Key Config Files

- `config/source_trust.yaml` — S/A/B/C source trust tiers
- `config/entity_allowlist.yaml` — approved and suppressed entities
- `config/editorial_rules.yaml` — editorial decision policy
- `config/risk_rules.yaml` — high-risk content routing
- `config/sources.yaml` — configured information sources
