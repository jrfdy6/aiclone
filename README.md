# AI Clone

AI Clone is a human-controlled operating system for grounded conversation, durable agent work, and evidence-bounded content workflows.

This public repository contains deployable application source only. Personal identity data, persona records, memory, transcripts, credentials, account details, private workspace state, and generated drafts are deliberately outside Git.

## Repository boundary

The public source projection is built from an explicit allowlist in `release/public_source_manifest.json`. The builder rejects high-confidence credentials, private keys, non-example email addresses, user-home paths, unreviewed binaries, forbidden private directories, and literals supplied through an external private denylist.

The source-of-truth split is:

- `backend/` — FastAPI application and public-safe service code
- `frontend/` — Next.js application and public-safe UI code
- `scripts/build_public_release.py` — deterministic public projection and receipt verification
- `docs/public_repository_boundary.md` — public/private data contract
- `docs/public_github_release_sop.md` — branch, CI, tag, and GitHub Release procedure

Private runtime inputs must arrive through authenticated storage or platform-managed variables. They must never be copied into this repository to make a deployment work.

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 3001
```

Frontend:

```bash
cd frontend
npm ci
npm run dev -- --port 3000
```

Without private runtime inputs, owner-specific features fail closed or use neutral scaffolding. They must not fabricate biography, evidence, or voice.

## Verification

The public release gate does not call a model or require a provider API key.

```bash
export AI_CLONE_PRIVATE_DENYLIST_FILE=/path/outside/repository/private-literals.txt
npm run verify:public
```

The gate builds a new isolated candidate, verifies its receipt, imports the backend, checks health, runs the focused public-boundary tests, installs frontend dependencies, runs frontend tests, and creates a production build.

## Deployments

- Railway backend project root: `backend/`
- Railway frontend project root: `frontend/`
- Vercel project root: `frontend/`

Connecting a GitHub branch to Railway or Vercel is allowed only after that branch belongs exclusively to the clean public lineage and the private runtime-data readiness check passes. A successful source build is not evidence that owner-specific runtime context is available.

GitHub Releases use annotated `public-v*` tags and are created only after the public-source gate and clean-lineage checks pass. Legacy branches or tags are never valid release sources.

## Security

If a credential ever entered public history, removing it from the current tree is insufficient. Revoke or rotate it first, then remove contaminated refs through a separately approved history migration.

Private implementation. All rights reserved.
