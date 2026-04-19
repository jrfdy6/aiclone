# Brain Truth Lanes And Promotion Flow

This document explains the difference between:
- Brain signal
- persona canon
- canonical memory
- PM truth

It also explains how `Neo`, `Jean-Claude`, and `Yoda` should reason over source material before it becomes durable system state or work.

## 1. The Brain Signal Layer

Brain Signal is the upstream review object.

It exists so the system can review signal from:
- source intelligence
- workspace execution
- crons
- Chronicle
- standups
- PM write-back
- owner reactions

without forcing every item into `persona_deltas`.

Persona deltas are still valid when a signal affects identity, voice, stories, principles, or content posture. They are one downstream route from Brain Signal, not the root object for all system interpretation.

## 2. The Three Truth Lanes

### Persona canon

Persona canon is the identity and voice layer.

It exists so the system can remember:
- who Johnnie is
- how he talks
- what principles repeat
- what stories matter
- what content posture should stay consistent

Current canon targets include:
- `identity/claims.md`
- `identity/VOICE_PATTERNS.md`
- `identity/decision_principles.md`
- `prompts/content_pillars.md`
- `history/story_bank.md`

This is not the same thing as the whole system brain.

### Canonical memory

Canonical memory is the operating memory layer.

It exists so the system can remember:
- what is currently true
- what changed
- what was learned
- what the cron layer should digest
- what standups should read before deciding next steps

Current canonical memory files include:
- `memory/persistent_state.md`
- `memory/LEARNINGS.md`
- `memory/daily-briefs.md`
- `memory/cron-prune.md`
- `memory/dream_cycle_log.md`
- `memory/YYYY-MM-DD.md`
- `memory/codex_session_handoff.jsonl`

### PM truth

PM truth is the execution layer.

It exists so the system can track:
- what work exists
- who owns it
- what is blocked
- what is in progress
- what is done

This is the board and execution state, not the identity layer and not the memory layer.

## 3. Current Brain UI Reality

Today the Brain user-facing review flow is strongest for persona canon.

That means the Brain persona queue already supports:
- reviewing a persona delta
- saving your actual take
- choosing promotion fragments
- rerouting those fragments
- committing them into persona canon

That is why the current promotion interface feels real.

But it is still mostly a `persona canon` console, not yet a unified router for the whole system brain.

## 4. What A Persona Delta Is

A persona delta is a candidate change to persona understanding.

It usually comes from:
- long-form source intake
- belief and reaction capture
- workspace-originated persona saves
- Brain review work

The queue is for deciding:
- whether the signal is real
- what part of it is durable
- whether it belongs in persona canon at all

Common lifecycle states include:
- `brain_pending_review`
- `workspace_saved`
- `pending_promotion`
- `committed`
- `resolved`

## 5. Where Yoda, Neo, And Jean-Claude Fit

### Yoda

Yoda answers:

`What does this mean for direction?`

Yoda is the strategic filter.

He decides whether a source changes:
- long-horizon direction
- FEEZIE OS positioning
- brand/career trajectory
- what should be protected
- what should stay advisory instead of becoming urgency

### Neo

Neo answers:

`What does this change across the whole system?`

Neo is the all-system operator.

He should be in the executive conversation whenever a signal might affect:
- multiple workspaces
- portfolio priorities
- system-wide architecture
- shared operating standards
- what gets escalated versus ignored

Neo is not the day-to-day executor, but he is absolutely part of the decision conversation.

### Jean-Claude

Jean-Claude answers:

`What should we do with this operationally?`

Jean-Claude is the translator from strategic meaning into action.

He decides whether a signal becomes:
- a standup agenda item
- a PM update
- an SOP
- a workspace handoff
- a memory promotion
- a no-action advisory note

## 6. When That Conversation Happens

The executive conversation should happen in:
- executive standups
- weekly review
- Saturday vision sync for long-horizon strategy only
- any source-intelligence review that materially affects direction or the operating model

For strategic or system-shaping inputs, the default conversation should be:
- `Yoda` interprets meaning
- `Neo` judges system-wide implications
- `Jean-Claude` translates the outcome into operational form

That means Yoda should not be reasoning alone, and Neo should not be absent from these decisions.

## 7. Can One Source Route To Multiple Places

Yes.

One source may legitimately affect more than one lane.

For example:
- a transcript may improve persona voice
- the same transcript may change FEEZIE OS messaging
- the same transcript may create a PM task
- the same transcript may only belong in weekly review for now

The rule is not `one source -> one destination`.

The rule is:

`one source -> one executive interpretation -> one or more justified routes`

## 8. Routing Matrix

### Default route for a strong signal

The default should usually be:

- `canonical memory`
- plus `standup`

Reason:
- remember it first
- interpret it second
- execute it only when the meaning is clear

This default can be expanded when justified:
- add `persona canon` if the signal changes identity, voice, story, or worldview
- add `PM truth` if the next step is concrete and ownership is already clear

### Route to persona canon when
- the signal changes identity, voice, principles, stories, or content posture
- the signal is durable
- owner intent is clear

### Route to canonical memory when
- the signal changes current truth
- the system should remember it for crons, standups, and future sessions
- it is not just a one-off reaction

### Route to standup when
- the signal needs interpretation
- there is a tradeoff
- multiple workspaces might be affected
- direction needs discussion before execution

### Route to PM truth when
- there is a concrete executable next step
- ownership is clear
- the work should move now

Reference:
- [chronicle_pm_promotion_boundary.md](/Users/neo/.openclaw/workspace/docs/chronicle_pm_promotion_boundary.md)

## 8. FEEZIE OS Rule

`FEEZIE OS` is more identity-adjacent than the other workspaces.

That means it should receive more strategic attention from:
- `Yoda`
- `Neo`
- `Jean-Claude`

But it still should not bypass digestion.

Even when a source feels highly relevant to FEEZIE OS:
- Yoda should filter strategic meaning
- Neo should judge portfolio/system impact
- Jean-Claude should convert the outcome into operations

## 9. What Is Missing Today

The Brain UI does not yet expose one unified promotion console for all routes.

The current MVP should expose a triage layer that can send reviewed signal to:
- persona canon
- canonical memory queue
- standup queue
- PM queue

Important current constraint:
- PM and standup routes can be created immediately because they live in the API/database layer
- canonical memory routes should be queued for the local brain loop instead of pretending the remote API can directly mutate the local memory files

Reference:
- [brain_canonical_memory_sync_contract.md](/Users/neo/.openclaw/workspace/docs/brain_canonical_memory_sync_contract.md)

That is the clean next evolution of the Brain.

## 10. Practical Reading Rule

When reading the Brain:
- use the `Persona` tab to review identity-shaping candidate signal
- use `Docs` to read the system contracts and canonical memory files
- use standups to watch strategic and operational decisions form
- use the PM board to confirm what became real work
