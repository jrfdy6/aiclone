# OpenClaw Cron Runtime Classification Matrix

Generated: `2026-03-31`

This matrix completes `OCR-002` by classifying every live OpenClaw cron job by:
- current runtime
- recommended runtime
- scope in the future operating system
- reasoning requirement
- aggregate cost pressure
- why the recommendation makes sense

## Decision Categories

- `keep in OpenClaw`
  - the job depends on active session context, judgment, or synthesis that is still best handled inside the OpenClaw runner
- `keep in OpenClaw but refactor`
  - the job still needs model reasoning, but deterministic helpers should do more of the file/report/write work
- `candidate for launchd`
  - the job is local, file-heavy, deterministic, or machine-dependent and should move to a local scheduler/script lane
- `candidate for Railway`
  - the job is mostly hosted API/status work and does not need local filesystem state
- `disable/replace`
  - the job is redundant or should be merged into another cleaner job

## Matrix

| Job | Current Runtime | Recommended Runtime | Scope | Reasoning Need | Aggregate Cost | Why |
| --- | --- | --- | --- | --- | --- | --- |
| Oracle Ledger | OpenClaw agent-turn | keep in OpenClaw | `shared_ops` | High | Medium | It reads active Control UI context and makes pruning decisions against live session history. That is session-aware judgment, not just scripting. |
| GitHub Backup | OpenClaw agent-turn | candidate for `launchd` | `global` | Low | Low | The real work is a deterministic archive + checksum script. OpenClaw is not buying much here beyond a summary. |
| Nightly Self-Improvement | OpenClaw agent-turn | keep in OpenClaw | `shared_ops` | High | Low-Medium | It synthesizes a day of automation outcomes into recommendations. That is operator judgment, not a file copy task. |
| Morning Daily Brief | OpenClaw agent-turn | keep in OpenClaw but refactor | `shared_ops` | High | Medium | The brief itself is synthesis, but signal collection, Tavily fetches, and append-only writes should be handled more deterministically. |
| Rolling Docs | OpenClaw agent-turn | keep in OpenClaw but refactor | `shared_ops` | Medium-High | Medium | It needs judgment about drift across docs, but the current freeform edit path is brittle and already failing. Snapshotting and log writes should be scripted. |
| Daily Memory Flush | OpenClaw agent-turn | keep in OpenClaw but refactor | `shared_ops` | High | Medium | Selecting durable lessons and summarizing the day is reasoning-heavy, but append-only log writing should be helper-driven. |
| Weekly Backup | OpenClaw agent-turn | candidate for `launchd` | `global` | Low | Very Low | It copies key files and records checksums. That is local deterministic backup work. |
| Progress Pulse | OpenClaw agent-turn | keep in OpenClaw but refactor | `shared_ops` | Medium-High | High | It reads live chat state and summarizes blockers, but at every 30 minutes it creates the highest recurring model pressure and currently fails on brittle writes. |
| Memory Archive Sweep | OpenClaw agent-turn | candidate for `launchd` | `shared_ops` | Low | Very Low | File moves, retention windows, manifests, and checksums are deterministic local filesystem work. |
| Memory Health Check | OpenClaw agent-turn | candidate for `launchd` | `shared_ops` | Low-Medium | Low | Most of the job already relies on helper scripts. The model is mostly wrapping a report around deterministic checks. |
| Context Guard | OpenClaw agent-turn | keep in OpenClaw | `shared_ops` | Medium | Medium | It is tied to active session context and webchat delivery. The runtime choice is justified, but delivery integrity is currently broken. |
| Dream Cycle | OpenClaw agent-turn | keep in OpenClaw | `shared_ops` | High | Medium | It rewrites the persistent operator snapshot from multiple memory/report sources. That is one of the strongest cases for model synthesis. |
| Service Status Monitor | OpenClaw agent-turn | disable/replace | `global` | Low | Low | It overlaps heavily with `Railway & GitHub API Monitor`. Keep one hosted monitor lane, not two near-duplicates. |
| Railway & GitHub API Monitor | OpenClaw agent-turn | candidate for `Railway` | `global` | Low | Very Low | This is hosted reachability work and does not need local filesystem state or OpenClaw session context. |

## Summary By Recommendation

- `keep in OpenClaw`
  - Oracle Ledger
  - Nightly Self-Improvement
  - Context Guard
  - Dream Cycle

- `keep in OpenClaw but refactor`
  - Morning Daily Brief
  - Rolling Docs
  - Daily Memory Flush
  - Progress Pulse

- `candidate for launchd`
  - GitHub Backup
  - Weekly Backup
  - Memory Archive Sweep
  - Memory Health Check

- `candidate for Railway`
  - Railway & GitHub API Monitor

- `disable/replace`
  - Service Status Monitor

## Scope Summary

- `shared_ops`
  - Oracle Ledger
  - Nightly Self-Improvement
  - Morning Daily Brief
  - Rolling Docs
  - Daily Memory Flush
  - Progress Pulse
  - Memory Archive Sweep
  - Memory Health Check
  - Context Guard
  - Dream Cycle

- `global`
  - GitHub Backup
  - Weekly Backup
  - Service Status Monitor
  - Railway & GitHub API Monitor

- `workspace`
  - none yet

Current cron is still monolithic. No existing job is truly workspace-routed yet.

## Immediate Consequences

1. Do not try to scale all current jobs under one OpenClaw agent-turn model.
2. The first migration targets should be:
   - GitHub Backup
   - Weekly Backup
   - Memory Archive Sweep
   - Memory Health Check
   - Service Status Monitor / Railway & GitHub API Monitor consolidation
3. The first OpenClaw jobs to refactor, not migrate, should be:
   - Progress Pulse
   - Rolling Docs
   - Morning Daily Brief
   - Daily Memory Flush
4. `Context Guard` should stay in OpenClaw for now, but delivery integrity has to be fixed before relying on it as a guardrail.

## Recommended Next Order

1. Phase 2: real automation truth + run ledger
2. Phase 3: delivery hygiene, especially `Context Guard`
3. Phase 4: deterministic refactor of the four mixed jobs
4. Phase 5: move low-judgment local jobs to `launchd` and consolidate hosted monitor work under one Railway-facing monitor
