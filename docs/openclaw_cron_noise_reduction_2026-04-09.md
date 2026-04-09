# OpenClaw Cron Noise Reduction 2026-04-09

This note records the runtime-side cron changes made after the `clean-main-2026-04-08` baseline to reduce Discord noise and improve job coordination.

Related docs:

- [golden_snapshot_sop.md](/Users/neo/.openclaw/workspace/docs/golden_snapshot_sop.md)
- [openclaw_runtime_backup_2026-04-08.md](/Users/neo/.openclaw/workspace/docs/openclaw_runtime_backup_2026-04-08.md)

Captured at:

- `2026-04-09 07:08:43 EDT -0400`

Runtime file:

- `/Users/neo/.openclaw/cron/jobs.json`
- SHA-256: `b5df6481dce09c8283442796808e1b64ae54dcb41076dbaea2cbcad934e7419a`

## Intent

Move the cron layer toward:

- one recurring Discord digest that only speaks when something materially changed
- silent maintenance jobs that write to memory instead of narrating success
- alert jobs that stay truly alert-only

## Runtime Changes

### 1. Progress Pulse

Job:

- `717f5346-f58f-4eac-ac30-014d8774a6c7`

Changes:

- cadence reduced from every 30 minutes to every 60 minutes
- added deterministic gate: `/Users/neo/.openclaw/workspace/scripts/progress_pulse_gate.py`
- job now checks for net-new handoff or persistent-state signal before delivering
- prompt now requires exact `NO_REPLY` when nothing materially changed
- prompt now requires UTC timestamps and forbids conversational filler

Operational effect:

- repeated near-identical digests should stop
- Discord should only receive Progress Pulse when there is a real new signal to report

### 2. Oracle Ledger

Job:

- `65cae370-55fd-4dd8-b93d-1ddf79ab33da`

Changes:

- `deleteAfterRun` corrected from `true` to `false`
- delivery mode changed from `announce` to `none`

Operational effect:

- Oracle Ledger keeps consolidating and writing to `memory/cron-prune.md`
- routine success summaries no longer clutter Discord

### 3. Context Guard

Job:

- `66807e25-3ffa-4cf2-8691-7e46eabb599a`

Changes:

- prompt now runs `context_usage.py --json`
- prompt now treats both `no-active-session` and `below-threshold` as hard `NO_REPLY`
- prompt explicitly forbids extra explanation when returning `NO_REPLY`

Operational effect:

- sub-threshold context checks should stop leaking “13k tokens / NO_REPLY” chatter into Discord
- only genuine flush events should announce

### 4. Dream Cycle Verifier

Job:

- `9d9b2c7e-110c-4e44-8865-4f3c86e1809f`

Observed outcome:

- `Dream Cycle Verification — 2026-04-09` completed `OK`
- verifier is no longer present in live `jobs.json`

Operational effect:

- the one-shot guardrail did its job and did not remain behind as recurring noise

## Repo-Side Contract Changes

These repo files were updated to match the new runtime behavior:

- `/Users/neo/.openclaw/workspace/scripts/progress_pulse_gate.py`
- `/Users/neo/.openclaw/workspace/skills/progress-pulse-digest/SKILL.md`
- `/Users/neo/.openclaw/workspace/skills/oracle-ledger-prune/SKILL.md`
- `/Users/neo/.openclaw/workspace/skills/morning-daily-brief/SKILL.md`
- `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`

## Expected Result

After this change set:

- `Morning Daily Brief` remains the once-daily synthesis message
- `Progress Pulse` becomes the only recurring operational digest and should post much less often
- `Oracle Ledger` becomes a quiet maintenance lane
- `Context Guard` becomes mostly invisible unless a real flush is needed

If Discord still shows repeated Progress Pulse boilerplate after this note, inspect the next runs for `717f5346-f58f-4eac-ac30-014d8774a6c7` and verify the model obeyed the gate result rather than narrating anyway.
