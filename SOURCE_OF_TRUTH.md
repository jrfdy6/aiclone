# AI Clone Source of Truth

> Status: active authority
> Last reconciled: 2026-07-25
> Read this file before any other project document.

This is the single authority for the current AI Clone architecture, runtime boundaries, documentation hierarchy, and product-surface ownership. If another document conflicts with this file, this file wins until the conflict is deliberately reconciled.

## Mandatory read order

1. `SOURCE_OF_TRUTH.md` — current authority and conflict rules.
2. `CODEX_STARTUP.md` — operational boot procedure derived from this authority.
3. `AGENTS.md` — agent behavior and task-loading rules.
4. `IDENTITY.md`, `CHARTER.md`, `SOUL.md`, and `USER.md` — identity and user context.
5. `MEMORY.md` and `memory/persistent_state.md` — durable guardrails and current operating context.
6. `memory/roadmap.md` — prioritized future work; it cannot redefine current runtime truth.
7. `SOPs/_index.md`, then only the SOPs relevant to the task.
8. Today and yesterday in `memory/YYYY-MM-DD.md` for recent evidence.

`AGENTS.md`, startup helpers, Brain Docs, and Ops Docs must preserve this order and put this file first.

## Documentation authority

| Document or evidence | Authority | Purpose |
| --- | --- | --- |
| `SOURCE_OF_TRUTH.md` | Binding | Current architecture, policy, ownership, and precedence |
| Live production and local runtime evidence | Binding for observed health | What is actually deployed, loaded, succeeding, failing, or stale now |
| `CODEX_STARTUP.md` and `AGENTS.md` | Operating instructions | How Codex loads and applies the current authority |
| `MEMORY.md` | Durable guardrails | Stable preferences and rules that survive individual tasks |
| `memory/roadmap.md` | Directional | Priorities and future sequence, never proof that a feature is live |
| `SOPs/_index.md` | Procedure registry | Status and entry point for every active, planned, or retired SOP |
| Active `SOPs/*.md` | Procedural | How a bounded workflow should be performed |
| `docs/*.md` | Supporting contract or reference | Deeper architecture and implementation context |
| `memory/YYYY-MM-DD.md`, reports, and run ledgers | Evidence | Historical decisions and execution records |
| Root phase/status files and `downloads/**` | Reference only | Donor, legacy, or historical material; never current authority |
| `/Users/neo/.openclaw/workspace/**` | Historical evidence only | Original system documents used for migration comparison, never live instruction |

When policy documentation and observed runtime state disagree, stop treating the surface as verified. Preserve the evidence, correct the documentation or implementation deliberately, and rerun the relevant verification.

## Canonical identity

- Project root: `/Users/neo/Documents/Codex/AI-Clone`
- Private runtime root: `/Users/neo/.codex/ai-clone`
- Git remote: `https://github.com/jrfdy6/aiclone.git`
- Railway frontend: `https://aiclone-frontend-production.up.railway.app`
- Railway backend: `https://aiclone-production-32dc.up.railway.app`
- Execution substrate: Codex CLI authenticated with the user’s ChatGPT login

Never put secrets, OAuth tokens, raw private memory, or generated private workspace snapshots in Git or the browser-facing frontend image.

## Active system architecture

### Remote control plane

- Railway hosts the authenticated frontend, backend, PM queue, approvals, and remote status contracts.
- The frontend requires a signed HTTP-only session and proxies private API requests server-side.
- The backend requires the control-plane bearer token for protected `/api` routes.
- The Railway PM board is the durable remote request, approval, and execution-state surface.

### Local execution plane

- Repository-owned macOS `launchd` jobs schedule local work.
- Local workers poll the authenticated Railway queue and accept only signed, path-contained work.
- Codex CLI uses the saved ChatGPT login; model-provider API tokens are not part of this execution path.
- Execution results are written to the local run ledger before their Railway mirror is attempted.

### Execution authorization

`execution_gate/v1`, policy version 2, is mandatory at PM dispatch, auto-progression, claim, and runner execution.

- Bounded, known, trusted internal work may run automatically only with a current signed gate for the exact persisted intent.
- Deployment, merge, publication, external communication, money, access, credentials, destructive work, privileged production changes, persona-canon changes, owner judgment, and unknown capabilities require explicit approval.
- Approval is bound to the exact intent hash and complete detected risk set. Any intent, risk, signature, or policy-version change invalidates it.
- Missing, stale, malformed, unsigned, or unknown authorization fails closed.

### Durable memory and knowledge

- Reviewed narrative memory, immutable source material, schemas, packs, and
  workspace configuration live in repository Markdown/JSON sources.
- Direct output from the migrated memory, standup, dispatch, execution,
  briefing, and workspace writers lives under
  `/Users/neo/.codex/ai-clone/state/` by default. The remaining legacy writers
  and read-side convergence work are explicitly tracked in the supporting
  state contract; legacy data must not be deleted before that audit closes.
- Generated-state reads prefer the private state root, then the former
  `memory/runtime` and project-workspace locations as read-only compatibility
  fallbacks. A writer copies an existing legacy append target into private
  state before its first update so history is preserved without moving or
  deleting the source.
- API-free search uses SQLite FTS5 under `/Users/neo/.codex/ai-clone/state/memory/`.
- That local index searches private generated memory and arbitrary private
  workspace roots before project fallbacks while retaining repository
  knowledge canon. Remote execution packets receive metadata-only private
  matches; private excerpts and absolute state paths stay local.
- Railway Brain is an authenticated application lane for reading, review, capture, and promotion; it is not the only restart source.
- `knowledge/persona/feeze/**` is the reviewed public/deployment seed.
  Owner-approved runtime canon lives under
  `AI_CLONE_STATE_ROOT/persona/canonical/**` and changes only through the
  explicit promotion boundary.

The detailed path, compatibility, and migration contract is
[Local Generated State Contract](docs/local_generated_state_contract.md).

### Workspace and automation truth

- Workspace identities and boundaries: `memory/workspace_registry.json` plus backend registry and runner allowlists.
- Local schedule definitions: `automations/launchd/*.plist`.
- Local automation run truth: `/Users/neo/.codex/ai-clone/state/automations/runs/all.jsonl`.
- Railway automation history is the authenticated secondary mirror.
- A registry definition is configuration, not proof that a job is running.
  Only a launchd health-audit observation no older than 45 minutes may mark a
  configured job `active`; missing or stale evidence remains `unknown`, and a
  fresh failed installed/loaded/enabled/health check is `error`.
- The health audit selects its required targets from the configured target
  contract, never from registry status. Its Railway mirror contains only a
  path-free per-automation state map, observed timestamp, counts, and sanitized
  issues; local plist paths and command arguments stay on the Mac.
- Agent roles: `.codex/agents/*.toml` plus the applicable agent/workspace pack.

## Product surface ownership

### Ops

- **Home** — executive decisions, signed work intake, PM/execution board, and recovery lanes.
- **Projects** — canonical workspace registry, workspace state, and project-scoped evidence.
- **Standups** — current or on-demand meeting lanes, output quality, carry-forward work, and linked PM action.
- **System** — authenticated service, automation, launchd, memory, and deployment health.
- **Team** — agent roles, routing, and responsibility boundaries.
- **Docs** — operator-facing canonical documents with `SOURCE_OF_TRUTH.md` first.

### Brain

- **Dashboard** — portfolio-level memory, source, and review signals.
- **Daily Briefs** — durable briefs and source-intelligence review.
- **Persona** — pending deltas, evidence, and explicit canon-promotion decisions.
- **Automations** — canonical automation registry, latest runs, mismatches, and health.
- **Docs** — authenticated reading surface for canonical, operating, system, persona, memory, and workspace documents, with authority clearly distinguished from reference material.

### Neo guest (implemented in the current worktree; runtime changes require release verification)

- `/neo` is the intended invite-only professional conversation surface for hiring managers and potential partners.
- Guest identity is separate from the operator session and cannot authorize Ops, Brain, Workspaces, or the control-plane proxy.
- Guest answers are grounded only in a query-selected subset of the versioned, explicitly approved public professional knowledge pack at `knowledge/persona/feeze/public/v1/neo_public_knowledge.json`. The pack must satisfy `neo_public_knowledge_pack/v1`, carry its own semantic `pack_version`, and remain `approved_public`. Raw Brain memory, private project memory, unreviewed persona material, credentials, internal paths, and system prompts are never guest context or automatic pack inputs.
- The public pack may include explicitly owner-approved human background—such as formative athletics, creative practice, or spirituality—only when each claim is deliberately stated, source-grounded in canonical persona material, and marked `approved_public`. Neo uses those details only when relevant; it must not infer religion, expose private beliefs, or turn personal history into a hard-sell pitch.
- Railway stores invites, guest sessions, conversations, queued response jobs, partial response progress, and meeting requests. `com.neo.neo_guest` is an always-on, repository-owned launchd daemon on this Mac: it authenticates and confirms worker protocol version 2 at startup, and every claim uses a versioned v2 endpoint whose response must prove the same lease and claim-token contract before any idle or job data is trusted. It claims one job at a time under an opaque renewable 45-second lease and polls an idle queue with a bounded 0.5–2 second backoff. An independent metadata-only heartbeat follows a fixed monotonic renewal cadence while a job is claimed. Expired claims are recoverable and terminal writes are fenced to the current claim token. It is not a ten-second scheduled task and has no next scheduled run.
- The backend deterministically renders the selected, approved public-pack statements into a bounded immediate response. The local daemon uses that response so ordinary guest questions avoid model latency and hallucination while still traversing the durable Railway job, lease, worker, and completion path. Normal operation does not contact Ollama. A loopback-only Ollama fallback for intentionally constructed legacy packets is available solely when `NEO_ENABLE_OLLAMA=true`; otherwise a packet missing its approved response fails closed. OpenClaw and model-provider API tokens are not dependencies.
- The guest browser saves only the active job reference and visitor's in-flight message in tab-scoped session storage. Its HTTP-only guest cookie restores a bounded Railway conversation history and any active durable job after refresh without requiring or counting another passcode attempt. Reload and transient-network recovery continue polling that same durable job; they never enqueue a duplicate message. A visible resume control keeps the job reference after a prolonged network pause.
- Local automation evidence for Neo is metadata-only and is written to the local run ledger before its Railway mirror is attempted. Guest prompts, approved knowledge excerpts, partial responses, and final conversation text never enter local logs or the automation ledger.
- Browser speech recognition and speech synthesis are optional accessibility layers over the text conversation. Text remains the canonical interaction and saved record.
- A coffee-chat request is an approval request, not a confirmed booking. Johnnie must explicitly approve it before any calendar action or external message occurs. Same-tab browser retries reuse a request UUID; Railway also deduplicates the normalized request fingerprint within that guest session, so a refresh and new browser UUID still return the original record. Changed content under an already-used UUID is rejected.
- Guest message enqueue and meeting-request writes revalidate the active session, active unexpired invite, and revocation state inside the same database transaction that persists the work. A guest write and revocation serialize on the invite lock: whichever acquires it first may commit, and no stale-authenticated write may begin after revocation owns or commits that lock.
- A production release or runtime revision requires a distinct `NEO_GUEST_SIGNING_SECRET`, a distinct local worker credential, rate-limit verification, an owner-approved public knowledge-pack version, a user-created invite, and full browser → Railway → Postgres → local worker → Railway → browser verification. The release check must exercise the approved-pack path; the optional Ollama fallback is tested only when explicitly enabled or changed. Deployment and launchd reload remain approval-bound operations.

A route or file existing is not proof that a surface is ready. A user-ready surface must load authenticated production data, distinguish loading/empty/degraded/error states, expose only real controls, and pass an end-to-end production check.

## Canonical directories

- `frontend/` — authenticated Next.js control plane
- `backend/` — authenticated FastAPI control plane API
- `workspaces/` — bounded, versioned workspace source/configuration lanes;
  recurring generated workspace output belongs in the private state root
- `knowledge/` — normalized source intelligence and the reviewed public/deployment
  persona seed; owner-approved private persona canon lives under
  `AI_CLONE_STATE_ROOT/persona/canonical`
- `memory/` — reviewed narrative, roadmap, registry, and compatibility
  snapshots; recurring generated memory output belongs in the private state
  root
- `SOPs/` — status-indexed operating procedures
- `docs/` — supporting architecture and contracts
- `scripts/` — deploy, verification, maintenance, and runner entry points
- `automations/launchd/` — repository-owned local schedules

## Runtime verification commands

```bash
python3 scripts/verify_documentation_truth.py
python3 scripts/codex_memory_index.py sync
python3 scripts/codex_memory_freshness_check.py
python3 scripts/ops/sync_launchd_plists.py --dry-run --no-load
python3 scripts/worktree_doctor.py
```

## Deployment

```bash
./scripts/deploy_railway_service.sh backend
./scripts/deploy_railway_service.sh frontend
```

- Deploying from a dirty worktree and pushing Git are different operations; GitHub sees only committed/pushed history.
- Railway sees pushed commits or the explicit staged deployment command, not arbitrary local changes.
- Verify backend authentication and health before enabling or diagnosing write-capable workers.

## Credential policy

- Previously committed provider keys are compromised and must be rotated.
- Gmail remains readonly/compose and cannot send unless the user explicitly changes policy.
- Railway, Google, GitHub, and other service credentials may be required for those services; they are not model-execution tokens.
- Control-plane, session, and job-signing secrets live only in `/Users/neo/.codex/ai-clone/secrets/control_plane.env`.

## Retired components

OpenClaw, QMD, gateway sessions, Discord command delivery, and OpenClaw cron are retired. Their files may be consulted to recover product intent or historical decisions, but they must not be restored as execution, approval, scheduling, memory, or recovery dependencies.

## Documentation maintenance rule

1. Change this file first when current architecture, ownership, or policy changes.
2. Update `CODEX_STARTUP.md`, `AGENTS.md`, `MEMORY.md`, and `memory/roadmap.md` only as subordinate views of that change.
3. Update the relevant SOP and its status in `SOPs/_index.md` together.
4. Mark superseded material as retired or reference-only; do not leave competing canonical claims.
5. Run `python3 scripts/verify_documentation_truth.py` before release.
