# System Cohesion Contract

This file defines the intended end-to-end operating loop for the OpenClaw + Codex system.

It exists to prevent split-brain behavior across:
- heartbeat
- context pruning
- Codex handoff
- source intelligence
- persistent memory
- cron jobs
- PM board
- standups

## Core principle

There must be one canonical operating memory loop.

The system should not create parallel planning layers that compete with each other.

## Intended operating loop

1. Live work happens in either:
   - Codex chat
   - OpenClaw chat

2. External source material may also enter the system.
   - videos
   - screenshots
   - transcripts
   - reference operating systems
   - those sources should enter through a source-intelligence digestion lane first
   - they are not canonical memory by default

3. Those live work surfaces must distill into canonical memory.
   - OpenClaw-native work can use context flush / pruning directly.
   - Codex-native work must write high-signal chunks into the Codex Chronicle lane at `memory/codex_session_handoff.jsonl`.
   - Those chunks should preserve high-delta signal without dumping raw chat.

4. Canonical memory lanes are:
   - `memory/YYYY-MM-DD.md`
   - `memory/LEARNINGS.md`
   - `memory/cron-prune.md`
   - `memory/daily-briefs.md`
   - `memory/persistent_state.md`
   - `memory/codex_session_handoff.jsonl` (`Codex Chronicle`)

5. Brain-maintenance cron jobs consume those canonical lanes.
   - `Context Guard`
   - `Progress Pulse`
   - `Morning Daily Brief`
   - `Oracle Ledger`
   - `Dream Cycle`
   - `Daily Memory Flush`
   - `Rolling Docs`

6. Those cron jobs should:
   - summarize what happened
   - update durable memory
   - identify blockers
   - identify next-step candidates
   - avoid duplicating each other

7. PM board and standups consume canonical memory plus automation output.
   - PM board is the source of truth for work state.
   - Standups are the coordination ritual that reads PM truth plus recent automation output.
   - Meetings should run independently of Johnnie once configured.
   - Standups should also read the latest Codex Chronicle chunks and decide:
     - what gets promoted into durable memory
     - what becomes PM updates
     - what becomes next-step assignments
   - Strategic standups may also read source-intelligence digests when those sources should shape future design or direction.
   - Every meaningful meeting should leave a transcript artifact.
   - Every meaningful meeting should have a follow-on dispatch and accountability path.

8. Agents use that truth to drive next action.
   - `Neo` = all-system operator
   - `Jean-Claude` = workspace operations president
   - `Yoda` = strategic overlay / direction

9. Execution results must write back into the same loop.
   - Bounded Codex work should update the same PM card that started it.
   - Results should append Chronicle.
   - Durable learnings and persistent-state signal should be promoted into canonical memory.
   - Standups and OpenClaw brain jobs should then react to those writes on the next cycle.

## Heartbeat contract

Heartbeat is not a daily brief.

Heartbeat should:
- wake the system
- perform a lightweight watchdog check
- update `memory/heartbeat-state.json`
- stay quiet with `HEARTBEAT_OK` when calm
- surface blockers only when needed

Heartbeat should not:
- replace cron jobs
- duplicate daily brief content
- invent new planning lanes

## Codex vs OpenClaw contract

`Codex` is now a primary live work surface.

That means OpenClaw can no longer assume its own session history is the only or primary truth source.

The bridge is the Codex Chronicle:
- `memory/codex_session_handoff.jsonl`

Rules:
- Codex work that changes plans, decisions, blockers, outcomes, identity signal, phrasing signal, learning signal, or project state should be reflected there.
- Codex Chronicle entries should be written periodically before context loss, especially when a Codex context window approaches roughly `70%` usage.
- OpenClaw brain jobs should read that bridge before stale chat-session assumptions.
- Runner ledgers are audit trails, not canonical memory.

## PM board contract

PM board should reflect:
- what was proposed
- what was started
- what stalled
- what was completed
- what new work became necessary after earlier work finished

Those changes should be grounded in:
- canonical memory
- automation events
- standup decisions

PM board should not depend on ad hoc memory from one agent session.

## Standup contract

Standups should read:
- PM board truth
- latest canonical memory
- latest automation findings
- latest Codex Chronicle chunks
- recent meeting transcripts when available

Standups should operate as real meetings, not synthetic summaries.

That means:
- minimum three rounds
- status
- analysis
- commitments / resolution
- real participants with separate workspace context
- PM board first, artifacts second

Standups should produce:
- transcript
- updated commitments
- blockers
- needs
- decisions
- owners
- PM updates
- memory promotions when Chronicle signal should become durable memory

Around standups there should be:
- watchdogs that catch missing output
- a post-sync dispatch step that turns commitments into PM work
- an accountability sweep that ensures those commitments actually move

## External source intelligence contract

Source intelligence is upstream of canonical memory.

That means:
- raw videos
- screenshots
- transcripts
- outside operating examples

should not write directly into PM truth or durable memory.

They should first become digests, then standup inputs, then promotion candidates.

Reference:
- `/Users/neo/.openclaw/workspace/docs/source_intelligence_contract.md`

## Current alignment status

### Aligned now
- Heartbeat writes to `memory/heartbeat-state.json`.
- `memory/codex_session_handoff.jsonl` exists as canonical bridge input.
- OpenClaw brain-job prompts were updated to read Codex handoff first.
- Cron rehab cleaned up delivery, mismatch visibility, and contract drift.

### Partially aligned
- Codex Chronicle exists in the current bridge lane, but it is not yet guaranteed to update automatically for every important Codex outcome or context-threshold event.
- PM board and standups exist in backend services, but they are not yet fully consuming canonical Codex/OpenClaw memory as one unified truth stream.
- Standups and PM board are still not fully workspace-scoped in the live operating model.
- Standup transcripts exist, but the meeting orchestration is still more synthesized than truly autonomous.
- External source intelligence is conceptually defined, but its digest/promotion lane is not automated yet.

### Not fully aligned yet
- Automatic promotion from canonical memory into PM cards is not complete.
- Automatic standup preparation from canonical memory + automation state is not complete.
- Codex and OpenClaw context-pruning behavior is not yet a fully unified, always-on loop.
- Meeting watchdogs, post-sync dispatch, and accountability sweep are not fully implemented yet.

## Non-negotiable design rules

1. No parallel truth systems.
2. Codex must feed canonical memory before context loss.
3. OpenClaw maintenance jobs must read canonical memory.
4. PM board must be downstream of canonical memory, not side-channel memory.
5. Standups must be downstream of PM + canonical memory + automation state.
6. Agents may interpret and prioritize, but they must not invent a separate shadow backlog.
7. Meetings must not become vanity theater without follow-through.

## Required convergence work

1. Keep heartbeat healthy and quiet.
2. Keep Codex Chronicle canonical and easy to append.
3. Ensure `Dream Cycle`, `Oracle Ledger`, `Morning Daily Brief`, and `Progress Pulse` consistently read handoff + memory files.
4. Feed PM board updates from canonical memory and automation findings.
5. Feed standup prep from PM board + automation findings + canonical memory, including Chronicle chunks.
6. Make workspace scoping explicit in PM cards, briefs, and standups.
7. Add meeting watchdog, dispatch, and accountability layers.
8. Add a source-intelligence digest layer so future videos and screenshots can shape workspaces safely.

## Current implementation hooks

- Codex Chronicle sync:
  - `python3 /Users/neo/.openclaw/workspace/scripts/sync_codex_chronicle.py`
- Standup prep generation:
  - `python3 /Users/neo/.openclaw/workspace/scripts/build_standup_prep.py --standup-kind executive_ops --workspace-key shared_ops --owner-agent jean-claude`
- Chronicle promotion:
  - `python3 /Users/neo/.openclaw/workspace/scripts/promote_codex_chronicle.py --prep-json <prep.json> --workspace-key shared_ops --write-pm-recommendations`

## Related contract

- `/Users/neo/.openclaw/workspace/docs/autonomous_meeting_system_contract.md`
- `/Users/neo/.openclaw/workspace/docs/source_intelligence_contract.md`
- `/Users/neo/.openclaw/workspace/docs/aiclone_brain_architecture.md`
- `/Users/neo/.openclaw/workspace/docs/end_to_end_memory_convergence_implementation_plan.md`

## Bottom line

The intended system is:

live work + source intelligence -> canonical memory -> brain-maintenance cron jobs -> PM board / standups -> next actions

That is the loop that must stay coherent.
