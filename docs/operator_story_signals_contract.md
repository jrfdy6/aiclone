# Operator Story Signals Contract

This lane exists to bridge raw OpenClaw operating memory into a bounded signal surface that downstream content and persona systems can inspect without reading raw cron output.

## 1. Why This Exists

OpenClaw already preserves building-story continuity in local memory files:

- `memory/codex_session_handoff.jsonl`
- `memory/persistent_state.md`
- `memory/daily-briefs.md`
- `memory/dream_cycle_log.md`
- `memory/cron-prune.md`

Those files are valuable, but they are too noisy and too mixed-purpose to use directly as prompt context.

The operator-story lane solves that by inserting one distillation step:

`raw OpenClaw memory -> operator story distiller -> operator_story_signals snapshot`

## 2. Design Rule

Share the story, not the noise.

That means:

- raw memory files stay as the durable operating lane
- the distiller extracts only signal-bearing items
- the snapshot stores route recommendations, not automatic promotions

## 3. Output Shape

The distiller writes a payload with:

- `generated_at`
- `workspace`
- `source_paths`
- `signals`
- `counts`

Each signal includes:

- `id`
- `title`
- `claim`
- `proof`
- `lesson`
- `artifact_paths`
- `workspace_keys`
- `topic_tags`
- `durability`
- `route`
- `source_kind`
- `source_ref`

Allowed `route` values:

- `keep_in_ops`
- `persona_candidate`
- `content_reservoir`

These are recommendations for downstream readers. The distiller does not directly mutate persona canon or reservoir files.

## 4. Local Reports

The local script writes:

- `memory/reports/operator_story_signals_latest.json`
- `memory/reports/operator_story_signals_latest.md`

The JSON report is the machine-readable source for snapshot persistence and future downstream readers.

## 5. Backend Sync

The sync contract is:

- `POST /api/brain/operator-story-signals/sync`

That route stores the distiller output as a workspace snapshot with:

- `workspace_key = linkedin-content-os` for the current FEEZIE content lane
- `snapshot_type = operator_story_signals`

This keeps the lane inspectable through the same snapshot surface as `source_assets` and `content_reservoir`.

## 6. Scheduling

The nightly launchd worker is:

- `automations/launchd/com.neo.operator_story_signals.plist`

The worker runs:

- `scripts/build_operator_story_signals.py`

## 7. Boundary

This is a memory bridge, not direct content generation.

The first version is intentionally conservative:

- it does not feed raw cron output into prompts
- it does not auto-promote anything into persona canon
- it does not rewrite workspace content files

It only produces a bounded, inspectable operator-story lane so the rest of the system can reason from the same distilled build story.
