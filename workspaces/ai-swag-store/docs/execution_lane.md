# AI Swag Store Execution Lane

AI Swag Store executes one recurring business loop:

Signal -> Offer -> Listing -> Visit -> Learn -> Iterate

Automation, PM cards, SOPs, and write-back exist to support this loop.
They are not the loop itself.

## Purpose

Turn store, traffic, and merch signal into differentiated offers and cleaner catalog decisions without allowing the lane to drift into generic merch churn.

## Lane Responsibilities

- Capture demand signal from visits, store behavior, and offer-level response
- Translate signal into clearer offers, listing changes, and landing-page improvements
- Keep the catalog disciplined instead of expanding it blindly
- Record what traffic or demand changed and what that suggests next
- Prepare standups around `Signal`, `Work Produced`, `Traction`, `Opportunities`, and `Next Focus`

## Valid Work Types

- Offer testing
- Product and listing refinement
- Landing-page refinement
- Traffic-signal review
- Demand-learning summaries
- Catalog decision notes
- Standup preparation tied to store learning

## Invalid Work Types

- Generic print-on-demand expansion
- Catalog sprawl with no signal
- Social-first activity with no store consequence
- Cross-workspace planning
- Automation validation as the primary deliverable

## Machine Cadence

- `5-minute` execution polling
- `30-minute` internal sync and standup-prep loop

## Dispatch Path

This lane stays on the delegated workspace pattern:

`You -> Neo -> Jean-Claude -> AI Swag Store Operator Agent or Codex -> PM write-back`

## Roles

- `Neo`: intake and prioritization
- `Jean-Claude`: execution manager
- `AI Swag Store Operator Agent`: default workspace executor
- `Codex workspace runner`: fallback for bounded direct execution when Jean-Claude keeps the packet local

## Standard flow

1. Open the work through the thin PM trigger.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key ai-swag-store \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Let Jean-Claude turn the card into a local SOP.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the workspace agent pick up execution.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution only if Jean-Claude explicitly keeps the work in his own lane.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Support Layer

PM cards, SOPs, workspace briefings, analytics snapshots, and standups should describe the work above in traceable form.
They should not become the main subject of the lane unless a system failure blocks output or visibility.

## Escalation Rule

Escalate only when one of these is true:

- traffic or demand signal is too weak to justify the next catalog move
- the packet requires cross-workspace coordination
- fulfillment or store constraints make the offer unsafe or misleading
- automation failure prevents the lane from shipping or tracking the next test
