# CODEX_STARTUP.md

This is the canonical startup brief for fresh Codex and OpenClaw sessions inside this workspace.

Read this file early. Its purpose is to stop the 30-45 minute relearning loop and make the system operable on the first pass.

## First read order
1. `CODEX_STARTUP.md`
2. `SOURCE_OF_TRUTH.md`
3. `SOUL.md`
4. `USER.md`
5. today + yesterday in `memory/YYYY-MM-DD.md`
6. `MEMORY.md`
7. `memory/roadmap.md`

Then load only the additional docs needed for the task at hand.

## Repo identity
- Workspace root: `/Users/neo/.openclaw/workspace`
- Git remote: `origin https://github.com/jrfdy6/aiclone.git`
- This repo is the active OpenClaw + AI Clone system, not a throwaway sandbox.
- Expect a dirty worktree. Do not revert unrelated user changes.

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

## High-value reference files
- `SOURCE_OF_TRUTH.md`
- `SOPs/direct_postgres_bootstrap.md`
- `docs/local_runtime_overrides.md`
- `frontend/README_ENV_SYNC.md`
- `scripts/deploy_railway_service.sh`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/README.md`

## One-sentence operating posture
Fresh Codex should treat this workspace as a live production-capable operator console with local CLI access to GitHub, Railway, OpenClaw, and the repo's own deploy/bootstrap scripts.
