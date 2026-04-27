---
name: daily-memory-flush
description: Capture the day’s key insights, decisions, and lessons in memory/runtime/LEARNINGS.md and memory/YYYY-MM-DD.md, then confirm archives. Use for the Daily Memory Flush cron.
---

# Daily Memory Flush Skill

## Goals
- Persist durable takeaways into memory files.
- Confirm archives/daily logs exist for the current date.

## Workflow
1. **Gather Signals**
   - Review today’s chat summaries, reports, and audit logs.
2. **Update Daily Log**
   - Append structured bullets to `memory/YYYY-MM-DD.md` (create file if missing).
3. **Update LEARNINGS**
   - Promote long-term lessons to `memory/runtime/LEARNINGS.md` under relevant headings.
   - If there are no durable lessons, leave the runtime file unchanged instead of writing a placeholder or "no new learnings" note into the live compatibility shell.
4. **Archive Confirmation**
   - Confirm that the day’s daily log is git-tracked; mention archive status in the output.
5. **Report**
   - Post completion note (Discord channel `1482486716584689856`) summarizing what was recorded and whether archives were created.

## Suggested Structure
```
Daily Memory Flush — <date>
Decisions:
- ...
Lessons:
- ...
Risks:
- ...
Archive: <confirmed|needs follow-up>
```
