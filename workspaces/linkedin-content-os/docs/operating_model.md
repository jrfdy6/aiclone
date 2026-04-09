# FEEZIE OS Operating Model

## Purpose

`FEEZIE OS` is the public-facing operating system for Feeze's visibility, starting with LinkedIn and expanding over time into a broader personal-brand and career-positioning lane.

It exists to turn lived work into trustworthy public signal without drifting into generic posting or fake founder performance.

## Core Rule

Persona truth first, posting second.

If a signal does not strengthen trust, clarify lived work, or support the long-term career and brand arc, it should not become public output.

## What Feeds The Lane

The lane should prioritize inputs in this order:

1. lived work and current operating reality
2. source signals and reactions worth responding to
3. canonical persona truth and story assets
4. backlog items and existing draft fragments
5. blank-page ideation only when stronger signal is absent

### Signal Intake Sources (working list)
- `memory/codex_session_handoff.jsonl` Chronicle entries tagged to `feezie-os`
- Daily/context flushes captured in `memory/YYYY-MM-DD.md`
- Workspace snapshot overlays exposed through `/ops` (`source_assets`, `reaction_queue`, `persona_review_summary`)
- Topic Intelligence and watchlists under `research/topic_intelligence/` and `research/watchlists.yaml`
- Saved LinkedIn / RSS / Reddit signals routed into `plans/reaction_queue.{md,json}`
- Persona canon (`knowledge/persona/feeze/**`) plus bundle deltas awaiting promotion
- Owner interviews (voice notes, standup deltas) summarized into `memory/execution_log.md` or `workspaces/linkedin-content-os/briefings/`

## Latest Validation Snapshot

- Accountability sweeps should reference `docs/operating_rhythm_status_2026-04-08.md`, which maps each stage in this model to concrete April 8 artifacts (weekly plan, reaction queue, draft queue, owner review packet, and scheduled retro slot).
- Append a new `operating_rhythm_status_YYYY-MM-DD.md` entry whenever the rhythm is re-validated so future cards can prove compliance without re-scrolling the entire workspace.

## Weekly Rhythm

### 1. Intake

- **Window:** Mondays 09:00–11:00 ET for the formal sweep, plus light-weight capture each morning.
- **Owner:** Jean-Claude (capture + triage) with Feeze adding lived context.
- **Inputs:** Chronicle, context flushes, `/ops` snapshot, Topic Intelligence, saved signals, persona canon updates.
- **Actions:**
  - Pull new signals into `plans/weekly_plan.md` under an "Intake" heading.
  - Append raw candidate bullets to `backlog.md` (unscored) and flag duplicates.
  - File net-new operating lessons into `memory/YYYY-MM-DD.md` so Chronicle can reference them.
- **Outputs:** timestamped intake bullets + evidence links with lane tags (`current-role`, `ai`, etc.).

### 2. Interpretation

- **Window:** Mondays 13:00–15:00 ET (immediately after Intake) and ad hoc when high-signal events hit midweek.
- **Owner:** Jean-Claude for classification; Feeze sanity-checks belief statements.
- **Actions:**
  - Label each intake item with lane, belief stance, and response mode inside `plans/reaction_queue.md`.
  - Decide whether the signal fuels comments, reposts, post seeds, or belief evidence only.
  - Drop low-signal items into an "archive" section to avoid recirculating vague ideas.
- **Outputs:** ranked interpretation list with `lane`, `stance`, `response_mode`, and `next action` columns.

### 3. Backlog

- **Window:** Tuesdays 10:00–12:00 ET.
- **Owner:** Jean-Claude curates; Feeze reviews if prioritization touches sensitive initiatives.
- **Actions:**
  - Convert the top interpretation items into backlog cards inside `backlog.md` and `drafts/queue_01.md`.
  - Attach proof references (doc paths, metrics, names) so drafting never hunts for evidence.
  - Note whether each backlog item targets comment, repost, or post slot.
- **Outputs:** prioritized backlog block with proof links and clear "Definition of Done" per idea.

### 4. Drafting

- **Window:** Wednesdays 09:00–14:00 ET and Thursday mornings if an additional slot is needed.
- **Owner:** Jean-Claude drives the workspace draft process; Feeze is the reviewer, not the drafter.
- **Actions:**
  - Pull 1–2 backlog items into active drafts under `drafts/feezie-00X_*.md`.
  - Record hook, takeaways, proof bullets, and CTA for each piece.
  - Update `drafts/queue_01.md` with the status (`drafting`, `owner-review-ready`).
- **Outputs:** owner-review-ready Markdown drafts plus supporting notes or screen captures when helpful.

### 5. Approval

- **Window:** Thursdays 15:00–17:00 ET (live or async) with emergency approvals as needed.
- **Owner:** Feeze approves; Jean-Claude prepares review packets.
- **Actions:**
  - Bundle each draft into a short review packet (context paragraph + link) inside `/workspaces/linkedin-content-os/drafts/` and, if needed, `briefings/`.
  - Record the approval decision in `memory/execution_log.md` and tag the PM card if it unblocks downstream work.
  - If rejected, capture why and feed it back into backlog criteria.
- **Outputs:** explicit owner approval or revision notes; updated draft status (`approved`, `revise`, `park`).

### 6. Review

- **Window:** Fridays 11:00–12:00 ET.
- **Owner:** Jean-Claude leads the retro; Feeze joins for narrative/brand adjustments.
- **Actions:**
  - Capture wins + misses in `memory/YYYY-MM-DD.md` and update `analytics/` once post data exists.
  - Decide which drafts roll over, which signals return to backlog, and which enter persona canon.
  - Update PM + Chronicle if the cadence exposed structural blockers.
- **Outputs:** retro notes, backlog adjustments, and a ready-to-go intake checklist for the next Monday.

### Weekly Cadence Timeline (signal → approval)
| Day (ET) | Focus | Primary Owner | Key Inputs | Required Outputs |
| --- | --- | --- | --- | --- |
| Monday AM | Intake sweep | Jean-Claude | Chronicle, `/ops`, Topic Intelligence, saved reactions | Updated `plans/weekly_plan.md` intake section + raw backlog bullets |
| Monday PM | Interpretation & routing | Jean-Claude + Feeze for belief checks | Intake notes, persona canon | Ranked interpretation list + `plans/reaction_queue.md` updates |
| Tuesday AM | Backlog promotion | Jean-Claude | Interpretation list, proof artifacts | Updated `backlog.md` + `drafts/queue_01.md` with lanes/proof |
| Wednesday | Drafting block | Jean-Claude | Prioritized backlog, persona files | Owner-review-ready drafts under `drafts/` + status notes |
| Thursday PM | Owner review & approval | Feeze (approver) + Jean-Claude (facilitator) | Draft packets, supporting artifacts | Approval/changes recorded in `memory/execution_log.md` + statuses toggled |
| Friday Midday | Retro & rollover | Jean-Claude + Feeze | Analytics, approval outcomes | Retro notes, backlog refresh, PM/Chronicle updates |

### Approval & Logging Guardrails
- Every approved or rejected draft must be logged in `memory/execution_log.md` and, when tied to a PM card, recorded via `scripts/runners/write_execution_result.py` so the PM board mirrors reality.
- If a draft moves to final polish, note it in the PM card comments and mark the backlog entry as consumed to prevent duplicate work.
- Chronicle entries should summarize cadence health weekly so accountability sweeps can trace whether intake → approval actually happened.

### Retro + Carry-Forward Checklist
- Close the week only after the Friday retro produces:
  - an updated backlog order,
  - a short retro paragraph in the daily log,
  - explicit owner decisions on each draft.
- Anything still waiting on approval by Friday rolls into the next Monday intake with a "carry" tag so it is reviewed before new ideas.

## Immediate 30-Day Focus

The first operating window should focus on:

1. defining the weekly rhythm from intake to approval
2. seeding a real backlog from canonical persona and lived work
3. creating the first draft queue with explicit approval gating

These are the first concrete PM-worthy moves because they create the minimum repeatable loop without forcing public output too early.

## PM Boundary

Use PM cards when the next step is concrete and bounded, for example:
- define the weekly operating rhythm
- seed the first backlog
- build the first draft queue

Do not create PM cards for:
- vague posting aspirations
- generic “be more visible” goals
- advisory statements that still need interpretation

## Standup Role

`Neo`, `Jean-Claude`, and `Yoda` should interpret strong public-facing signals together in FEEZIE standups:

- `Yoda`: does this strengthen the long-term story and North Star?
- `Neo`: how does this affect the larger system and adjacent lanes?
- `Jean-Claude`: what should be operationalized now inside FEEZIE OS?

Execution remains direct under `Jean-Claude` for this lane.

## Success Markers

The lane is on track when:
- source intake is regular instead of ad hoc
- backlog items come from real work and real signal
- drafts sound recognizably Feeze
- approval is explicit
- public output starts supporting a coherent career and brand narrative
