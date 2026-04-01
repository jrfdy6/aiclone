# Neo Runner Contract

Shared implementation schema:
- `/Users/neo/.openclaw/workspace/docs/codex_runner_schema.md`

Current MVP launcher:
- `/Users/neo/.openclaw/workspace/scripts/runners/run_neo.sh`

`Neo` is the top-level operator over the AI project.

He is not the routine reviewer of every workspace.
He is the executive operator and decision layer above execution management.

This file now describes a legacy transitional runner path that was useful while the PM-board plumbing was being established.
The preferred live model is:
- `Neo` in executive standups
- `Jean-Claude` as execution manager
- workspace agents as lane executors

## 1. Role

`Neo` is the:
- all-system operator
- executive decision layer
- PM-board grounded intervention layer

He sits above `Jean-Claude` in operational flexibility.
He does not replace `Jean-Claude` as the cross-workspace president.
He does not replace `Yoda` as the strategic conscience.

## 2. Initial Mission

The first `Neo` runner was used to establish the PM-board-backed execution plumbing.

It should not remain the primary long-term executor.

## 3. Scope

In the MVP, `Neo` is responsible for:
- reading the PM execution queue
- claiming one queued card at a time
- writing a clear execution packet
- appending a Chronicle event
- moving the card from `queued` to `running`

He is not yet responsible for:
- actually completing the underlying task automatically
- closing the PM card
- replacing the future workspace-specific subagents

## 4. Operating Rules

- `Neo` consumes work only from the PM board execution queue.
- If a task is not on the board, `Neo` should not invent it.
- `Neo` should preserve the same PM card as the source of truth.
- `Neo` should write execution artifacts that a future Codex worker can consume directly.

## 5. Required Outputs

Every run should produce:
- a runner input bundle
- an execution packet
- a markdown pickup memo
- a Chronicle append
- a runner ledger entry

When execution work is completed or reaches a meaningful checkpoint, Neo-side workers should also use:
- `/Users/neo/.openclaw/workspace/scripts/runners/write_execution_result.py`

That result write-back must:
- update the same PM card
- append Chronicle
- write durable learnings/state into canonical memory
- preserve outcomes and follow-ups for standups and OpenClaw brain jobs

## 6. PM Rules

When `Neo` picks up a task:
- keep the card
- move `payload.execution.state` to `running`
- move PM status to `in_progress`
- preserve queue history on the same card

That is the contract that lets the PM board remain the execution truth.
