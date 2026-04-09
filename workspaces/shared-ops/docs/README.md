# shared_ops Docs Index

This folder captures the artifacts and playbooks that keep the executive lane legible.

## Core references
- `workspace_identity_alignment_YYYY-MM-DD.md` — dated pack/registry/UI alignment checks.
- `workspace_pack_executive_review_YYYY-MM-DD.md` — dated cross-workspace audits (Fusion OS lane status, heartbeat recovery, planned-lane blockers).
- `heartbeat_verification_YYYY-MM-DD.md` — dated heartbeat diagnostics and recovery proofs.
- `openclaw_codex_smoke_followup_YYYY-MM-DD.md` — dated smoke-test follow-up memos and host-run checklists.
- `execution_lane.md` — step-by-step contract for running Jean-Claude work packets inside shared_ops.
- `stale_pm_lane_review_2026-04-07.md` — status check on the accountability-sweep cards with links to their latest artifacts and open follow-ups.
- `heartbeat_recovery_playbook.md` — operator steps for switching the heartbeat model and verifying diagnostics reach Discord again.
- `openclaw_codex_smoke_report_2026-04-08.md` — latest evidence for the Codex ↔ OpenClaw smoke test attempt, including command output and the remaining connectivity blocker.

## When to read what
- Before touching registry, runner, or UI naming: read `docs/README.md` plus the latest dated executive review that matches the current issue.
- Before executing a PM card: skim `execution_lane.md` to keep the prep → build → write-back loop tight.
- After shipping work: add a dated artifact that matches the conventions above rather than rotating this index for every run.
