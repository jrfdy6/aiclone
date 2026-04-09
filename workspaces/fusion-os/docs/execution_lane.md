# Fusion OS Execution Lane

Fusion OS now has the same dispatch + execution plumbing as the other workspaces. The delegated proof card verified that we can open SOPs, generate workspace packets, and write PM updates. This guide turns that one-off proof into a recurring lane the team can run without guessing.

## Scope and purpose
- Keep Fusion admissions / operations work inside `fusion-os`.
- Let Fusion Systems Operator own workspace delivery while Jean-Claude keeps the PM/standup surface honest.
- Run every packet through PM → SOP → work order → execution-result so Chronicle, LEARNINGS, and persistent_state stay in sync.

## Roles
| Role | Responsibilities |
| --- | --- |
| Jean-Claude | Decide priorities from Fusion standups, run `run_jean_claude_execution.py` to open SOPs, review workspace briefs, and own the final write-up / escalation. |
| Fusion Systems Operator | Pick up delegated packets via `run_workspace_agent.py`, execute inside `fusion-os`, and hand results back through `write_execution_result.py`. |
| Codex workspace runner | Optional accelerator when we want the model to execute directly inside `fusion-os` (`run_codex_workspace_execution.py`). |

## Standard flow
1. **Standup → PM card**
   - Standup prep already links Fusion OS cards (see `/memory/standup-prep/fusion-os/*`).
   - Confirm the card details via `memory/runner-inputs/jean-claude-execution/<stamp>.json` before dispatching again.
2. **Dispatch the SOP (Jean-Claude)**
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key fusion-os \
     --card-id 61b440e6-1723-456d-889e-32d2155983d8 \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
   - Produces `dispatch/<stamp>_sop.json` + `briefings/<stamp>_briefing.md`.
   - Payload points at the repo root so Codex or a workspace agent stays fully sandboxed inside `fusion-os`.
3. **Workspace pickup (delegated mode)**
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key fusion-os \
     --card-id 61b440e6-1723-456d-889e-32d2155983d8 \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
   - Writes `dispatch/<stamp>_fusion-systems-operator_work_order.json` and mirrored status briefings.
4. **Direct execution (Jean-Claude or Codex)**
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --packet workspaces/fusion-os/dispatch/20260406T230319Z_jean_claude_work_order.json \
     --worker-id jean-claude \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
   - Use when Jean-Claude is executing personally, or hand the packet to Codex with the same command.
5. **Write the result back**
   ```bash
   # Force API mode if the runner inherited DATABASE_URL
   OPEN_BRAIN_DATABASE_URL="" DATABASE_URL="" \
   python3 scripts/runners/write_execution_result.py \
     --work-order workspaces/fusion-os/dispatch/20260406T230319Z_jean_claude_work_order.json \
     --api-url https://aiclone-production-32dc.up.railway.app \
     --runner-id jean-claude \
     --author-agent Jean-Claude \
     --status review \
     --summary "<what changed>" \
     --artifact workspaces/fusion-os/docs/execution_lane.md
   ```
   - Clearing `OPEN_BRAIN_DATABASE_URL`/`DATABASE_URL` forces API mode and avoids the "Open brain database url is not configured" crash that stalled the 2026‑04‑06 run.

## Guardrails
- **Lane containment**: never pull identity or docs from outside `workspaces/fusion-os/`. Dispatch already embeds the local pack; if something is missing, fix it locally.
- **Packet noise**: earlier attempts spawned hundreds of `dispatch/20260401T*.json` files because the runner kept re-queuing without a completion. Keep only the latest packet per card when staging a run; archive older copies rather than deleting them.
- **Result discipline**: every execution ends with the writer. Dry runs (`--dry-run`) are fine for smoke tests, but the PM card stays `running` until an actual result gets posted.
- **Manager attention flag**: if a packet fails (e.g., writer blows up), use the `--status blocked` path and list the blocker verbatim so the accountability sweep does not reroute blindly.
- **Dispatch hygiene**: run `python3 workspaces/fusion-os/scripts/archive_dispatch_packets.py --card-id <pm-card> --keep 2` after a packet closes so only the latest SOP + work order pairs live in `dispatch/`. Older artifacts land under `dispatch/archive/<card-id>/…` for auditors but stop overwhelming Codex runners.

## Chronicle → standup → PM wiring
- Build the Fusion OS standup payload with `python3 scripts/build_standup_prep.py --standup-kind fusion-os --workspace-key fusion-os`. The builder only auto-promotes Chronicle entries that are explicitly tagged for `fusion-os` and suppresses PM recommendations whenever the live PM snapshot is unavailable, so shared_ops noise can’t spawn duplicate cards and offline runs stay recommendation-only.
- Promote Chronicle signal into durable memory (and PM recommendations when available) with `python3 scripts/promote_codex_chronicle.py --prep-json memory/standup-prep/fusion-os/<stamp>.json --workspace-key fusion-os --write-pm-recommendations`. When the PM API is reachable, the resulting JSON in `memory/pm-recommendations/` becomes the wrapper-owned write-back input; otherwise the promotion only updates the daily log.
- Always cite the generated `memory/standup-prep/fusion-os/<stamp>.{json,md}` in briefs or execution-log entries so accountability sweeps can trace which Chronicle inputs drove each decision.

## What "recurring" means now
- Fusion standups already emit PM cards; Jean-Claude simply needs to run the dispatch script at the beginning of each work packet.
- This playbook lives beside the workspace knowledge base so Fusion Systems Operator or Codex can execute without reverse‑engineering the lane again.
- Once the lane runs cleanly for a few packets, promote the cadence into `memory/roadmap.md` and mark the PM card `done`. Until then, default to `review` with a traceable artifact (this file + execution log entries).

## Open follow-ups
1. Run the same checklist for card `Review Fusion OS delegated lane proof and either close it or return it to execution` so the delegated proof and the review card enter the same recurrence loop.
2. Create the first workspace-local Fusion standup (pending follow-up from the March 31 execution log) so future cards originate from a real standup transcript instead of manual proofs.
3. _[done 2026-04-07]_ Clean up duplicated dispatch files by archiving them under `workspaces/fusion-os/dispatch/archive/` once each packet is superseded.
