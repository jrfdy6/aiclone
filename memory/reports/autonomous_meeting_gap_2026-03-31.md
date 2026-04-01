# Autonomous Meeting Gap Report

Date: `2026-03-31`

## Reference source

This gap read is based on:
- Boot Camp / Clear Mud meeting transcript notes reviewed today
- Desktop screenshots from `2026-03-31`

Key screenshot references:
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.23.50 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.25.23 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.26.00 PM.png`
- `/Users/neo/Desktop/Screenshot 2026-03-31 at 5.26.52 PM.png`

## What is aligned now

- Executive standups are now PM-board-first instead of artifact-first.
- Executive standups now store:
  - agenda
  - PM snapshot
  - discussion rounds
  - decisions
  - owners
- `Jean-Claude`, `Neo`, and `Yoda` are all present in the executive meeting layer.
- Workspace execution still routes through `Jean-Claude` into workspace agents.
- PM board remains the work truth.
- New meeting placeholders now exist for:
  - `Weekly Review`
  - `Saturday Vision Sync`

## What is still missing

### 1. Real autonomous meeting orchestration

Current state:
- the standup contract is stronger
- the transcript rounds are still synthesized from the prep packet

Missing:
- true spawned parallel meeting participants
- bounded wait/collect behavior for reports
- transcript assembled from genuinely separate reports

### 2. Meeting watchdogs

Current state:
- cron watchdog is a known system pattern
- meeting-specific watchdogs are not fully implemented

Missing:
- watchdog per important meeting
- transcript existence checks
- transcript-size / non-trivial-output checks
- auto-retry or alert path

### 3. Post-sync dispatch

Current state:
- standup promotion can create PM cards

Missing:
- transcript parsing for commitments
- extraction of:
  - who committed
  - what they committed to
  - deadline / timing
- autonomy-tier routing

### 4. Accountability sweep

Current state:
- PM board exists
- execution queue exists

Missing:
- cron or runner that checks whether meeting commitments actually moved
- stale commitment escalation
- no-vanity-meeting enforcement

### 5. Meeting dashboard views

Current state:
- the Ops page shows standup rooms and transcripts

Missing:
- list view
- weekly calendar view
- monthly view
- stronger calendar/list visibility over meeting runs and cron-backed syncs

### 6. Mobile-first transcript delivery

Current state:
- Discord is active in the system

Missing:
- explicit meeting transcript delivery contract to mobile
- per-meeting delivery rules

Resolved decisions:
- `Saturday Vision Sync` stays strategy-only by default
- mobile delivery is `Discord transcript-only`
- no audio generation is needed
- no conference-room / immersive playback view is needed

## Recommended build order

1. Keep the PM-first standup payload.
2. Build meeting watchdogs.
3. Build post-sync dispatch.
4. Build accountability sweep.
5. Build transcript/mobile delivery.
6. Build practical list / weekly / monthly meeting views.

## Design rules to keep

1. PM board is ground truth.
2. Meetings should point to skills/contracts, not duplicate them.
3. Live metrics should beat stale memory when available.
4. Minimum three rounds.
5. Every important meeting gets a watchdog.
6. Strategy syncs should not devolve into routine PM churn.

## Remaining design question

1. Which meeting types should be daily versus weekly on day one of rollout?
