# Autonomous Meeting System Contract

This document captures the best-practice meeting pattern we want to adopt for the OpenClaw + Codex system.

It is based on:
- the Boot Camp / Clear Mud meeting pattern
- the transcript notes reviewed on `2026-03-31`
- screenshot references on the Desktop from `2026-03-31`

Primary visual references:
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.23.50 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.25.23 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.26.00 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.26.52 PM.png`

## 1. Core principle

Meetings must be:
- real
- grounded
- autonomous
- accountable

They must not become vanity rituals.

If a meeting happens, its action items must move down the pipeline.

## 2. What makes a meeting real

A real meeting is not:
- one model pretending to be three agents
- one shared memory pretending to be multiple viewpoints
- consensus generated from a single synthetic conversation

A real meeting requires:
- separate agents
- separate workspaces
- separate identity packs
- separate memory lanes
- separate backlog or PM context
- independent reports that can disagree

For this project that means:
- `Neo`
- `Jean-Claude`
- `Yoda`
- later each workspace-specific operator

Every workspace agent must stay inside its own workspace lane.

## 3. Ground truth rules

1. PM board is the source of truth for work.
2. Live data should beat stale memory files whenever real metrics or real board state exist.
3. Cron prompts should point to skills/contracts, not duplicate them.
4. Meetings must have at least three rounds:
   - status
   - analysis
   - commitments / resolution
5. Every meeting must leave a transcript.
6. Every meeting should have a watchdog.

## 4. Required meeting flow

The intended flow is:

1. meeting cron fires
2. context is loaded
3. real agents are spawned in parallel
4. reports are collected with bounded waiting
5. cross-agent analysis happens
6. transcript is compiled
7. transcript is delivered to a mobile-friendly surface
8. meeting dashboard is updated
9. post-sync dispatch parses commitments into PM work
10. accountability sweep makes sure the work actually moves

For this system:
- the mobile-friendly delivery surface should be `Discord`, not Telegram
- the transcript is the canonical meeting artifact
- delivery should remain transcript-only
- no audio generation is required
- outside source material should be ingested as digests, not dropped into meetings as raw files

## 5. Meeting types

### Daily executive sync
- purpose: daily executive coordination
- participants: `Jean-Claude`, `Neo`, `Yoda`
- source of truth:
  - PM board slice first
  - Chronicle
  - pruning cycles
  - OpenClaw maintenance outputs
  - recent runner results
  - source-intelligence digests when they change strategic or portfolio direction
- output:
  - decisions
  - owners
  - PM mutations
  - transcript

### Workspace sync
- purpose: workspace execution review
- participants:
  - `Jean-Claude`
  - relevant workspace agent
  - optional `Neo` / `Yoda` only when needed
- source of truth:
  - workspace PM slice
  - workspace artifacts
  - workspace execution log
  - latest SOP / briefing
  - workspace-relevant source-intelligence digests when they are strong enough to change local execution
- output:
  - workspace commitments
  - execution changes
  - transcript

### Weekly review
- purpose: retrospective + next-week planning
- cadence: weekly
- source of truth:
  - PM board outcomes from the week
  - meeting transcripts from the week
  - major runner outputs
  - major automation outcomes
  - approved source-intelligence digests from the week
- output:
  - what completed
  - what slipped
  - what rolls forward
  - strategic adjustments for the next week

### Saturday vision sync
- purpose: long-horizon thinking
- cadence: weekly on Saturday
- participants: `Jean-Claude`, `Neo`, `Yoda`
- focus:
  - Johnnie
  - long-term goals
  - `FEEZIE OS`
  - brand / career direction
  - strategic leverage
  - source-intelligence digests from relevant videos, screenshots, and transcripts
- rule:
  - no routine PM hygiene
  - no shallow operational churn
  - PM mutations should happen only if the strategic conclusion clearly deserves to become real work

## 6. Watchdog pattern

Every important meeting should have a watchdog cron roughly 30 minutes later.

Watchdog responsibility:
- check whether the meeting produced a transcript
- check whether the transcript is non-trivial
- alert if missing
- optionally re-trigger the meeting

Watchdogs protect against:
- machine restarts
- runtime failures
- stale schedulers
- silent no-op meeting runs

## 7. Post-sync dispatch

After the meeting:
- parse the transcript
- extract commitments
- determine who committed to what
- determine expected deadline / timing when possible
- create or update PM cards
- route work by autonomy tier

Autonomy tiering should remain explicit:
- ships autonomously
- needs review
- human only

For this system:
- anything front-facing, public, or human-response-oriented should default to human review

## 8. Accountability sweep

Meetings alone are not enough.

An accountability sweep should run after the post-sync dispatch and verify:
- commitments became PM cards
- PM cards moved
- assigned work was picked up
- blocked work is visible
- nothing important went stale

The sweep should:
- push stuck work back into visibility
- escalate stale items
- keep the meeting layer from becoming theater

## 9. Meeting dashboard requirements

The meeting system should prioritize practical planning views:

### List view
- chronological list of meetings
- transcript preview
- speaker-colored or clearly separated dialogue

### Weekly view
- 7-day meeting grid
- meeting type color coding
- planned vs completed visibility

### Monthly view
- calendar overview
- dots / counts per day
- click into day-level meetings

These are organizational views of the same meeting truth and cron history.

They are not separate planning systems.

## 10. Mapping to this project

### Already in place
- typed standup lanes
- PM-board-first executive standup payload
- standup transcripts stored as payload discussion rounds
- `Jean-Claude`, `Neo`, and `Yoda` meeting roles
- workspace delegation model
- PM card creation from standup promotion

### Still missing
- true autonomous multi-agent meeting orchestration
- watchdog cron per meeting
- post-sync dispatch
- accountability sweep
- transcript parsing into commitments
- weekly review automation
- Saturday vision sync automation
- practical list / weekly / monthly meeting views
- Discord transcript delivery rules

## 11. Implementation order

1. Keep the PM-first executive standup contract.
2. Add meeting types:
   - weekly review
   - Saturday vision sync
3. Build meeting watchdogs.
4. Build post-sync dispatch.
5. Build accountability sweep.
6. Build transcript-backed dashboard views.
7. Keep delivery transcript-only unless requirements change later.

## 12. Non-negotiables

1. PM board stays the work truth.
2. Meetings must operate on real data, not stale theater.
3. Separate agents need separate workspaces and identity packs.
4. Every meeting needs a transcript.
5. Every important meeting needs a watchdog.
6. Every meeting pipeline needs dispatch plus accountability.
7. Strategy meetings should not dissolve into shallow task churn.

## 13. Bottom line

The target system is:

real autonomous meetings -> transcript -> PM dispatch -> accountability sweep -> real movement

That is the standard we should now build toward.
