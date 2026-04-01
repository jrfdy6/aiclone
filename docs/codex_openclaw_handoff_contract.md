# Codex to OpenClaw Handoff Contract

This document defines the canonical bridge between:
- `Codex` as the primary live work surface
- `OpenClaw` as the maintenance and brain layer

## 1. Problem This Solves

The original OpenClaw loop assumed the main live context lived inside OpenClaw session history.

That is no longer reliably true.

Now the real work often happens in Codex first.

That means OpenClaw cron jobs like:
- `Oracle Ledger`
- `Progress Pulse`
- `Morning Daily Brief`
- `Dream Cycle`

cannot treat `agent:main:main` or `openclaw-control-ui` as the primary truth source anymore.

## 2. Canonical Bridge

The canonical bridge file is:

- `/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl`

This file is the first-class bridge from Codex into canonical memory.

It is:
- append-only
- JSONL-friendly
- machine-readable
- simple enough for both humans and cron jobs to inspect

It should now be treated as the current implementation lane for the `Codex Chronicle`.

See:
- `/Users/neo/.openclaw/workspace/docs/codex_chronicle_contract.md`

Runner ledgers are audit trails.

They are not the primary bridge.

## 3. Operating Rule

When meaningful work happens in Codex, the system should write a Chronicle or handoff event here before expecting OpenClaw brain jobs to reason about it.

That includes:
- major decisions
- blockers
- implementation shifts
- completed repairs
- task closures
- important follow-ups
- Discord-triggered actions that ran locally through Codex
- high-signal learning
- identity/voice signal that matters to the AI clone

## 4. Handoff Schema

Each line is one JSON object.

The minimum compatible shape stays the same, but richer Chronicle fields are now allowed.

```json
{
  "schema_version": "codex_handoff/v1",
  "handoff_id": "uuid",
  "created_at": "2026-03-31T14:00:00Z",
  "source": "codex-cli",
  "author_agent": "neo",
  "workspace_key": "shared_ops",
  "scope": "shared_ops",
  "importance": "medium",
  "summary": "OpenClaw cron jobs were rewired to read Codex handoff first.",
  "decisions": [
    "Treat codex_session_handoff.jsonl as canonical bridge input."
  ],
  "blockers": [],
  "follow_ups": [
    "Verify next Oracle Ledger run is grounded in Codex handoff entries."
  ],
  "artifacts": [
    "/Users/neo/.openclaw/workspace/docs/codex_openclaw_handoff_contract.md"
  ],
  "tags": [
    "openclaw",
    "cron",
    "codex"
  ]
}
```

## 5. Scope Rules

- `workspace_key`
  - use a real workspace when the handoff belongs to one lane
  - use `shared_ops` for system-level work

- `scope`
  - allowed initial values:
    - `workspace`
    - `shared_ops`
    - `portfolio_strategy`
    - `global_control`

## 6. Read Priority For OpenClaw Jobs

The affected OpenClaw jobs should read sources in this order:

1. latest entries in `memory/codex_session_handoff.jsonl`
2. canonical memory files like:
   - `memory/cron-prune.md`
   - `memory/daily-briefs.md`
   - `memory/persistent_state.md`
3. OpenClaw session history only as fallback for OpenClaw-specific cleanup

This is the key shift.

OpenClaw session introspection is no longer the default truth source.

## 7. Write Helper

Use:

```bash
python3 /Users/neo/.openclaw/workspace/scripts/append_codex_handoff.py \
  --summary "Rewired Oracle Ledger and Progress Pulse to read Codex handoff first." \
  --workspace-key shared_ops \
  --scope shared_ops \
  --source codex-cli \
  --author-agent neo \
  --decision "Codex handoff is now canonical input for brain jobs." \
  --follow-up "Verify the next scheduled runs use the new input path."
```

## 8. What This Is Not

This is not:
- a replacement for the PM board
- a replacement for daily briefs
- a second planning system
- a general dumping ground for every thought

It is a compact bridge from live Codex work into canonical memory.

## 9. Expected Outcome

Once this contract is in use:
- OpenClaw cron summaries should stop hallucinating confidence from stale session access
- Oracle and Progress should reflect real work that happened in Codex
- Morning Daily Brief and Dream Cycle should read the same current truth
- Discord alerts can stay lightweight because the brain layer is grounded again
