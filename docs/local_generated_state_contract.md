# Local Generated State Contract

> Status: active supporting contract
> Authority: [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md)

## Purpose

AI Clone continuously ingests information and produces memory, standups,
dispatch packets, execution results, briefings, and workspace evidence. Those
normal runtime events must not leave the Git worktree dirty.

The repository remains the home of code, reviewed source material, schemas,
packs, configuration, and deliberately checkpointed documentation. Mutable,
machine-generated operating state belongs outside the repository under the
private local state root.

## Canonical layout

The defaults are:

```text
AI_CLONE_ROOT/
  memory/                         reviewed source and legacy read fallback
  workspaces/                     workspace source, packs, and legacy fallback

AI_CLONE_STATE_ROOT/              default: ~/.codex/ai-clone/state
  memory/                         generated global memory and reports
  persona/
    canonical/                    owner-approved private persona overlay
  workspaces/
    <canonical-workspace-key>/    generated state for any current/future workspace
  config/                         optional private runtime overrides
  automations/                    local automation run state
```

Examples:

```text
~/.codex/ai-clone/state/memory/codex_session_handoff.jsonl
~/.codex/ai-clone/state/persona/canonical/identity/claims.md
~/.codex/ai-clone/state/memory/source-intelligence/index.json
~/.codex/ai-clone/state/memory/standup-prep/
~/.codex/ai-clone/state/workspaces/feezie-os/briefings/
~/.codex/ai-clone/state/workspaces/shared_ops/dispatch/
```

Workspace state uses the canonical registry key rather than a historical
folder slug. The path helper accepts any valid lowercase workspace key, so a
new registered workspace does not require another hard-coded directory rule.

## Read and write rules

For generated memory, readers use this order:

1. `AI_CLONE_STATE_ROOT/memory/<path>`
2. `AI_CLONE_ROOT/memory/runtime/<path>` (legacy compatibility)
3. `AI_CLONE_ROOT/memory/<path>` (legacy compatibility)

For generated workspace artifacts, readers use:

1. `AI_CLONE_STATE_ROOT/workspaces/<canonical-key>/<path>`
2. the configured project workspace source folder
3. `AI_CLONE_ROOT/workspaces/<canonical-key>/<path>` when applicable

Writers covered by this contract target private state. Before the first append
or in-place update, a migrated writer copies an existing legacy regular file
to the new state path. It then updates only the copy. This preserves append
history and idempotency markers while leaving the original source untouched.

Immutable source/configuration readers do not copy project data. They may use
a private state override when one exists and otherwise read the repository
file directly.

Persona canon follows a narrower copy-on-first-write rule:

1. `AI_CLONE_STATE_ROOT/persona/canonical/<allowlisted-file>`
2. `AI_CLONE_ROOT/knowledge/persona/feeze/<allowlisted-file>` as the immutable
   public/deployment seed

Only an explicitly owner-committed Brain promotion can trigger a persona
write. The first write copies the corresponding tracked seed into private
state; all later additions and removals mutate only that private copy. The
existing static persona-file allowlist remains authoritative, and every path
component is checked for traversal and symlink escapes. Railway receives only
a content-free sync receipt; private canon bytes and absolute paths are never
uploaded. Publishing a reviewed private change into the tracked public seed
is a separate, manual Git workflow.

Explicit paths supplied by tests or bounded operator commands remain
supported. Every state helper rejects absolute relative-path inputs, parent
traversal, and invalid workspace keys.

## What migrated

The following high-frequency entry points now write their direct generated
output to private state:

- canonical Brain memory synchronization;
- Brain signal capture, review, routing, and local snapshot generation;
- Codex Chronicle synchronization and promotion;
- standup-preparation reports;
- Jean-Claude and workspace-agent dispatch, briefing, ledger, and execution
  artifacts;
- Codex workspace execution packets, canonical-memory routes, and direct
  workspace write-backs;
- execution-result ledgers, memos, Chronicle entries, daily memory, Learnings,
  persistent state, and workspace execution logs;
- mutable LinkedIn/FEEZIE scheduling evidence seeded from repository
  templates;
- owner-approved persona promotions, seeded from the tracked public bundle
  and persisted only in the private canonical overlay;
- the generated source-intelligence index, FEEZIE idea-qualification and
  latent-idea projections, latent-transform drafts, stale-reaction manifest,
  market-signal archive, and autonomous backlog projection;
- YouTube watchlist discovery assets and transcript backfills, with merged
  private-state plus legacy reads and copy-before-mutate compatibility.

Source packs, schemas, registry definitions, prompts, SOPs, code, and the
reviewed public persona seed remain repository inputs. An explicitly claimed
Codex software-engineering task may still change repository code or reviewed
work products by design; routine ingestion, memory, reports, and automation
bookkeeping may not.

## Safe migration procedure

There is deliberately no automatic bulk move or cleanup. Existing project
data may contain the only copy of historical evidence, so migration is
copy-first and per-file as each writer runs.

Before any later cleanup:

1. stop write-capable local workers;
2. inventory legacy generated files and their private-state counterparts;
3. compare counts, sizes, hashes, and append identifiers;
4. merge any split append-only history and rerun idempotency checks;
5. create a recoverable backup;
6. only then decide which legacy files should be archived or removed.

Run the metadata-only inventory with:

```bash
python3 scripts/audit_generated_state.py --summary-only
```

The audit reads both trees without creating anything and reports counts,
sizes, hashes, statuses, and dynamically discovered workspace keys. Omit
`--summary-only` only when the path-by-path comparison is needed.

Do not delete, move, truncate, or rewrite legacy data merely to make
`git status` clean. The current contract makes future runs clean while
preserving old files for an explicit audit.

Create a local, owner-only state snapshot with:

```bash
python3 scripts/run_secure_state_snapshot.py
```

The existing daily Secure Project Snapshot automation also invokes this state
snapshot, so the manual command is an on-demand safety check rather than the
only backup path.

The archive is stored below the private runtime backup root, outside Git and
outside the state being archived. It contains an embedded path/size/SHA-256
manifest and is verified immediately after creation. It never includes the
secrets root, skips secret-like filenames and symlinks, does not upload
anything, and does not automatically remove older backups. SQLite databases
are captured with SQLite's online backup API, their WAL/SHM sidecars are
excluded, and the archived database copy must pass `PRAGMA integrity_check`
before the snapshot is accepted.

Verify any archive without extracting it:

```bash
python3 scripts/run_secure_state_snapshot.py --verify /absolute/path/to/ai-clone-state-YYYYMMDDTHHMMSSZ.tar.gz
```

Recovery is deliberately manual: verify the archive, extract it into a new
staging directory, compare its manifest and application reads, stop writers,
then replace only the explicitly approved state root. Never extract directly
over live state.

## Environment and tests

Supported overrides:

- `AI_CLONE_ROOT`
- `AI_CLONE_RUNTIME_ROOT`
- `AI_CLONE_STATE_ROOT`
- `AI_CLONE_SECRETS_ROOT`
- `AI_CLONE_LOG_ROOT`

Tests should provide temporary project and state roots. Runner tests that
replace the project root use a child `.ai-clone-state` directory inside that
temporary project so they never write into the operator's real local state.

Core path and containment coverage lives in:

```text
backend/tests/test_runtime_paths.py
backend/tests/test_runner_security.py
backend/tests/test_write_execution_result.py
```

## Remaining audit boundary

This contract covers the direct high-frequency writers named above. It does
not make bulk legacy cleanup safe by itself. Portfolio/Brain snapshots now
prefer private generated artifacts, Chronicle synchronization and promotion
have cross-process replay protection, and the audited lower-frequency writers
use the same runtime path contract. Remaining work is data migration rather
than another automatic rewrite:

- retain the metadata audit and verified backup before any legacy cleanup;
- reconcile the two reviewed/mixed legacy paths (the source-intelligence
  index and FEEZIE backlog seed) into private state before archiving them;
- review any newly introduced writer against this contract before enabling
  its launchd job.

Deployment must continue to exclude raw private memory and generated workspace
snapshots. Source intelligence is staged only through the cloud-safe projection:
aggregate counts plus sources explicitly classified `shared`, `public`, or
`cloud`. Local roots, filesystem paths, private summaries, routing state, and
unclassified sources are withheld. No state directory or raw local index is
staged broadly.
