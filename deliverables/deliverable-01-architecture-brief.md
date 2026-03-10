# Deliverable 01 — neo-core Phase 1 Architecture Brief

> **Framing:** neo-core is a constrained orchestration spine where auditability is the primary feature and execution is a strictly gated side effect.

## 1. Objectives & Scope Guardrails
- Enforce long-term leverage: no autonomous execution, no public engagement, no payment work, no multi-env orchestration.
- Work domains: strategic tradeoff modeling, systems architecture evaluation, code drafting (no merges), CI/CD workflow generation, deployment readiness scoring, risk classification, backlog prioritization.
- Interfaces: Discord (≤7 structured commands) for control + approvals; Railway-hosted dashboard for read-only observability.
- Hosting: Node.js/TypeScript service on Railway; GitHub Actions → Railway deploy path gated by explicit approval.
- Security: repo-scoped GitHub token, Railway project token, secrets stored off Discord, rollback via tagged releases.

## 2. High-Level Component Map
1. **Discord Command Plane** – structured slash/command interface delivering inputs (diffs, intents) and receiving reports + approval prompts.
2. **Policy & Evaluation Engine** – pure-function module that ingests repo state + guardrails and emits structured evaluations/risk scores; cannot trigger external actions.
3. **Approval Gate** – receives evaluation outputs, records operator approvals as signed artifacts, and hands off only when approval_signature is present.
4. **Execution Adapter** – GitHub Actions/Railway integration that verifies signatures, enforces idempotency, triggers CI/CD, and reports post-deploy status. No approval → no execution.
5. **Immutable Audit Layer** – append-only ledger (write-once, tamper-evident) persisting every significant event and the approval artifacts.
6. **Drift Detection Pipeline** – monitors guardrails, risk distributions, and execution cadence for deviation; escalates via Discord + dashboard alerts.
7. **Observability Dashboard** – Railway-protected, read-only portal for logs, guardrail status, drift signals, and approval lineage.

All components live in the `neo-core` repo but communicate via explicit interfaces and module boundaries to prevent logic creep.

## 3. Data Flow (Happy Path)
1. Developer pushes branch → GitHub webhook notifies neo-core.
2. Discord command (`/evaluate` or similar) requests assessment.
3. Evaluation Engine pulls PR diff/workflow context, applies policy rules, generates:
   - `evaluation_hash` (deterministic hash of diff contents, config snapshot, guardrail version, and model/runtime version)
   - risk classification + justification
   - deployment readiness report
   - recommended CI workflow adjustments (if any)
4. Output logged as `evaluation_produced` event in audit layer.
5. Approval Gate posts structured summary in Discord, awaits `/approve-deploy` command.
6. Upon approval, Gate generates signed `approval_signature`, marks approval artifact as **single-use + 2-hour TTL**, logs `approval_granted` event, and hands artifact to Execution Adapter.
7. Execution Adapter verifies signature, TTL, absence of blocking events, and that no `execution_started` exists for this `evaluation_hash`; only then triggers GitHub Actions workflow to deploy to Railway.
8. CI run status + Railway deploy result streamed back; Adapter logs `execution_started` / `execution_completed` events and posts readiness + post-deploy reports.

## 4. Immutable Audit Layer Specification
- **Storage:** append-only log (SQLite WAL or equivalent) with write-once semantics and hashed chaining.
- **Event Schema:**
  ```text
  event_id             // monotonic counter
  prev_hash            // SHA-256 hash of prior event payload (tamper evidence)
  event_hash           // hash of current payload
  event_type           // evaluation_produced | approval_granted | approval_expired | execution_started | execution_completed | execution_duplicate | risk_escalated | drift_alert | rollback_initiated | rollback_completed | guardrail_violation | dependency_outage | key_rotation
  actor                // system component or operator handle
  input_hash           // reference to evaluated diff/config snapshot
  evaluation_hash      // deterministic hash incl. model/runtime version + guardrail version
  risk_score           // categorical + numeric (e.g., {level: HIGH, value:0.82})
  decision             // PASS | BLOCK | ESCALATE | ROLLBACK
  execution_ref        // CI run ID / Railway deploy ID / rollback tag
  approval_signature   // base64 signature for approval events (Option B model)
  approval_status      // PENDING | USED | EXPIRED
  key_id               // identifier for signing key used (supports key-ring verification)
  timestamp            // ISO8601
  metadata             // JSONB for structured contexts (command ID, channel, dependency state)
  ```
- **Replay Protection & Idempotency:**
  - Approval events include `approval_status`. Execution Adapter performs an atomic compare-and-set (`PENDING -> USED`) **within the same transaction that writes `execution_started`**; transaction spans both updates so no race window exists.
  - Adapter rejects triggers if audit already contains `execution_started` referencing the same `evaluation_hash`/`approval_signature`.
  - Rollbacks recorded as new events, never reversals.
- **Key Storage, Rotation & Verification:**
  - Signing key stored solely in Railway secret store, derived from offline-generated key pair.
  - Each approval event records `key_id`; Execution Adapter maintains a verification key ring (current + N previous) and will accept signatures from keys marked `valid` within TTL window.
  - Rotation logged as `key_rotation` with `old_key_id`/`new_key_id`. Upon rotation, previous key remains in verify set until all outstanding approvals expire; then marked `retired`.

## 5. Component Separation Contracts & Enforcement
- Repo structured as three TypeScript workspaces (`evaluation/`, `approval/`, `execution/`) plus shared types.
- Compile-time guard: each package exports interfaces; circular imports disallowed via TS path mapping + ESLint rules.
- Runtime guard: each service exposes an internal HTTP/gRPC endpoint with explicit schemas; Execution Adapter cannot import Evaluation code directly.

### Evaluation Engine
- Pure-function style: takes `input_hash`, repo metadata, constitution docs, CI configs; emits `EvaluationResult`.
- No side effects, no network calls beyond read-only GitHub fetch.
- Output includes `model_version` + `engine_version` baked into `evaluation_hash`.

### Approval Gate
- Consumes `EvaluationResult` + operator intent from Discord.
- Generates `approval_signature = Sign(evaluation_hash, operator_id, timestamp)` using key `key_id`.
- Writes `approval_granted` event, sets TTL (2 hours) and single-use flag.
- Cannot access Execution Adapter code; communicates through message queue / internal API.

### Execution Adapter
- Requires explicit parameters: `{evaluation_hash, approval_signature, approval_event_id, execution_plan}`.
- Validates signature against recorded `key_id`, TTL, `approval_status`, absence of newer `rollback` events, and ensures no existing `execution_ref` for that evaluation.
- If validation fails, logs `execution_blocked`/`execution_duplicate` and aborts.

## 6. Drift Detection Pipeline
**Baselines:**
- Sliding 24-hour window establishes baseline averages (minimum 200 evaluations, else extend window).
- Sliding 2-hour window provides live metrics.

**Signals & Thresholds:**
- Guardrail violations: freeze if ≥2 HIGH severity violations in any 2-hour window **or** ≥5 MEDIUM in 24-hour window.
- Risk distribution: alert if HIGH risk rate deviates >25% (absolute) from 24-hour baseline for two consecutive 2-hour windows.
- Prompt deviation: alert if >20% of evaluations within last 25 lack mandatory metadata; freeze at >40%.
- Execution anomalies: if `execution_started` occurs without preceding `approval_granted`, immediate freeze + `drift_freeze` event.

**Detection Mechanisms:** moving averages, EWMA scoring, constitution hash diffing, heartbeat validation of evaluation→approval→execution ordering.

**Escalation:**
1. **Log-only:** minor variance (auto-record `drift_log`).
2. **Operator Alert:** Discord + dashboard highlight when threshold reached once.
3. **Execution Freeze:** Approval Gate refuses approvals until `/resolve-drift` logged.

## 7. Failure Mode Matrix (incl. edge cases)
| Dependency / Scenario | First 5 Seconds | First 5 Minutes |
|----------------------|-----------------|-----------------|
| **Discord API outage** | Bot enters read-only safe state; audit `dependency_outage:discord`; approval queue paused. | Backoff retries; dashboard banner; after 5 min still down → require manual acknowledgement before re-enabling commands. |
| **GitHub rate limit** | Evaluation flagged `deferred`; audit logs event; Approval Gate blocked for affected PRs. | Retry at reset; if >5 min outstanding, escalate to operator and allow manual upload of diff for evaluation to avoid stalling. |
| **Railway partial deploy** | Execution Adapter health-checks; if unhealthy, auto-rollback to previous tagged release; log `rollback_initiated`. | Freeze new approvals until service green 5 consecutive checks; require postmortem entry. |
| **Risk engine crash pre-execution** | Approval artifacts remain pending but unusable; Gate locks; log `risk_engine_failure`. | After restart, revalidate evaluations; approvals older than TTL auto-expire (logged). Operator may re-run evaluation before approval. |
| **Risk engine crash post-approval/pre-execution** | Execution Adapter detects missing fresh evaluation heartbeat; aborts run, logs `execution_blocked`. | Approval expires if engine not healthy within TTL; operator must reapprove after re-evaluation. |
| **Railway deploy changes evaluation behavior** | Drift detector compares `engine_version` + `model_version`; mismatch triggers `drift_alert`. | Freeze approvals until version mismatch reviewed; requires operator sign-off recorded via `/resolve-version-shift`. |

## 8. Observability Dashboard Scope
- Hosted on Railway behind built-in auth; single-operator access.
- Features: event log viewer, guardrail/drift panels, approval lineage explorer, dependency health board.
- Explicit prohibitions: no command triggers, no approval buttons, no reprocessing, no re-signing, no metadata edits, no API endpoints that mutate state. Render-only.

## 9. Security & Secrets
- GitHub access via repo-scoped token/GitHub App; read-only except for triggering Actions workflows.
- Railway deploy token scoped to single project; stored as Railway secret + GitHub Actions secret.
- Signing key: private key stored solely in Railway secret store; verification key ring maintained in Execution Adapter, keyed by `key_id`. Rotation logged + previous key kept valid only for outstanding approval TTL, then retired.
- Approval artifacts single-use; TTL 2 hours; expired artifacts recorded as `approval_expired` events, preventing replay.
- No master infrastructure keys ever stored; secrets never pass through Discord.

## 10. Execution Idempotency & Replay Protections
- Execution Adapter queries audit log for existing `execution_started` referencing same `evaluation_hash`. If found, aborts with `execution_duplicate` event.
- Approval artifacts carry nonce + `approval_event_id`; Execution Adapter must reference same event when writing `execution_started`, preventing mismatched use.
- Approval status transition and `execution_started` logging run inside a single DB transaction for atomicity.
- Rollbacks require referencing the `execution_ref` they unwind; prevents ambiguous reversals.

## 11. Expansion & Phase-2 Hooks
- Audit layer can migrate to dedicated ledger (Option C) without schema change (hash chaining already in place).
- CLI/alternate interface withheld until governance expands; architecture leaves gRPC endpoints stubbed but disabled.
- Dashboard auth upgrade path (SSO/IP allowlist) documented for phase 2; currently leverages Railway-provided auth to stay minimal.
- Drift thresholds stored in repo config → PR review + approval required for any change.

## 12. Next Steps (Post-Approval)
1. Lock Discord command taxonomy (≤7 commands; ties to capabilities above).
2. Derive build plan + backlog from this architecture (Deliverable #2).
3. Flesh out command schema + structured outputs (Deliverable #3).
4. Only after Deliverable #3 approval do we touch code.

---
This brief embeds all hard invariants: immutable, tamper-evident audit spine; single-use signed approvals with TTL; deterministic evaluation hashes (incl. model/runtime version); explicit component boundaries (compile- and runtime-enforced); defined failure behaviors for every dependency; measurable drift detection with numeric thresholds and freeze triggers; Railway-protected read-only dashboard; execution idempotency with atomic state transitions; and key-rotation-safe verification. Execution remains a gated side effect of an auditable decision system.
