# Backend Contracts — Priority Routers

## 1. Knowledge (`/api/knowledge`)
- **Entities**
  - `KnowledgeDoc`: `{ id, title, summary, tags[], source_path, last_updated, content_url }`
  - Derived from `knowledge/aiclone/**` inventory (NotebookLM packs, SOPs).
- **Endpoints**
  - `GET /api/knowledge`: list docs with optional `?tag`, `?search` filters.
  - `GET /api/knowledge/{id}`: fetch full metadata + signed URL (Drive/Git).
  - `POST /api/knowledge/refresh`: trigger re-index from Drive (requires service account & `ingest_drive`).
- **Data source**: Firestore `knowledge_docs` collection + Drive folder IDs (per `ingest_drive` SOP).

## 2. Playbooks (`/api/playbooks`)
- **Entities**
  - `Playbook`: `{ id, name, category, steps[], sop_path, linked_docs[] }`.
- **Endpoints**
  - `GET /api/playbooks`: list; supports `?category=` (`prospecting`, `content`, `ops`).
  - `GET /api/playbooks/{id}`: return structured SOP.
  - `POST /api/playbooks/sync`: import from Drive/Markdown (ties to knowledge ingestion flow).
- **Data source**: Firestore `playbooks` collection, populated from `knowledge/aiclone/`.

## 3. Prospects (`/api/prospects`, `/api/prospect-discovery`)
- **Entities** (from `test_prospect_extraction.py`, `test_all_categories.py`):
  - `Prospect`: `{ id, name, title, organization, category, source, url, confidence, contact: { email, phone }, tags[], created_at }`.
  - `ProspectDiscoveryRequest`: `{ category, location, max_results, keywords[], crawl_mode }`.
  - `ProspectDiscoveryResult`: `{ prospects[], metadata: { scraped_urls[], errors[] } }`.
- **Endpoints**
  - `POST /api/prospect-discovery/run`: accepts `ProspectDiscoveryRequest`, runs scraping/extraction.
  - `GET /api/prospects`: list stored prospects with filters (`?category`, `?source`, `?has_email`).
  - `POST /api/prospects/manual`: manual entry (per `prospects_manual` router).
  - `POST /api/outreach/manual`: log outreach attempts.
- **Dependencies**: ProspectDiscoveryService (scraping + Firecrawl fallback), Firestore `prospects` & `outreach` collections.

## 4. System Logs & Analytics (`/api/system/logs`, `/api/analytics`)
- **Entities**
  - `SystemLog`: `{ id, timestamp, level, component, message, context }` (feeds Discord dashboard).
  - `Metric`: `{ name, value, window, source }` for workflow compliance metrics.
- **Endpoints**
  - `GET /api/system/logs`: paginated logs with `?component`, `?level` filters.
  - `POST /api/system/logs`: allow services to push structured log events.
  - `GET /api/analytics/compliance`: returns metrics (approvals pending, drafts posted, alerts raised).
- **Data sources**: Firestore `system_logs`, `metrics` collections populated by collectors/job runners.

## 5. Ingest Drive (`/api/ingest/drive`)
- **Entities**
  - `IngestJob`: `{ id, drive_folder_id, target_collection ('knowledge'|'playbook'), tag_map, status, started_at, completed_at, errors[] }`.
- **Endpoints**
  - `POST /api/ingest/drive`: body `{ folder_id, tags[], dry_run }`.
  - `GET /api/ingest/drive/{job_id}`: status + processed docs.
- **Dependencies**: Google Drive service account (already configured), mapping to Firestore.

## 6. Calendar & Notifications (`/api/calendar`, `/api/notifications`)
- **Entities**
  - `CalendarEvent`: `{ id, title, start, end, source ('google'), attendees[], status }`.
  - `Notification`: `{ id, channel ('discord','email'), template, payload, sent_at }`.
- **Endpoints**
  - `GET /api/calendar/upcoming?window=48h` — used for daily briefing.
  - `POST /api/calendar/refresh` — trigger sync from Google Calendar.
  - `POST /api/notifications/send` — used by workflows to emit Discord/Gmail drafts.
- **Dependencies**: Google Calendar API, Discord webhook/token, Gmail draft service.

## 7. Templates / Personas / Vault
- **Entities**
  - `Template`: `{ id, name, category, body, tokens_per_send, linked_assets[] }`.
  - `Persona`: `{ id, name, summary, constraints, voice_patterns[] }` (ties to `knowledge/aiclone/content/`).
  - `VaultItem`: `{ id, type ('transcript','asset'), path, tags[] }`.
- **Endpoints**
  - `GET /api/templates`, `GET /api/personas`, `GET /api/vault` for retrieval.
  - `POST /api/templates`: allow updates from knowledge ingestion jobs.

## 8. Authentication / Webhooks
- **Entities**
  - `AuthSession`: `{ token, scopes, expires_at }` (Discord/GitHub handshake for approvals).
  - `WebhookEvent`: payloads from LinkedIn, Firecrawl, Railway.
- **Endpoints**
  - `POST /api/auth/discord` — verify Discord command approval.
  - `POST /api/webhooks/railway` — capture deploy status updates for the dashboard.

---
**Next Step:** use these contracts to scaffold actual FastAPI modules—starting with `knowledge`, `playbooks`, `prospects`, `system_logs`, `ingest_drive`, `calendar`, `notifications`. Each module will pull from Firestore using the service account we control and expose the endpoints listed above.
