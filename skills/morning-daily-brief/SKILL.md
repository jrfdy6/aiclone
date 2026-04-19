---
name: morning-daily-brief
description: Generate the morning brief from cron/doc sources, append to memory/daily-briefs.md, and deliver to Discord. Use for the Morning Daily Brief cron.
---

# Morning Daily Brief Skill

## Inputs
- `python3 /Users/neo/.openclaw/workspace/scripts/build_morning_daily_brief.py`
- `memory/codex_session_handoff.jsonl`
- `memory/persistent_state.md`
- `memory/cron-prune.md`
- `memory/doc-updates.md`
- `memory/LEARNINGS.md`
- `memory/daily-briefs.md`
- `python3 /Users/neo/.openclaw/workspace/scripts/heartbeat_report.py --summary`
- PM board and automation mismatch context

## Workflow
1. **Build The Deterministic Brief First**
   - Run `python3 /Users/neo/.openclaw/workspace/scripts/build_morning_daily_brief.py`.
   - Treat the script output as the final brief text. Do not paraphrase it.
2. **Verify Only When Needed**
   - If you need to verify a cited route, artifact, or alert, inspect the referenced Chronicle entry, PM card, heartbeat summary, or memory tail directly.
   - Inspect `memory_diagnostics["memory/persistent_state.md"]` before trusting persistent-state language. If it shows `snapshot_heading_stale` or `boilerplate_flags`, treat that file as stale context rather than fresh highlights.
3. **Respect The Delivery Contract**
   - The brief must answer: what changed, why it matters, what action is now required, where it was routed, and which source artifact or PM card supports it.
   - Do not send filler like "Daily log input processing completed without errors" or "Latest heartbeats are syncing".
   - If `persistent_state.md` is stale, make that an explicit alert and pivot to Chronicle / PM / execution evidence.
4. **Write Brief**
   - Upsert the current-date brief into `memory/daily-briefs.md`.
5. **Deliver**
   - Send the builder output to Discord channel `1482486716584689856`.

## Template
```
Morning Daily Brief — <date>
What Changed:
- ...
Why It Matters:
- ...
Action Now:
- Owner: ...
- Next: ...
Routing:
- Workspace: ...
- Route: ...
Source:
- ...
Alerts:
- ...
```
