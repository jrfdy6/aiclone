# End-To-End Memory Convergence Implementation Plan

## Objective

Finish the memory architecture that is already partially defined so the system can reliably:

1. capture live work before context loss,
2. promote durable signal into retrievable memory,
3. let standups, PM, and agents use that memory for future decisions,
4. reduce git noise without weakening the memory loop.

## Problem To Solve

The current system already has the right broad shape, but the implementation is only partially converged.

Current reality:

- `memory/codex_session_handoff.jsonl` is the current bridge from Codex into OpenClaw.
- canonical markdown memory exists under `memory/**/*.md`.
- QMD indexes markdown memory and knowledge from disk.
- standups and agent runners still rely heavily on the recent handoff tail.
- runner ledgers, memos, reports, and generated plans create heavy git churn.

The key risk is this:

- recent work is visible,
- durable work is sometimes visible,
- but the system does not yet guarantee that important older signal becomes retrievable memory before it falls out of the recent JSONL tail.

## Design Rule

If a fact, lesson, decision, or operating constraint should influence behavior after the recent handoff window, it must be promoted into the durable markdown retrieval lane.

Put differently:

- `Chronicle bridge` is for recent cross-surface continuity.
- `Canonical markdown memory` is for durable retrieval.
- `PM board` is for bounded work state.
- `Runner ledgers / memos / latest reports` are audit and runtime exhaust, not primary long-term truth.

## Existing Contracts This Plan Finishes

- [system_cohesion_contract.md](/Users/neo/.openclaw/workspace/docs/system_cohesion_contract.md)
- [codex_openclaw_handoff_contract.md](/Users/neo/.openclaw/workspace/docs/codex_openclaw_handoff_contract.md)
- [brain_canonical_memory_sync_contract.md](/Users/neo/.openclaw/workspace/docs/brain_canonical_memory_sync_contract.md)
- [brain_truth_lanes_and_promotion_flow.md](/Users/neo/.openclaw/workspace/docs/brain_truth_lanes_and_promotion_flow.md)
- [chronicle_pm_promotion_boundary.md](/Users/neo/.openclaw/workspace/docs/chronicle_pm_promotion_boundary.md)
- [persistent_memory_blueprint.md](/Users/neo/.openclaw/workspace/docs/persistent_memory_blueprint.md)

## End-State Guarantee

When this plan is complete:

1. meaningful Codex and OpenClaw work lands in Chronicle quickly,
2. durable signal is promoted into markdown memory or knowledge on a predictable schedule,
3. QMD can retrieve that durable signal months later,
4. standups and agent runners can use both recent Chronicle and durable retrieval,
5. git stays clean because runtime exhaust is no longer treated as versioned source.

## Memory Tiers

### Tier 1: Recent bridge memory

Primary file:

- `memory/codex_session_handoff.jsonl`

Purpose:

- preserve recent high-signal work before context loss
- bridge Codex work into OpenClaw jobs
- feed near-term standup and cron reasoning

Constraint:

- do not rely on this lane alone for long-horizon memory

### Tier 2: Durable retrievable memory

Primary files and directories:

- `memory/persistent_state.md`
- `memory/LEARNINGS.md`
- `memory/daily-briefs.md`
- `memory/cron-prune.md`
- `memory/dream_cycle_log.md`
- `memory/YYYY-MM-DD.md`
- `knowledge/**/*.md`
- workspace research markdown such as `workspaces/linkedin-content-os/research/market_signals/*.md`

Purpose:

- preserve durable operating truth
- support QMD retrieval and semantic search
- influence future decisions after recent handoff tail is gone

Rule:

- anything that should matter after 7-30 days must reach this tier

### Tier 3: Runtime exhaust and audit lanes

Typical files:

- `memory/runner-ledgers/**`
- `memory/runner-results/**`
- `memory/runner-memos/**`
- `memory/standup-prep/**`
- `memory/reports/*latest*`
- workspace `briefings/**`
- workspace `memory/execution_log.md`
- generated plans such as `weekly_plan.md`, `reaction_queue.md`, and `social_feed.md`

Purpose:

- support current execution
- provide traceability
- expose latest status to local dashboards

Rule:

- these files must stay on disk at stable paths
- they do not need to be the main durable memory lane
- they should not define long-term memory correctness

## Program Structure

This work should be done in six phases.

Do not skip order.

## Phase 0: Freeze The Contract And Measure The Current Gap

### Goal

Create a baseline so convergence work is verified against actual behavior.

### Tasks

- confirm the live QMD collections remain healthy:
  - `memory-main`
  - `memory-dir-main`
  - `knowledge-main`
- inventory which jobs and runners read:
  - recent Chronicle tail
  - canonical markdown memory
  - PM state
  - automation outputs
- record which important decisions currently live only in `codex_session_handoff.jsonl`
- record which tracked files are pure runtime exhaust

### Deliverables

- a baseline audit note under `docs/`
- a known-good QMD health check result
- a tracked list of hot git-churn paths

### Exit Criteria

- we can point to the exact files used for:
  - recent continuity
  - durable retrieval
  - PM truth
  - runtime exhaust

## Phase 1: Make Chronicle Writes Reliable

### Goal

Ensure important live work always reaches the bridge before context loss.

### Tasks

- standardize Chronicle write triggers for:
  - major decisions
  - blockers
  - completed repairs
  - implementation shifts
  - durable learnings
  - strategy-shaping source conclusions
- require Chronicle writes before context compaction and before significant runner completion
- verify every major runner path appends to the same bridge contract
- keep runner ledgers as audit trails, not substitutes for Chronicle

### Implementation Hooks

- `scripts/append_codex_handoff.py`
- `scripts/sync_codex_chronicle.py`
- runner write-back scripts

### Exit Criteria

- important work no longer depends on one active session history
- recent system truth is consistently visible in `memory/codex_session_handoff.jsonl`

## Phase 2: Promote Durable Signal Out Of Chronicle

### Goal

Guarantee that long-term signal does not die in the recent JSONL tail.

### Tasks

- define promotion classes:
  - `persistent_state`
  - `LEARNINGS`
  - `daily_briefs`
  - `cron_prune`
  - `dream_cycle`
  - `knowledge`
- codify what must be promoted:
  - stable operating constraints
  - repeated lessons
  - worldview and identity signal
  - recurring blockers
  - portfolio and workspace state shifts
  - important source-intelligence digests
- keep PM-worthy work separate from durable memory promotions
- route reviewed Brain signal through the local canonical memory sync worker
- add a promotion checklist to standup and cron flows

### Implementation Hooks

- `scripts/brain_canonical_memory_sync.py`
- `scripts/promote_codex_chronicle.py`
- standup prep generation
- Dream Cycle and Morning Daily Brief prompts

### Exit Criteria

- a months-old important decision can be found in markdown memory even if it is no longer in the recent handoff tail

## Phase 3: Converge Retrieval

### Goal

Make the system use the right retrieval lane for the right kind of memory.

### Tasks

- preserve QMD indexing of markdown memory and knowledge
- keep `.memory-dir-link -> memory` healthy
- add a shared retrieval helper for decision-making flows that need more than the recent handoff tail
- update standup prep and strategic runners to use:
  1. recent Chronicle tail for fresh changes
  2. QMD retrieval for older durable memory
  3. PM board for work truth
- explicitly distinguish:
  - recent context
  - durable retrieved memory
  - live PM state

### Important Clarification

Today some decision paths still read only the recent Chronicle tail.

That is acceptable for short-horizon coordination, but not as the full long-term memory guarantee.

### Exit Criteria

- at least one standup path and one agent-runner path can cite durable retrieved memory older than the recent Chronicle tail

## Phase 4: Converge Standups, PM, And Execution Write-Back

### Goal

Make meetings and execution consume the same unified truth stream.

### Tasks

- standup prep must read:
  - PM board truth
  - recent Chronicle
  - durable markdown memory when relevant
  - latest automation findings
- keep the promotion boundary narrow:
  - Chronicle -> canonical memory -> standup -> PM only when concrete
- require execution results to write back into:
  - PM state
  - Chronicle
  - durable memory when the result contains long-term lessons or state changes
- ensure meaningful meetings leave:
  - transcript
  - dispatch
  - accountability path

### Implementation Hooks

- `scripts/build_standup_prep.py`
- `scripts/promote_codex_chronicle.py`
- `scripts/runners/write_execution_result.py`
- meeting watchdog and dispatch jobs

### Exit Criteria

- the same important signal is visible consistently across memory, standup output, PM recommendation, and execution write-back

## Phase 5: Reduce Git Noise Without Weakening Memory

### Goal

Keep maximum memory effectiveness while making the repository clean enough to work in confidently.

### Policy

- do not move live runtime files in the first cleanup pass
- keep paths stable so existing readers keep working
- reduce noise by changing git tracking, not memory architecture

### Keep Tracked In Phase 1

- code
- docs
- SOPs
- skills
- workspace contracts and charters
- watchlists and persona canon
- core canonical markdown memory:
  - `memory/persistent_state.md`
  - `memory/LEARNINGS.md`
  - `memory/daily-briefs.md`
  - `memory/cron-prune.md`
  - `memory/dream_cycle_log.md`
  - `memory/codex_session_handoff.jsonl`
  - selected daily logs if still desired
- durable research markdown that should influence future work

### Untrack First

- `memory/runner-results/**`
- `memory/runner-memos/**`
- `memory/standup-prep/**`
- `memory/reports/*latest*`
- `memory/reports/*verification*`
- workspace `briefings/**`
- workspace `memory/execution_log.md`
- generated plan outputs that can be rebuilt

### Defer Until After Verification

- broader untracking of workspace research or core memory files
- path migrations
- replacing markdown durable memory with a different store

### Additional Safeguard

- keep milestone or daily snapshot docs that summarize hashes and key excerpts of core canonical memory files
- rely on workspace backups for full local runtime state

### Exit Criteria

- after a normal cron cycle, `git status` remains readable and mostly reflects intentional work rather than runtime exhaust

## Phase 6: Observability, Tests, And Operating Discipline

### Goal

Prove the new memory loop is real and stays real.

### Tests

- QMD alias and freshness checks pass
- a durable memory item older than 30 days is retrievable with QMD
- a standup or runner can reference that durable memory in an output artifact
- a Chronicle-only recent item appears in standup context before promotion
- PM recommendation gating still prevents advisory noise
- backup coverage still includes untracked runtime files

### Dashboards And Reports

- expose QMD alias health
- expose promotion lag
- expose last successful Chronicle write time
- expose last successful durable memory promotion time
- expose PM blocked reasons separately from memory blocked reasons

### Operating Rule

If a signal matters long-term but is still only in:

- recent handoff JSONL, or
- runner exhaust, or
- a latest report file

then the system is not done with that signal yet.

## Recommended Rollout Order

1. Freeze the contract and baseline the current memory loop.
2. Make Chronicle writes reliable everywhere.
3. Make durable promotions explicit and testable.
4. Update one standup path and one runner path to use durable retrieval.
5. Untrack only obvious runtime exhaust.
6. Verify a full daily cycle end to end.
7. Expand cleanup only after the retrieval guarantee is proven.

## Final Acceptance Criteria

This plan is complete only when all of the following are true:

1. Important work is never lost because it stayed only inside one live session.
2. Important long-term signal does not remain only in the recent Chronicle tail.
3. QMD can retrieve durable markdown memory from older periods.
4. Standups and agents can use both recent and durable memory appropriately.
5. PM stays the narrow execution lane instead of becoming a dumping ground.
6. Git remains clean enough that intentional changes are obvious.

## Decision Rule For Future Work

When unsure where something belongs:

- if it is recent and high-signal, write Chronicle
- if it should matter later, promote it into durable markdown memory
- if it is concrete work, bring it through standup into PM
- if it is runtime exhaust, keep it on disk but do not treat it as versioned source
