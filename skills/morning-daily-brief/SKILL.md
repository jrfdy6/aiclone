---
name: morning-daily-brief
description: Generate the morning brief from cron/doc sources, append to memory/daily-briefs.md, and deliver to Discord. Use for the Morning Daily Brief cron.
---

# Morning Daily Brief Skill

## Inputs
- `memory/codex_session_handoff.jsonl`
- `memory/cron-prune.md`
- `memory/doc-updates.md`
- `memory/LEARNINGS.md`
- Tavily search output via `/Users/neo/.openclaw/workspace/scripts/tavily_daily_brief.py` (set `TAVILY_API_KEY` or ~/.openclaw/secrets/tavily.key)
- Latest cron run history (Oracle Ledger, Rolling Docs, Daily Memory Flush, etc.)

## Workflow
1. **Collect Signals**
   - Read each input file and extract highlights, blockers, and pending follow-ups.
   - Treat the latest Codex handoff entries as the primary signal for what actually moved most recently.
2. **Summarize**
   - Cover: top cron results, outstanding follow-ups (e.g., rich memory ingestion, Railway cache validation, doc updates, backup jobs), and any alerts.
3. **Write Brief**
   - Append structured brief to `memory/daily-briefs.md` (date-stamped heading).
4. **Deliver**
   - Send brief to Discord channel `1482486716584689856`, explicitly calling out alerts needing attention.

## Template
```
Morning Daily Brief — <date>
Highlights:
- ...
Follow-ups:
- ...
Alerts:
- ...
```
