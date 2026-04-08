---
name: dream-cycle
description: Roll the current day into a durable persistent-state snapshot, append the narrative to memory/dream_cycle_log.md, and surface follow-up actions. Use for the Dream Cycle cron.
---

# Dream Cycle Skill

## Inputs
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
   - Read today's daily log, the latest Codex handoff entries, recent cron outputs, and the latest health/report artifacts.
   - Resolve wildcard inputs to a concrete file path first; do not try to read `memory_health_*.md` literally.
   - Resolve placeholder paths to concrete current-date files first; do not try to read `memory/YYYY-MM-DD.md` literally.
   - If knowledge ingestions matter, list recent files under `knowledge/` and inspect specific files; do not try to read the `knowledge/` directory itself.
   - If heartbeat freshness, Discord summary quality, or automation drift is in question, run `heartbeat_report.py` and use the concrete timestamps in the snapshot.
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
Findings:
- ...
Actions:
- ...
```
