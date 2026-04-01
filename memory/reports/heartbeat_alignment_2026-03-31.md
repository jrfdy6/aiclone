# Heartbeat Alignment - 2026-03-31

## Problem

Heartbeat was configured in `~/.openclaw/openclaw.json`, but the active workspace file at `workspace/HEARTBEAT.md` was effectively a no-op while the older root file `~/.openclaw/HEARTBEAT.md` still contained the real checklist.

That made startup ambiguous:
- scheduler on
- workspace heartbeat instructions off
- no `memory/heartbeat-state.json`

## Fix Applied

- `workspace/HEARTBEAT.md` is now the canonical heartbeat checklist.
- `workspace/memory/heartbeat-state.json` now exists with an initial structure.

## Operating Rule

- Treat `workspace/HEARTBEAT.md` as the live heartbeat contract because the configured agent workspace is:
  - `/Users/neo/.openclaw/workspace`
- Treat `~/.openclaw/HEARTBEAT.md` as legacy reference only.

## Intended Heartbeat Scope

Heartbeat should stay lightweight and focus on:
- automation health
- Discord/gateway churn
- PM or workspace blockers surfaced in canonical memory

Heartbeat should not:
- duplicate cron summaries
- behave like a daily brief
- invent broad new tasks

## Readiness Note

This aligns the heartbeat files and state expectations, but it does not by itself prove that the live heartbeat runner is delivering useful outputs yet. The next useful proof is observing the next heartbeat cycle after this alignment and checking whether it:

1. reads the workspace heartbeat checklist
2. updates `memory/heartbeat-state.json`
3. stays quiet with `HEARTBEAT_OK` when nothing needs attention
4. avoids duplicating cron summaries
