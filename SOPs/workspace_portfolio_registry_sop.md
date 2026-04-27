# Workspace Portfolio Registry SOP

This SOP defines the canonical portfolio model for OpenClaw and Codex sessions.

If a task touches `Ops`, `Brain`, workspace routing, workspace snapshots, deploy staging, or the addition of a new workspace, read this SOP before changing code.

## Purpose

The system is no longer a single-workspace app with one special-case child lane.

It is a multi-workspace platform with:

- one executive lane
- multiple child workspaces
- one canonical registry for workspace identity, status, routing, and filesystem roots

The goal is to make every new workspace systemic by default instead of rebuilding workspace assumptions in scattered frontend and backend files.

## Canonical portfolio truth

The current canonical portfolio is:

| Key | Kind | Display | Status | Filesystem root | Notes |
| --- | --- | --- | --- | --- | --- |
| `shared_ops` | executive | Executive | `live` | `shared-ops` | Cross-workspace executive lane |
| `feezie-os` | workspace | FEEZIE OS | `live` | `linkedin-content-os` | Active live workspace; legacy root slug remains in use |
| `fusion-os` | workspace | Fusion OS | `standing_up` | `fusion-os` | Second workspace; currently being stood up |
| `easyoutfitapp` | workspace | EasyOutfitApp | `live` | `easyoutfitapp` | Live product repo at `/Users/neo/Desktop/closetgptrenew`; runtime/deploy truth lives in that repo's canonical operator playbook |
| `ai-swag-store` | workspace | AI Swag Store | `planned` | `ai-swag-store` | Planned workspace |
| `agc` | workspace | AGC | `planned` | `agc` | Planned workspace |

## Canonical sources of workspace truth

Backend source of truth:

- `backend/app/services/workspace_registry_service.py`

Backend public API for workspace truth:

- `GET /api/workspace/registry?include_executive=true|false`
- `GET /api/workspace/{workspace_key}/snapshot`

Frontend fallback mirror for workspace truth:

- `frontend/lib/workspace-registry.ts`

These files define:

- workspace key
- display name
- status
- workspace root slug
- operator and agent identity
- execution mode
- route
- accent
- portfolio visibility

## Non-negotiable rules

### 1. Registry first

Any platform-level workspace behavior must derive from the canonical registry before adding new conditional logic.

This includes:

- frontend workspace selectors
- route labels and badges
- workspace file matching
- workspace snapshot loading
- backend workspace routing
- deploy staging
- workspace doc discovery

### 2. Key is not the same as filesystem root

Workspace identity is keyed by canonical workspace key, not by old folder names.

Important example:

- canonical key: `feezie-os`
- current filesystem root slug: `linkedin-content-os`

Do not use legacy filesystem slugs as if they are the workspace identity.

### 3. Platform code must stay generic

The following should be generic and registry-driven:

- backend registry and runtime contracts
- generic snapshot routes
- frontend ops/brain/workspace path matching
- doc discovery for workspace packs
- deploy scripts that stage workspace files

### 4. Workspace-specific logic is allowed only when it is actually the product

It is valid for Feezie-specific logic to remain in places where the workspace itself is the product surface.

Examples:

- social feed builder behavior for the current Feezie lane
- LinkedIn/posting workflow specifics
- Feezie persona/content generation behavior

Those are not platform bugs unless they leak into shared platform surfaces.

### 5. New workspaces must not require a hunt across hardcoded arrays

If adding a workspace requires editing many unrelated hardcoded lists, the platform is drifting and should be corrected before more workspace rollout.

## Add-a-workspace checklist

When creating a new workspace:

1. Create the workspace folder under `workspaces/<workspace-root>/`
2. Add the canonical entry to `backend/app/services/workspace_registry_service.py`
3. Mirror the fallback entry in `frontend/lib/workspace-registry.ts`
4. Set:
   - `key`
   - `display_name`
   - `status`
   - `workspace_root`
   - `operator_name`
   - `execution_mode`
   - `default_standup_kind`
   - `portfolio_visible`
5. Confirm:
   - backend registry endpoint returns it
   - frontend ops/brain renders it without new hardcoded logic
   - generic workspace snapshot route works for it
   - Railway backend staging includes the workspace files
   - the workspace root has the minimum non-executive lane shape:
     - `dispatch/`
     - `briefings/`
     - `docs/README.md`
     - `memory/execution_log.md`
     - `agent-ledgers/`
   - the workspace `AGENTS.md` startup contract points to those same local anchors
6. Only after that, add workspace-specific product logic if the workspace needs its own execution surface

## Current system boundary

The platform cleanup already covers:

- canonical backend workspace registry
- registry-backed runtime contracts
- generic workspace snapshot route
- full workspace staging in backend deploy
- frontend registry model
- ops and brain consuming the registry
- registry-driven workspace file matching in shared frontend surfaces

The system still intentionally allows Feezie-specific execution logic where Feezie is the actual product lane.

That is acceptable.

The rule is:

- generic platform logic must be registry-driven
- product-specific workspace logic may remain workspace-specific

## Read order for workspace-sensitive tasks

When a task touches workspace architecture, read in this order:

1. `CODEX_STARTUP.md`
2. `SOURCE_OF_TRUTH.md`
3. `SOPs/_index.md`
4. `SOPs/workspace_portfolio_registry_sop.md`

Then load only the workspace-specific docs needed for the task.

## Verification commands

Use these to verify the portfolio model quickly:

```bash
cd /Users/neo/.openclaw/workspace
curl -sS 'https://aiclone-production-32dc.up.railway.app/api/workspace/registry?include_executive=true'
./scripts/verify_frontend_release.sh
./scripts/verify_production.sh
```

## Operator reminder

If a future session says:

- “Fusion is only planned”
- “there is just one workspace”
- “workspace truth lives in whatever page is currently hardcoded”

that session is out of date.

The canonical truth is the portfolio registry.
