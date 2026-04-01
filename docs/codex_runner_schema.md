# Codex Runner Schema

This document defines the concrete schema for local Codex runners.

It is the implementation bridge between:
- the architecture
- the Jean-Claude contract
- the Yoda contract
- the PM board
- the runner ledger

This schema is designed to align with the current backend direction:
- `workspace_key`
- `owner_agent`
- `scope`
- `automation_runs`

## 1. Design Goals

The schema should be:
- `workspace-first`
- `PM-board grounded`
- `append-friendly`
- `JSONL-friendly`
- `role-extensible`

That means:
- every meaningful runner event can be written as one JSON object
- every event can be routed to one workspace or `shared_ops`
- Jean-Claude and Yoda share the same base envelope
- canonical Codex-to-OpenClaw handoff context can be injected without inventing a second planning system
- canonical Codex Chronicle context can be injected without inventing a second planning system
- role-specific behavior lives inside `role_payload`

## 2. Canonical Terms

- `runner`
  - a local scheduled Codex-driven agent process

- `run`
  - one invocation of a runner

- `workspace_key`
  - the workspace lane the action belongs to

- `scope`
  - the routing class for the action
  - allowed values:
    - `workspace`
    - `shared_ops`
    - `portfolio_strategy`
    - `global_control`

- `owner_agent`
  - the role identity responsible for the run
  - allowed initial values:
    - `neo`
    - `jean-claude`
    - `yoda`

## 3. Base Run Input Schema

Every runner invocation should start from a normalized input object.

```json
{
  "schema_version": "runner_input/v1",
  "run_id": "uuid-or-stable-id",
  "runner_id": "jean-claude",
  "owner_agent": "jean-claude",
  "scope": "shared_ops",
  "workspace_scope": [
    "linkedin-os",
    "fusion-os",
    "easyoutfitapp",
    "ai-swag-store",
    "agc"
  ],
  "primary_workspace_key": null,
  "goal": "Review all active workspaces and identify the highest-leverage next actions.",
  "run_mode": "scheduled",
  "time_budget_minutes": 30,
  "model": "openai/gpt-5.3-codex",
  "dry_run": false,
  "allowed_paths": [
    "/Users/neo/.openclaw/workspace"
  ],
  "allowed_command_prefixes": [
    "git status",
    "rg",
    "sed",
    "cat"
  ],
  "pm_context": {},
  "automation_context": {},
  "codex_handoff_context": {},
  "codex_chronicle_context": {},
  "workspace_context": {},
  "previous_run_context": {},
  "role_payload": {}
}
```

## 4. Base Run Output Schema

Every runner run must end with a normalized output object.

```json
{
  "schema_version": "runner_output/v1",
  "run_id": "uuid-or-stable-id",
  "runner_id": "jean-claude",
  "owner_agent": "jean-claude",
  "status": "ok",
  "scope": "shared_ops",
  "workspaces_touched": [
    "linkedin-os",
    "fusion-os"
  ],
  "summary": "LinkedIn OS and Fusion OS have the highest-priority next moves.",
  "artifacts_written": [],
  "codex_handoff_write": null,
  "memory_promotions": [],
  "pm_updates": [],
  "blockers": [],
  "dependencies": [],
  "recommended_next_actions": [],
  "escalations": [],
  "role_payload": {}
}
```

## 5. Runner Ledger Entry Schema

Each completed run should append one JSONL record to a role-specific ledger.

Recommended path pattern:
- `/Users/neo/.openclaw/workspace/memory/runner-ledgers/<runner_id>.jsonl`

Schema:

```json
{
  "schema_version": "runner_ledger/v1",
  "run_id": "uuid-or-stable-id",
  "runner_id": "jean-claude",
  "owner_agent": "jean-claude",
  "scope": "shared_ops",
  "primary_workspace_key": null,
  "workspace_scope": [
    "linkedin-os",
    "fusion-os",
    "easyoutfitapp",
    "ai-swag-store",
    "agc"
  ],
  "started_at": "2026-03-31T16:00:00Z",
  "finished_at": "2026-03-31T16:12:00Z",
  "duration_ms": 720000,
  "status": "ok",
  "model": "openai/gpt-5.3-codex",
  "goal": "Review all active workspaces and propose next actions.",
  "summary": "LinkedIn OS and Fusion OS need attention first.",
  "artifacts_written": [],
  "codex_handoff_write": null,
  "memory_promotions": [],
  "pm_updates": [],
  "blockers": [],
  "dependencies": [],
  "recommended_next_actions": [],
  "escalations": [],
  "error": null,
  "metadata": {}
}
```

## 6. PM Update Schema

PM effects need to be structured so the runner cannot invent vague work.

```json
{
  "action": "create_card",
  "pm_card_id": null,
  "workspace_key": "linkedin-os",
  "scope": "workspace",
  "owner_agent": "jean-claude",
  "title": "Clarify LinkedIn OS to FEEZIE OS migration plan",
  "status": "todo",
  "reason": "Strategic shift identified in runner review.",
  "payload": {
    "priority": "high",
    "source": "runner",
    "source_runner": "jean-claude",
    "source_run_id": "uuid-or-stable-id"
  }
}
```

Allowed initial `action` values:
- `create_card`
- `update_card`
- `move_status`
- `add_note`
- `recommend_only`

## 7. Artifact Reference Schema

Every material write should be explicit.

```json
{
  "kind": "file",
  "path": "/Users/neo/.openclaw/workspace/memory/runner-memos/jean-claude/2026-03-31_ops_review.md",
  "workspace_key": "shared_ops",
  "label": "ops review memo"
}
```

Allowed initial `kind` values:
- `file`
- `pm_note`
- `report`
- `memo`

## 8.5 Codex Handoff Write Schema

Meaningful runner passes may also emit a compact Codex handoff payload for OpenClaw brain jobs.

```json
{
  "schema_version": "codex_handoff/v1",
  "workspace_key": "shared_ops",
  "scope": "shared_ops",
  "summary": "Jean-Claude detected that OpenClaw and Codex need a canonical handoff bridge.",
  "decisions": [
    "Use memory/codex_session_handoff.jsonl as canonical bridge input."
  ],
  "blockers": [],
  "follow_ups": [
    "Patch Oracle Ledger and Progress Pulse to read handoff first."
  ],
  "tags": [
    "runner",
    "handoff"
  ]
}
```

## 8.6 Codex Chronicle Context Schema

Runner inputs may also receive recently appended Chronicle chunks.

```json
{
  "entries": [
    {
      "schema_version": "codex_chronicle/v1",
      "workspace_key": "shared_ops",
      "summary": "High-signal Codex work was preserved before context rollover.",
      "signal_types": [
        "decision",
        "learning",
        "identity"
      ],
      "project_updates": [],
      "learning_updates": [],
      "identity_signals": [],
      "mindset_signals": [],
      "outcomes": [],
      "memory_promotions": [],
      "pm_candidates": []
    }
  ]
}
```

## 8.7 Memory Promotion Schema

Standups and runners may recommend that Chronicle signal become durable memory.

```json
{
  "target": "persistent_state",
  "workspace_key": "shared_ops",
  "reason": "This learning should survive beyond the current Codex context.",
  "content": "Codex Chronicle should preserve high-signal project and identity context before rollover."
}
```

## 9. Escalation Schema

Escalations should be structured and destination-aware.

```json
{
  "target_agent": "yoda",
  "kind": "strategy_review",
  "workspace_key": "linkedin-os",
  "reason": "Brand direction question exceeds Jean-Claude scope.",
  "recommended_action": "Review whether LinkedIn OS should shift immediately into FEEZIE OS framing.",
  "severity": "medium"
}
```

Allowed initial `target_agent` values:
- `neo`
- `jean-claude`
- `yoda`

## 10. Jean-Claude Role Payload Schema

Jean-Claude uses the base schema plus this role payload:

```json
{
  "portfolio_health": "stable",
  "workspaces_reviewed": [
    "linkedin-os",
    "fusion-os",
    "easyoutfitapp",
    "ai-swag-store",
    "agc"
  ],
  "highest_priority_workspace": "linkedin-os",
  "operating_recommendations": [
    "Reduce drift in Fusion OS task sequencing.",
    "Clarify next action in LinkedIn OS."
  ]
}
```

Jean-Claude-specific output should emphasize:
- blockers
- sequencing
- dependencies
- next actions
- PM effects

## 10. Yoda Role Payload Schema

Yoda uses the base schema plus this role payload:

```json
{
  "trajectory_read": "positive but fragmented",
  "feezie_os_guidance": "LinkedIn OS should broaden into FEEZIE OS with explicit Instagram/career linkage.",
  "identity_notes": [
    "Current effort is strong, but narrative coherence is lagging."
  ],
  "deprioritization_recommendations": [
    "Reduce energy on work that does not compound into brand credibility."
  ]
}
```

Yoda-specific output should emphasize:
- alignment
- strategic direction
- identity coherence
- long-horizon risk
- FEEZIE OS guidance

## 11. File Layout

Recommended first-pass runner file layout:

- `/Users/neo/.openclaw/workspace/memory/runner-ledgers/jean-claude.jsonl`
- `/Users/neo/.openclaw/workspace/memory/runner-ledgers/yoda.jsonl`
- `/Users/neo/.openclaw/workspace/memory/runner-memos/jean-claude/`
- `/Users/neo/.openclaw/workspace/memory/runner-memos/yoda/`

Optional later:
- `/Users/neo/.openclaw/workspace/memory/runner-ledgers/index.json`

## 12. Minimal Validation Rules

### Required for every run
- `run_id`
- `runner_id`
- `owner_agent`
- `scope`
- `status`
- `summary`
- `started_at`
- `finished_at`

### Required when a workspace is touched
- `workspace_key` inside each PM update or artifact

### Invalid states
- PM update with no `workspace_key`
- workspace artifact written with `scope=shared_ops` but no explanation
- escalation with no `target_agent`
- runner output with `status=ok` and no summary

## 13. First Implementation Boundary

For MVP:
- use file-based JSONL ledgers
- do not require DB persistence yet
- allow PM update objects to be generated before automatic PM mutation is fully wired
- append logs first, automate mutations second

This keeps the first runner build simple and observable.

## 14. Bottom Line

This schema gives you:
- one shared base contract
- two role-specific extensions
- clear PM linkage
- clear ledger behavior
- workspace-safe routing

Jean-Claude and Yoda can now be implemented against the same runner infrastructure without collapsing into the same job.
