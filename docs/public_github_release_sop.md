# Public GitHub Release SOP

> Status: supporting public-source reference. In the private canonical
> workspace, `SOPs/public_github_release_sop.md` is the indexed active procedure
> and owns current ticket, authorization, and deployment status.

## Purpose

Publish deployable AI Clone source without publishing personal identity, credentials, private operating data, or contaminated Git ancestry.

## Non-negotiable boundary

The canonical private workspace and the public Git repository are different surfaces.

- The private workspace may contain reviewed persona records, memory, transcripts, operating documents, and generated state.
- The public repository contains only the receipt-bound projection produced by `scripts/build_public_release.py`.
- Copying a private file into the public branch to repair a deployment is prohibited.
- A clean current tree does not make inherited history safe.

## Required controls and outcomes

Before building, provide an external private-literal denylist stored outside the
repository and a reviewed `release/public_source_manifest.json` digest. Passing
application/privacy verification and a clean, approved, single-root Git lineage
are required outcomes before push or release; they are not assumed inputs.

The denylist contains private names, organizations, account identifiers, and other owner-specific literals. CI receives it only through a protected GitHub Actions secret. Neither its contents nor matching source text may be printed.
The protected workflow materializes it only for the standard-library privacy and
history verifier, deletes it immediately, and runs dependency installation,
application tests, and builds afterward with a non-secret sentinel.

## Build and verify

```bash
export AI_CLONE_PRIVATE_DENYLIST_FILE=/path/outside/repository/private-literals.txt
AI_CLONE_PUBLIC_OUTPUT_ROOT=/absolute/new/public-candidate npm run verify:public
```

The gate must:

1. compute and bind the exact manifest digest;
2. create a new isolated candidate;
3. scan only allowlisted source and fail closed on privacy or secret policy violations;
4. normalize file permissions to Git-portable `0644`/`0755` modes and bind those modes in the immutable receipt;
5. verify the immutable receipt before tests mutate the candidate;
6. import the backend and exercise `/health`;
7. run the public-boundary tests;
8. run frontend tests and a production build;
9. perform no model call, publication, learning update, or external message.

When `AI_CLONE_PUBLIC_OUTPUT_ROOT` names a new directory outside the private
workspace, the gate rebuilds a clean candidate after testing, requires its
receipt to match the tested candidate exactly, verifies it again, and preserves
that clean copy for the orphan Git checkout. Without this variable, the gate
uses and removes an ephemeral candidate.

Inside that committed public checkout, the hook and GitHub workflow set
`AI_CLONE_PUBLIC_GIT_TREE_MODE=1`. In this explicit mode the same gate verifies
the receipt, approved lineage, complete reachable history, and application from
the exact Git tree; it does not try to rebuild private-source file mappings that
do not exist in the public projection.

## Branch procedure

1. Create the first public branch as an orphan; never branch it from legacy `main`, `fellowship-release`, a snapshot branch, or an old tag.
2. Populate the orphan worktree only from the verified candidate.
3. Use the exact non-personal Git identity `AI Clone Release` with a GitHub no-reply address.
4. Push a new `codex/public-source-*` topic branch without rewriting existing refs.
5. Review the exact committed tree and GitHub Actions result.
6. After the exact topic SHA passes the required protected check, promote it
   only by a non-force fast-forward push of that unchanged SHA to
   `public-release`. Do not use GitHub merge, squash, or rebase buttons for this
   release lane: GitHub can rewrite the committer identity, making the
   protected history differ from the verified commit.
7. Immediately prove `public-release` resolves to that exact SHA and that
   force-push and deletion remain disabled.
8. Promote a clean public default branch only with exact owner approval because changing the default branch and retiring legacy refs changes the repository control plane.
9. Never merge the orphan public lineage into a contaminated branch or merge a contaminated branch into it.

An unrelated-history pull request is not a safe promotion mechanism. Review happens against the receipt and commit tree until a clean public base branch exists.

## Historical remediation

Before calling the owner-controlled public source clean and deployable:

1. revoke or rotate every credential reported by GitHub secret scanning;
2. confirm the clean public branch is complete and deployable;
3. obtain exact owner approval for the named branches and tags to delete or rewrite;
4. change the default branch to the clean public branch;
5. delete contaminated legacy branches and tags;
6. classify GitHub secret-scanning alerts accurately after rotation or
   revocation is verified;
7. rescan all current owner-controlled GitHub heads, tags, and release tags.

GitHub Support determined on 2026-08-17 that rotation or revocation is
sufficient and that no pull-ref purge or history rewrite is required. Ticket
`#4669337` was updated but is not known closed, and the old GitHub-owned pull
refs are not known purged; neither condition is a publishing,
deployment-source-connection, or Release gate. GitHub-owned pull refs 1–4 remain
truthful historical residue, while refs 5–6 descend from the approved clean
lineage. Do not attest that every server-owned historical ref belongs to the
approved single-root lineage. Before reconnecting
a GitHub deployment source or creating a `public-v*` tag or Release, require the
exact sanitized tree/receipt, protected checks, current owner-controlled
head/tag ancestry and secret scans, runtime-readiness gates, and explicit owner
authorization.

History deletion is destructive and does not remove copies held by forks, caches, or prior clones. Credential rotation remains mandatory.

## GitHub Releases

- Only annotated tags matching `public-vMAJOR.MINOR.PATCH` are eligible.
- The tag must point into the single-root public lineage.
- The root commit must contain `.public-lineage-root`.
- Every visible tag must also belong to that lineage before the automated release job can proceed.
- Every visible tag must match the `public-vMAJOR.MINOR.PATCH` convention. A
  nonconforming legacy tag must be deleted after exact approval, not repointed.
- Every owner-controlled remote head and release tag must descend from the
  approved root. GitHub-owned pull refs are historical evidence, not release
  inputs.
- The public verification workflow must pass on the tagged commit.
- Release notes and source archives must be generated from that exact tag.
- Never create a GitHub Release from a legacy or snapshot tag.
- Release notes are derived from the verified receipt, not generated from pull-request text.

## Railway and Vercel

- Railway backend root: `backend/`
- Railway frontend root: `frontend/`
- Vercel root: `frontend/`
- Platform credentials and private runtime inputs stay in platform-managed secrets or authenticated storage.
- Neo guest facts stay outside Git. Before connecting a GitHub-sourced Railway
  backend, inject the exact approved `neo_public_knowledge_pack/v1` JSON as
  `NEO_PUBLIC_KNOWLEDGE_JSON` and require the protected aggregate knowledge
  status to be ready, digest-bound to the reviewed release, integrity verified,
  and populated. Never print or commit the value; invalid, unbound, or missing
  runtime JSON blocks migration. Run
  `REQUIRE_NEO_RUNTIME_ENVIRONMENT=1 npm run verify:production` for this source
  migration so a staged-file fallback cannot count as proof.
- A verified private runtime-data channel for owner-specific behavior is a prerequisite to connecting either deployment platform to GitHub, not a prerequisite to building or reviewing the public source branch.
- Both Railway application services are connected to protected
  `jrfdy6/aiclone:public-release` with Wait for CI. Receipt-bound staged upload
  remains a separately approval-bound fallback.
- The private runtime channel is refreshed only by the signed local
  `refresh_feezie_workspace` action. It builds both inputs before a network
  write and synchronizes only the closed privacy-safe
  `feezie_weekly_plan_projection/v1` plus the private
  `feezie_runtime_context/v1` bundle. It makes no Codex/model-provider call,
  uses no model-provider API key, publishes nothing, updates no learning, and
  does not recompute persona review. `refresh_persona_review` remains a
  separate DB-owned recomputation.
- Before connection or reconnection, the local public-source and deterministic
  clean-checkout gates must prove: 36-hour private-runtime freshness with only
  5 minutes of future skew; `checked_at`, persisted `context_generated_at`,
  `age_seconds`, and `stale_after_seconds: 129600`; exact Brain sync
  workspace/type/payload-hash/disposition validation; the bound owner-only
  local context cache; and closed aggregate-only browser projections for
  `source_assets`, `content_reservoir`, `operator_story_signals`,
  `content_safe_operator_lessons`, `persona_review_summary`, and
  `long_form_routes` in both Workspace and Brain.
- Changing a deployment source is privileged production work and requires exact
  owner approval naming the platform, service, `public-release` branch, project
  root, and rollout order. Passing local gates does not authorize connection or
  deployment.
- A GitHub-triggered deploy must prove owner-specific runtime context readiness after deploy. Generic fallback behavior is not an acceptable substitute for FEEZIE quality.
- The authenticated frontend must complete the exact Railway safe-public-feed
  run before queueing the Mac action, poll only its bounded exact-card status,
  and require a fresh safe weekly projection plus ready private runtime context
  whose timestamps bind to that job. The browser receives no private bundle,
  raw weekly rows, storage receipts, or executor errors.
- If that readiness contract fails, stop the protected release. Use the
  receipt-bound staged Railway fallback only after separate exact approval; it
  is not an automatic bypass.
- A GitHub Release certifies public source safety; it does not certify owner-specific production context or FEEZIE output quality.

## Rollback

Roll back code only to another verified commit in the clean public lineage. Do not restore a contaminated tag or reintroduce private files to recover functionality. Restore private runtime inputs through their authenticated channel and rerun production verification.
