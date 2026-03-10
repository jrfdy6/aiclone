# AI Clone Backend Recovery Plan

## 1. Current State
- Only `backend/app/main.py` plus empty package stubs (`routes/`, `services/`, `models/`, `utils/`). The original git object store is incomplete, so route/service implementations are missing.
- External dependencies referenced:
  - Firebase/Firestore (`app.services.firestore_client`, env vars `FIREBASE_SERVICE_ACCOUNT`).
  - Google Drive ingestion (`ingest_drive` routes).
  - LinkedIn, Firecrawl, Perplexity, MCP, etc. (per imported knowledge + tests).
- Tests and scripts outside `app/` still exist (e.g., `test_prospect_extraction.py`, `test_all_categories.py`), giving us expected data contracts.

## 2. Router Surface from `main.py`
`chat, ingest, ingest_drive, knowledge, playbook, prospects, prospects_manual, outreach_manual, calendar, notifications, research_tasks, activity, templates, vault, personas, system_logs, automations, websocket, analytics, auth, webhooks, predictive, recommendations, nlp, content_optimization, bi, advanced_reporting, predictive_insights, multi_format_content, content_library, cross_platform_analytics, linkedin, topic_intelligence, prospect_discovery, content_generation`.

## 3. Data/Integration Touchpoints
- **Firestore**: primary data store for knowledge, personas, activities, etc.
- **Google Drive**: ingestion of docs/playbooks (`ingest_drive`).
- **LinkedIn / Prospect scraping**: see `test_prospect_extraction.py`, `LINKEDIN_*`, `SCRAPING_*` guides.
- **Railway**: hosting + env distribution (per deployment docs).
- **MCP/Cursor/Perplexity**: extended toolchains used by frontend + ops scripts.

## 4. Rebuild Strategy
1. **Recreate the scaffolding**
   - Implement `app/services/firestore_client.py` using the new service account we already configured for Drive (or add a Firestore-specific key if needed).
   - Stand up minimal `models` (pydantic schemas) for core resources: Playbook, Prospect, ActivityLog, Template, Persona.
2. **Prioritize workflows that feed our current plan**
   - `system_logs`, `analytics`, `prospects`, `playbook`, `knowledge`, `ingest_drive`, `calendar`, `notifications`.
   - For each, define endpoints using the SOPs now in `knowledge/aiclone/` plus the test scripts (e.g., `test_all_endpoints.sh`, `test_all_categories.py`).
3. **Stub high-risk integrations**
   - Provide placeholder implementations that log payloads and return canned responses until we add real LinkedIn/Firecrawl credentials. This keeps Discord/Railway workflows unblocked.
4. **Add observability**
   - Reuse the logging middleware + health checks already in `main.py`.
   - Map outputs to the Discord dashboard collector we’re building.
5. **Gradually reintroduce the remaining routers**
   - Once the priority set is stable, implement the rest (predictive, nlp, recommendations, etc.) using doc references.

## 5. Next Actions
- [x] Define data contracts for the priority routers by mining the existing test scripts + knowledge docs (`notes/aiclone-backend-contracts.md`).
- [x] Create new `backend/app/services/firestore_client.py` plus local fallbacks.
- [x] Rebuild `app/routes/knowledge.py`, `playbook.py`, `prospects.py`, `prospects_manual.py`, `system_logs.py`, `analytics.py`, `ingest_drive.py`, `calendar.py`, `notifications.py`.
- [ ] Add Firestore seed/load scripts for the new collections.
- [ ] Wire Discord/Railway collectors to these endpoints once they exist.
