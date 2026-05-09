# Test Plan: neican-editor

## Static Validation

- Command: `bash scripts/validate.sh`
- Expected result: validation passes and required project files exist.
- Required before reporting any documentation or development task as ready.

The validation suite must cover the MVP Quality Gate Sprint 01 checks added after `docs/mvp反馈.md`:

- Low AI relevance raw items are ignored before event creation.
- Daily brief generation dedupes by event ID, source URL, and normalized title.
- Entity registry/profile generation assigns `entity_role` and `entity_quality`, and public entity export suppresses source media/noise/context entities.
- Source trust rules block weak-source high-risk A-grade candidates from automatic A-grade publishing.
- Entity allowlist promotes approved core organizations and infrastructure entities to public export eligibility.
- Existing generated Hugo content can be backfilled through quality gates: noisy entity pages are removed, daily briefs are filtered/deduped, weak-source noisy insights are removed, and Hugo link checking passes.
- Insight generation writes a valid non-zero date and thesis-oriented sections.
- Topic generation writes Topic Hub header sections.
- Hugo build checks internal links after a successful build.
- Public templates do not render internal workflow metadata such as `draft`, `needs_review`, `event_id`, or `generated_by`.

## Local Functional Validation

No local functional validation command is mandatory yet.

Candidate tests from the migrated workspace include Python tests under `openclaw/agent/tests/`, but this document does not promote them to required validation until dependencies and expected runtime setup are confirmed.

- Test: To be confirmed.
- Steps: To be confirmed.
- Expected result: To be confirmed.

## OpenClaw Runtime Validation

- Manual runtime test command: To be confirmed.
- Expected result: To be confirmed.

Runtime validation is allowed only after deployment and only after the exact command is documented. Do not invent OpenClaw CLI commands.

## Manual Task Tests

### Test: Development Repository Boundary

- Given the development repository `/home/ai/projects/openclaw-apps/neican-editor-dev`, when Codex updates docs or source files, then changes are made inside that repository.
- Given the runtime workspace `~/.openclaw/workspace-neican-editor`, when Codex is asked to change agent behavior, then it does not directly edit the runtime workspace.

### Test: Deployment Boundary

- Given completed source changes, when the user has not requested deployment, then Codex does not run `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.
- Given the user explicitly requests deployment, when deployment is performed, then the only documented deployment command is `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.

### Test: Documentation Completeness

- Given a future coding agent starts from the docs, when it reads `docs/project_spec.md` and `docs/openclaw-contract.md`, then it can identify project purpose, artifact type, development repository, runtime workspace, validation command, deployment command, and forbidden OpenClaw command invention.

### Test: Knowledge Engine Behavior

- Given configured source input and valid scripts, when ingestion and modeling workflows are run through approved project commands, then raw items, events, decisions, Memory Wiki assets, and Hugo content are produced according to the migrated project docs and schemas.
- Given uncertain or incomplete source material, when content or knowledge assets are generated, then uncertainty is marked rather than invented.
- Given generic finance, transport, macro, social, or entertainment items without direct AI relevance, when event modeling runs, then the item is ignored and cannot contaminate daily briefs, timelines, entities, or topics.
- Given duplicate event records, when daily brief generation runs, then the same event/source/title appears only once.
- Given events mention both core AI actors and source/context/noise entities, when entity product generation runs, then only approved core entities get public pages.
- Given public Hugo output, when pages are rendered, then internal workflow states remain in front matter or audit data and are not displayed as user-facing copy.

## Regression Checklist

- [ ] Project documents are complete enough for another coding agent.
- [ ] Artifact type is clearly `OpenClaw sub-agent workspace`.
- [ ] `/home/ai/projects/openclaw-apps/neican-editor-dev` is documented as the development repository.
- [ ] `~/.openclaw/workspace-neican-editor` is documented as the runtime workspace.
- [ ] Docs say Codex must not directly edit the runtime workspace.
- [ ] Deployment command is exactly `AGENT_NAME=neican-editor bash scripts/deploy-agent.sh`.
- [ ] Validation command is exactly `bash scripts/validate.sh`.
- [ ] OpenClaw CLI commands are not invented.
- [ ] No secrets, logs, caches, `.env`, credentials, or `.git` content are required for validation.
- [ ] Assumptions and open questions are separated from confirmed facts.
- [ ] AI relevance, dedupe, public-field hiding, valid insight dates, Topic Hub headers, and internal link checks are validated by tests.
