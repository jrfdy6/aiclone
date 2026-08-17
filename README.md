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

Neo's approved guest knowledge also stays outside Git. A GitHub-sourced backend
must receive the validated `neo_public_knowledge_pack/v1` JSON through the
platform-managed `NEO_PUBLIC_KNOWLEDGE_JSON` setting, and its protected
aggregate readiness endpoint must prove the exact release-bound digest and
version with `integrity_verified: true` before traffic is accepted. Validate a
GitHub-source migration with
`REQUIRE_NEO_RUNTIME_ENVIRONMENT=1 npm run verify:production` so a staged-file
fallback cannot satisfy the gate.

GitHub-owned pull refs 1-4 remain as historical residue, so do not claim that
every server-owned historical ref belongs to this clean public lineage. GitHub
Support determined on 2026-08-17 that rotation or revocation is sufficient and
that no pull-ref purge or history rewrite is required. Ticket `#4669337` was
updated; its closure is not a deployment-source gate. Before connecting or
reconnecting Railway or Vercel to GitHub, require the exact sanitized public
tree and receipt, protected public-source check, current owner-controlled
head/tag ancestry and secret scans, and the local public-source,
clean-checkout-runtime, cache-security, and aggregate-browser gates. Those
checks do not authorize a deployment.

For FEEZIE, ready private runtime context is at most 36 hours old and no more
than 5 minutes ahead of the verifier clock. Its aggregate browser status reports
`checked_at`, the persisted `context_generated_at`, `age_seconds`, and
`stale_after_seconds: 129600`. The local Brain sync succeeds only when it
validates workspace `feezie-os`, snapshot type `feezie_runtime_context`, the
exact submitted/retained payload hash, and an accepted stored, recovered, or
same-hash idempotent disposition.

Workspace and Brain expose `source_assets`, `content_reservoir`,
`operator_story_signals`, `content_safe_operator_lessons`,
`persona_review_summary`, and `long_form_routes` only through closed
`feezie_private_grounding_browser_status/v1` availability/count projections.
Rows, text, names, identifiers, hashes, filenames, paths, URLs, and excerpts
remain outside browser responses.

GitHub Releases use annotated `public-v*` tags and are created only after the public-source gate and clean-lineage checks pass. Legacy branches or tags are never valid release sources.

## Security

If a credential ever entered public history, revoke or rotate it first and remove it from the current tree. Treat historical refs as residue after rotation; rewrite history only when the remaining sensitive data cannot be made harmless through rotation and a separately approved migration is warranted.

Private implementation. All rights reserved.
