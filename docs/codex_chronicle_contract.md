# Codex Chronicle Contract

This document defines how Codex work should be preserved before context loss.

It exists so the system can retain high-signal knowledge from:
- terminal sessions
- Codex chat work
- local device-hosted jobs
- cross-workspace execution
- AI-clone identity and development work

## Core principle

Codex should not dump raw chat into memory.

Codex should write compact Chronicle chunks that preserve the highest-delta signal.

## Chat-Derived Opt-In Boundary

Chat-derived Chronicle signal may be preserved in Chronicle and surfaced in standup highlights.

That does not mean it should auto-promote into durable memory or PM.

Default rule:
- chat-derived signal stays visible for operator context
- automatic memory closeout is blocked unless there is explicit opt-in
- PM recommendations should come from curated/action-shaped signal, not raw chat residue

This keeps the Chronicle useful without turning the executive lane into a raw-chat spillway.

## Current canonical lane

For compatibility with the current OpenClaw brain jobs, the Codex Chronicle lives at:

- `/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl`

This file is already in use by the OpenClaw maintenance loop.

It should now be treated as the Codex Chronicle lane, not just a narrow end-of-task handoff lane.

## What the Chronicle should preserve

Each Chronicle chunk should capture the signal most likely to be lost if the Codex context window rolls over.

That includes:
- major decisions
- blockers
- completed outcomes
- failed outcomes
- project changes
- new ideas worth revisiting
- learning gained during implementation
- identity signal about Johnnie
- phrasing and voice signal
- mindset signal
- proposed follow-up work
- artifacts and files that matter later

## What the Chronicle should not be

It should not be:
- a raw chat dump
- a second PM board
- a replacement for persistent memory
- a replacement for standups
- a dumping ground for low-value chatter

## Write triggers

Chronicle writes should happen when one or more of these are true:

1. Codex context usage is approaching roughly `70%`.
2. A meaningful task or subtask completes.
3. A blocker changes what should happen next.
4. A project direction changes.
5. A useful learning appears that should survive the session.
6. A strong identity/voice/mindset signal appears that should inform the AI clone.
7. A local device-hosted job finishes with meaningful outcomes.
8. A standup is about to run and the current Codex session has unpromoted signal.

## Chronicle chunk schema

Each line should be one JSON object.

```json
{
  "schema_version": "codex_chronicle/v1",
  "entry_id": "uuid",
  "created_at": "2026-03-31T17:00:00Z",
  "source": "codex-cli",
  "author_agent": "neo",
  "workspace_key": "shared_ops",
  "scope": "shared_ops",
  "trigger": "context_threshold",
  "context_usage_pct": 72,
  "importance": "high",
  "summary": "Refined the OpenClaw and Codex memory loop so standups become the promotion layer.",
  "signal_types": [
    "decision",
    "learning",
    "identity",
    "project_update"
  ],
  "decisions": [
    "Treat Codex Chronicle as a periodic memory stream instead of a narrow handoff."
  ],
  "blockers": [],
  "project_updates": [
    "Standups should read Chronicle chunks and decide what to promote into durable memory."
  ],
  "learning_updates": [
    "Codex conversations contain higher-signal project and identity context than OpenClaw alone."
  ],
  "identity_signals": [
    "Johnnie wants the AI clone to preserve human-readable continuity about his growth and projects."
  ],
  "mindset_signals": [
    "Perfect memory matters because the system should tell the story back better than a human can."
  ],
  "phrase_signals": [],
  "outcomes": [
    "Defined Chronicle as the missing bridge between Codex work and durable memory."
  ],
  "follow_ups": [
    "Add Chronicle ingestion into standup preparation."
  ],
  "memory_promotions": [
    "Codex Chronicle is part of the canonical memory loop."
  ],
  "pm_candidates": [
    "Build standup prep from Chronicle plus automation state."
  ],
  "artifacts": [
    "/Users/neo/.openclaw/workspace/docs/codex_chronicle_contract.md"
  ],
  "tags": [
    "codex",
    "memory",
    "standups"
  ]
}
```

## Read order

The system should read sources in this order when trying to understand recent Codex work:

1. latest Codex Chronicle entries
2. canonical memory files
3. PM board current state
4. automation outcomes
5. raw session history only as fallback

## Relationship to persistent memory

Chronicle is not persistent memory by itself.

It is the staging lane that preserves signal until the system decides what becomes durable.

That promotion should happen through:
- standups
- daily brief synthesis
- dream cycle / oracle style consolidation
- deliberate memory promotion scripts

## Relationship to standups

Standups are the best reconciliation point.

Standups should read recent Chronicle chunks and decide:
- what belongs in durable memory
- what becomes PM work
- what becomes a follow-up
- what is complete and can simply be noted

That keeps the system from losing signal while also keeping durable memory cleaner than raw chat.

## Relationship to the AI clone

Chronicle exists for more than operations.

It should help preserve:
- how Johnnie talks
- what he is building
- how his thinking evolves
- what he learns
- what mindset shifts matter
- what the system should remember about him over time

That is necessary if the AI clone is supposed to function like a second brain.

## Initial implementation rule

Do not wait for perfect automation.

The first working rule should be:
- append Chronicle chunks when context nears `70%`
- append Chronicle chunks when major work completes
- have standups ingest those chunks before deciding memory promotions and PM updates

That is enough to preserve high signal without creating a second shadow system.

## Current command path

The first concrete implementation path is:

1. Periodic Codex sync into Chronicle

```bash
python3 /Users/neo/.openclaw/workspace/scripts/sync_codex_chronicle.py
```

2. Standup prep from Chronicle + canonical memory + automation state

```bash
python3 /Users/neo/.openclaw/workspace/scripts/build_standup_prep.py \
  --standup-kind executive_ops \
  --workspace-key shared_ops \
  --owner-agent jean-claude
```

3. Promotion into durable memory + PM recommendation file

```bash
python3 /Users/neo/.openclaw/workspace/scripts/promote_codex_chronicle.py \
  --prep-json /absolute/path/to/prep.json \
  --workspace-key shared_ops \
  --write-pm-recommendations
```
