# SOP: Neo Guest Conversation

> Authority: evolving procedure subordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md). Confirm status in the [SOP Index](./_index.md).

## Purpose

Give approved hiring managers and potential partners a safe way to talk with Neo about Johnnie's professional work and request a 15-minute coffee chat without gaining access to the private AI Clone control plane.

## Boundaries

- Operator and guest authentication are different credentials, sessions, routes, and authorization checks.
- Invite passcodes and guest session tokens are stored as keyed digests, never plaintext.
- Use a unique invite per visitor. The operator can revoke an invite and every session created by it.
- Neo receives only a query-selected subset of the versioned, owner-approved public professional knowledge pack plus that guest's bounded recent conversation. Raw Brain memory, private project memory, unreviewed persona material, and private project files are excluded.
- Text is canonical. Browser speech recognition may populate the text draft and browser speech synthesis may read a response aloud.
- The Mac-local worker completes bounded responses rendered from the approved public pack. Loopback Ollama is disabled by default and is available only when `NEO_ENABLE_OLLAMA=true` for an authorized legacy packet that intentionally omits that response. The worker cannot open operator routes or perform external actions.
- Meeting requests collect name, email, phone, purpose, preferred times, and timezone. They remain `pending` until Johnnie approves or declines them in Neo Inbox.
- Approval records owner intent; it does not create a calendar event in this MVP.

## Public professional knowledge contract

- The only guest knowledge source is `knowledge/persona/feeze/public/v1/neo_public_knowledge.json`.
- The file must validate as `neo_public_knowledge_pack/v1`, use a semantic `pack_version`, and keep both the pack and every entry at `approved_public`.
- Pack content is deliberately curated from public-safe canonical professional claims, stories, wins, biography, resume, and timeline evidence. Brain, project workspaces, raw memory, pending persona deltas, credentials, and internal operating material never sync into it automatically.
- Human background may be included only through an individually owner-approved public entry. Formative athletics, creative practice, and spiritual grounding may explain work style when the visitor's question makes them relevant; Neo must not infer or assign a religious affiliation, disclose private beliefs, or inject those details into an unrelated sales pitch.
- Changing public claims, evidence, source policy, approval state, or pack version requires explicit owner review. A newer pack is not production truth until the relevant release and guest-response checks pass.
- The backend selects only the bounded entries relevant to the visitor's question. The Mac worker does not search Brain or private project files.

## Runtime flow

1. Operator creates a unique invite in `/inbox/neo`.
2. Visitor exchanges the passcode at `/neo` for a guest-only HTTP-only session cookie.
3. The frontend sends new writes to versioned v2 guest endpoints; Railway Postgres records the visitor message and creates a pending Neo job. The legacy write endpoints remain temporarily backward compatible during a backend-first/frontend-second release, while all current-browser idempotency guarantees belong to v2.
4. `com.neo.neo_guest` keeps one repository-owned launchd daemon alive. At startup it authenticates to the worker-capability endpoint and requires protocol version 2, a positive lease contract, and claim-token fencing. Every subsequent claim uses only the versioned v2 claim endpoint and validates that the claim response proves the same protocol before trusting either an idle response or a job. A missing, older, malformed, unauthorized, or rolled-back backend therefore blocks before a job is claimed without adding a second request to each idle poll.
5. The backend renders the selected, approved public statements into a bounded response without copying the guest query. The Mac-local worker uses that response, completing ordinary guest questions without model latency or an Ollama dependency. A loopback-only Ollama fallback exists solely for an authorized legacy packet and only when `NEO_ENABLE_OLLAMA=true`; otherwise a missing approved response fails closed. The daemon polls for one scoped job at a time with a bounded 0.5–2 second idle backoff.
6. Claiming assigns an opaque per-claim token and a renewable 45-second lease. An independent metadata-only heartbeat renews the lease on fixed monotonic deadlines shorter than the lease from claim through terminal acknowledgement; request duration does not get added to the renewal interval. Progress also renews the lease; an interrupted worker leaves a recoverable expired claim, and progress, completion, or failure from an older claim token is rejected. The approved rendered path completes directly.
7. The approved rendered response contains only whole statements from the selected pack entries and has a 1,200-character service cap plus the worker's 7,500-character final cap. Conversation context keeps at most the newest eight messages within an aggregate 8,000-character history budget, always preserving the newest visitor question and keeping the system plus approved public knowledge first.
8. The worker writes the bounded response or failure back to the same job. Completion acknowledgement is retry-safe for the same completed claim and never creates a second assistant message. The browser stores the active job reference and in-flight visitor message in tab-scoped session storage, while the HTTP-only guest cookie bootstraps bounded server history and the oldest active job after refresh. It polls its own job beyond the worker timeout, reconciles an explicitly cleared partial after recovery, preserves current progress through transient failures, resumes the same job after reload, and never repeats the message-creation POST. Browser and frontend-proxy requests have bounded timeouts. After a prolonged network pause the browser keeps the reference and offers a GET-only resume action.
9. Completed and failed executions write metadata-only evidence to the local automation ledger before best-effort Railway mirroring. Guest prompts, public-knowledge excerpts, partial responses, and final text are excluded from local logs and ledger rows.
10. Meeting requests appear in `/inbox/neo` for explicit approval or decline. The browser gives each normalized submission a UUID and reuses it for same-tab ambiguous retries. The backend returns the original request for either the same UUID and content or the same normalized request fingerprint within the session, which preserves deduplication through refresh; different content under the same UUID is rejected.
11. Message enqueue and meeting creation lock and revalidate the guest session plus its active, unexpired invite inside the same transaction as the write. The write and revocation serialize on the invite lock: whichever acquires it first may commit, and a stale authenticated request cannot begin its durable write after revocation owns or commits the lock.

## Release gate

1. Configure `NEO_GUEST_SIGNING_SECRET` as a new 32+ character Railway secret. Do not reuse operator, session, or worker secrets.
2. Confirm `LOCAL_CODEX_BRIDGE_TOKEN` is distinct from `CONTROL_PLANE_SERVICE_TOKEN` and present only in the private Mac runtime and Railway backend.
3. Validate and explicitly approve the public knowledge-pack version intended for release; do not promote raw Brain or project memory into it.
4. At the coordinated maintenance boundary, confirm no guest response is active and stop the previously loaded Neo worker. Do not let an old worker claim across the schema/protocol transition.
5. Deploy the backward-compatible backend first. Verify protected worker capability protocol version 2, the v2 claim route, the legacy guest-write canary, and the strict v2 guest-write contracts before deploying the frontend that switches same-origin proxies to v2.
6. Replace and load the repository launchd plist only after the deployed worker endpoints pass scoped-auth tests. Confirm the installed contract uses `KeepAlive`, has no `StartInterval`, and provides a 180-second exit window.
7. Confirm the reloaded worker reports a successful protocol handshake and `mode=approved_public_knowledge_packet`, with no normal-operation Ollama preload.
8. Create the first test invite from the authenticated Neo Inbox; do not commit the passcode.
9. Verify the full story with a test guest: access → capability handshake → claim → immediate approved-pack response → saved final conversation → retry-safe meeting request → owner approval. Test the guarded Ollama fallback only when it is explicitly enabled or changed. Retry one completion acknowledgement and one meeting POST with their original IDs and confirm each has exactly one durable record.
10. During the synthetic test, interrupt the worker after claim, restart it, and confirm the expired job is recovered once with exactly one assistant message and no stale partial text.
11. Race a revocation against a message and meeting write; confirm the invite lock serializes them, the lock winner commits first, and no new write begins after revocation owns or commits the lock. Confirm revoked invites and old guest sessions fail closed, operator routes reject guest and worker tokens, no private memory appears in responses, and local logs/ledger remain metadata-only.

## Failure behavior

- If the Mac-local worker is offline, preserve the message and show a delayed/failed response; never fall back to a paid model silently.
- If a partial-progress post fails, preserve final generation and completion; progress is best-effort and cannot become a second provider path.
- If a worker stops after claim, allow its lease to expire and recover the same durable job under a new claim token. Never create a second assistant message for one job.
- If the capability handshake does not prove protocol version 2, do not claim. Restore backend/worker compatibility before resuming the daemon.
- If completion commits but its HTTP acknowledgement is lost, retry completion with the same claim token; do not turn an ambiguous acknowledgement into a false failure.
- If guest polling is interrupted, keep the active job reference and partial response and resume with GET requests only. Never turn a browser retry into a second queued message.
- If a meeting POST has an ambiguous result, retry the identical normalized request with the same UUID in the active tab. After refresh, a new UUID with the same normalized fingerprint must still return the original session request rather than insert a duplicate.
- If the public knowledge pack is absent, invalid, unapproved, or outside its versioned contract, fail closed instead of substituting Brain or project memory.
- If signing configuration is missing, invite creation and access fail closed.
- If the local worker credential is missing or ambiguous, the worker cannot claim jobs.
- If the database is unavailable, do not create an in-memory conversation that looks durable.
