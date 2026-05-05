---
name: track-review
description: Automatically review candidate timeline tracks discovered from structured events and decide whether each candidate should be approved as a public track, merged into an existing track, watched for more evidence, or rejected as noise. Use when implementing or running candidate track promotion, timeline track governance, RSS-to-track workflows, or any task involving candidate_tracks / track_review_decisions.
---

# Track Review

## Overview

Use this skill to keep timeline tracks stable while still allowing the system to discover new lines from RSS-derived events. The skill acts as an automatic editor: it reviews evidence, compares candidates against existing public tracks, and emits a structured decision.

## Decision Contract

Return one of four decisions:

- `approved`: create or promote a new public timeline track.
- `merge`: fold the candidate into an existing public track.
- `watch`: keep the candidate private and wait for more evidence.
- `rejected`: mark as duplicate, noisy, too narrow, or not structurally meaningful.

Use this JSON shape for every decision:

```json
{
  "decision": "merge",
  "target_track": "ai-agents-enterprise",
  "proposed_title": "Agent 评测成为企业采购门槛",
  "reason": "候选线与既有 AI Agents 企业化主线高度重叠，应并入而不是新建。",
  "confidence": 0.82,
  "evidence_event_ids": [12, 18, 21]
}
```

## Review Rules

Approve a candidate only when it has:

- At least 5 strong events, or at least 3 events involving multiple high-signal entities.
- A title that describes a durable industry question, not a short-term keyword.
- Clear separation from existing public tracks.
- Enough explanatory value for a reader-facing timeline page.

Merge when:

- The candidate shares a dominant topic or entity with an existing track.
- Its evidence strengthens a current track rather than opening a distinct long-term line.
- A new public URL would fragment the reader map.

Watch when:

- The candidate has fewer than 3 events.
- Events come from one narrow source or one company only.
- The idea may become important but lacks enough recurrence.

Reject when:

- The candidate is a duplicate wording of an existing track.
- It is only a one-off launch, rumor, lawsuit detail, or SEO phrase.
- It lacks coherent entities, topics, or evidence events.

## Workflow

1. Read existing public tracks from `config/timeline_tracks.yaml`.
2. Read proposed candidates from `candidate_tracks`.
3. Compare candidate topics/entities against existing track match rules.
4. Decide using the Review Rules.
5. Write a row to `track_review_decisions`.
6. Update `candidate_tracks.status` to `approved`, `merged`, `watch`, or `rejected`.

## Guardrails

- Do not create public tracks directly from raw RSS text.
- Do not approve candidates with no evidence event IDs.
- Prefer `merge` over `approved` when reader navigation would become more fragmented.
- Keep decisions auditable: always include reason, confidence, target track when merging, and evidence event IDs.
