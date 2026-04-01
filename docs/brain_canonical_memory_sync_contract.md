# Brain Canonical Memory Sync Contract

This document defines how reviewed Brain signal becomes real local canonical memory.

## 1. Why This Exists

The Brain UI can review and route signal from the persona queue.

But the deployed API should not pretend it can directly mutate local files like:
- `memory/persistent_state.md`
- `memory/LEARNINGS.md`
- `memory/codex_session_handoff.jsonl`

So canonical-memory routing happens in two steps:

1. the Brain UI queues canonical-memory targets into persona-delta metadata
2. a local sync worker drains that queue into the real files

## 2. Queue Shape

Queued route entries live in:
- `persona_deltas.metadata.pending_canonical_memory_routes`

Each queued route may target one or more of:
- `persistent_state`
- `learnings`
- `chronicle`

## 3. Local Sync Worker

The local worker is:
- [brain_canonical_memory_sync.py](/Users/neo/.openclaw/workspace/scripts/brain_canonical_memory_sync.py)

It should:
- fetch persona deltas from the live backend API
- find queued canonical-memory routes
- append durable content into the correct local memory files
- write a sync report
- clear only the processed queue items
- leave a history trail in persona-delta metadata

## 4. File Writes

### `persistent_state`

Use for:
- current durable system truth
- portfolio state
- stable operating constraints

### `LEARNINGS`

Use for:
- lessons from execution
- workflow lessons
- judgment improvements that should persist

### `chronicle`

Use for:
- recording the promotion event in the Codex/OpenClaw shared memory stream
- preserving cross-surface awareness of what Brain promoted

## 5. Reports

The worker writes its latest reports to:
- `memory/reports/brain_canonical_memory_sync_latest.json`
- `memory/reports/brain_canonical_memory_sync_latest.md`

## 6. Scheduling

The local schedule is:
- [com.neo.brain_canonical_memory_sync.plist](/Users/neo/Library/LaunchAgents/com.neo.brain_canonical_memory_sync.plist)

This keeps Brain review connected to the real local memory loop.

## 7. Design Rule

Canonical-memory routes are local-memory intents, not remote-file writes.

That distinction is required to keep the architecture honest:
- Brain UI can route
- backend API can persist queue state
- local worker owns real file mutation

## 8. Result

The full path becomes:

`reviewed Brain signal -> queued canonical-memory route -> local sync worker -> memory files -> briefs / standups / crons`
