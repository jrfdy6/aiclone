# AI Clone System Architecture

Last reviewed: 2026-04-23

Primary source files for this map:
- `backend/app/main.py`
- `frontend/app/page.tsx`
- `frontend/components/NavHeader.tsx`
- `frontend/app/ops/page.tsx`
- `frontend/app/ops/OpsClient.tsx`
- `backend/app/routes/workspace.py`
- `backend/app/services/workspace_snapshot_service.py`
- `backend/app/services/workspace_registry_service.py`
- `backend/app/services/open_brain_db.py`
- `backend/app/services/automation_service.py`
- `docs/aiclone_brain_architecture.md`
- `docs/system_cohesion_contract.md`
- `docs/brain_truth_lanes_and_promotion_flow.md`

What this repo is, in one sentence:

AI Clone is now a hybrid system with two overlapping planes:
1. a product plane for knowledge, prospects, topic intelligence, and content generation
2. an operating-system plane for Ops, Brain, PM, standups, workspace OSs, and local automations

========================================================================
1. TOP-LEVEL SYSTEM MAP
========================================================================

                              +-----------------------+
                              |   External Inputs     |
                              |-----------------------|
                              | uploads / drive       |
                              | youtube / rss / web   |
                              | user actions / review |
                              +-----------+-----------+
                                          |
                                          v
+------------------------------------------------------------------------+
| Local workers + ingestion                                               |
| `scripts/*.py`, launchd jobs, OpenClaw cron, workspace runners          |
| - daily briefs / memory sync / standup prep / watchdogs                 |
| - source fetch / youtube ingest / FEEZIE content refresh                |
+-----------------------------+-------------------------------+------------+
                              |                               |
                              v                               v
+-----------------------------+-------------------------------+------------+
| Durable state                                                            |
|                                                                          |
| Filesystem (repo truth)                                                  |
| - `memory/`        canonical operating memory                            |
| - `knowledge/`     persona, transcripts, source intelligence             |
| - `docs/`          contracts, runbooks, architecture                     |
| - `workspaces/*/`  bounded workspace state                               |
|                                                                          |
| Postgres / Open Brain DB                                                 |
| - `knowledge_capture`, `memory_vectors`, `persona_deltas`                |
| - `pm_cards`, `standups`, `daily_briefs`, `workspace_snapshots`          |
| - `build_reviews`, `brief_reactions`, `session_metrics`                  |
|                                                                          |
| Firestore                                                                |
| - `knowledge_docs`, `prospects`, `topic_intelligence`                    |
| - still used by part of the original product plane                       |
+-----------------------------+-------------------------------+------------+
                              |                               |
                              v                               v
+-----------------------------+-----------------+   +----------------------+
| Backend API (FastAPI)                         |   | Background services   |
| `backend/app/main.py`                         |   | `backend/app/services`|
|-----------------------------------------------|   |----------------------|
| Brain / Open Brain / Persona                  |   | workspace snapshots   |
| PM Board / Standups / Workspace snapshots     |   | PM orchestration      |
| Automations / Briefs / Timeline / Email ops   |   | standup promotion     |
| Knowledge / Prospects / Topic Intelligence    |   | automation registry   |
| Content generation / Lab / Build reviews      |   | social feed refresh   |
+-----------------------------+-----------------+   +-----------+----------+
                              |                                 |
                              +---------------+-----------------+
                                              |
                                              v
+------------------------------------------------------------------------+
| Frontend runtime surfaces (Next.js)                                     |
| - `/ops`       Mission Control, PM, workspaces, docs                    |
| - `/brain`     review queue, control plane, memory/docs visibility      |
| - `/workspace` live FEEZIE workspace                                    |
| - `/lab`       experiments + quality loops                              |
| - `/prospect-discovery`, `/outreach`, legacy product pages              |
+------------------------------------------------------------------------+

========================================================================
2. THE TWO BIG PLANES
========================================================================

OPERATING-SYSTEM PLANE
- current control center
- driven by `/ops`, `/brain`, `/workspace`, `/lab`
- centered on PM truth, standups, workspace snapshots, memory, automations

PRODUCT PLANE
- original AI Clone application surface
- centered on knowledge retrieval, prospecting, topic intelligence, content generation
- still present and partly live, but no longer the main runtime shell

Practical rule:
- if the change affects how the system thinks, coordinates, or routes work, it is in the operating-system plane
- if the change affects prospecting, knowledge search, or output generation for end users, it is in the product plane

========================================================================
3. THE FOUR TRUTH LAYERS
========================================================================

1. Identity / persona canon
   Paths: `knowledge/persona/feeze/**`
   Services: persona delta + promotion services
   Purpose: who Johnnie/FEEZIE is and how the system should speak

2. Canonical operating memory
   Paths: `memory/**`
   Purpose: current truth, learnings, Chronicle bridge, briefs, durable state

3. Execution truth
   Store: Postgres tables `pm_cards` + `standups`
   Purpose: what work exists, who owns it, what is blocked, what is done

4. Workspace-local truth
   Paths: `workspaces/*/**`
   Purpose: bounded state for FEEZIE, Fusion, Easy Outfit, AGC, and other lanes

Default motion of signal:

`source -> review/digest -> memory/standup -> PM/workspace execution`

Not:

`source -> direct canon/task without interpretation`

========================================================================
4. LIVE OPERATING LOOP
========================================================================

External signal or user action
    -> script or API ingest
    -> files and/or DB records change
    -> snapshot/control-plane services read latest state
    -> Ops / Brain / Workspace surfaces display it
    -> standup or PM decision is made
    -> runner / workspace agent / operator executes
    -> result writes back into PM + memory + workspace artifacts

Codex/OpenClaw bridge:
- `memory/codex_session_handoff.jsonl`
- Brain maintenance jobs and standups are expected to read this before acting

========================================================================
5. WORKSPACE MODEL
========================================================================

`shared_ops`
- executive lane
- cross-workspace interpretation and portfolio follow-through

`feezie-os`
- only live workspace with a first-class runtime surface
- aliases include `linkedin-os` and `linkedin-content-os`
- route: `/workspace`

`fusion-os`, `easyoutfitapp`, `ai-swag-store`, `agc`
- standing up as delegated workspace lanes
- represented in the registry, docs, and file structure
- not as live in the UI as FEEZIE yet

Common workspace shape:

`workspaces/<workspace>/`
  `docs/`
  `briefings/`
  `dispatch/`
  `memory/`
  `analytics/`
  `standups/`
  `agent-ledgers/`

FEEZIE adds more execution-specific folders:
- `drafts/`
- `plans/`
- `research/`
- `content_bank/`
- `reports/`

========================================================================
6. REPO MAP: WHAT PART OF THE SYSTEM AM I IN?
========================================================================

If you are in...

- `frontend/app/ops/**`
  You are changing Mission Control, docs ordering, PM/ops visibility, or workspace drill-down.

- `frontend/app/brain/**`
  You are changing Brain review, control-plane visibility, or memory/doc reading.

- `frontend/app/workspace/**`
  You are changing the live FEEZIE execution surface.

- `backend/app/routes/**`
  You are changing the HTTP contract.

- `backend/app/services/**`
  You are changing the real orchestration and business logic.

- `scripts/**`
  You are changing local automations, launchd jobs, cron-fed flows, or runners.

- `memory/**`
  You are changing canonical operating memory.

- `knowledge/**`
  You are changing persona canon, transcripts, or source-intelligence assets.

- `workspaces/**`
  You are changing bounded workspace execution state.

- `docs/**`
  You are changing human-readable contracts and system models.

========================================================================
7. ACTIVE VS LATENT CODE
========================================================================

This repo is large enough that filename presence is not the same as runtime truth.

Current scale snapshot from the repo audit:
- 55 backend route files
- 113 backend service files
- 79 top-level automation/helper scripts
- 7 workspace roots

Important:
- `frontend/app/page.tsx` redirects home to `/ops`
- Ops is the runtime homepage
- `backend/app/main.py` is the live route mount list
- some older product pages and route files still exist, but are not the operating center

When in doubt, trust these first:
- `backend/app/main.py`
- `frontend/app/page.tsx`
- `frontend/components/NavHeader.tsx`
- `frontend/app/ops/OpsClient.tsx`
- `backend/app/routes/workspace.py`
- `backend/app/services/workspace_snapshot_service.py`
- `backend/app/services/workspace_registry_service.py`

========================================================================
8. FAST ORIENTATION BY GOAL
========================================================================

Goal: "I need the docs / PM / Ops view to change"
  Start in `frontend/app/ops/OpsClient.tsx`
  Then check `frontend/app/ops/page.tsx`
  Then `backend/app/routes/workspace.py`
  Then `backend/app/services/workspace_snapshot_service.py`

Goal: "I need Brain to notice, review, or route a new signal"
  Start in `backend/app/routes/brain.py`
  Then `backend/app/services/brain_signal_*.py`
  Then `frontend/app/brain/**`

Goal: "I need execution or owner workflow behavior to change"
  Start in `backend/app/routes/pm_board.py`
  Then `backend/app/routes/standups.py`
  Then `backend/app/services/pm_card_service.py`
  Then `backend/app/services/standup_service.py`

Goal: "I need a local automation or background job"
  Start in `scripts/**`
  Then `backend/app/services/automation_service.py`
  Then `/ops` and `/automations`

Goal: "I need FEEZIE content/workspace behavior"
  Start in `workspaces/linkedin-content-os/**`
  Then workspace/social-feed services
  Then `frontend/app/workspace/**`

Goal: "I need search / knowledge / prospects / topic intelligence behavior"
  Start in `backend/app/routes/knowledge.py`
  Then `prospects.py`, `topic_intelligence.py`, `content_generation.py`
  Check Firestore and local-store dependencies

========================================================================
9. SIMPLE MENTAL MODEL
========================================================================

Think of AI Clone as three stacked machines:

[1] Signal machine
    collects source material, user actions, and automation output

[2] Interpretation machine
    Brain, standups, PM, persona review, workspace snapshots

[3] Execution machine
    workspace agents, local scripts, content generation, manual operator work

Most bugs come from breaking the handoff between those machines,
not from one component being wrong in isolation.

========================================================================
10. MISSION CONTROL DOCS FEED
========================================================================

Mission Control's Docs tab is fed by two paths:
- server bootstrap: `frontend/app/ops/page.tsx`
- live snapshot refresh: `backend/app/services/workspace_snapshot_service.py`

This file is intentionally pinned first in both paths so the architecture map
stays at the top of the Docs tab in Mission Control.

========================================================================
11. DETAILED TRANSFORMATION FLOWS
========================================================================

FLOW A: External source -> digest -> coordination -> action

`raw source asset`
  -> source-intelligence digest / normalized signal
  -> Brain review or standup input
  -> canonical memory promotion when durable
  -> PM card / workspace task / advisory note when the next step is clear

Rules:
- external source material is upstream signal, not canonical truth by default
- the normal first route is memory + standup
- direct `source -> PM truth` is only valid when ownership and next action are already obvious
- direct `source -> persona canon` is only valid when the signal really changes identity, voice, story, or worldview

FLOW B: Codex/OpenClaw live work -> Chronicle -> maintenance -> PM/standup

`live work session`
  -> high-delta Chronicle chunk in `memory/codex_session_handoff.jsonl`
  -> brain-maintenance cron read
  -> daily brief / persistent-state / learnings updates
  -> standup and PM read the shared memory loop
  -> next-step assignment, escalation, or durable promotion

Rules:
- Chronicle is the bridge between live work and the rest of the system
- PM and standups should not depend on one session's memory
- runner ledgers are audit trails, not canonical memory

FLOW C: Persona promotion

`signal`
  -> persona delta
  -> review queue
  -> promotion fragments
  -> target canon file
  -> bundle sync / grounded content retrieval

Common targets:
- `knowledge/persona/feeze/identity/claims.md`
- `knowledge/persona/feeze/identity/VOICE_PATTERNS.md`
- `knowledge/persona/feeze/identity/decision_principles.md`
- `knowledge/persona/feeze/history/story_bank.md`

Rules:
- persona canon is a downstream identity lane
- not every strong signal belongs in canon
- canon should change only when the system should remember a lasting identity-level truth

FLOW D: PM truth -> queue -> runner -> artifact -> writeback

`pm_cards`
  -> execution queue entry
  -> execution packet / briefing / SOP reference
  -> runner / workspace agent execution
  -> workspace artifact or report
  -> PM status + result summary + memory promotion writeback

Rules:
- PM board is the truth for work state
- execution should move through queue and packet state, not hidden side channels
- results should write back into PM + memory + workspace artifacts

FLOW E: Execution result -> memory -> operator story -> public-safe lesson -> post context

`execution result`
  -> Chronicle + `memory/LEARNINGS.md` + `persistent_state.md`
  -> `operator_story_signals`
  -> `content_safe_operator_lessons`
  -> content-generation context / future post draft

Rules:
- architecture or systems work should not die inside a completed PM card
- if the execution produced a durable lesson, it should become a canonical learning
- raw memory should be distilled before it becomes content context
- the content bank is a separate latent-idea banking loop, not the direct writeback target for execution results
- public-facing lessons should stay grounded in execution proof, not generic inspiration

FLOW F: Repo change -> push -> deploy -> live Mission Control

`local edit`
  -> commit
  -> push
  -> staged Railway deploy
  -> live frontend/backend runtime
  -> snapshot/UI verification

Rules:
- local git state is not the same as live runtime
- GitHub being updated is still not the same as production
- Mission Control shows what the deployed frontend/backend are serving

========================================================================
12. TRUTH / OWNERSHIP MATRIX
========================================================================

1. Brain signal / review object
   Canonical for:
   upstream interpretation candidates
   Writers:
   source intelligence, workspace execution, Chronicle, cron outputs, owner reactions
   Readers:
   Brain review, standups, Neo, Jean-Claude, Yoda
   Promotes to:
   canonical memory, persona canon, PM truth, advisory notes
   Boundary:
   should not jump straight to canon or PM without interpretation

2. Persona canon
   Canonical for:
   identity, voice, stories, principles, content posture
   Writers:
   persona delta review and promotion flow
   Readers:
   Brain, content generation, workspace writing surfaces, bundle sync
   Promotes to:
   grounded content retrieval and persona bundles
   Boundary:
   should not absorb every interesting signal

3. Canonical memory
   Canonical for:
   current truth, learnings, state changes, Chronicle bridge
   Writers:
   Chronicle writes, memory sync, brain-maintenance jobs, durable promotions
   Readers:
   standups, PM promotion logic, daily briefs, system operators
   Promotes to:
   PM truth, docs, standup prep, operating context
   Boundary:
   should not become a second backlog or a dump of raw source material

4. PM truth
   Canonical for:
   work state, ownership, blockers, execution lifecycle
   Writers:
   PM services, standup dispatch, execution writeback, operator review
   Readers:
   Mission Control PM board, standups, runners, workspace agents
   Promotes to:
   execution queue entries, packets, accountability state
   Boundary:
   should not rely on off-board memory to know what work exists

5. Workspace-local truth
   Canonical for:
   bounded execution context in a specific workspace
   Writers:
   workspace runners, local agents, drafts, analytics, dispatch artifacts
   Readers:
   workspace UI, Brain exchange, standups, local operators
   Promotes to:
   Brain signals, PM updates, reports, public outputs
   Boundary:
   should not silently replace shared PM truth or global canonical memory

6. Operator story / public-safe lessons
   Canonical for:
   distilled internal lessons that downstream content can safely reuse without reading raw memory or exposing internal mechanics
   Writers:
   operator-story distiller, content-safe lesson distiller, synced memory reports
   Readers:
   content generation context, Brain snapshots, future drafting lanes, operators reviewing build-story signals
   Promotes to:
   public-safe claims, proof packets, story beats, and grounded post context
   Boundary:
   should not be treated as final post copy or as a direct mutation of the content bank; it is the bridge between internal memory and future content use

7. Live deployed runtime
   Canonical for:
   what users actually see right now
   Writers:
   Railway frontend/backend deploys
   Readers:
   operators, live UI surfaces, snapshot consumers
   Promotes to:
   production verification confidence
   Boundary:
   should not be confused with local git state or an unshipped fix
