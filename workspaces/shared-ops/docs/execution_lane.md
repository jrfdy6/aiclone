# shared_ops Execution Lane

This is the canonical loop for Jean-Claude packets in the executive workspace.

1. **Load identity + review context**  
   Read the local pack, `docs/README.md`, and the latest review artifact so you know which gaps are already logged.

2. **Read the packet stack**  
   Open the current `dispatch/<timestamp>_sop.json`, `briefings/<timestamp>_briefing.md`, and work order to confirm scope, linked standup, and write-back contract.

3. **Inspect PM + diagnostics**  
   Confirm the PM card’s current execution state, standup prep entry, and any referenced diagnostics (heartbeat report, standup prep JSON, Chronicle entries).

4. **Execute in-lane**  
   Make the repo changes, update registry/runbooks/scripts as required, and keep notes in `docs/` or `memory/` instead of ad hoc scratchpads.

5. **Write back**  
   - Update `memory/execution_log.md` with card, outcome, blockers, and follow-ups.  
   - Run `python3 scripts/runners/write_execution_result.py ...` per the packet’s `write_back_contract`.  
   - Attach any new artifacts (docs, scripts, SOP diffs) so the PM record stays traceable.

6. **Surface follow-ups**  
   If a finding belongs to another workspace, log it as a follow-up in the PM result and in `memory/execution_log.md`, then hand it off via PM instead of keeping it implicit.

Treat this lane as closed loop: no work is “done” until the PM writer succeeds and the artifact path is recorded.
