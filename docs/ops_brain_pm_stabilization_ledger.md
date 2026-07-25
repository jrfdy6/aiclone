# Ops, Brain, Standup, and PM Stabilization Ledger

> Status: active implementation ledger
> Scope: non-destructive stabilization before information-architecture changes
> Governing authority: `SOURCE_OF_TRUTH.md`, `CHARTER.md`, and active SOPs

## Objective

Preserve the AI Clone operating loop while making its state trustworthy and its
surfaces legible:

`Brain interpretation -> standup decision -> PM truth -> workspace execution -> result write-back`

This work does not create a new repository, a second PM system, or a second
standup store.

## Canonical Ownership

| Concern | Canonical owner | Other surfaces may |
| --- | --- | --- |
| Global source interpretation, worldview, Persona, and memory | Brain | Show summaries and deep links |
| Decision ritual, meeting outcomes, and carry-forwards | Standups | Show latest outcome and freshness |
| Executable commitments, approvals, recovery, and completion | PM cards | Show filtered projections and safe actions |
| Project-local artifacts, drafts, and results | Workspace | Report pulse and write-back |
| Portfolio prioritization and system readiness | Ops | Aggregate canonical state without copying it |
| Local automation runtime evidence | Codex run ledger | Mirror verified observations to Railway |

## Preservation Rules

1. Historical PM cards and standups are archived or reclassified, not deleted.
2. Existing source identifiers remain available for traceability.
3. Legacy workspace aliases are normalized in read models before any stored
   record migration is considered.
4. Ops aggregates canonical records; it does not introduce an `ops_decisions`
   lifecycle or shadow status.
5. Brain may propose or route work, but PM remains execution truth.
6. A standup is useful only when it produces a decision, a justified
   carry-forward, an executable PM lane, or an explicit no-action outcome.
7. Read-only health and portfolio endpoints must not repair or mutate state.
8. Persona canon changes continue to require the explicit promotion boundary.

## Observed Production Baseline — 2026-07-25

These counts are point-in-time evidence and should not be hard-coded into the
product.

- At least 200 recent standups were returned by the production API.
- 112 of those recent standups belonged to `shared_ops`.
- The portfolio meeting watchdog reported 10 of 10 required lanes as fresh.
- The PM API returned 237 cards, including 29 active cards.
- 18 active cards still used the legacy `linkedin-os` workspace identity.
- Several active cards referenced expired April scheduling actions or retired
  OpenClaw paths.
- Several cards displayed an active PM status while their execution state was
  failed.
- The executive decision queue returned 95 pending items:
  - 48 email
  - 20 PM
  - 7 standup
  - 10 Persona
  - 6 workspace review
  - 4 Brain signal
- Executive verification was partial because Brain-signal and automation-run
  collectors reached their read caps.
- Portfolio Standup Prep and PM dispatch had recent mirrored evidence.
- Meeting Watchdog, Post-Sync Dispatch, and Accountability Sweep were
  configured but lacked current mirrored run evidence.

## Workspace Identity Normalization

### Canonical identity

- Canonical key: `feezie-os`
- Display label: `FEEZIE OS — Visibility & Distribution`
- Historical aliases include:
  - `linkedin-os`
  - `linkedin-content-os`
  - `linkedin`
  - `feezie`

### Read-model rule

All portfolio, PM, standup, execution, and executive-decision counts must group
historical aliases under `feezie-os`. Raw source values remain visible only in
advanced evidence views.

### Stored-data rule

Do not bulk-rewrite historical PM or standup rows during the UI stabilization
phase. Any future migration must have:

- a dry-run report,
- an explicit record count,
- a reversible mapping artifact,
- post-migration API verification.

## Truth Classification

Every projected work item should expose these independent dimensions:

### Attention

- `needs_owner` — a decision only Feeze can make
- `needs_host` — an external/manual step only the host can perform
- `autonomous` — the system can continue without interruption
- `informational` — useful context, not work

### Execution

- `queued`
- `running`
- `review`
- `blocked`
- `failed`
- `completed`
- `unverified`

### Freshness

Freshness must use the meaningful source timestamp, due date, or execution
transition—not a carry-forward refresh that merely touched `updated_at`.

- `current`
- `aging`
- `stale`
- `expired`
- `unknown`

### Resolution

- `active`
- `superseded`
- `archived`
- `closed`

The UI must not describe a card as simply “in progress” when its current
execution state is failed, blocked, stale, or unverified.

## Standup Quality Contract

A standup should answer:

1. What materially changed?
2. What evidence supports that conclusion?
3. What decision was made?
4. What existing PM lane is carried forward?
5. What new PM work, if any, was justified?
6. Who owns the next move?
7. What result should return to the next standup?

Repeated summaries with no new evidence, decision, carry-forward change, or
explicit no-action outcome should be collapsed into freshness evidence rather
than rendered as another primary transcript.

## Target Product Surfaces

### Ops / Today

- trustworthy readiness strip
- Portfolio Pulse
- at most five ranked `Needs you` decisions
- current standup decisions and commitments
- collapsed work-in-motion summary

### Ops / Projects

Each project card shows:

- project status
- genuine owner decisions
- active PM work
- latest standup and freshness
- current blocker
- latest accepted result
- `Open project`

### Ops / Standups

- current meeting lanes
- latest material decision per lane
- unresolved carry-forward
- PM work created or reused
- output-quality and freshness evidence
- transcript history in a secondary view

### Ops / Execution

- canonical PM board
- explicit attention, execution, freshness, and resolution facets
- workspace and source filters
- recovery lanes separated from owner decisions

### Brain

- sources
- interpretation and review
- briefs
- Persona and canon
- memory
- route status: standup, PM, workspace, memory, or no action

Brain does not own a competing PM board or standup archive.

### FEEZIE OS — Visibility & Distribution

- opens on `Today’s Distribution`
- Create: at most two ranked actions
- Engage: at most three ranked actions
- every action includes source, prepared copy, destination, selection reason,
  and `Use it`, `Edit it`, `Not for me`
- project pulse shows latest standup, active PM work, current execution, and
  latest accepted result

Relationship intelligence remains planned until the system has a grounded
contact, organization, interaction, and follow-up model.

## Implementation Sequence

### Phase 1 — Preserve and reconcile

- [x] Record the observed baseline and preservation rules.
- [ ] Ensure the executive queue implementation is tracked intentionally.
- [x] Reconcile repository registry, runtime registry, and UI labels.
- [x] Normalize legacy workspace aliases in shared read models.

### Phase 2 — Stabilize truth

- [x] Add side-effect-free PM and execution reads.
- [x] Add attention, execution, freshness, and resolution classification.
- [x] Detect expired host actions and legacy-path instructions.
- [x] Distinguish configured automation from observed automation.
- [x] Repair standup and PM deep links.
- [x] Gate Today by freshness so stale Gmail, Persona, Brain, and standup residue remains in the backlog without masquerading as current executive work.

### Phase 3 — Shared contracts

- [x] Add a readiness contract with healthy, watch, and degraded states.
- [x] Add a registry-driven Portfolio Pulse contract.
- [x] Add standup outcome quality, freshness, and PM linkage summaries.

### Phase 4 — Product restructuring

- [x] Restructure Ops into Today, Projects, Standups, Execution, and System.
- [x] Simplify Brain around global intelligence and downstream routing.
- [x] Make FEEZIE open on Today’s Distribution.
- [x] Add consistent project pulse navigation to full workspaces.

### Phase 5 — Verification and release

- [x] Backend tests.
- [x] Frontend tests, type checking, and production build.
- [x] Authenticated browser verification.
- [ ] Production canaries.
- [ ] Deploy only after the live API and UI agree on counts and status.

## Destructive-Action Gate

No historical PM card, standup, source asset, Persona delta, or workspace
artifact may be deleted or bulk-rewritten under this ledger without a separate
review of exact targets and a recoverable migration plan.
