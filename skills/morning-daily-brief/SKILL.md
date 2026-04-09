---
name: morning-daily-brief
description: Generate the morning brief from cron/doc sources, append to memory/daily-briefs.md, and deliver to Discord. Use for the Morning Daily Brief cron.
---

# Morning Daily Brief Skill

## Inputs
- shared memory contract from `python3 /Users/neo/.openclaw/workspace/scripts/build_cron_memory_contract.py --workspace-key shared_ops --memory-path memory/persistent_state.md --memory-path memory/cron-prune.md --memory-path memory/doc-updates.md --memory-path memory/LEARNINGS.md --memory-path memory/daily-briefs.md --memory-path memory/{today}.md`
- `memory/codex_session_handoff.jsonl`
- `memory/persistent_state.md`
- `memory/cron-prune.md`
- `memory/doc-updates.md`
- `memory/LEARNINGS.md`
- Tavily search output via `/Users/neo/.openclaw/workspace/scripts/tavily_daily_brief.py` (set `TAVILY_API_KEY` or ~/.openclaw/secrets/tavily.key)
- Latest cron run history (Oracle Ledger, Rolling Docs, Daily Memory Flush, etc.)

## Workflow
1. **Collect Signals**
   - Run `build_cron_memory_contract.py` first and treat its JSON as the canonical merged context for this brief.
   - Use `chronicle_entries` as the primary recent signal for what actually moved most recently.
   - Use `durable_memory_context` when older markdown memory changes the interpretation of today's work.
   - Use `memory_context` tails as the compact operator state; those paths may resolve to the live file or the latest tracked snapshot fallback.
   - Read Tavily and latest cron run history only after reconciling them against the merged memory contract.
2. **Summarize**
   - Cover: top cron results, outstanding follow-ups, and any alerts that actually matter today.
   - This is the once-daily synthesis layer. Do not simply restate Progress Pulse boilerplate.
   - Prefer one clear next opportunity or risk over a long list of minor maintenance notes.
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
