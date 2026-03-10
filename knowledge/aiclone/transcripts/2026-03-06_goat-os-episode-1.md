---
title: Goat OS Bootcamp – Episode 1 (Bedrock)
source: YouTube live (https://www.youtube.com/live/jf9D4Oh7RwI)
received: 2026-03-05
raw_path: downloads/transcripts/jf9D4Oh7RwI.txt
tags: [ops, brain, lab, cron, onboarding]
---

## Summary
- Episode 1 is all about bootstrapping a fresh Goat OS agent: set SOUL/USER/Memory, light up Ops/Brain/Lab, and resist adding polish before the foundation is real.
- Ops requires SSE-driven Mission Control dashboards, cached telemetry, and immediate visibility into cron + session health.
- Brain focuses on the Daily Briefs flow (left history, right markdown renderer) fed exclusively by automations after the initial seed.
- Lab runs staging-only experiments, nightly self-improvement, and append-only build logs before anything hits production.

## Key Requirements / Directives
1. Stand up the four baseline crons (GitHub backups, overnight self-improvement, morning daily brief, rolling docs) with staging-first behavior and full audit logs.
2. Mirror the Goat OS UI structure: tabs for Ops/Brain/Lab, glassmorphic panes, neon module accents, and persistent bottom dock.
3. Document the org chart early (human → core agent → module chiefs → sub-agents) even if most roles are still “planned.”
4. Feed the agent ~10 minutes of fresh context daily so it keeps learning Feeze’s goals, tone, and workflows.

## Follow-ups / Tasks
- [ ] Wire Discord/Railway collectors so Ops → Mission Control reflects the same telemetry as the automations manifest.
- [ ] Finish Brain → Daily Briefs/Automations/Docs tabs using markdown+history pattern.
- [ ] Stand up Lab staging (port 8900) and hook nightly self-improvement logs into its cards.

## Notes
- Emphasis on “no mock data” once dashboards are live.
- All cron jobs must run in isolated sessions and write results to both Ops → Mission Control and Brain → Automations.
- Homework: keep sketching the org chart and narrate context to the agent daily.
