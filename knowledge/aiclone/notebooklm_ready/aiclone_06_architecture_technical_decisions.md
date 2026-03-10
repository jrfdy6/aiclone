# AI Clone: Architecture & Technical Decisions

**Date:** 2025  
**Source:** `README.md`, codebase structure, deployment documentation  
**Purpose:** Complete technical architecture and key design decisions

---

## System Architecture Overview

### High-Level Structure

```
aiclone/
├── backend/          # FastAPI service
│   ├── app/
│   │   ├── main.py   # Entry point, route wiring
│   │   ├── routes/    # API endpoints
│   │   ├── services/ # Business logic
│   │   └── models/    # Data models
│   └── requirements.txt
├── frontend/         # Next.js 14 UI
│   ├── app/          # App Router pages
│   └── package.json
└── start_servers.sh  # Dev convenience script
```

---

## Backend Architecture

### Technology Stack
- **Framework:** FastAPI (Python 3.10+)
- **Database:** Firestore (Firebase)
- **Embeddings:** HashingVectorizer (deterministic 1024-dim vectors)
- **Retrieval:** Cosine similarity over Firestore-stored embeddings
- **AI:** OpenAI API (GPT-4, GPT-3.5-turbo)

### Key Design Decisions

#### 1. Deterministic Embeddings
**Decision:** Use `HashingVectorizer` instead of OpenAI embeddings

**Rationale:**
- Cost-effective (no API calls for embeddings)
- Deterministic (same text = same embedding)
- Fast (local computation)
- Sufficient for similarity search

**Trade-off:**
- Less sophisticated than transformer embeddings
- But adequate for knowledge retrieval use case

#### 2. Firestore for Storage
**Decision:** Use Firestore instead of PostgreSQL or vector DB

**Rationale:**
- NoSQL flexibility for varied data structures
- Built-in scalability
- Easy integration with Firebase ecosystem
- Sufficient for current scale

**Structure:**
```
users/{userId}/
  memory_chunks/{chunkId}
  ingest_jobs/{jobId}
  prospects/{prospectId}
  prospect_discoveries/{discoveryId}
  topic_intelligence/{researchId}
```

#### 3. Weighted Retrieval System
**Decision:** Implement tag-based weighted retrieval for persona chunks

**Rationale:**
- Different content types need different persona sections
- LinkedIn posts need VOICE_PATTERNS, not BIO_FACTS
- Automatic prioritization without manual filtering

**Implementation:**
- Tags: VOICE_PATTERNS, STRUGGLES, EXPERIENCES, PHILOSOPHY, VENTURES, BIO_FACTS, LINKEDIN_EXAMPLES
- Weighted query: `"persona voice style {topic} {category} content writing"`
- System automatically fetches most relevant chunks

#### 4. Anti-AI Writing Rules
**Decision:** Embed anti-AI writing rules directly in prompt

**Rationale:**
- Prevents generic LLM output
- Ensures human-sounding content
- Battle-tested rules from actual content generation

**Implementation:**
- Constant string in `build_content_prompt()` function
- Prepended to every content generation request
- Includes before/after examples

#### 5. Anti-Hallucination Safeguards
**Decision:** Strict rules preventing AI from inventing stories

**Rationale:**
- Authenticity is critical for personal brand
- Fabricated stories damage credibility
- Better to write generic insights than fake anecdotes

**Implementation:**
- Explicit list of real ventures/experiences
- Rule: "If no relevant anecdote exists, use general reflection"
- System message enforces these rules

---

## Frontend Architecture

### Technology Stack
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** (TBD - check frontend code)

### Key Design Decisions

#### 1. App Router
**Decision:** Use Next.js 14 App Router instead of Pages Router

**Rationale:**
- Modern React patterns
- Better performance
- Improved developer experience

#### 2. API Integration
**Decision:** Centralized API client with configurable base URL

**Rationale:**
- Easy environment switching (local vs production)
- Consistent error handling
- Type safety with TypeScript

---

## API Design

### Endpoint Structure

#### Knowledge
- `POST /api/chat` - Retrieve top chunks for query
- `POST /api/knowledge` - Broader search
- `POST /api/ingest/upload` - Upload file
- `POST /api/ingest_drive` - Ingest Google Drive folder

#### Prospects
- `GET /api/prospects` - List prospects
- `POST /api/prospect-discovery/search-free` - Free search
- `POST /api/prospect-discovery/ai-search` - AI-assisted search
- `POST /api/prospect-discovery/search` - Full search

#### LinkedIn
- `POST /api/linkedin/search` - Search LinkedIn posts
- `GET /api/linkedin/industries` - List industries
- `GET /api/linkedin/industry/{industry}/insights` - Industry insights

#### Content Generation
- `POST /api/content/generate` - Generate content

#### Topic Intelligence
- `GET /api/topic-intelligence/themes` - List themes
- `POST /api/topic-intelligence/run` - Run research
- `POST /api/topic-intelligence/store` - Store findings

### Design Principles

1. **RESTful where possible** - GET for reads, POST for writes
2. **JSON responses** - Consistent format
3. **Error handling** - Proper HTTP status codes
4. **Documentation** - Swagger/OpenAPI at `/api/docs`

---

## Data Models

### Memory Chunk
```python
{
    "chunk_id": str,
    "user_id": str,
    "chunk": str,  # Text content
    "embedding": List[float],  # 1024-dim vector
    "metadata": {
        "file_name": str,
        "chunk_index": int,
        "persona_tag": str,  # Optional tag
        "created_at": datetime
    }
}
```

### Prospect
```python
{
    "prospect_id": str,
    "user_id": str,
    "name": str,
    "organization": str,
    "contact_info": {
        "email": str,  # Optional
        "phone": str,  # Optional
        "linkedin": str  # Optional
    },
    "specialties": List[str],
    "influence_score": int,  # 0-100
    "source": str,
    "discovered_at": datetime
}
```

### Content Generation Request
```python
{
    "user_id": str,
    "topic": str,
    "context": str,  # Optional
    "content_type": str,  # "linkedin_post", "cold_email", etc.
    "category": str,  # "value", "sales", "personal"
    "audience": str,  # "general", "education", "tech", etc.
    "pacer_elements": List[str],  # Optional
    "tone": str  # Optional
}
```

---

## External Integrations

### OpenAI
- **Purpose:** Content generation
- **Models:** GPT-4, GPT-3.5-turbo
- **Usage:** Content generation endpoint
- **Cost:** Pay-per-token

### Firecrawl
- **Purpose:** Web scraping (LinkedIn, directories)
- **Usage:** Prospect discovery, topic intelligence
- **Rate Limits:** Handle 403/429 errors gracefully

### Google Custom Search
- **Purpose:** Finding URLs for prospect discovery
- **Usage:** Free search endpoint
- **Rate Limits:** 100 queries/day (free tier)

### Perplexity
- **Purpose:** AI-assisted research
- **Usage:** Topic intelligence, AI search
- **Models:** Various (configured via API)

### Google Drive
- **Purpose:** Document ingestion
- **Usage:** Ingest Drive folder endpoint
- **Auth:** Service account

### Firebase/Firestore
- **Purpose:** Primary database
- **Usage:** All data storage
- **Auth:** Service account JSON

---

## Deployment Architecture

### Railway Deployment

#### Backend
- **Procfile:** `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** Python 3.11
- **Dependencies:** `requirements.txt`

#### Frontend
- **Procfile:** `web: npm start`
- **Environment:** Node 20
- **Dependencies:** `package.json`

### Environment Variables

#### Backend (Required)
- `FIREBASE_SERVICE_ACCOUNT` - Stringified JSON

#### Backend (Optional)
- `FIRECRAWL_API_KEY`
- `PERPLEXITY_API_KEY`
- `GOOGLE_CUSTOM_SEARCH_API_KEY`
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`
- `GOOGLE_DRIVE_SERVICE_ACCOUNT`
- `OPENAI_API_KEY`
- `CORS_ADDITIONAL_ORIGINS`

#### Frontend
- `NEXT_PUBLIC_API_URL` - Backend URL

---

## Security Considerations

### API Keys
- Stored as environment variables
- Never committed to git
- Rotated periodically

### CORS
- Configured for specific origins
- Additional origins via `CORS_ADDITIONAL_ORIGINS`

### Firestore
- Service account authentication
- User-scoped data (users/{userId}/...)

### Rate Limiting
- Handle Firecrawl 403/429 errors
- Graceful degradation when APIs fail

---

## Performance Optimizations

### Embeddings
- Deterministic (cached effectively)
- Local computation (no API latency)

### Retrieval
- Cosine similarity (fast)
- Top-k limiting (manageable result sets)

### Chunking
- Overlapping windows (context preservation)
- Reasonable chunk sizes (balance granularity vs. context)

---

## Scalability Considerations

### Current Scale
- Single user (user_id scoped)
- Firestore handles scaling automatically
- Railway handles infrastructure scaling

### Future Considerations
- Multi-tenant support (if needed)
- Vector database migration (if embeddings grow)
- Caching layer (if retrieval becomes bottleneck)

---

## Key Technical Decisions Summary

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Deterministic embeddings | Cost-effective, fast | Less sophisticated than transformers |
| Firestore | Flexible, scalable | Less structured than SQL |
| Weighted retrieval | Automatic relevance | More complex than simple retrieval |
| Anti-AI rules in prompt | Prevents generic output | Longer prompts |
| Anti-hallucination safeguards | Ensures authenticity | May limit creative content |
| Railway deployment | Simple, integrated | Vendor lock-in |

---

**This architecture has been tested in production and supports the core aiclone functionality.**
