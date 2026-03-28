# SOP: Main Safety Release Flow

## Purpose
Make `main` safe enough to function as the release lane without relying on a long-lived branch for confidence.

## Scope
- Applies to code that affects the AI Clone app, especially the LinkedIn/social workspace.
- Covers the local verification gate, the deploy step, the post-deploy smoke gate, and the current GitHub Actions limitation.

## Canonical Entry Points
- Local gate: `npm run verify:main`
- Production gate: `npm run verify:production`
- Hook installer: `npm run hooks:install`
- Local hook: `.githooks/pre-push`
- Backend smoke suite: `backend/tests/test_workspace_smoke.py`
- Staged Railway deploy: `./scripts/deploy_railway_service.sh backend` and `./scripts/deploy_railway_service.sh frontend`

## Procedure
1. `cd /Users/neo/.openclaw/workspace`
2. Check the worktree first:
   - `./scripts/worktree_doctor.py`
   - confirm you are not about to commit append-only memory noise by accident
3. Run the local gate:
   - `npm run verify:main`
4. If the local gate passes, commit only the intended files.
5. Push to `main`.
   - If hooks are installed, the pre-push gate will rerun automatically.
6. Deploy with the staged Railway script:
   - `./scripts/deploy_railway_service.sh backend`
   - `./scripts/deploy_railway_service.sh frontend`
   - This stages only the service-specific deploy context plus the required workspace/persona assets.
   - If the release touches transcript/media source expansion, confirm the staged backend context also includes:
     - `knowledge/aiclone/transcripts/`
     - `knowledge/ingestions/`
     Otherwise production will return an empty `source_assets` inventory even if local checks pass.
   - The backend staged deploy excludes heavy raw media under `knowledge/ingestions/raw/` so Railway upload stays below timeout thresholds; runtime source-asset inventory and long-form sync only need the normalized/transcript review artifacts.
   - The backend deploy script now tolerates a missing `docs/persistent_memory_blueprint.md` instead of failing the release.
7. After deploy completes, run the live smoke gate:
   - `npm run verify:production`
8. If both gates pass, treat the release as operational.

## What The Local Gate Checks
- backend smoke coverage for:
  - `GET /health`
  - `GET /api/workspace/linkedin-os-snapshot`
  - `POST /api/workspace/ingest-signal`
- direct service/builder richness for the social feed
- frontend production build success

## What The Production Gate Checks
- backend health endpoint
- live workspace snapshot richness
- live signal preview generation
- analytics/logs fallback routes
- frontend `/ops` availability

## Failure Handling

### If `verify:main` fails
- Do not push.
- Fix the failing layer first:
  - backend smoke failure: inspect `backend/tests/test_workspace_smoke.py`
  - frontend build failure: inspect the Next.js build output
  - dirty worktree confusion: rerun `./scripts/worktree_doctor.py`

### If `verify:production` fails
- Treat that as a release incident.
- Identify which step failed:
  - backend health
  - snapshot payload
  - ingest preview
  - analytics/logs fallback
  - `/ops` page
- Fix the broken service, redeploy, and rerun `npm run verify:production`

## Known Limitation
The GitHub Actions workflow file exists locally at:
- `.github/workflows/main-safety.yml`

It is not yet pushed if the active GitHub token lacks `workflow` scope.
Until GitHub auth is upgraded, the enforced safety system is:
- local `verify:main`
- optional local pre-push hook
- post-deploy `verify:production`

The workflow-backed version is preserved locally on:
- branch `backup/main-safety-with-workflow`

## Notes
- `verify:main` may coexist with append-only memory files changing in the background. Review memory dirt separately from code dirt.
- The staged deploy script is the canonical release path for Railway. Do not assume unrelated repo dirt will ship; the script stages a narrow deploy context on purpose.
- The goal is not “nothing ever fails.” The goal is “failures are caught in a known gate with a known next step.”
- Keep this SOP in sync with `SOPs/_index.md`, `workspaces/linkedin-content-os/AGENTS.md`, and `workspaces/linkedin-content-os/README.md`.
