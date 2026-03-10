# AI Clone → Current Workflow Crosswalk

## 1. Discord HQ / Compliance + Metrics Dashboard
- **Relevant assets**
  - `RAILWAY_*` guides (deployment, logs, env vars, troubleshooting) → inform how to expose metrics + dashboards via Railway.
  - `SESSION_SUMMARY.md`, `SYSTEM_LOGS` routes (referenced in `app/main.py`) → expected APIs for surfacing approvals/alerts in Discord.
  - `RAILWAY_MANUAL_TEST.md`, `PRODUCTION_TEST_CHECKLIST.md` → define the audit cadence we can pipe back into #hq.
- **Gaps / actions**
  - Backend `system_logs` router missing from tree; need to rebuild or rehydrate to post updates into Discord.
  - Need a lightweight collector that calls these endpoints and posts summaries (ITC Step 3).

## 2. Gmail / Calendar Triage & Briefings
- **Relevant assets**
  - `calendar` + `notifications` routers referenced in backend.
  - SOPs like `DAILY_BRIEFING` content (within `SESSION_SUMMARY.md`, `START_FRONTEND_PROMPT.md`).
  - NotebookLM packs (`aiclone_01...` to `_06`) cover tone + synthesis guidelines for briefings.
- **Gaps / actions**
  - Actual Gmail/Calendar connectors aren’t in the code snapshot—likely lived in missing routes/services. Need to rebuild connectors using the existing SOPs + new Google integrations.

## 3. Railway Dashboard Collector (workflow compliance metrics)
- **Relevant assets**
  - `RAILWAY_BACKEND_TEST_RESULTS.md`, `RAILWAY_DEPLOYMENT_CHECKLIST.md`, `RAILWAY_ENV_VARS_NEEDED.md` for the expected telemetry and env settings.
  - Shell helpers (`view_railway_logs.sh`, `check_railway_logs.sh`, `generate_railway_json.py`).
  - Back-end analytics routers (`analytics`, `bi`, `advanced_reporting`, `predictive_insights`).
- **Gaps / actions**
  - Need to define which metrics to pull first (per your “workflow compliance over engagement” call).
  - Many analytics routes missing; will either recreate or stub minimal collectors for Discord posts.

## 4. Knowledge & Playbook Management
- **Relevant assets**
  - Entire Markdown library + `notebooklm_ready/` bundle.
  - `knowledge`, `playbook`, `vault`, `templates`, `personas` routers referenced in backend.
  - Scripts (`process_ai_exports.py`, `run_ai_exports.sh`, NotebookLM guides) for ingesting external knowledge.
- **Gaps / actions**
  - Need to ingest/tag these docs into our workspace’s knowledge base (e.g., `/knowledge/playbooks/*.md`).
  - Determine single source of truth: begin migrating critical SOPs into the new markdown canon so Discord commands can reference them.

## 5. Prospecting / Outreach Engine
- **Relevant assets**
  - Backend routers: `prospects`, `prospects_manual`, `outreach_manual`, `linkedin`, `prospect_discovery`, `topic_intelligence`.
  - Python tests: `test_prospect_extraction.py`, `test_all_categories*.py`, `test_linkedin_*` scripts.
  - Docs: `PROSPECT_DISCOVERY_PIPELINE.md`, `PROSPECTING_WORKFLOW_API_DOCS.md`, `LINKEDIN_*` guides, `MOM_GROUPS` analyses, persona files.
- **Gaps / actions**
  - Actual route implementations missing → need to recreate API surfaces or call external services.
  - Define how much of this pipeline moves into the new system vs. remains as historical reference.

## 6. Content / Research / Automations
- **Relevant assets**
  - Frontend apps for `content-marketing`, `content-pipeline`, `research-tasks`, `automations`, `templates` plus the associated backend routes.
  - Content SOPs: `CONTENT_STYLE_GUIDE.md`, `VOICE_PATTERNS.md`, `AI_JUMPSTART_PLAYBOOK.md`, `TOPIC_INTELLIGENCE_GUIDE.md`.
  - Scripts for extractor testing (`test_extractor_system.py`, `test_scraping_success.py`).
- **Gaps / actions**
  - Need to decide which of these flows we bring online first (after dashboard + Gmail). Many rely on Firecrawl/LinkedIn credentials we don’t yet have wired into the new stack.

## 7. Infra / Governance Hooks
- **Relevant assets**
  - Cost management docs (`COST_OPTIMIZED_MODEL_SETUP.md`, `KEY_ROTATION_CHECKLIST.md`, `FIREBASE_KEY_ROTATION_SAFE.md`).
  - Security guides (`SECURITY_FIX.md`, `SECURITY_FIX_URGENT.md`, `GIT_HISTORY_SECRETS_EXPLAINED.md`).
  - Model routing and MCP setup files.
- **Gaps / actions**
  - Need to encode these policies into our markdown canon + Discord guardrails (e.g., approvals, cost ceilings, rotation reminders).

## Summary
- The archive already encodes the workflows we want; we just need to (a) ingest the SOPs, (b) resurrect or reimplement the missing API layers, and (c) wire new collectors/automations so Discord/Gmail/Railway all point at the same truth.
- Biggest blockers: missing backend route files and sensitive env dependencies (Firebase, LinkedIn, Firecrawl).
