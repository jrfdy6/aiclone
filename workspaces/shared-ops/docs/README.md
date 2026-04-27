# shared_ops Docs Index

This folder captures the artifacts and playbooks that keep the executive lane legible.

## Core references
- `portfolio_inbox_routing_spec.md` — source of truth for the shared Gmail inbox pattern, workspace routing precedence, AGC lane rules, and frontend inbox layout.
- `gmail_inbox_connection_runbook.md` — host steps for placing the Gmail OAuth client JSON, authorizing `neo512235@gmail.com`, and switching inbox sync from sample data to live Gmail.
- `email_ops_content_generation_bridge_design.md` — concrete design for replacing simple inbox draft templates with a thread-grounded bridge into the current content-generation system, without porting the legacy outreach architecture.
- `workspace_identity_alignment_YYYY-MM-DD.md` — dated pack/registry/UI alignment checks.
- `workspace_pack_executive_review_YYYY-MM-DD.md` — dated cross-workspace audits (Fusion OS lane status, heartbeat recovery, planned-lane blockers).
- `heartbeat_verification_YYYY-MM-DD.md` — dated heartbeat diagnostics and recovery proofs.
- `openclaw_codex_sync_alignment_2026-04-27.md` — current workflow-alignment memo for PM card `16f0e323-c8a9-4e44-aa26-fac3a0e1a8fa`, re-verifying the executive read path against the latest 2026-04-27 briefing, prep bundle, and LinkedIn ready-state proof rule.
- `openclaw_codex_sync_alignment_2026-04-24.md` — current workflow-alignment memo for PM card `2bbd3270-9d06-4c02-96e4-d80b721e4abd`, updating the executive read path after the Codex runner gained host-action automation lanes.
- `../../../docs/repo_surface_truth_enforcement_implementation_plan.md` — canonical system-wide implementation plan for turning the repo truth map into enforced runtime, fallback, legacy, and donor-repo contracts.
- `../../../docs/repo_surface_truth_baseline_audit_2026-04-25.md` — Phase 0 baseline audit capturing the current live/scaffold/legacy/reference split plus the concrete page/API mismatches this enforcement work is meant to close.
- `../../../docs/repo_surface_truth_baseline_2026-04-25.json` — machine-readable baseline used by the Phase 2 repo-surface verifier to allow known legacy debt while failing on new drift.
- `../../../docs/fallback_policy_contract.md` — canonical fallback taxonomy and the current allowed-vs-temporary-vs-failure inventory exposed through Brain.
- `../../../docs/truth_lane_cleanup_decision.md` — explicit decision to leave historical runtime memory in place for now, audit suspect residue, and only rebuild if that residue contaminates primary coordination surfaces again.
- `../../../docs/work_lifecycle_vocabulary.md` — shared loop-state vocabulary for Brain signals, standups, PM execution, and execution-result write-back.
- `../../../docs/downloads_aiclone_donor_boundary.md` — explicit donor-boundary decision for the old `downloads/aiclone` repo, including what is still worth porting, what remains reference-only, and what should be abandoned.
- `chronicle_standup_pm_flow_wire_2026-04-25.md` — current Chronicle standup/PM flow follow-up for PM card `cc6d0842-da36-48ec-ad92-99de50d84655`, tightening recommendation hygiene now that the executive decision loop is already live.
- `codex_chronicle_durable_memory_promotion_2026-04-27.md` — current durable-memory promotion memo for PM card `1a06a79d-e929-4dfa-8bc5-d021e80df19f`, packaging the rule that chat-derived Chronicle entries stay visible for standup context but require explicit opt-in before automatic durable-memory or PM promotion.
- `codex_chronicle_durable_memory_promotion_2026-04-25.md` — current durable-memory promotion memo for PM card `4f71c07e-5858-4e74-9d87-5881bde15d65`, packaging the rule that Codex conversations need periodic Chronicle writes so OpenClaw stays aligned with current work.
- `fallback_watchdog_verification_2026-04-27.md` — current fallback watchdog verification for PM card `53b020d4-4e26-4cf4-8913-87e42f04fe3b`, covering the daily-log resolution contract when the latest live daily memory is yesterday's artifact.
- `fallback_watchdog_verification_2026-04-25.md` — current fallback watchdog verification for PM card `05e874a0-f3bd-4fbe-82a3-a60e15a1fce5`, covering the non-material Daily Memory Flush write into the live `LEARNINGS.md` shell.
- `fallback_watchdog_verification_2026-04-23.md` — current fallback watchdog verification for PM card `f0ae4204-159f-4d33-825c-6f657007213b`, covering persistent-state-only Progress Pulse delivery suppression.
- `fallback_watchdog_verification_2026-04-22.md` — current fallback watchdog verification for PM card `839a845c-5ce0-463e-9c4b-48f20efa30fe`, covering the stale live-prefix persistent-state mirror repair.
- `fallback_watchdog_verification_2026-04-21.md` — current fallback watchdog verification for the PM card `cee49dd6-b3db-4c3c-8b3e-2a197c663038` delivery-lane timing alert.
- `fallback_watchdog_verification_2026-04-20.md` — memory/retrieval source-contract repair note and no-network watchdog verification for the requeued fallback cards.
- `openclaw_codex_smoke_followup_YYYY-MM-DD.md` — dated smoke-test follow-up memos and host-run checklists.
- `execution_lane.md` — step-by-step contract for running Jean-Claude work packets inside shared_ops.
- `stale_pm_lane_review_2026-04-14.md` — latest accountability-sweep decisions (current reroute covers the FEEZIE Slot 0 scheduling + Batch 2 lanes and lists the host-only steps still outstanding).
- `stale_pm_lane_review_2026-04-12.md` — accountability-sweep decisions for the rerouted Fusion OS lanes and the host-only blockers keeping them in review.
- `stale_pm_lane_review_2026-04-07.md` — status check on the accountability-sweep cards with links to their latest artifacts and open follow-ups.
- `heartbeat_recovery_playbook.md` — operator steps for switching the heartbeat model and verifying diagnostics reach Discord again.
- `openclaw_codex_smoke_report_2026-04-08.md` — latest evidence for the Codex ↔ OpenClaw smoke test attempt, including command output and the remaining connectivity blocker.

## When to read what
- Before building inbox or email routing UI/backend: read `portfolio_inbox_routing_spec.md` first.
- Before wiring generative drafting into the inbox: read `email_ops_content_generation_bridge_design.md`.
- Before authenticating the shared inbox against Gmail: read `gmail_inbox_connection_runbook.md`.
- Before touching registry, runner, or UI naming: read `docs/README.md` plus the latest dated executive review that matches the current issue.
- Before auditing the OpenClaw ↔ Codex execution loop: read `openclaw_codex_sync.md` plus the latest dated `openclaw_codex_sync_alignment_YYYY-MM-DD.md`.
- Before executing a PM card: skim `execution_lane.md` to keep the prep → build → write-back loop tight.
- After shipping work: add a dated artifact that matches the conventions above rather than rotating this index for every run.
