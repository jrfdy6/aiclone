# AGC Execution Lane

AGC executes one recurring business loop:

Signal -> Positioning -> Capability -> Surface -> Inbound Email -> Qualified Conversation -> Capture

Automation, PM cards, SOPs, and write-back exist to support this loop.
They are not the loop itself.

## Purpose

Turn credible market and procurement signal into qualified inbound conversations and clearer capture moves without letting the lane drift into unsupported consulting claims.

## Lane Responsibilities

- Capture opportunity signal from agencies, prime contractors, and adjacent buyers
- Turn signal into clearer AI consulting positioning
- Build or refine capability materials tied to real opportunity surfaces
- Qualify inbound email conversations and record what they mean
- Prepare standups around `Signal`, `Work Produced`, `Traction`, `Opportunities`, and `Next Focus`

## Valid Work Types

- Opportunity-signal review
- Capability and positioning refinement
- Capture-note updates
- Response drafting
- Qualification summaries
- Standup preparation tied to opportunity movement

## Invalid Work Types

- Invented certifications, past performance, or contract claims
- Legal or compliance advice presented as fact
- Broad consulting brainstorming with no market signal
- Cross-workspace planning
- Automation validation as the primary deliverable

## Machine Cadence

- `5-minute` execution polling
- `30-minute` internal sync and standup-prep loop

## Dispatch Path

This lane stays on the delegated workspace pattern:

`You -> Neo -> Jean-Claude -> AGC Operator Agent or Codex -> PM write-back`

## Roles

- `Neo`: intake only
- `Jean-Claude`: execution manager
- `AGC Operator Agent`: delegated workspace executor
- `Codex workspace runner`: optional direct executor when Jean-Claude needs a bounded local run

## Standard flow

1. Create or update the PM card through the thin trigger path.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key agc \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Have Jean-Claude open the workspace SOP.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the AGC workspace agent pick up delegated execution.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution only when Jean-Claude keeps the work in his lane.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Support Layer

PM cards, SOPs, workspace briefings, analytics snapshots, and standups should describe the work above in traceable form.
They should not become the main subject of the lane unless a system failure blocks output or visibility.

## Escalation Rule

Escalate only when one of these is true:

- the packet requires unsupported capability or compliance claims
- opportunity signal is too weak to justify the next capture move
- the work would cross workspace boundaries
- automation failure prevents the lane from qualifying or tracking the next step
