# Chronicle To PM Promotion Boundary

This document defines the boundary between:
- `memory only`
- `standup only`
- `PM-worthy work`

It exists so the system does not pollute the PM board with advisory language, vague observations, or duplicate work.

## Core Rule

Strong signal should usually move like this:

`Chronicle -> canonical memory -> standup -> PM only if the next step is concrete`

PM is the narrowest lane.

Not every important Chronicle line deserves a PM card.

## Route To Memory Only

Keep the signal in canonical memory when it is:
- a durable observation
- a lesson
- an identity or worldview signal
- a record of what happened
- useful for future context but not yet actionable

Examples:
- lessons from execution
- a change in how the system understands Feeze
- a note that a workspace remains underdefined

## Route To Standup Only

Bring the signal to standup when it is:
- strategically important
- still ambiguous
- cross-workspace
- identity-adjacent
- likely to affect routing or priorities
- not ready to become bounded execution

Examples:
- a source changes the meaning of FEEZIE OS
- a workflow problem needs executive interpretation
- an observation reveals drift but not yet a precise fix

## Route To PM

Create or recommend PM work only when all of these are true:

- the next step is concrete
- the work can be named as a bounded action
- the owning lane is clear
- the item is not already active on the PM board
- the language describes work, not advice

Examples of PM-worthy titles:
- `Tighten Chronicle-to-PM promotion criteria for autonomous execution`
- `Standardize workspace identity packs across registry, PM, runners, and UI`
- `Verify heartbeat wake, logging, and summary quality`

## What Should Not Become PM

Do not promote sentences that are really:
- advice
- commentary
- reminders
- status narration
- executive interpretation

Examples that should stay out of PM:
- `Jean-Claude should resolve the promotion boundary and reopen the card with a narrowed SOP.`
- `Workspace execution should report back through PM and result write-back before the next executive standup.`
- `Keep execution inside fusion-os and return status through the same PM card.`

These may still belong in:
- Chronicle
- standup notes
- execution result follow-ups

But they should not become standalone PM titles.

## Action-Shaped PM Language

Preferred PM titles start with verbs like:
- `Align`
- `Backfill`
- `Build`
- `Clarify`
- `Create`
- `Define`
- `Document`
- `Make`
- `Promote`
- `Refine`
- `Run`
- `Standardize`
- `Tighten`
- `Turn`
- `Verify`
- `Wire`

Avoid titles that start with:
- `Jean-Claude should`
- `Neo should`
- `Yoda should`
- `Workspace execution should`
- `Keep`
- `Complete`
- `Review`
- `Decide whether`

Those are usually discussion or management language, not clean work objects.

## Current Enforcement

The first-pass enforcement lives in:
- [build_standup_prep.py](/Users/neo/.openclaw/workspace/scripts/build_standup_prep.py)

That script now:
- normalizes weak PM candidate titles
- rejects advisory phrasing
- rejects duplicates when the same title already exists on the active PM board
- requires a live PM snapshot before emitting promotion candidates, and records a `pm_updates_blocked_reason` when the board is unreachable

## Executive Rule

When the system is unsure:
- keep it in memory
- bring it to standup
- do not force it onto the PM board

The PM board should stay smaller, cleaner, and more trustworthy than the total volume of Chronicle signal.

## Promotion Writer Guardrails

`scripts/promote_codex_chronicle.py` reads the prep output and now refuses to write PM recommendation files when `pm_updates_blocked_reason` is set. Instead, the daily log notes that recommendations were blocked (e.g., “PM snapshot unavailable during prep”). Chronicle entries still land in memory so nothing is lost, but PM remains untouched until the board is reachable again.

## Autonomous Execution Checklist

Before letting the Chronicle → standup → PM path run without a human in the loop, confirm these four conditions:

1. **Builder health** — `python3 scripts/build_standup_prep.py --standup-kind <kind> --workspace-key <workspace>` must either show a live PM snapshot or explicitly set `pm_updates_blocked_reason`. A blocked prep means recommendations remain advisory-only.
2. **Candidate hygiene** — Inspect the generated `memory/standup-prep/<kind>/<stamp>.json` and ensure every entry in `pm_updates` passed `_pm_candidate_gate` (action-shaped title, no advisory prefix, no duplicate on the active board).
3. **Writer behavior** — Run `python3 scripts/promote_codex_chronicle.py --prep-json <path> --workspace-key <workspace> --write-pm-recommendations`. When the prep was blocked, the command must print `Skipped PM recommendation write: <reason>`; otherwise it should emit the recommendations file path.
4. **Result logging** — After a successful run, capture the decision through `scripts/runners/write_execution_result.py` so the daily log, workspace execution log, and PM card all reflect the automation’s state.

If any checklist item fails, leave the system in recommendation-only mode, fix the blocker (usually PM API access), and rerun the builder + promotion flow before touching the PM board.
