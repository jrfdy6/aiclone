# Public Repository Boundary

This repository has two different release concerns:

1. public source code that may be committed to a public Git host and used by a deployment integration;
2. private runtime data that may be synchronized to an authenticated service but must never enter public Git history.

`release/public_source_manifest.json` is the allowlist for the first concern. The existing application deployment process is not a substitute for this public-source boundary.

## Public candidate

The public candidate contains only:

- backend application source and service configuration;
- frontend application source, static assets, dependency locks, and service configuration;
- the minimum generic runtime helper imported by the backend;
- the public candidate builder, its manifest, this contract, and its focused tests.
- the public Git safety workflow, release SOP, lineage marker, and non-personal repository metadata.

The public candidate never includes persona material, memory, transcripts, ingestions, workspace content, automation configuration, installed scheduler definitions, local state, credentials, operating-system metadata, or private operating documents.

## Content policy

The builder fails closed when an allowlisted file contains:

- a high-confidence credential or private-key shape;
- a quoted credential literal that is not an explicit placeholder;
- a non-reserved email address;
- a platform-specific user-home path;
- a literal from the external private denylist;
- an unreviewed binary format.

Reserved example email domains are permitted in synthetic fixtures. A non-reserved email may appear only in an exact lockfile path named by `third_party_email_metadata_paths`, because generated third-party metadata can contain upstream maintainer contact text.

The external denylist is stored outside the repository. It should contain one private literal per line, such as a personal name, organization name, account identifier, or known credential fragment. The builder reports only the relative file path and policy code; it never reports the matched literal or surrounding source text. The canonical manifest requires this denylist for both build and verification.

## Reproducible build

Review the exact manifest digest, then build into a new directory:

```bash
MANIFEST_SHA="$(python3 scripts/build_public_release.py manifest-sha256)"
python3 scripts/build_public_release.py build \
  --candidate-root PUBLIC_CANDIDATE_DIR \
  --expected-manifest-sha256 "$MANIFEST_SHA" \
  --private-denylist PRIVATE_DENYLIST_FILE
```

The destination must not already exist and must be outside the source tree. The builder copies through a temporary sibling directory and atomically publishes the finished candidate. It records sorted relative paths, modes, sizes, and content hashes in `.public-release/receipt.json`. No timestamp, source-machine path, Git identity, or denylist value enters the receipt, so identical reviewed inputs produce identical receipt bytes and tree hashes.

Verify the candidate with the receipt digest returned by the build:

```bash
python3 scripts/build_public_release.py verify \
  --candidate-root PUBLIC_CANDIDATE_DIR \
  --expected-receipt-sha256 RECEIPT_SHA \
  --private-denylist PRIVATE_DENYLIST_FILE
```

For the complete application gate plus a clean candidate preserved for Git,
use a new external output path:

```bash
export AI_CLONE_PRIVATE_DENYLIST_FILE=/path/outside/repository/private-literals.txt
AI_CLONE_PUBLIC_OUTPUT_ROOT=/absolute/new/public-candidate npm run verify:public
```

The gate tests an ephemeral copy because dependency installation and builds
create ignored files. It then rebuilds the requested output from the same
source, requires the receipt digest to match the tested copy, and verifies the
preserved output before returning success.

## Deployment data

Private production inputs belong in authenticated database records, private object storage, platform-managed secrets, or a separately authorized signed synchronization path. A public Git deployment must remain functional without committing the private files that produced those records.

Neo's explicitly approved guest facts also remain outside the public Git tree.
A GitHub-sourced Railway backend receives the exact validated
`neo_public_knowledge_pack/v1` JSON through `NEO_PUBLIC_KNOWLEDGE_JSON`; a staged
private backend may carry only the one approved
`public/v1/neo_public_knowledge.json` file, never the surrounding subtree. The
service binds the pack's canonical digest and version to the reviewed release.
The protected
`/api/neo/admin/knowledge-status` response is aggregate-only and must prove a
ready, integrity-verified exact version and nonzero entry count without
returning identity or knowledge content. Missing, malformed, oversized,
unbound, or unapproved runtime JSON fails closed rather than falling back to
generic guest claims.

Owner-specific public-copy redactions also remain outside the public tree. The
backend receives a reviewed literal-to-public-replacement JSON object through
`AI_CLONE_PUBLIC_REDACTION_MAP_JSON`. Source code contains only the generic
loader and safe public replacements; private organizations, locations, and
vendors are supplied through the managed runtime variable. The external
denylist scan also normalizes common regex escapes so a private literal cannot
be hidden in an escaped pattern.

The private staged Railway lane also excludes backend tests and rejects staged
symlinks and high-confidence credential literals before upload. This stage
audit complements the public Git projection scan; it does not make private
application data public.

For FEEZIE, the authorized application-data path is the authenticated Brain
workspace sync of `feezie_runtime_context/v1` under workspace `feezie-os` and
snapshot type `feezie_runtime_context`. The local runner derives a strict,
hash-bound bundle from the approved strategy, canonical persona chunks,
approved voice examples, and anonymized public-safe proof. Runtime readers use
the filesystem first and that row only when the private files are absent. The
row is rejected for raw-source fields, credentials, email addresses, absolute
paths, unknown fields, invalid strategy, missing required facets, excessive
size, receipt/hash mismatch, age beyond 36 hours (`129600` seconds), or a source
time more than 5 minutes (`300` seconds) in the future.

The Brain sync response must prove the retained row, not merely return HTTP
success. `snapshots.feezie_runtime_context` must identify workspace `feezie-os`
and snapshot type `feezie_runtime_context`, return the exact submitted
`payload_sha256`, and use only these accepted receipt pairs: `stored: true` with
`stored` or `recovered_invalid_runtime`, or `stored: false` with
`idempotent_same_hash`.

The browser must never receive that row. It may receive only
`feezie_private_runtime_context_status/v1`, whose bounded contract is state,
reason codes, counts/booleans for persona canon, approved voice examples,
anonymized proof, and source integrity, `checked_at`, the persisted
`context_generated_at`, `age_seconds`, `stale_after_seconds: 129600`, plus an
aggregate-only data policy. A clean-checkout release must prove the fallback
and fail-closed cases through the deterministic public lifecycle gate before a
deployment source is changed.

The authenticated Workspace and Brain browser responses must also replace all
six private grounding sections—`source_assets`, `content_reservoir`,
`operator_story_signals`, `content_safe_operator_lessons`,
`persona_review_summary`, and `long_form_routes`—with closed
`feezie_private_grounding_browser_status/v1` availability/count objects. No
underlying row, title, name, identifier, hash, filename, path, URL, or excerpt
belongs in those responses.

The local generation context cache is not a replacement private-data channel.
It uses owner-only `0700` directories and `0600` regular files, no-follow and
size-bounded reads, and atomic replacement. Its key binds cache version,
workspace, snapshot hash, and request fingerprint; its payload SHA-256 binds
the exact context packet and metadata. Missing, naive, future beyond 5 minutes,
expired, mismatched, symlinked, or oversized entries are cache misses.

Changing or deleting existing public Git history is a separate operation. This builder prevents new exposure; it does not remove data already reachable through branches, tags, cached commits, forks, or prior clones.

## Git and deployment truth

The public branch is a single-root orphan lineage marked by `.public-lineage-root`. CI verifies that the tracked checkout exactly matches its committed receipt; an allowlisted subdirectory passing a scan is not enough when extra tracked files exist.

GitHub Releases are limited to annotated `public-vMAJOR.MINOR.PATCH` tags whose complete tag set remains inside that lineage. Existing legacy tags must be remediated before the release job can pass.

Railway and Vercel may build from the clean public branch, but owner-specific
behavior still requires an authenticated private runtime-data channel. Before
either platform is connected or reconnected to GitHub, the exact sanitized
public tree and receipt, protected public-source check, current
owner-controlled head/tag ancestry and secret scans, and the local
public-source plus deterministic runtime/cache/browser readiness gates must
pass. GitHub Support determined on 2026-08-17 that rotation or revocation is
sufficient and that pull-ref purge, history rewrite, and ticket closure are not
prerequisites. These checks do not authorize a deployment. A generic fallback
or successful health check must never be reported as proof that FEEZIE has its
approved voice examples and anonymized evidence.
