# Persistent Memory Blueprint

This document restores the cron/runtime contract expected by startup docs and OpenClaw jobs.

## Canonical Memory Lanes

- `memory/persistent_state.md`: current operating snapshot for restarts
- `memory/YYYY-MM-DD.md`: daily append-only log
- `memory/LEARNINGS.md`: durable rules and lessons
- `memory/doc-updates.md`: rolling document-change log for the Rolling Docs cron
- `memory/daily-briefs.md`: executive rollups and daily briefs
- `memory/reports/`: health checks, audits, and generated reports

## Canonical Automations In The Memory Lane

- `Oracle Ledger`
- `Rolling Docs`
- `Daily Memory Flush`
- `Morning Daily Brief`
- `Nightly Self-Improvement`
- `Memory Health Check`
- `Dream Cycle`
- `GitHub Backup`

## Operating Rule

Automations may summarize to Discord, but durable truth belongs in `memory/` files first.

## Startup / Reinjection

Use:

```bash
python3 /Users/neo/.openclaw/workspace/scripts/load_context_pack.py --sop --memory
```

That command is the compatibility loader for fresh Codex/OpenClaw sessions.

## Runtime Guardrails

- Compaction reserve floor should stay at or above `40000`
- Soft threshold should stay at or above `4000`
- Memory flush must stay enabled
- Validate with:

```bash
python3 /Users/neo/.openclaw/workspace/scripts/check_local_runtime_overrides.py
python3 /Users/neo/.openclaw/workspace/scripts/compaction_guardrail_check.py
```
