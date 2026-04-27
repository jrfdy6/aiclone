---
title: "Cheap models, better systems"
draft_kind: owner_review
source_kind: feezie_queue
lane: ai
priority_lane: ai
publish_posture: approved
risk_level: low
role_alignment: role_anchored
source_path: workspaces/linkedin-content-os/drafts/queue_01.md
created_at: 2026-04-01T04:52:39+00:00
owner_decision: approve
owner_reviewed_at: 2026-04-19T18:53:49Z
owner_review_source: "PM card 2d6d367a-7ad8-4d7b-92f4-4a58098df574"
owner_review_notes: "Approved; package into scheduling lane as the next concrete release step."
scheduling_packet: workspaces/linkedin-content-os/docs/release_packets/feezie-001_schedule_packet_20260419.md
---

# Cheap models, better systems

## Why this draft exists
- Queue item: `FEEZIE-001`
- Lane: `ai`
- Why now: the AI Clone / Brain work is active and publicly legible.

## Proof anchors
- ``../../knowledge/persona/feeze/history/story_bank.md``
- ``../../knowledge/persona/feeze/history/initiatives.md``
- ``../../knowledge/persona/feeze/history/wins.md``

## First-pass draft

We restarted the AI Clone / Brain control plane on GPT-3.5 budgets. There was no promise of "GPT-X is coming," so reliability had to be engineered, not purchased.

That constraint forced us to type the entire retrieval layer. Proof, story, and example live in separate packets, every chunk cites an artifact, and JSON validation kills the run if the schema falls apart. It is the reason Brain, Ops, daily briefs, persona review, and long-form routing now share one workspace snapshot instead of five brittle prompts.

Cheap models also surfaced every lazy instruction. Context Guard and the restart harness require us to declare inputs, validation, and rollback paths before a token is generated. When a persona delta does not cite evidence or a long-form route hands us malformed JSON, the validator stops it before it touches the dashboards.

Working inside those constraints is what turned the system into an operating system, not a fragile demo. We debugged our instructions instead of blaming the model, we made outputs deterministic, and we kept proof packets attached so every response carries receipts.

So when somebody says "just wait until we get GPT-X," I ask the same question we used on ourselves: if your workflow collapses on a cheaper model, do you really have a workflow or just a demo?

## Owner notes
- Tighten the hook if needed.
- Keep this grounded in real proof, not abstraction.
- Do not publish without explicit owner approval.
