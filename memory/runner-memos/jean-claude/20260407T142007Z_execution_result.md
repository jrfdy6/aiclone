# Execution Result - Tighten Chronicle-to-PM promotion criteria for autonomous execution

- Card: `f57fbbf8-1603-4814-89cb-94b0a411cbb5`
- Workspace: `shared_ops`
- Status: `review`

## Summary
Chronicle-to-PM promotion now refuses to emit new PM recommendations unless the builder can reach the live PM board, and the promotion writer mirrors that rule so we stop leaking advisory text onto the board when the API is down.

## Blockers
- None.

## Decisions
- Added `pm_updates_blocked_reason` to the prep builder so shared_ops standups capture why PM recommendations were suppressed whenever the PM snapshot is unavailable.
- Updated the Chronicle promotion writer and SOP to honor the new block reason, keeping held signal in memory until the PM API comes back online.

## Learnings
- None.

## Outcomes
- scripts/build_standup_prep.py:930-948 now guards PM candidate building behind a live snapshot and records `pm_updates_blocked_reason`, which shows up in the fresh prep bundle at memory/standup-prep/executive_ops/20260407T141815Z.json:1-36,575.
- scripts/promote_codex_chronicle.py:62-141 skips pm-recommendation files when a block reason is present and annotates the daily log instead, matching the builder’s behavior.
- docs/chronicle_pm_promotion_boundary.md:117-137 documents the snapshot requirement plus the writer guardrail so future packets know the rule, and workspaces/shared-ops/memory/execution_log.md:142-157 captures today’s result for PM truth.

## Follow-ups
- None.
