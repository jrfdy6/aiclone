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

Changing or deleting existing public Git history is a separate operation. This builder prevents new exposure; it does not remove data already reachable through branches, tags, cached commits, forks, or prior clones.

## Git and deployment truth

The public branch is a single-root orphan lineage marked by `.public-lineage-root`. CI verifies that the tracked checkout exactly matches its committed receipt; an allowlisted subdirectory passing a scan is not enough when extra tracked files exist.

GitHub Releases are limited to annotated `public-vMAJOR.MINOR.PATCH` tags whose complete tag set remains inside that lineage. Existing legacy tags must be remediated before the release job can pass.

Railway and Vercel may build from the clean public branch, but owner-specific behavior still requires an authenticated private runtime-data channel. A generic fallback or successful health check must never be reported as proof that FEEZIE has its approved voice examples and anonymized evidence.
