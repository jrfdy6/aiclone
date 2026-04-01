---
name: dream-cycle
description: Roll the current day into a durable persistent-state snapshot, append the narrative to memory/dream_cycle_log.md, and surface follow-up actions. Use for the Dream Cycle cron.
---

# Dream Cycle Skill

## Inputs
- `memory/YYYY-MM-DD.md`
- `memory/codex_session_handoff.jsonl`
- `memory/cron-prune.md`
- `memory/doc-updates.md`
- `memory/backup-log.md`
- latest `memory/reports/memory_health_*.md`
- `memory/self-improvement.md`
- `memory/daily-briefs.md`

## Workflow
1. **Collect The Day**
   - Read today's daily log, the latest Codex handoff entries, recent cron outputs, and the latest health/report artifacts.
2. **Update Persistent State**
   - Overwrite `memory/persistent_state.md` with a compact operator snapshot:
     - Snapshot
     - Automation Health
     - Findings
     - Actions
3. **Append Narrative**
   - Append a dated entry to `memory/dream_cycle_log.md` capturing what changed and what matters next.
4. **Surface Actions**
   - Call out blockers, automation drift, or repair work that should be promoted to the next day.
5. **Report**
   - Keep the outgoing summary short and action-oriented.

## Output Template
```
Dream Cycle — <date>
Snapshot:
- ...
Automation Health:
- ...
Actions:
- ...
```
