---
name: dream-cycle
description: Roll the current day into a durable persistent-state snapshot, append the narrative to memory/dream_cycle_log.md, and surface follow-up actions. Use for the Dream Cycle cron.
---

# Dream Cycle Skill

## Inputs
- shared memory contract from `python3 /Users/neo/.openclaw/workspace/scripts/build_cron_memory_contract.py --workspace-key shared_ops --memory-path memory/persistent_state.md --memory-path memory/cron-prune.md --memory-path memory/doc-updates.md --memory-path memory/self-improvement.md --memory-path memory/daily-briefs.md --memory-path memory/{today}.md`
- today's daily log resolved to a concrete path such as `memory/2026-04-08.md`
- `memory/codex_session_handoff.jsonl`
- `memory/cron-prune.md`
- `memory/doc-updates.md`
- `memory/backup-log.md`
- latest `memory/reports/memory_health_*.md` resolved via `python3 /Users/neo/.openclaw/workspace/scripts/latest_matching_file.py --glob '/Users/neo/.openclaw/workspace/memory/reports/memory_health_*.md'`
- `memory/self-improvement.md`
- `memory/daily-briefs.md`
- heartbeat diagnostics from `python3 /Users/neo/.openclaw/workspace/scripts/heartbeat_report.py` when heartbeat freshness or Discord quality is relevant
- concrete recently modified files under `knowledge/` when new ingestions matter

## Workflow
1. **Collect The Day**
   - The canonical Dream Cycle writer is `python3 /Users/neo/.openclaw/workspace/scripts/build_dream_cycle_snapshot.py --write`.
   - Use that builder instead of manually composing markdown or hand-editing memory files.
   - The builder already grounds the snapshot in Chronicle, PM context, automation state, heartbeat diagnostics, and current memory tails.
2. **Update Persistent State**
   - The builder must write the same snapshot to:
     - `memory/runtime/persistent_state.md`
     - `memory/persistent_state.md`
   - The runtime file is the live read lane; the top-level file is the human-readable mirror.
3. **Append Narrative**
   - The builder must upsert the dated `memory/dream_cycle_log.md` entry for the current day.
4. **Surface Actions**
   - Call out blockers, automation drift, or repair work that should be promoted to the next day.
5. **Report**
   - Return the builder output exactly; do not paraphrase it.

## Output Template
```
Dream Cycle — <date>
Snapshot:
- ...
Automation Health:
- ...
Findings:
- ...
Actions:
- ...
```
