# Discord to Codex Command Bridge

Yes, it is possible to use Discord to trigger things on the home computer through Codex.

But the right shape is:
- `Discord` as the command surface
- `local bridge` as the validator/router
- `Codex runner` as the execution engine
- `OpenClaw memory` as the canonical record

Do not run long Codex work directly inside the Discord listener.

The existing OpenClaw gateway logs already show historically slow Discord listeners.

## 1. Target Flow

The clean command path is:

1. a command lands in a specific Discord channel or DM
2. a lightweight local bridge validates:
   - allowed user
   - allowed channel
   - allowed command prefix
3. the bridge writes a local command record
4. the bridge launches the correct local Codex runner
5. the runner performs the bounded action
6. the runner writes:
   - runner ledger entry
   - Codex handoff entry
   - PM recommendations or updates when needed
7. the bridge posts a concise completion or failure note back to Discord

## 2. Why Queue/Worker Beats Direct Execution

Direct execution inside the Discord event handler is the wrong pattern because:
- listener timeouts are more likely
- long tasks make the bot feel unstable
- failures are harder to retry cleanly
- command history is harder to audit

The bridge should acknowledge quickly, then hand work to a local worker.

## 3. Safe Command Types

Good initial Discord-triggered Codex actions:
- run Jean-Claude review now
- run Yoda strategy review now
- refresh a workspace summary
- inspect a repo or workspace status
- write a Codex handoff entry
- create a PM recommendation bundle

Bad initial Discord-triggered actions:
- unrestricted shell access
- broad destructive edits
- arbitrary filesystem writes
- long multi-repo refactors without bounded scope

## 4. Security Rules

At minimum the bridge should enforce:
- allowlisted Discord users
- allowlisted channels
- a command prefix such as `!neo` or `/neo`
- a constrained command grammar
- bounded path scopes
- structured logging of every invocation

Every command should produce:
- a request record
- a result record
- a Codex handoff entry when the result is meaningful

## 5. Recommended First Commands

Start with these:
- `!neo run jean-claude`
- `!neo run yoda`
- `!neo status brain`
- `!neo handoff <summary>`

These are narrow enough to prove the loop without creating a security mess.

## 6. How This Fits The Existing System

This does not replace OpenClaw.

It extends the current architecture:
- OpenClaw maintains the brain
- Codex runners do local execution
- Discord becomes a thin remote control surface

The command bridge should write into:
- `/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl`
- runner ledgers
- PM recommendation/output paths

That keeps the whole system on the same page.
