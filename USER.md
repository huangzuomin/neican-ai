# USER.md

## User Context

The user is maintaining an existing OpenClaw sub-agent named `neican-editor`.

The development repository at `/home/ai/projects/openclaw-apps/neican-editor-dev` is the source for this agent. The active runtime workspace is `~/.openclaw/workspace-neican-editor`. The runtime workspace must not be edited directly — deployment uses `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.

The user expects `neican-editor` to behave like an AI industry intelligence editor, not a generic news aggregator. Public output should answer what changed, why it matters, why the source can be trusted, and where a reader should continue exploring.

Current product-quality priority: keep low AI relevance, duplicate events, noisy entities, weak-source high-risk claims, invalid dates, broken links, and internal workflow fields out of public pages.

Do not store secrets, credentials, private tokens, or temporary task notes here.
