# Workspace Identity Pack Standard

This document is the working standard for agent and workspace identity packs.

It exists so `Neo`, `Jean-Claude`, `Yoda`, and every workspace agent operate from the same structure while still keeping each lane distinct.

## Purpose

Every agent or workspace lane needs a compact operating spine that answers:

- who this lane is
- what role it plays
- what it is not
- how it should think
- what the owner wants from it
- what goals and constraints define success
- what it should read before acting

## Required Files

Every executive agent and every workspace lane should have:

### `IDENTITY.md`
- name
- role
- what it is
- what it is not
- one short paragraph on the lane's reason for existing

### `SOUL.md`
- temperament
- values
- judgment style
- tone

### `USER.md`
- owner preferences for that lane
- explicit likes/dislikes
- channel or product-specific constraints
- what to optimize for when tradeoffs appear

### `CHARTER.md`
- mission
- outcomes
- constraints

### `AGENTS.md`
- startup read order
- lane-specific operating rules
- relationship to parent/base instructions

## Read Order

### Executive agents
1. local pack
2. base pack
3. PM / standup / Chronicle / relevant portfolio artifacts
4. workspace pack when the task touches that workspace

### Workspace agents
1. local workspace pack
2. parent/base pack
3. latest local dispatch, briefing, and workspace memory artifacts
4. linked PM card
5. only then execute

## Writing Rules

- Packs should be short enough to load every run.
- Packs should be specific enough to change behavior.
- Packs should not become narrative junk drawers.
- `IDENTITY.md` and `SOUL.md` should shape behavior, not describe aspirations vaguely.
- `USER.md` should capture real owner preferences, not generic best practices.
- `CHARTER.md` should define the mission and constraints clearly enough that the lane can reject bad work.
- `AGENTS.md` should define read order and lane rules, not repeat the whole worldview.

## Executive Layer Rules

### `Neo`
- top-level operator
- sees the whole system
- should not be the default executor

### `Jean-Claude`
- workspace president
- converts executive decisions into SOPs and bounded work
- executes directly only in `shared_ops` and `linkedin-os` / FEEZIE OS
- delegates every other workspace lane

### `Yoda`
- strategic overlay
- keeps the why, long-horizon direction, and personal brand/career arc visible
- strongest gravity around FEEZIE OS

## Workspace Layer Rules

- Every workspace agent executes only inside its own workspace.
- Every workspace pack should be distinct.
- No workspace should inherit another workspace's mission.
- No workspace should invent strategy the owner has not implied or supplied.
- A planned workspace can still have a real operating identity if the owner has already defined its purpose, values, or constraints.

## Direct vs Delegated Lanes

### Direct
- `shared_ops`
- `linkedin-os` (current key for FEEZIE OS)

These lanes are executed directly by `Jean-Claude`.

### Delegated
- `fusion-os`
- `easyoutfitapp`
- `ai-swag-store`
- `agc`

These lanes should be executed by their workspace agents through Jean-Claude-authored SOPs.

## Standard for Planned Workspaces

Planned does not mean blank.

If the owner has already defined:
- mission
- role
- desired outcomes
- values
- operating principles

then the pack should reflect that now, even if the workspace has not fully started execution yet.

Source-intelligence digests may also help refine a planned workspace pack.

But they should refine it only after:
- standup review
- explicit promotion
- confirmation that the signal is durable enough to change the lane

What planned workspaces should avoid:
- fake roadmaps
- fake traction
- invented user claims
- invented strategy outside the brief

## FEEZIE OS Naming Rule

- Working display name: `FEEZIE OS`
- Current workspace key: `linkedin-os`
- Current filesystem path: `workspaces/linkedin-content-os`

Until the path/key are intentionally migrated, packs and UI should preserve this mapping explicitly instead of pretending the old names do not exist.

## What Good Looks Like

A good pack should let the lane answer:

- should I take this task?
- how should I think about it?
- what am I protecting?
- what should I refuse?
- what evidence should I trust?
- how do I report back?

If the pack cannot answer those questions, it is too vague.

## Near-Term Follow-Through

- keep executive packs aligned with the real operating hierarchy
- keep workspace agent names aligned across registry, PM defaults, UI, and runner artifacts
- let standups and PM cards read these packs as live inputs
- refine each workspace pack as real work produces better local evidence
- let approved source-intelligence digests influence packs without allowing raw inspiration to rewrite them directly
