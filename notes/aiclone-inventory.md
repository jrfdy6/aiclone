# AI Clone Archive — Inventory (2026-03-03)

**Location:** `downloads/aiclone` (unzipped from latest archive)

## Snapshot
- Bundles both application code and institutional knowledge for the original AI Clone build.
- Includes a partial `.git` directory (HEAD → `72c2b520…`) but the object store is incomplete, so `git status` fails.
- Contains committed virtual environments (`.venv/`), production build artifacts (`frontend/.next/`), and full `node_modules/` trees.

## Core Code Surfaces
### Backend (`backend/`)
- FastAPI 2.0 service with global middleware, CORS, health checks, and >20 routers (`app/main.py`).
- Subpackages for `middleware/`, `models/`, `services/`, `utils/`; however `app/routes/` is currently empty in the working tree (likely lost in the archive or requires a fresh checkout from the missing git objects).
- Deployment helpers: `Procfile`, `requirements.txt`, `setup_api_keys.sh`, `generate_railway_json.py`, `check_railway_json.py`, `verify_firestore_json.py`.
- Logs + env files present: `server.log`, `.env`, `.env.bak`, `.env.backup`, `.env.example`.

### Frontend (`frontend/`)
- Next.js App Router project with sub-apps for `activity/`, `automations/`, `content-*`, `prospects/`, `topic-intelligence/`, etc.
- Includes `components/` (Command Palette, Prospect panels, Notifications, etc.), `lib/` helpers (API client, Firestore server bindings, websocket helpers), and `public/` assets.
- Deployment configs for Railway/Vercel: `Procfile`, `railway.toml`, `nixpacks.toml`, `.vercel/`, `.env.local`, `.env.production`.
- Complete `.next/` build output and `node_modules/` (large, but useful for reference only).

### Scripts & Automation
- Python utilities: `analyze_prospects.py`, `process_ai_exports.py`, `iterate_to_success.py`, `debug_*` scripts, `reingest_persona_docs.py`, etc.
- Shell helpers: `start_servers.sh`, `run_ai_exports.sh`, `capture_recent_logs.sh`, `test_*` Bash harnesses, Railway log viewers, Firebase variable updaters.
- Extensive automated test suites (`test_*.py`, `.sh`, `.ts`) covering APIs, scraping, LinkedIn integrations, treatment-center extraction, validation loops, etc.

## Knowledge & SOP Assets
- Root-level Markdown library (>100 docs): phase roadmaps, deployment checklists, category improvement logs, MCP setup guides, prospecting playbooks, validation findings, persona briefs (`JOHNNIE_FIELDS_PERSONA*.md`), style guides, cost-optimization notes, etc.
- `notebooklm_ready/`: curated six-part knowledge packs (system prompts, anti-AI rules, frameworks, voice guides, workflows, architecture decisions).
- `bio_facts.md`, `philosophy.md`, `voice_patterns.md`, `audience_communication.md`, etc.—useful for persona grounding.
- `LLM.ext`: extension manifest/config (likely Cursor/Copilot integration) included at root.

## Tooling / Environment
- `.venv/` (Python 3.13) fully materialized, with pip/whisper utilities installed.
- `keys/` directory (currently only `.gitkeep`, but expected to hold service-account files in real deployments).
- `.git/` present but incomplete; `.git/cursor` artifacts indicate Cursor agent usage history.

## Notable Observations
1. **Routes missing in working tree:** `backend/app/routes/` is empty even though `main.py` imports many modules. Need to recover from a fuller archive or rehydrate via git if the missing objects can be restored.
2. **Repository is "dirty" by default:** packaged `.venv`, `node_modules`, `.next`, `.git`, and logs aren’t pruned—should treat as reference material, not something to commit into our active workspace.
3. **Docs outweigh code footprint:** this archive doubles as the knowledge base; ingesting/tagging these Markdown files is high leverage for our new workflows.
4. **Deployment stories target Railway + Firebase + Google Drive:** environment files and scripts assume service-account JSON and Firestore connectivity—aligns with our current infra discussions.

## Next Steps (per plan)
- Document sensitive assets separately (`notes/aiclone-sensitive.md`).
- Map key modules/docs to the workflows we’re standing up (Discord audit, Gmail triage, Railway dashboard, etc.).
