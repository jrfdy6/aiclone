# SOP: OpenClaw Workspace Alignment Audit

## Purpose

Confirm that OpenClaw is answering from the same canonical workspace contract the codebase enforces.

This audit is deliberately end to end:

- canonical contract is derived from repo files
- OpenClaw answers through a real isolated agent run
- the audit forces `openai/gpt-5-nano`
- the reply is checked deterministically against the canonical contract

The goal is not to test whether the model sounds plausible.

The goal is to prove whether OpenClaw and the platform are aligned on:

- canonical workspace portfolio
- Feezie naming and filesystem mapping
- minimum non-executive lane shape
- startup anchors
- `shared_ops` executive exemption

## Canonical script

- `scripts/openclaw_workspace_alignment_audit.py`

## Modes

### `spec`

Build the canonical expected contract and write the latest report files without invoking OpenClaw.

Use this to inspect what the audit expects before running a live model check.

### `run-openclaw`

Runs one isolated OpenClaw audit case per prompt using `gpt-5-nano`, captures the cron run summary, parses the JSON reply, and scores it deterministically.

This is the real alignment check.

## Canonical command

```bash
cd /Users/neo/.openclaw/workspace
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python scripts/openclaw_workspace_alignment_audit.py --mode run-openclaw
```

Optional:

```bash
cd /Users/neo/.openclaw/workspace
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python scripts/openclaw_workspace_alignment_audit.py --mode spec
```

## What a pass means

The audit passes only if OpenClaw returns the same contract the codebase expects for:

- portfolio registry case
- lane contract case
- Feezie alias case

This is stricter than a casual chat answer because the audit requires machine-parseable JSON and exact contract values.

## Report paths

- `memory/reports/openclaw_workspace_alignment_latest.json`
- `memory/reports/openclaw_workspace_alignment_latest.md`
- dated copies under `memory/reports/openclaw_workspace_alignment_<DATE>.json`
- dated copies under `memory/reports/openclaw_workspace_alignment_<DATE>.md`

## Failure interpretation

If the audit fails:

- treat it as contract drift first, not model stupidity
- inspect which case failed
- inspect the canonical contract files
- inspect the workspace `AGENTS.md` and registry files
- only then decide whether the issue is docs drift, platform drift, or OpenClaw prompt/runtime drift

## Guardrails

- This audit does not replace code-level workspace tests.
- This audit is for contract alignment, not business-logic correctness.
- Do not let the audit auto-edit workspace packs or registry files.
- Use it as a truth-checking instrument before changing prompts or startup docs.

## Related documents

- [Workspace Portfolio Registry](./workspace_portfolio_registry_sop.md)
- [Workspace Governance](./workspace_governance_sop.md)
- [OpenClaw Local Automation Scheduling](./openclaw_local_automation_sop.md)
- [Workspace Agent Contract](../docs/workspace_agent_contract.md)
- [Workspace Identity Pack Standard](../docs/workspace_identity_pack_standard.md)
