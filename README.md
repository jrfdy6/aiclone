# AI Clone

Note: Rolling Docs refreshed on 2026-04-27. See memory/doc-updates.md for details.

AI Clone is an AI-powered **knowledge + prospecting workspace** built with **FastAPI (backend)** + **Next.js 14 (frontend)**.

The AI Clone is designed to: 
- ingest documents (file upload + Google Drive)
- store chunked “memory” in Firestore
- retrieve relevant chunks via deterministic embeddings + cosine similarity
- discover + manage prospects (via scraping/search)
- support LinkedIn intelligence workflows

> This repo contains many phase/status markdown files. This `README.md` is the **canonical** source for setup + current functionality.

### Table of contents

- Quick start (local)
- Architecture
- Environment variables
- What’s implemented vs scaffolded
- Local development
- Key API endpoints
- Firestore data layout
- Deployment
- Troubleshooting
- Docs map

### Quick start (local)

#### Prereqs

- **Python**: 3.10+ (recommended 3.11)
- **Node**: 18+ (recommended 20)
- **Firestore** enabled in a Firebase project
- A **Firebase service account** for the backend

#### Backend (FastAPI)

```bash
cd backend

python -m venv ../.venv
source ../.venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env` (do **not** commit secrets). Minimum requirement:
- `FIREBASE_SERVICE_ACCOUNT` (stringified JSON) **or** `GOOGLE_APPLICATION_CREDENTIALS` (path to JSON file)

Start the API:

```bash
cd backend
uvicorn app.main:app --reload --port 3001
```

Verify:
- Health: `http://localhost:3001/health`
- Swagger: `http://localhost:3001/api/docs`

#### Frontend (Next.js)

```bash
cd frontend
npm install
```

Set:
- `NEXT_PUBLIC_API_URL=http://localhost:3001`

Run:

```bash
cd frontend
npm run dev -- --port 3000
```

Open:
- `http://localhost:3000`

#### One-command dev (optional)

There’s a helper script that starts both servers and logs to `backend/server.log` and `frontend/server.log`:

```bash
./start_servers.sh
```

Override ports if needed:

```bash
FRONTEND_PORT=3002 BACKEND_PORT=3001 ./start_servers.sh
```

### Architecture

#### Backend

- Entry point: `backend/app/main.py`
- Storage: Firestore (via `firebase-admin`)
- Embeddings: deterministic 1024-dim vectors via `HashingVectorizer` (`backend/app/services/embedders.py`)
- Retrieval: cosine similarity over Firestore-stored embeddings (`backend/app/services/retrieval.py`)

#### Frontend

- Next.js 14 App Router in `frontend/app`
- API base URL is controlled by `NEXT_PUBLIC_API_URL`

#### Optional integrations

Some flows require additional keys:
- **Google Drive**: Drive ingestion (Docs/Slides/PDF/PPTX)
- **Firecrawl**: scraping (LinkedIn + directories)
- **Google Custom Search**: finding URLs for LinkedIn/directory discovery
- **Perplexity**: research / AI-assisted discovery

### Environment variables

#### Backend (`backend/.env`)

- **Firestore**
  - `FIREBASE_SERVICE_ACCOUNT`: stringified service account JSON
  - Alternative: `GOOGLE_APPLICATION_CREDENTIALS=/abs/path/to/service-account.json`
  - (ADC fallback is also supported)

- **Google Drive ingestion**
  - `GOOGLE_DRIVE_SERVICE_ACCOUNT` (stringified JSON)
  - or `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` (absolute path)

- **Scraping + search**
  - `FIRECRAWL_API_KEY`
  - `GOOGLE_CUSTOM_SEARCH_API_KEY`
  - `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`

- **Research**
  - `PERPLEXITY_API_KEY`

- **Optional**
  - `PORT` (used by Railway)
  - `CORS_ADDITIONAL_ORIGINS` (comma-separated extra origins)

#### Frontend (`frontend/.env.local` recommended)

- `NEXT_PUBLIC_API_URL` (e.g. `http://localhost:3001`)

### What’s implemented vs scaffolded (important)

This repo contains both working endpoints and scaffolding. The most reliable source of truth is:
- Swagger: `/api/docs`
- Router wiring: `backend/app/main.py`

#### Implemented (working)

- **Knowledge**
  - file upload ingest: `POST /api/ingest/upload`
  - Google Drive folder ingest: `POST /api/ingest_drive`
  - retrieval: `POST /api/chat`, `POST /api/knowledge`
- **Prospecting**
  - discovery: `/api/prospect-discovery/*`
  - list/manage prospects: `GET /api/prospects`
- **LinkedIn intelligence**
  - post search: `POST /api/linkedin/search`
  - industry insights: `GET /api/linkedin/industry/{industry}/insights`, `GET /api/linkedin/industries`
- **Topic intelligence**
  - run pipeline: `POST /api/topic-intelligence/run`
  - store MCP-generated research: `POST /api/topic-intelligence/store`

#### Scaffolded / WIP

Some routes exist as placeholders (returning empty arrays/messages), and some frontend pages may call endpoints that are not currently wired in `backend/app/main.py`.

### Local development

#### Repo structure

```
aiclone/
  backend/         # FastAPI service
  frontend/        # Next.js 14 UI
  start_servers.sh # convenience runner
```

#### Frontend pages (high level)

- `/` – workflow home (pipeline entry points)
- `/prospect-discovery` – prospect discovery UI
- `/prospects` – prospect list (reads Firestore via backend)
- `/knowledge` – knowledge retrieval UI
- `/topic-intelligence` – run/store topic intelligence

### Key API endpoints (current)

Use Swagger: `GET /api/docs`

#### Health
- `GET /health`

#### Knowledge
- `POST /api/ingest/upload` (multipart)
- `POST /api/ingest_drive` (JSON)
- `POST /api/chat` (JSON: `{ user_id, query, top_k }`)
- `POST /api/knowledge` (JSON: `{ user_id, search_query, top_k }`)

#### Prospects + discovery
- `GET /api/prospects?user_id=...`
- `POST /api/prospect-discovery/search-free`
- `POST /api/prospect-discovery/ai-search`
- `POST /api/prospect-discovery/search`

#### LinkedIn
- `POST /api/linkedin/search`
- `POST /api/linkedin/test`
- `GET /api/linkedin/industries`
- `GET /api/linkedin/industry/{industry}/insights`

#### Topic intelligence
- `GET /api/topic-intelligence/themes`
- `POST /api/topic-intelligence/run`
- `POST /api/topic-intelligence/store`

### Firestore data layout (core collections)

```
users/{userId}/
  memory_chunks/{chunkId}
  ingest_jobs/{jobId}
  prospects/{prospectId}
  prospect_discoveries/{discoveryId}
  topic_intelligence/{researchId}
```

### Deployment

#### Backend (Railway)

- Procfile: `backend/Procfile` (runs `uvicorn ... --port $PORT`)
- Set Railway env vars (minimum): `FIREBASE_SERVICE_ACCOUNT`
- Optional feature env vars: `FIRECRAWL_API_KEY`, `PERPLEXITY_API_KEY`, `GOOGLE_CUSTOM_SEARCH_*`, Drive creds

#### Frontend (Railway)

- Procfile: `frontend/Procfile` (runs `npm start`)
- Set `NEXT_PUBLIC_API_URL` to your backend’s public URL

### Troubleshooting

- **CORS issues**
  - add your origin to `CORS_ADDITIONAL_ORIGINS`
- **Firestore init failures**
  - validate `FIREBASE_SERVICE_ACCOUNT` is valid JSON (Railway often requires it on one line)
  - or use `GOOGLE_APPLICATION_CREDENTIALS`
- **Firecrawl 403/429**
  - try smaller searches; LinkedIn + scraping are sensitive to rate limits/anti-bot

### Docs map (high-signal)

- Setup / workflow: `QUICK_START.md`, `READY_TO_TEST.md`
- MCP: `MCP_SETUP_GUIDE.md`, `MCP_WORKFLOW_GUIDE.md`
- Deployment: `RAILWAY_SETUP.md`, `RAILWAY_DEPLOYMENT_QUICK_START.md`
- Persona/voice: `JOHNNIE_FIELDS_PERSONA.md`, `CONTENT_STYLE_GUIDE.md`

### License

Private project — all rights reserved.
