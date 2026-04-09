# Golden Snapshot SOP

This SOP defines how to treat the April 8, 2026 clean snapshot as the stable baseline for future work.

## Purpose

Use this SOP when you want one trusted restore point, one living branch to keep building on, and one clear procedure for handling runtime drift outside git.

## Canonical Baseline

- Immutable restore tag: `clean-main-2026-04-08`
- Exact restore commit: `206b447bc227bed9dd2623157bf14f69de587370`
- Living branch for ongoing work: `main`
- Runtime restore note: [openclaw_runtime_backup_2026-04-08.md](/Users/neo/.openclaw/workspace/docs/openclaw_runtime_backup_2026-04-08.md)
- Post-baseline cron tuning note: [openclaw_cron_noise_reduction_2026-04-09.md](/Users/neo/.openclaw/workspace/docs/openclaw_cron_noise_reduction_2026-04-09.md)
- Core memory snapshot lane: [README.md](/Users/neo/.openclaw/workspace/docs/runtime_snapshots/core_memory/README.md)

Interpretation:

- `clean-main-2026-04-08` is the permanent anchor.
- `main` is expected to keep moving.
- The runtime backup note is the source of truth for OpenClaw files that live outside the git repo.

## Non-Negotiable Rules

1. Never move, retag, or reuse `clean-main-2026-04-08`.
2. Always build new work on `main`, not on the tag.
3. If runtime files under `/Users/neo/.openclaw/` are intentionally changed, update the current runtime backup note or add a new dated runtime note in the same work session.
4. If a new milestone deserves its own clean baseline, create a new tag. Do not redefine this one.
5. Do not treat a dirty working tree by itself as proof that the baseline is bad; OpenClaw automation updates tracked files continuously.
6. If you need to recover the exact known-good state, restore from the tag first, then reconcile the live runtime files using the runtime backup note.

## What Counts As Runtime Drift

These files are outside the repo and therefore are not restored by git alone:

- `/Users/neo/.openclaw/openclaw.json`
- `/Users/neo/.openclaw/cron/jobs.json`
- `/Users/neo/.openclaw/agents/main/qmd/xdg-config/qmd/index.yml`

Any meaningful change to heartbeat behavior, cron behavior, Dream Cycle behavior, or QMD collection wiring must be reflected in the runtime backup note.

## Normal Working Rules

1. Use `main` for everyday development.
2. Leave `clean-main-2026-04-08` untouched as the fallback anchor.
3. Expect memory ledgers, reports, and some generated files to drift while automations run.
4. Before calling the system "broken," distinguish between:
   - expected automation churn in tracked files
   - actual regressions in runtime config or cron behavior
5. When making a major platform repair or stabilization pass, create a new dated tag instead of replacing the old anchor.

## Daily Operator Routine

Use [operator_baseline_routine.sh](/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh) as the front door for normal baseline hygiene.

1. Start the day or a repair session by checking baseline status.

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh status
```

2. When you want to freeze the current live memory state into the tracked snapshot lane, capture a core-memory snapshot.

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh snapshot
```

3. If you intentionally changed non-git OpenClaw runtime files, record the new hashes before updating the runtime backup note.

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh runtime-hashes
```

4. If the live markdown memory lane needs to be rehydrated from git-tracked state, restore it from the snapshot lane.

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh restore-memory
```

5. If you want a quick runtime confidence check after a repair or restore, run the health bundle.

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh health
```

Interpretation:

- Active memory files changing during normal use is expected. Snapshot them when you want a durable freeze point.
- Cron summaries being repetitive is an output-quality issue, not proof that the memory system is broken.
- Runtime drift outside git is the one category that must be documented immediately in the runtime backup note.

## Restore Procedure

1. Restore the repo baseline.

```bash
git fetch origin --tags
git switch -c restore-clean-main clean-main-2026-04-08
```

2. Compare live runtime files against the backup note.

```bash
shasum -a 256 /Users/neo/.openclaw/openclaw.json
shasum -a 256 /Users/neo/.openclaw/cron/jobs.json
shasum -a 256 /Users/neo/.openclaw/agents/main/qmd/xdg-config/qmd/index.yml
```

3. If hashes differ, reapply the required runtime snippets from the backup note.

4. Restart the gateway.

```bash
openclaw gateway stop
openclaw gateway start
```

5. Run the critical health checks.

```bash
qmd search 'Codex handoff' -c memory-dir-main
python3 /Users/neo/.openclaw/workspace/scripts/context_usage.py
python3 /Users/neo/.openclaw/workspace/scripts/heartbeat_report.py
```

6. If the live markdown memory lane is missing after a fresh clone or restore, rehydrate it from the tracked snapshot lane.

```bash
python3 /Users/neo/.openclaw/workspace/scripts/restore_core_memory_snapshot.py
```

Shortcut:

```bash
/Users/neo/.openclaw/workspace/scripts/operator_baseline_routine.sh restore-guide
```

## When To Create A New Golden Snapshot

Create a new clean tag only when all of the following are true:

1. `main` reflects the intended code state.
2. Runtime files outside git have been verified and documented.
3. Core cron behavior is healthy enough to trust.
4. You want a new permanent recovery point for future work.

Recommended naming pattern:

- `clean-main-YYYY-MM-DD`

Examples:

- `clean-main-2026-04-08`
- `clean-main-2026-06-01`

## What Not To Do

- Do not force-push over `main` just to recreate an old clean point.
- Do not rely on memory or Discord summaries instead of the tag and runtime backup note.
- Do not assume git restore alone fully restores OpenClaw.
- Do not overwrite this baseline tag with a newer state.

## Decision Rule

If there is any conflict between a moving branch, a dirty worktree, chat history, or Discord output, trust these in this order:

1. The restore tag `clean-main-2026-04-08`
2. The runtime backup note
3. The current contents of `main`
4. Automation-generated summaries and Discord notifications

This SOP exists so the baseline remains stable even while the system continues changing around it.
