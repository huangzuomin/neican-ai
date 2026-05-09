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

## info-fetcher Route

neican-editor must not directly spawn or call info-fetcher. When it needs external information fetching, return a route signal to the main agent:

```text
需要抓取：<specific fetch task>
```

The main agent（璇玑）is responsible for dispatching info-fetcher and forwarding results back. Local scripts keep deterministic RSS work only:

- `scripts/fetch_sources.py` parses RSS feeds, deduplicates, writes `raw_items`, and records full-text needs in `info_fetch_requests`.
- `scripts/heartbeat_pipeline.py` prints pending `需要抓取：...` messages when queued requests exist.
- `scripts/info_fetch_requests.py` owns request enqueueing, pending route message formatting, and consuming structured results forwarded back to neican-editor.

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
