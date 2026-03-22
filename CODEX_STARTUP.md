# CODEX_STARTUP.md

This is the canonical startup brief for fresh Codex and OpenClaw sessions inside this workspace.

Read this file early. Its purpose is to stop the 30-45 minute relearning loop and make the system operable on the first pass.

## First read order
1. `CODEX_STARTUP.md`
2. `SOURCE_OF_TRUTH.md`
3. `SOUL.md`
4. `USER.md`
5. `memory/persistent_state.md`
6. today + yesterday in `memory/YYYY-MM-DD.md`
7. `MEMORY.md`
8. `memory/roadmap.md`
9. `docs/persistent_memory_blueprint.md` when the task touches continuity, automations, or OpenClaw runtime behavior

Then load only the additional docs needed for the task at hand. Keep `SOPs/_index.md` handy so you can jump to the canonical capability map instead of hunting through doc folders.

## Repo identity
- Workspace root: `/Users/neo/.openclaw/workspace`
- Git remote: `origin https://github.com/jrfdy6/aiclone.git`
- This repo is the active OpenClaw + AI Clone system, not a throwaway sandbox.
- Expect a dirty worktree. Do not revert unrelated user changes.
- "Dirty worktree" is a Git state label, not a judgment that the memory system is broken or noisy. This repo intentionally accumulates append-only memory logs, generated workspace snapshots, runtime artifacts, and in-flight operating files.

## System map

### Core app surfaces
- `frontend/`: Next.js app deployed to Railway as `aiclone-frontend`
- `backend/`: FastAPI app deployed to Railway as `aiclone-backend`
- `workspaces/linkedin-content-os/`: child workspace for LinkedIn OS operations
- `frontend/app/ops/`: Mission Control umbrella
- `frontend/app/linkedin/`: LinkedIn workspace surface
- `frontend/app/brain/`: Brain, briefs, persona, and docs surfaces

### Knowledge and memory
- `knowledge/persona/feeze/`: canonical persona bundle
- `knowledge/ingestions/`: normalized ingestion artifacts
- `memory/`: daily logs, roadmap, learnings, reports
- `SOPs/`: repeatable production-safe operating procedures
- `docs/`: implementation notes, local runtime overrides, deployment references

### Automations and scripts
- `scripts/`: operational scripts, bootstrap loaders, deploy helpers, context tools
- `extensions/`: OpenClaw-linked local plugins
- `ingestion/`: stage-1 capture intake pipeline

## OpenClaw-specific facts
- Local runtime overrides are real and matter. Read `docs/local_runtime_overrides.md` before changing OpenClaw behavior.
- Checker for local overrides: `python3 scripts/check_local_runtime_overrides.py`
- If OpenClaw is upgraded or reinstalled, the local media-ack patch may need reapplication via `python3 scripts/reapply_openclaw_media_ack_patch.py`.
- QMD/session telemetry lives under `~/.openclaw/agents/main/sessions`.

## OpenClaw persistent memory model
- The primary restart lane is local QMD plus `memory/persistent_state.md`.
- Railway/Open Brain is a secondary capture and search lane for the app. It is not the canonical resume path after a relaunch, compaction event, or outage.
- Startup reinjection is handled by `python3 scripts/load_context_pack.py --sop --memory`. That loader pulls SOP, roadmap, persistent state, memory guardrails, and runtime override status.
- Mid-task continuity is protected by `python3 scripts/context_flush.py ...`, which appends structured flushes into `memory/YYYY-MM-DD.md`.
- Daily and weekly persistence health is maintained by Dream Cycle, Morning Daily Brief, Memory Health Check, GitHub Backup, and the related memory hygiene automations described in `docs/persistent_memory_blueprint.md`.
- QMD freshness and resume readiness can be checked with `python3 scripts/qmd_freshness_check.py`.
- The latest health reports live under `memory/reports/`.

## Fresh-start checks
Run these early when a session needs to become operational fast:

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/load_context_pack.py --sop --memory
python3 scripts/qmd_freshness_check.py
python3 scripts/check_local_runtime_overrides.py
git status -sb
```

- `load_context_pack.py` gives the compact operator context.
- `qmd_freshness_check.py` confirms the local memory lane is current.
- `check_local_runtime_overrides.py` verifies required OpenClaw runtime patches/trust settings.
- `git status -sb` shows repo state, but do not confuse Git dirtiness with invalid memory state.

## GitHub operating model
- Always inspect first: `git status -sb`
- Review only the files relevant to the request.
- Stage only your own intended changes.
- Use non-interactive git commands only.
- If Feeze explicitly asks to push, do not stop at "I cannot push." Attempt the push from the CLI. If the environment requires network/escalated approval, request it through the tool and continue.

### Standard git flow
```bash
cd /Users/neo/.openclaw/workspace
git status -sb
git add <files>
git commit -m "your message"
git push origin main
```

## Railway operating model
- Frontend service name: `aiclone-frontend`
- Backend service name: `aiclone-backend`
- Postgres service is accessed through Railway CLI and direct loader scripts.
- Preferred deploy entrypoint from repo root:

```bash
cd /Users/neo/.openclaw/workspace
./scripts/deploy_railway_service.sh frontend
./scripts/deploy_railway_service.sh backend
```

- The deploy script stages a small deploy context under `tmp/*-railway-deploy.current/` and then runs `railway up` with `--path-as-root`.
- This exists specifically to avoid large-context deploy failures.

### Railway checks
```bash
railway status
railway logs -s aiclone-frontend
railway logs -s aiclone-backend
railway service status
```

### Env sync
- Frontend/backend env coordination is documented in `frontend/README_ENV_SYNC.md`.
- If build/runtime behavior looks wrong, check `NEXT_PUBLIC_API_URL`, service-account blobs, OpenAI keys, and CORS settings first.

## Production endpoints
- Frontend production URL: `https://aiclone-frontend-production.up.railway.app`
- Backend production URL: `https://aiclone-production-32dc.up.railway.app`

## Direct production data operations
When data must be seeded without waiting for a backend redeploy, use the direct Postgres path in `SOPs/direct_postgres_bootstrap.md`.

### Canonical commands
```bash
cd /Users/neo/.openclaw/workspace
railway run --service Postgres -- \
  python3 scripts/bootstrap_ingestions_direct.py --root knowledge/ingestions

railway run --service Postgres -- \
  python3 scripts/bootstrap_open_brain_memory_direct.py --root knowledge/ingestions

railway run --service Postgres -- \
  python3 scripts/bootstrap_session_metrics_direct.py \
    --root ~/.openclaw/agents/main/sessions \
    --sessions-index ~/.openclaw/agents/main/sessions/sessions.json \
    --extra-root /Users/neo/backup-goat-os/sessions
```

Use those commands when the task is "seed production data" rather than "ship new API code."

## Current product model
- `Ops` is the umbrella Mission Control view for the whole project.
- `Workspace` means a child operating context with its own identity and operating files.
- `LinkedIn OS` is the first real child workspace and should surface its workflows natively in the UI.
- The frontend increasingly reads canonical workspace files instead of forcing the user to run scripts manually.

## Decision rules for fresh Codex sessions
- Assume the repo, GitHub remote, Railway CLI, and OpenClaw CLI are usable until a command proves otherwise.
- If Feeze explicitly asks for a production-impacting action, execute it carefully instead of only describing it.
- Production-impacting actions still require confirmation from Feeze, but once that confirmation exists, move forward.
- Prefer existing scripts and SOPs over inventing new one-off commands.
- Do not claim a capability is unavailable without testing the actual command path first.

## Essential references
- `SOPs/_index.md` (master list of SOPs/capabilities)
- `SOURCE_OF_TRUTH.md`
- `memory/persistent_state.md`
- `docs/persistent_memory_blueprint.md`
- `docs/cron_delivery_guidelines.md`
- `SOPs/direct_postgres_bootstrap.md`
- `docs/local_runtime_overrides.md`
- `frontend/README_ENV_SYNC.md`
- `scripts/deploy_railway_service.sh`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/README.md`
- `scripts/worktree_doctor.py` (classifies git status output so you can see what’s genuinely dirty)

## Boot checklist
- Confirm `SOPs/_index.md`, `memory/persistent_state.md`, `memory/roadmap.md`, and `docs/cron_delivery_guidelines.md` are loaded before acting.
- Run `python3 scripts/load_context_pack.py --sop --memory`, `python3 scripts/qmd_freshness_check.py`, and `python3 scripts/check_local_runtime_overrides.py` to validate the persistence lane and runtime patches.
- Use `./scripts/worktree_doctor.py` to label dirty files and only stage the `other` bucket when pushing.

## One-sentence operating posture
Fresh Codex should treat this workspace as a live production-capable operator console with local CLI access to GitHub, Railway, OpenClaw, and the repo's own deploy/bootstrap scripts.

## Worktree hygiene shortcut
Run `./scripts/worktree_doctor.py` before you open a new session so you know which files are “noise” (memory logs, generated snapshots, tmp deploy folders) versus code that actually needs review. When a script flags `memory` or `generated` entries, those are usually safe if they’re expected append-only writes; focus your staging on the `other` bucket.
