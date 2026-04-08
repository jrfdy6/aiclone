---
name: dream-cycle-verification
description: Verify that a Dream Cycle cron run completed in the expected window, updated durable files, avoided known input failures, and still has healthy QMD grounding.
---

# Dream Cycle Verification Skill

## Inputs
- Target local date to verify, for example `2026-04-09`
- `/Users/neo/.openclaw/workspace/scripts/verify_dream_cycle_run.py`
- `/Users/neo/.openclaw/workspace/memory/cron-prune.md`
- Report output path such as `/Users/neo/.openclaw/workspace/memory/reports/dream_cycle_verification_2026-04-09.md`

## Workflow
1. Run:
   - `python3 /Users/neo/.openclaw/workspace/scripts/verify_dream_cycle_run.py --date <YYYY-MM-DD> --report-out <ABS_REPORT_PATH> --json`
2. Read the JSON result and treat `status` as the source of truth.
3. Append a short timestamped recap to `memory/cron-prune.md` using:
   - `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py /Users/neo/.openclaw/workspace/memory/cron-prune.md --body "<UTC timestamp> - Dream Cycle verification <status> for <YYYY-MM-DD>: ..."`
4. Return a concise final summary only. Do not call the message tool.

## Quality Gates
- `ALERT` means the run missed the expected window, failed to update durable files, hit known wildcard/directory input failures, or lost QMD alias readiness.
- `WARN` is acceptable only for expected conditions such as Dream Cycle running before heartbeat active hours.
- Always include the report path in the final summary.

## Output Template
```
Dream Cycle Verification — <YYYY-MM-DD>
Status: OK | WARN | ALERT
Observed Run: <timestamp or missing>
Checks:
- persistent_state updated: <true|false>
- dream_cycle_log updated: <true|false>
- known failures: <none|summary>
- qmd alias ready: <true|false>
Report: <absolute path>
```
