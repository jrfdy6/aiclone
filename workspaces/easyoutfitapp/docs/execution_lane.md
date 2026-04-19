# Easy Outfit App Execution Lane

Easy Outfit App executes one recurring business loop:

Wardrobe Signal -> Context -> Recommendation -> Visit or Use -> Feedback -> Improve

Automation, PM cards, SOPs, and write-back exist to support this loop.
They are not the loop itself.

## Purpose

Turn product signal, user context, and wardrobe intelligence into a more trustworthy daily dressing experience while keeping restore-mode work and growth-mode work visible.

## Lane Responsibilities

- Improve recommendation quality and context handling
- Keep the product closet-first instead of purchase-first
- Treat restoration work as real progress when the local environment is incomplete
- Capture what users or visits reveal about the next product move
- Prepare standups around `Signal`, `Work Produced`, `Traction`, `Opportunities`, and `Next Focus`

## Valid Work Types

- Product restoration
- Recommendation-quality refinement
- Context and metadata improvements
- Onboarding and experience cleanup
- Website-visit review
- User-signal summaries
- Standup preparation tied to product progress

## Invalid Work Types

- Context-blind outfit recommendations
- Affiliate-shopping pressure as the primary answer
- Fashion-influencer content with no product consequence
- Cross-workspace planning
- Automation validation as the primary deliverable

## Machine Cadence

- `5-minute` execution polling
- `30-minute` internal sync and standup-prep loop

## Dispatch Path

This lane stays on the delegated workspace pattern:

`You -> Neo -> Jean-Claude -> Easy Outfit App Operator Agent or Codex -> PM write-back`

## Roles

- `Neo`: front-door intake
- `Jean-Claude`: execution manager
- `Easy Outfit App Operator Agent`: default workspace executor
- `Codex workspace runner`: direct executor for bounded local packets

## Standard flow

1. Open work through the thin PM contract.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key easyoutfitapp \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Have Jean-Claude create the SOP and briefing.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the workspace agent execute the delegated packet.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution when Jean-Claude owns the implementation personally.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Support Layer

PM cards, SOPs, workspace briefings, analytics snapshots, and standups should describe the work above in traceable form.
They should not become the main subject of the lane unless a system failure blocks output or visibility.

## Escalation Rule

Escalate only when one of these is true:

- the product context is too incomplete to make a trustworthy change
- the next step requires cross-workspace coordination
- a recommendation or product decision would be misleading without more evidence
- automation failure prevents the lane from shipping or tracking the next improvement
