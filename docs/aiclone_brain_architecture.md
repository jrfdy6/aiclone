# AI Clone Brain Architecture

This document defines how the AI Clone brain should work across:
- Codex
- OpenClaw
- cron jobs
- standups
- PM board
- workspace agents
- external source intelligence like videos, screenshots, and transcripts

The goal is not just to store memory.

The goal is to make sure the system can:
- retrieve the right signal
- digest it correctly
- route it to the right place
- act on it without creating split-brain behavior

Brain must observe every active workspace, not only the public-facing `FEEZIE OS` lane. Workspaces return local state and execution proof to Brain; Brain returns digested context, standup decisions, PM work, and canonical-memory promotions through the shared exchange protocol.

`FEEZIE OS` is the direct, executive-facing public workspace. The actual portfolio executive standup remains `shared_ops`, because system health, PM truth, automation drift, memory sync, and cross-workspace routing need a neutral lane that is not also the public content workspace.

Reference:
- [brain_workspace_exchange_protocol.md](/Users/neo/.openclaw/workspace/docs/brain_workspace_exchange_protocol.md)

## 1. What The Brain Is

The brain is not one file and not one agent.

The brain is the operating pipeline that decides:
- what the system notices
- what the system keeps
- what the system promotes
- what becomes work
- what stays advisory
- what should shape identity, strategy, or execution

A generic `Brain Signal` is the review object for source, workspace, cron, Chronicle, PM, or meeting signal that is not automatically persona canon. Persona deltas remain a downstream identity lane, not the whole Brain substrate.

## 2. Brain Layers

### Layer A: Intake

Current intake lanes:
- Codex live work
- OpenClaw live work
- context pruning / flush cycles
- cron outputs
- meeting transcripts
- workspace execution artifacts
- external source intelligence

External source intelligence includes:
- video transcripts
- screenshots
- notes from videos
- reference operating systems
- founder/operator strategy material

### Layer B: Digestion

Every meaningful input should be classified by:
- workspace relevance
- strategic horizon
- durability
- actionability
- identity relevance
- learning value
- confidence

Core digestion question:

`Is this signal operational, strategic, personal, or merely interesting?`

Default digestion outcome for a strong signal:
- promote to canonical memory
- bring it to the relevant standup
- only then turn it into PM work unless the action is already obvious

### Layer C: Canonical Memory

Current canonical memory lanes:
- [2026-03-31.md](/Users/neo/.openclaw/workspace/memory/2026-03-31.md)
- [LEARNINGS.md](/Users/neo/.openclaw/workspace/memory/LEARNINGS.md)
- [cron-prune.md](/Users/neo/.openclaw/workspace/memory/cron-prune.md)
- [daily-briefs.md](/Users/neo/.openclaw/workspace/memory/daily-briefs.md)
- [persistent_state.md](/Users/neo/.openclaw/workspace/memory/persistent_state.md)
- [codex_session_handoff.jsonl](/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl)

The Brain UI can queue promotions into this layer, but the real writes should be done by the local sync worker:
- [brain_canonical_memory_sync_contract.md](/Users/neo/.openclaw/workspace/docs/brain_canonical_memory_sync_contract.md)

Workspace-local memory should stay inside the workspace lane:
- execution logs
- workspace briefings
- local dispatch artifacts
- workspace-specific standing context

### Layer D: Coordination

Coordination surfaces:
- brain-maintenance crons
- standups
- PM board

Rules:
- PM board is the task truth
- standups are the decision ritual
- crons are digestion and maintenance helpers

### Layer E: Execution

Execution hierarchy:
- `Neo` sees the whole system
- `Jean-Claude` manages execution
- `Yoda` protects the North Star
- workspace agents execute inside their own workspace only

Execution results must write back into canonical memory and PM truth.

## 3. Routing Rules

### Route to `persistent_state.md`

Use for:
- current system truth
- stable portfolio state
- active priorities
- current operating constraints

### Route to `LEARNINGS.md`

Use for:
- lessons from execution
- lessons from failures
- lessons from workflow design
- lessons that should improve future judgment

### Route to workspace-local memory

Use for:
- workspace-specific execution details
- local blockers
- local SOP outcomes
- local implementation context

### Route to PM board

Use for:
- concrete executable work
- blockers that require intervention
- next actions with ownership
- work that should move down the pipeline

Reference:
- [chronicle_pm_promotion_boundary.md](/Users/neo/.openclaw/workspace/docs/chronicle_pm_promotion_boundary.md)

### Route to standups

Use for:
- unresolved tradeoffs
- coordination decisions
- strategic interpretation
- promotion decisions

### Route to identity packs

Use only when the signal is durable enough to change how a lane should think.

That means:
- repeated evidence
- high-confidence owner intent
- clear strategic shift
- not one random inspiring source

## 4. Cron Intertwining

Crons should not become a second brain.

They should maintain and digest the brain.

### Context Guard / Progress Pulse
- read current memory + Chronicle + PM state
- surface blockers, drift, and context pressure
- do not invent new planning layers

### Morning Daily Brief
- summarize what matters now
- point at the most important next opportunity
- use canonical memory, not stale session assumptions

### Dream Cycle
- consolidate the day into compact durable state
- sharpen `persistent_state.md`
- identify durable themes and emerging direction

### Daily Memory Flush
- move small but durable learnings into `LEARNINGS.md`
- keep the daily log coherent

### Rolling Docs
- update docs only when enough stable evidence exists
- do not rewrite the operating system from one transient thought

### Meeting Watchdog / Post-Sync Dispatch / Accountability Sweep
- ensure coordination rituals happened
- ensure commitments became PM truth
- ensure work moved

## 5. External Source Intelligence

Videos, screenshots, transcripts, and outside operating examples should influence the system.

But they should not enter the system as raw truth.

They should move through a dedicated digestion lane first:
- raw source asset
- source-intelligence digest
- Chronicle / standup input
- promotion decision

Reference:
- [source_intelligence_contract.md](/Users/neo/.openclaw/workspace/docs/source_intelligence_contract.md)

## 6. FEEZIE OS Special Role

`FEEZIE OS` is not just another workspace.

It is the public-facing and identity-adjacent lane where:
- brand
- career
- distribution
- personal narrative
- public leverage

start to converge.

That means `FEEZIE OS` should be influenced by:
- Johnnie identity signal
- founder/operator system insights
- public-facing content and audience feedback
- long-term strategic inputs from Yoda

The filter should be:
- `Yoda` for direction
- `Jean-Claude` for operational translation
- `Neo` for system-level implications

## 7. Design Rules

1. No raw-source-to-PM shortcut.
2. No workspace should learn from outside signals without digestion.
3. No identity-pack changes from one weak signal.
4. No cron should behave like a separate planner.
5. No workspace agent should consume cross-workspace noise directly.
6. FEEZIE OS should be shaped carefully because it influences the broader AI-clone identity layer.

## 8. Recommended Future Flow

The future brain loop should be:

1. ingest Codex, OpenClaw, cron, and source-intelligence signal
2. classify by workspace, durability, and actionability
3. write Chronicle or source-intelligence digests
4. let crons consolidate durable truth
5. let standups decide promotions and PM work
6. let Jean-Claude manage execution
7. let workspace agents execute locally
8. write results back into the same memory loop

## 9. Practical Next Steps

1. Keep Codex Chronicle as the canonical bridge for live work.
2. Add a source-intelligence digest lane for videos, screenshots, and transcripts.
3. Feed source-intelligence digests into:
   - weekly review
   - Saturday vision sync
   - FEEZIE OS standups when relevant
4. Only promote source insights into workspace packs after standup review.
5. Keep FEEZIE OS direct under Jean-Claude until you are ready to define its dedicated workspace agent.

## Bottom Line

The AI Clone brain should be:

`intake -> digestion -> canonical memory -> cron consolidation -> standup decision -> PM truth -> workspace execution -> write-back`

That is the loop that will let the system stay coherent while still learning from new source material and supporting the future growth of FEEZIE OS.
