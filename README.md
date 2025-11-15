# AI Clone

Hybrid FastAPI + Next.js scaffold for an AI-enabled personal clone with human-in-the-loop safeguards. The backend exposes pure JSON endpoints meant for CustomGPT Actions. Firestore acts as the memory/provenance layer and Google Drive now powers ingestion.

## Project Structure

```
aiclone/
  backend/       # FastAPI service (Railway deploy target)
  frontend/      # Next.js 14 app router frontend (Vercel deploy target)
```

### Backend Highlights
- FastAPI routers for chat retrieval, knowledge search, manual ingestion, and Google Drive ingestion.
- Firestore-backed memory store with provenance metadata (file ID, folder, timestamps, tags).
- Retrieval helpers performing cosine similarity search over stored embeddings.
- Local embedding generation via `HashingVectorizer` (no external LLM, no API keys).
- Google Drive client that ingests Docs, Slides, and PDFs directly into Firestore chunks.

### Frontend Highlights
- App router layout with a simple chat UI that displays raw retrieval chunks and metadata.
- Knowledge inspector page (WIP) ready to plug into GPT Actions flows.

## Environment Configuration

### Railway (Backend)
Set the following environment variables in Railway:
- `FIREBASE_SERVICE_ACCOUNT` – stringified Firebase service account JSON.
- `GOOGLE_DRIVE_SERVICE_ACCOUNT` or `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` – Drive service account credentials for ingestion.

For local development you can export:
```
export FIREBASE_SERVICE_ACCOUNT="$(cat firebase-service-account.json)"
export GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/absolute/path/to/drive-service-account.json
```

### Vercel (Frontend)
Define:
- `NEXT_PUBLIC_API_URL` – URL of the deployed backend (e.g. `https://your-backend.up.railway.app`).

The frontend never needs direct access to Firestore or Drive credentials.

## Firestore Schema
- `users/{userId}/memory_chunks/{chunkId}` – embeddings, metadata, and provenance per chunk.
- `users/{userId}/ingest_jobs/{jobId}` – ingestion job tracking.
- `users/{userId}/audit_logs/{logId}` – optional action history.
- `global/agents_config/{doc}` – shared agent prompts (read-only for clients).

Recommended indexes: `created_at`, `source`, `tags`, and `folder_id` for quick filtering.

## Security Rules (Starter)
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/{collection}/{docId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    match /global/agents_config/{doc} {
      allow read: if true;
      allow write: if request.auth.token.admin == true;
    }
  }
}
```

Only the backend service account should perform ingestion writes.

## REST Endpoints (CustomGPT Actions)

### `POST /api/chat`
Retrieves the top `top_k` chunks for a query with similarity scores and metadata.

**Request**
```json
{
  "user_id": "dev-user",
  "query": "negotiation tactics",
  "top_k": 5
}
```

**Response**
```json
{
  "success": true,
  "query": "negotiation tactics",
  "results": [
    {
      "source_id": "file_123",
      "source_file_id": "1AbCdEf...",
      "chunk_index": 0,
      "chunk": "BATNA is the walk-away alternative...",
      "similarity_score": 0.83,
      "metadata": {
        "file_name": "negotiation_slides.pdf",
        "file_type": "application/pdf",
        "upload_timestamp": "2025-11-14T12:00:00Z",
        "topic": "Salary negotiation",
        "extra_tags": ["BATNA", "Anchor"],
        "folder_id": "drive-folder-id"
      }
    }
  ]
}
```

### `POST /api/knowledge`
Same contract as `/api/chat` but intended for broader document search (field is `search_query`).

### `POST /api/ingest/upload`
Uploads a local file, extracts text, chunks, embeds locally, and stores each chunk.

### `POST /api/ingest_drive`
Ingests every file inside a Google Drive folder ID. Supported types today: Google Docs, Google Slides, PDFs, PPT/PPTX, plain text. Automatically chunks + embeds and stores metadata (folder, file ID, MIME type).

**Request**
```json
{
  "user_id": "dev-user",
  "folder_id": "drive-folder-id",
  "max_files": 5
}
```

**Response**
```json
{
  "success": true,
  "files_ingested": 3,
  "chunks_created": 84,
  "ingest_job_id": "gdrive_bf7e...",
  "message": "Drive folder ingested successfully."
}
```

## Running Locally

1. Install backend deps (Python 3.11 recommended):
   ```
   python -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Start the FastAPI server:
   ```
   cd backend
   uvicorn app.main:app --reload --port 3001
   ```
3. Install frontend deps:
   ```
   cd ../frontend
   npm install
   npm run dev
   ```


## AI Jumpstart Playbook Alignment
- The project follows the AI Advantage Jumpstart Playbook philosophy (Tony Robbins & Dean Graziosi).
- Clone tone: practical, human-first, clear, and action-oriented; avoid jargon and hype.
- Onboarding: embed the "Train My AI Assistant" prompt so CustomGPT knows user goals, pain points, tone, and systems.
- Starter prompts: surface the 10 Jumpstart prompts (plus bonus prompt) to help users remove roadblocks, reclaim time, improve CX, and future-proof skills.
- Roadmap guiding principles: choose one primary AI tool, train it, start with the most pressing prompt, iterate for quick wins.
- Challenges & solutions: address info overload, unclear prompting, and lack of time with focused guidance and automation suggestions.

## Next Steps
- Implement audio transcription + OCR pipelines for richer ingestion (connect to Drive video/audio files).
- Add authentication middleware to secure API endpoints.
- Integrate a dedicated vector database for faster search once the corpus grows.
