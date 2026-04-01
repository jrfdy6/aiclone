# Codex Local Agent Runner Architecture

This document defines the next system layer after the OpenClaw cron rehab work.

The goal is not to replace OpenClaw.

The goal is to:
- keep OpenClaw responsible for `brain maintenance`
- run new autonomous agent loops locally on the machine
- use OpenAI Codex-family models as the execution engine for those local agents
- keep all work routed back into the same PM board / brief / workspace operating system

## 1. Objective

Build a two-layer system:

1. `OpenClaw maintenance layer`
2. `local Codex runner layer`

The OpenClaw layer keeps the brain healthy.

The Codex layer does real autonomous work.

This is the clean split that preserves reliability, lowers confusion, and avoids overloading OpenClaw with both platform maintenance and execution autonomy.

## 2. Core Principle

The system should be:

1. `workspace-first`
2. `PM-board grounded`
3. `maintenance separated from execution`
4. `cheap by default`
5. `local-first for machine-bound autonomy`

That means:
- OpenClaw owns maintenance, hygiene, digestion, and lightweight operating signals
- Codex runners own execution tasks, code work, structured research, and autonomous local workflows
- `memory/codex_session_handoff.jsonl` is the canonical bridge from Codex work into the OpenClaw brain loop
- the PM board remains the single source of truth for meaningful work
- no job writes into the wrong workspace
- Discord is an alert/digest surface, not a second task system

## 3. Official OpenAI Fit

This design assumes:

- `gpt-5-nano` is used for cheap/high-volume maintenance where task shape is constrained
- Codex-family models are used for actual autonomous coding/execution loops

OpenAI docs currently position:
- `gpt-5-nano` as the fastest, most cost-efficient GPT-5 model
- `gpt-5-codex` / `gpt-5.3-codex` as models optimized for agentic coding workflows
- Responses API as the API surface for those Codex models

Reference:
- https://platform.openai.com/pricing
- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5-codex
- https://developers.openai.com/api/docs/models/gpt-5.3-codex

## 4. System Layers

### Layer A: OpenClaw Maintenance Layer

Purpose:
- keep memory healthy
- keep daily state coherent
- keep logs, backups, briefs, and context hygiene reliable
- provide alerting and digest surfaces

Current/target maintenance jobs:
- `GitHub Backup`
- `Rolling Docs`
- `Daily Memory Flush`
- `Weekly Backup`
- `Memory Archive Sweep`
- `Memory Health Check`
- `Oracle Ledger`
- `Nightly Self-Improvement`
- `Morning Daily Brief`
- `Progress Pulse`
- `Context Guard`
- `Dream Cycle`
- monitor jobs

OpenClaw should continue to own:
- maintenance scheduling
- brain hygiene
- brief generation
- context protection
- health checks
- lightweight alerts

OpenClaw should not become the main autonomous execution engine for future workspace agents.

### Layer B: Local Codex Runner Layer

Purpose:
- execute autonomous work loops on the local machine
- interact with local files, repos, prompts, and tools
- operate per workspace
- create/advance real tasks

This layer should be scheduled outside OpenClaw, likely through:
- `launchd` on macOS
- local scripts and runner wrappers

This layer will still call OpenAI under the hood.
It is "outside OpenClaw," not "outside the OpenAI API boundary."

## 5. Responsibility Split

### OpenClaw owns
- memory cleanup
- summary generation
- context compression
- daily briefs
- persistent state refresh
- automation health checks
- delivery routing
- brain-level logs and reports

### Local Codex runners own
- workspace execution
- ticket advancement
- repo-level actions
- code review/fix loops
- structured research loops
- file creation/update inside their own workspace lane
- autonomous subagent work

## 6. Agent Roles

Top-level team model:
- `Neo`
  - primary lead identity over the entire AI project
  - knows the full system, can touch the full system, and can move anywhere when needed
  - should not be trapped in routine oversight because versatility is the point

- `Jean-Claude`
  - president / operating lead over the workspace layer
  - initially supervises all workspaces before each workspace has its own subagent
  - owns execution flow, PM truth, blockers, sequencing, and cross-workspace dependencies

- `Yoda`
  - board / governance / long-horizon judgment
  - thinks about strategic direction across the system, with strongest focus on `LinkedIn OS` as it evolves into `FEEZIE OS`
  - reasons about brand, career direction, identity, and whether the workspaces are actually moving Johnnie where he wants to go

Overlap note:
- `Neo` and `Yoda` both see across the full system
- `Neo` is the top-level operational force and flexible executor
- `Yoda` is the strategic overlay and directional conscience
- keep the overlap intentional, but do not make them redundant

These roles should exist in the local Codex runner layer as role profiles.

This does not require only three actual processes forever.
It means all subagents should inherit one of those operating postures.

## 7. Workspace Model

The workspace remains the unit of separation.

Target workspaces:
- `linkedin-os`
- `fusion-os`
- `easyoutfitapp`
- `ai-swag-store`
- `agc`

Note:
- `linkedin-os` is expected to expand into `FEEZIE OS`
- that lane should eventually include LinkedIn, Instagram, and broader career strategy rather than staying a narrow content workspace

Each workspace needs:
- its own task lane
- its own artifact path
- its own standup history
- its own brief history
- its own runner logs
- its own output contract

No cross-workspace write should happen unless explicitly promoted.

## 8. PM Board Contract

The PM board remains the single source of truth for meaningful work.

Rules:
- if it is not on the PM board, it is not real
- if it has no `workspace_key`, it is malformed
- if it is cross-workspace, it belongs in `shared_ops`, not a random workspace

Every Codex runner action that creates meaningful work should either:
- create a PM card
- update a PM card
- attach evidence to a PM card
- resolve a PM card

Every runner output should include:
- `workspace_key`
- `owner_agent`
- `run_type`
- `task_ref` or `pm_card_id`
- `artifact_refs`
- `summary`
- `status`
- `next_action`

## 9. Codex Runner Contract

Each local Codex runner should have:

Implementation reference:
- `/Users/neo/.openclaw/workspace/docs/codex_runner_schema.md`

### Required inputs
- workspace identity
- role identity
- task source
- allowed filesystem scope
- allowed tool scope
- current PM card context
- latest workspace brief/state
- latest Codex handoff context when real work happened outside OpenClaw

### Required outputs
- status
- summary
- artifacts written
- proposed next action
- PM board mutation or recommendation

Each meaningful runner pass should also be able to append a compact handoff into:
- `/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl`
- error state if incomplete

### Required safety controls
- max run time
- max token/model budget
- allowed directories
- allowed command prefixes
- dry-run mode when needed
- stop file / kill switch
- per-run logs

### Required persistence
- run log
- latest outcome
- artifact list
- PM linkage
- workspace linkage

## 10. Runtime Design

Each local Codex runner should be launched by a local wrapper.

Suggested runtime path:

`launchd`
-> runner script
-> task/context loader
-> Codex model invocation
-> local action execution
-> artifact/log write
-> PM board update
-> optional brief/alert emission

This wrapper should abstract away the raw OpenAI call details so the system feels like "Codex runners" rather than hand-authored API jobs.

## 11. Model Policy

### OpenClaw maintenance jobs

Use:
- `gpt-5-nano` for low-risk constrained maintenance jobs
- `gpt-4o-mini` where nuance/alert quality still matters

### Local Codex runners

Use Codex-family models for:
- code generation
- code modification
- repo-aware reasoning
- multi-step tool use
- execution/reflection loops

Do not use `gpt-5-nano` as the primary engine for your serious autonomous coding agents.
Use it for cheap maintenance, not for your main builder brain.

## 12. Logging And Ledgers

You need two ledgers:

### Automation ledger
For maintenance jobs:
- job id
- model
- run time
- status
- delivery state
- artifact refs

### Runner ledger
For Codex agents:
- runner id
- workspace key
- role
- task ref
- model
- started/finished
- status
- artifacts written
- PM effects
- cost usage if available

These ledgers should remain separate.

Maintenance history and autonomous work history are not the same thing.

## 13. Standup Integration

There should be two standup layers:

### Workspace standup
- per workspace
- reads PM board + recent runner outputs
- focuses on actual project work

### Executive ops standup
- cross-workspace
- led operationally by `Jean-Claude`
- informed by `Yoda` governance signals when needed
- reads maintenance signals from OpenClaw and major runner blockers
- handles escalation, drift, and dependencies

`Neo` should stay available as the intervention layer above this ritual, not the routine owner of it.

OpenClaw maintenance outputs should feed standups.
They should not replace them.

Meeting best-practice additions:
- daily executive syncs should run without Johnnie attending
- meeting prompts should point at skills/contracts instead of duplicating instructions
- PM board should be the meeting ground truth
- meetings should have minimum three rounds
- meetings should produce transcripts
- important meetings should have watchdogs
- transcripts should flow into post-sync dispatch and accountability sweep

Recommended meeting types:
- daily executive sync
- workspace syncs
- weekly review
- Saturday vision sync

Recommended dashboard views:
- list
- weekly
- monthly
- practical meeting history over the existing cron/meeting surfaces

These are all views over the same meeting truth.
They must not become separate planning systems.

## 14. What Must Not Happen

Do not:
- put all autonomous work inside OpenClaw cron
- let Codex runners write blindly across all workspaces
- let Discord become the task system
- let maintenance files become the source of truth for project work
- let subagents bypass PM board updates
- mix brain-maintenance logs and runner execution logs into one undifferentiated memory pool

## 15. Recommended Build Order

### Phase 1: stabilize maintenance layer
- observe current OpenClaw cron behavior for several days
- confirm the current jobs remain healthy
- confirm the new `gpt-5-nano` maintenance tier stays stable

### Phase 2: create the local runner contract
- define runner input/output schema
- define workspace routing
- define PM mutation rules
- define stop/kill controls

### Phase 3: build one runner
- one operating runner
- all workspaces in read/write oversight mode
- one schedule
- one log
- one PM feedback path

Suggested first runner:
- `Jean-Claude` as the cross-workspace operating president

### Phase 4: add review layer
- add first workspace-specific subagent
- give it one workspace only
- keep `Jean-Claude` as the supervising layer

### Phase 5: add coordination layer
- add `Yoda` governance layer
- periodic strategic review
- escalation summaries
- longer-horizon critique and portfolio-level risk checks
- strongest tie to `LinkedIn OS` -> `FEEZIE OS`, while still evaluating the five-workspace portfolio

### Phase 6: expand to multi-workspace operation
- only after the single-workspace lane is stable

## 16. Go / No-Go Criteria

Do not scale into full autonomous subagents until:
- maintenance cron health remains stable
- mismatch report stays clean
- PM board routing is trustworthy
- one local Codex runner can complete tasks without corrupting workspace boundaries
- logs and artifacts are recoverable
- kill/stop controls are proven

## 17. Bottom Line

The right system is:

- `OpenClaw = brain maintenance`
- `Local Codex runners = autonomous work`
- `PM board = task truth`
- `workspace = separation boundary`
- `Neo / Jean-Claude / Yoda = operating roles`

Role shorthand:
- `Neo` asks: what needs to happen anywhere in the system?
- `Jean-Claude` asks: what needs to move across the workspaces right now?
- `Yoda` asks: is this actually taking Johnnie where he is trying to go?

That is the architecture that gives you autonomy without turning the whole machine into one confused shared loop.
