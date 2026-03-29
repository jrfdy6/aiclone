# SOP Index

This index ties identity → capabilities → SOPs → automations so nothing critical drifts out of memory. Start here when you need to remember what Neo knows how to do.

| Identity Anchor (IDENTITY.md) | Capability / Access Point | SOP | Automation / Script | Notes |
| --- | --- | --- | --- | --- |
| Builder/strategist AI focused on long-term leverage | Railway service + API management | [Railway API Usage](./railway_api_sop.md) | Service status monitor cron → `restart_services.sh` | Keeps production deployment + health endpoints within reach; failures hand off to restart SOP. |
| Same anchor | GitHub operational access | [GitHub API Usage](./github_api_sop.md) | Service status monitor cron → `restart_services.sh` | Mirrors auth checks (`gh auth status`) plus SOP commands for repo + issue workflows. |
| Systems mapper | Worktree hygiene (OpenClaw boot) | [Worktree Hygiene (OpenClaw Boot)](./worktree_hygiene_sop.md) | `./scripts/worktree_doctor.py` | Run at each boot so you see which files are real diffs and which are append-only memory snapshots before committing. |
| Release operator | Main-safe release verification | [Main Safety Release Flow](./main_safety_release_sop.md) | `npm run verify:main` + `./scripts/deploy_railway_service.sh <service>` + `npm run verify:production` + `.githooks/pre-push` | Canonical release gate for the app and LinkedIn workspace; use this before and after production changes. |
| Context architect | Stage 1 ingestion + YAML note structure | [Ingestion README](../ingestion/README.md) | `npm run intake:route` (cron-safe) | Single queue for Discord/Codex/Tavily/YouTube notes, feeding `/api/capture` with persona metadata. |
| Signal architect | Shared transcript/media source contract | [Shared Source System Contract](./source_system_contract_sop.md) | `backend/app/services/workspace_snapshot_service.py` + `knowledge/ingestions/**` + `knowledge/aiclone/transcripts/` | One ingest surface, multiple consumers: briefs, weekly plan, persona review, and social routing all extend the same upstream assets. |
| Control-plane architect | Brain vs Workspace ownership boundary | [Brain vs Workspace Boundary](./brain_workspace_boundary_sop.md) | `frontend/app/brain/**` + `frontend/app/ops/**` + `persona_deltas` lifecycle | Brain is the global control plane; child workspaces are project execution surfaces and may only mirror or hand off global state. |
| Persona steward | Canon-safe persona promotion | [Persona Canon Promotion Contract](./persona_canon_promotion_sop.md) | `persona_deltas` → `knowledge/persona/feeze/**` + `automations/persona_bundle_sync.py` | Defines the semantic extraction, gating, and persistence rules so Brain review does not leak reflective notes into canon. |
| Persona steward | Core identity vs absorbed bundles | [Persona Identity State Contract](./persona_identity_state_sop.md) | Planned `Brain` identity-state tab + current `scripts/persona/bundle_health_check.py` guardrail | Defines how a tight core, supporting bundles, and identity reshaping should stay visible and governable without taking priority over current persona-to-content quality work. |
| Persona steward | Grounded content generation from persona canon | [Persona-Grounded Content Generation](./persona_grounded_content_generation_sop.md) | `backend/app/routes/content_generation.py` + `backend/app/services/persona_bundle_context_service.py` + `backend/app/services/retrieval.py` | Defines the typed-memory, typed-retrieval, and grounding-gate plan so content generation stops mixing core identity, proof, stories, and examples into one weak retrieval surface. |
| Persona steward | Restart critical services automatically | [Restart Services](./restart_services_sop.md) | `scripts/intake_router.js` error handling + service monitor cron | Script path is canonical recovery hook when GitHub/Railway outages trip monitors. |
| Data bootstrapper | Direct Postgres seeding (vectors + persona + metrics) | [Direct Postgres Bootstrap](./direct_postgres_bootstrap.md) | `railway run --service Postgres -- python3 scripts/bootstrap_*_direct.py` | Lets us backfill Open Brain captures/vectors, persona deltas, PM cards, and session metrics without redeploying the backend. |
| Signal amplifier | Audio → transcript conversions | [Audio Transcription Process](./audio_transcription_sop.md) | Cron/skill: Daily Memory Flush + ingestion queue template | Workflow for yt-dl/ffmpeg download + Whisper transcription before dropping into `ingestion/`. |
| Signal amplifier | Canonical media intake contract | [Media Intake Contract](../docs/media_intake_contract.md) | Planned watcher over `media/transcripts` + `media/audio` | Defines the exact inbox/output contract so transcript drops, podcast/audio drops, and downstream build/persona routing all share one path. |
| Systems mapper | Web crawling + research inputs | [Tavily Web Crawling](./tavily_web_crawling_sop.md) | Capture jobs triggered from Tavily collector scripts | Ensures crawled content lands in YAML+Markdown format for queue processing. |
| Memory custodian | Persistent memory architecture | [Persistent Memory Architecture](./persistent_memory_architecture.md) | Monthly review cron (see MEMORY.md guardrail) | Defines how IDENTITY, MEMORY, and SOPs stay linked; this index is referenced there. |

## How to Use

1. **Start with identity** (`IDENTITY.md`) to understand the role or capability in question.
2. **Jump to this index** to find the SOP that governs the workflow.
3. **Follow the linked automation** (script or cron) to see how it stays alive day-to-day.
4. **Update both** the SOP *and* this index whenever you add a new critical access path.

Cross-link this file from any new SOP so there is always a single hop back to the canonical map.
