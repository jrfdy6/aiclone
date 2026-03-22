# Source of Truth for Project

This file is the short-form current-state reference. For the full operator map, read `CODEX_STARTUP.md`.

## Canonical identity
- Repo root: `/Users/neo/.openclaw/workspace`
- Git remote: `https://github.com/jrfdy6/aiclone.git`
- Frontend service: `aiclone-frontend`
- Backend service: `aiclone-backend`
- Production frontend: `https://aiclone-frontend-production.up.railway.app`
- Production backend: `https://aiclone-production-32dc.up.railway.app`

## Current product structure
- `Ops` is the umbrella Mission Control surface.
- `LinkedIn OS` is the first child workspace and now has a dedicated UI surface at `/linkedin`.
- `Brain` holds persona, briefs, docs, automations, and Open Brain telemetry surfaces.
- Canonical workspace data should come from repo files and production APIs, not ad hoc one-off scripts.

## Canonical directories
- `frontend/`: Next.js client
- `backend/`: FastAPI app
- `workspaces/linkedin-content-os/`: child workspace files, plans, drafts, research
- `knowledge/persona/feeze/`: canonical persona bundle
- `knowledge/ingestions/`: normalized ingestions for direct/bootstrap loading
- `SOPs/`: production-safe operational procedures
- `scripts/`: deploy, bootstrap, and maintenance scripts

## Standard deploy paths
- Git push path:
  - `git status -sb`
  - `git add <files>`
  - `git commit -m "<message>"`
  - `git push origin main`
- Railway deploy path:
  - `./scripts/deploy_railway_service.sh frontend`
  - `./scripts/deploy_railway_service.sh backend`

## Standard production data paths
- Use `SOPs/direct_postgres_bootstrap.md` for:
  - `scripts/bootstrap_ingestions_direct.py`
  - `scripts/bootstrap_open_brain_memory_direct.py`
  - `scripts/bootstrap_session_metrics_direct.py`

## Runtime-specific guardrails
- Local OpenClaw overrides are documented in `docs/local_runtime_overrides.md`.
- Frontend/backend env sync is documented in `frontend/README_ENV_SYNC.md`.
- If a fresh session claims it cannot push or deploy, it should test the actual command path first and request escalation when needed.
