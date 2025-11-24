# AI Clone

A comprehensive AI-powered platform combining knowledge management, prospecting automation, content marketing, and learning systems. Built with FastAPI + Next.js, designed for CustomGPT Actions integration, and aligned with the AI Advantage Jumpstart Playbook philosophy.

## Overview

AI Clone is a hybrid system that serves as:
- **Personal Knowledge Base**: Ingest, search, and retrieve from your documents (Google Drive, PDFs, presentations)
- **Prospecting Assistant**: Semi-autonomous workflow for research → discovery → scoring → outreach
- **Content Marketing Engine**: Research, analyze, and optimize content using AI-powered tools
- **Learning System**: Pattern recognition and continuous improvement from engagement data
- **LinkedIn Intelligence**: Search and analyze high-performing LinkedIn posts for content inspiration

## Project Structure

```
aiclone/
  backend/       # FastAPI service (Railway deploy target)
    app/
      models/   # Pydantic models for requests/responses
      routes/   # API route handlers
      services/ # Business logic and external API clients
      utils/    # Utilities (chunking, etc.)
  frontend/      # Next.js 14 app router frontend (Railway deploy target)
    app/         # Pages and routes
    components/  # React components
```

## Core Features

### 1. Knowledge Management
- **Document Ingestion**: Google Drive integration (Docs, Slides, PDFs, PPT/PPTX)
- **Local File Upload**: Direct file upload with automatic text extraction
- **Semantic Search**: Cosine similarity search over embedded chunks
- **Provenance Tracking**: Full metadata (file ID, folder, timestamps, tags)

### 2. Prospecting Workflow
- **Research Trigger**: Industry/topic research using Perplexity + Firecrawl
- **Prospect Discovery**: Google Custom Search + web scraping for contact discovery
- **Hybrid Scoring**: Multi-dimensional fit scoring (fit_score, referral_capacity, signal_strength)
- **Outreach Generation**: Personalized outreach angles based on research insights
- **Learning Loop**: Pattern recognition from engagement data to improve targeting

### 3. Content Marketing
- **Content Research**: Comprehensive topic research with comparison tables
- **Internal Linking Analysis**: Website crawl and linking opportunity detection
- **Micro Tools Generation**: HTML/JS/CSS tool generation for lead magnets
- **PRD Generation**: Product Requirements Document creation
- **SEO Optimization**: Keyword optimization and content structure improvements

### 4. LinkedIn PACER Strategy Integration
- **LinkedIn Post Search**: Find high-performing posts in target niches (EdTech, AI, stealth founders)
- **Content Drafting**: Generate LinkedIn post drafts aligned with PACER pillars (referral, thought leadership, stealth founder)
- **Content Calendar**: Schedule and manage posting cadence
- **Outreach Generation**: Personalized DMs and connection requests for prospects
- **Engagement Tracking**: Track post performance and learn what content performs best
- **Learning Integration**: Automatically track which pillars, hashtags, and topics drive engagement
- **Industry Insights**: Analyze what works in specific industries
- **Content Modeling**: Use top-performing posts as templates

### 5. Metrics & Learning
- **KPI Tracking**: Weekly/monthly metrics (prospects analyzed, emails sent, meetings booked)
- **Pattern Learning**: Track what works (industries, job titles, outreach angles)
- **Performance Scoring**: Automatic pattern performance calculation
- **Top Performers**: Identify best-performing segments

### 6. AI Jumpstart Playbook Integration
- **Onboarding Prompt**: "Train My AI Assistant" template
- **10 Starter Prompts**: Pre-built prompts for common use cases
- **Playbook API**: Access to playbook summary, prompts, and onboarding

## Environment Configuration

### Required Environment Variables

#### Backend (Railway/Local)

**Core Services:**
- `FIREBASE_SERVICE_ACCOUNT` – Stringified Firebase service account JSON
- `GOOGLE_DRIVE_SERVICE_ACCOUNT` or `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` – Drive service account credentials

**AI/Research Services:**
- `PERPLEXITY_API_KEY` – For research and content generation ([Get Key](https://www.perplexity.ai/settings/api))
- `FIRECRAWL_API_KEY` – For web scraping and content extraction ([Get Key](https://firecrawl.dev))

**Search & Discovery:**
- `GOOGLE_CUSTOM_SEARCH_API_KEY` – For prospect discovery ([Get Key](https://console.cloud.google.com/apis/credentials))
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` – Custom search engine ID ([Create Engine](https://programmablesearchengine.google.com/))

**Optional:**
- `CORS_ADDITIONAL_ORIGINS` – Comma-separated additional CORS origins
- `PORT` – Server port (default: 8080)

#### Frontend (Vercel/Local)
- `NEXT_PUBLIC_API_URL` – Backend API URL (e.g., `https://your-backend.up.railway.app`)

### Local Development Setup

```bash
# Backend
export FIREBASE_SERVICE_ACCOUNT="$(cat keys/firebase-service-account.json)"
export GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/absolute/path/to/drive-service-account.json
export PERPLEXITY_API_KEY="your-key"
export FIRECRAWL_API_KEY="your-key"
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-key"
export GOOGLE_CUSTOM_SEARCH_ENGINE_ID="your-engine-id"

# Frontend
export NEXT_PUBLIC_API_URL="http://localhost:3001"
```

## Firestore Schema

### Collections Structure

```
users/{userId}/
  ├── memory_chunks/{chunkId}          # Document chunks with embeddings
  ├── ingest_jobs/{jobId}               # Ingestion job tracking
  ├── research_insights/{researchId}    # Research summaries and insights
  ├── prospects/{prospectId}            # Discovered prospects
  ├── learning_patterns/{patternId}     # Learned patterns (industry, job_title, etc.)
  ├── metrics/{metricId}                # Weekly/monthly KPIs
  ├── content_drafts/{draftId}          # LinkedIn content drafts
  ├── content_calendar/{calendarId}     # Scheduled posts
  ├── linkedin_metrics/{metricsId}      # Post engagement metrics
  └── audit_logs/{logId}                # Optional action history

global/
  └── agents_config/{doc}               # Shared agent prompts (read-only)
```

### Recommended Indexes
- `created_at` (ascending/descending)
- `source` (ascending)
- `tags` (array-contains)
- `folder_id` (ascending)
- `approval_status` (ascending)
- `industry` (ascending)
- `job_title` (ascending)

## API Endpoints

### Knowledge & Chat

#### `POST /api/chat`
Semantic search over knowledge base.

**Request:**
```json
{
  "user_id": "dev-user",
  "query": "negotiation tactics",
  "top_k": 5
}
```

#### `POST /api/knowledge`
Broader document search (same contract as `/api/chat`).

#### `POST /api/ingest/upload`
Upload and process local files.

#### `POST /api/ingest_drive`
Ingest Google Drive folder.

**Request:**
```json
{
  "user_id": "dev-user",
  "folder_id": "drive-folder-id",
  "max_files": 5
}
```

### Prospecting Workflow

#### `POST /api/research/trigger`
Trigger research on topic/industry.

**Request:**
```json
{
  "user_id": "user123",
  "topic": "SaaS companies serving SMBs",
  "industry": "SaaS"
}
```

#### `POST /api/research/store`
Store MCP-generated research (for Cursor workflows).

#### `POST /api/prospects/discover`
Discover prospects using search + scraping.

**Request:**
```json
{
  "user_id": "user123",
  "company_name": "Acme Corp",
  "industry": "SaaS",
  "location": "San Francisco, CA",
  "max_results": 50
}
```

#### `POST /api/prospects/approve`
Approve or reject discovered prospects.

#### `POST /api/prospects/score`
Score prospects using hybrid approach.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_ids": ["prospect_123"],
  "audience_profile": {
    "ideal_customer": "SaaS companies",
    "pain_points": ["scaling", "retention"]
  }
}
```

### Content Marketing

#### `POST /api/content/research`
Research topic with comparison tables.

**Request:**
```json
{
  "topic": "best AB testing tools 2025",
  "num_results": 10,
  "include_comparison": true
}
```

#### `POST /api/content/internal-linking`
Analyze website for internal linking opportunities.

#### `POST /api/content/micro-tool`
Generate HTML/JS/CSS micro tool.

#### `POST /api/content/prd`
Generate Product Requirements Document.

### LinkedIn Intelligence

#### `POST /api/linkedin/search`
Search for LinkedIn posts.

**Request:**
```json
{
  "query": "AI tools",
  "industry": "Technology",
  "max_results": 20,
  "min_engagement_score": 50,
  "sort_by": "engagement"
}
```

#### `GET /api/linkedin/industry/{industry}/insights`
Get industry-specific insights.

#### `GET /api/linkedin/industries`
List supported industries.

### LinkedIn Content Management (PACER Strategy)

#### `POST /api/linkedin/content/drafts/generate`
Generate LinkedIn post drafts based on PACER pillars.

**Request:**
```json
{
  "user_id": "user123",
  "pillar": "referral",
  "topic": "Supporting students with mental health",
  "include_stealth_founder": false,
  "linked_research_ids": ["research_123"],
  "num_drafts": 3,
  "tone": "authentic and insightful"
}
```

#### `POST /api/linkedin/content/drafts/generate-prompt`
Generate a prompt for manual content creation in ChatGPT/Claude.

#### `POST /api/linkedin/content/drafts/store`
Store manually created drafts.

#### `GET /api/linkedin/content/drafts`
List content drafts (filterable by pillar, status).

#### `POST /api/linkedin/content/calendar/schedule`
Schedule a content draft for publishing.

**Request:**
```json
{
  "user_id": "user123",
  "draft_id": "draft_123",
  "scheduled_date": 1703980800,
  "notes": "Tuesday morning post"
}
```

#### `GET /api/linkedin/content/calendar`
Get scheduled content calendar.

#### `POST /api/linkedin/content/outreach/generate`
Generate personalized outreach (connection requests, DMs).

#### `POST /api/linkedin/content/metrics/update`
Update engagement metrics for a published post.

#### `GET /api/linkedin/content/metrics/draft/{draft_id}`
Get engagement metrics for a specific draft/post.

#### `POST /api/linkedin/content/metrics/update-learning-patterns`
Update learning patterns based on content performance.

### Learning & Metrics

#### `POST /api/learning/update-patterns`
Update learning patterns from engagement.

#### `GET /api/learning/patterns`
Get learned patterns (filterable by type).

#### `GET /api/metrics/current`
Get current period metrics.

#### `POST /api/metrics/update`
Update metrics based on action.

### Playbook

#### `GET /api/playbook/summary`
Get AI Jumpstart Playbook summary.

#### `GET /api/playbook/onboarding`
Get onboarding prompt template.

#### `GET /api/playbook/prompts`
Get 10 starter prompts + bonus.

### Health & Status

#### `GET /`
Root status endpoint.

#### `GET /health`
Health check for Railway.

#### `GET /test`
Simple test endpoint.

## Running Locally

### Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Set environment variables (see Environment Configuration above)

# Start server
uvicorn app.main:app --reload --port 3001
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set environment variable
export NEXT_PUBLIC_API_URL="http://localhost:3001"

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3002` (or the port configured in Next.js).

## Frontend Pages

- `/` - Main chat interface with knowledge retrieval
- `/knowledge` - Knowledge inspector (WIP)
- `/prospecting` - Prospecting workflow interface
- `/content-marketing` - Content marketing tools
- `/jumpstart` - AI Jumpstart Playbook interface

## LinkedIn PACER Strategy

For detailed documentation on using the LinkedIn PACER strategy integration, see [LINKEDIN_PACER_INTEGRATION.md](./LINKEDIN_PACER_INTEGRATION.md).

This integration provides end-to-end support for:
- Researching high-performing LinkedIn posts in your niches
- Generating content drafts aligned with PACER pillars (referral, thought leadership, stealth founder)
- Discovering and targeting prospects in your referral network
- Generating personalized outreach messages
- Scheduling and managing content calendar
- Tracking engagement metrics and learning what works

## Services & Integrations

### External Services
- **Firestore**: Primary database for all data storage
- **Google Drive API**: Document ingestion
- **Perplexity AI**: Research and content generation
- **Firecrawl**: Web scraping and content extraction
- **Google Custom Search**: Prospect discovery

### Internal Services
- **Embedders**: Local embedding generation (HashingVectorizer)
- **Retrieval**: Cosine similarity search
- **Scoring**: Multi-dimensional prospect scoring
- **Memory Service**: Chunk management and provenance
- **Parsers**: PDF, PPTX, audio transcription, OCR

## AI Jumpstart Playbook Alignment

The project follows the **AI Advantage Jumpstart Playbook** philosophy (Tony Robbins & Dean Graziosi):

- **Human-first**: Practical, clear, direct, action-oriented guidance
- **Workflow-driven**: Choose one tool, train it, start with the most pressing prompt, iterate
- **Confidence through quick wins**: Curated tools, onboarding, and prompts that create momentum
- **10 Starter Prompts**: Pre-built prompts for removing roadblocks, reclaiming time, improving CX, and future-proofing skills
- **Onboarding Template**: "Train My AI Assistant" prompt for personalized AI setup

See `AI_JUMPSTART_PLAYBOOK.md` for full details.

## Architecture Highlights

### Backend
- **FastAPI**: Modern, fast Python web framework
- **Firestore**: NoSQL database with real-time capabilities
- **Local Embeddings**: No external LLM required for embeddings (uses scikit-learn)
- **Modular Routes**: Separate routers for each feature area
- **Error Handling**: Comprehensive exception handling and logging
- **CORS**: Configurable CORS for frontend integration

### Frontend
- **Next.js 14**: App router with React Server Components
- **TypeScript**: Full type safety
- **Component-based**: Reusable chat and UI components

### Data Flow
1. **Ingestion**: Documents → Text Extraction → Chunking → Embedding → Firestore
2. **Retrieval**: Query → Embedding → Similarity Search → Ranked Results
3. **Prospecting**: Research → Discovery → Approval → Scoring → Outreach
4. **Learning**: Engagement Data → Pattern Updates → Improved Targeting

## Security

### Firestore Security Rules (Starter)

```javascript
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

**Note**: Only the backend service account should perform ingestion writes. Frontend never accesses Firestore directly.

## Deployment

### Backend (Railway)
1. Connect GitHub repository
2. Set environment variables in Railway dashboard
3. Deploy automatically on push to main

### Frontend (Vercel)
1. Connect GitHub repository
2. Set `NEXT_PUBLIC_API_URL` environment variable
3. Deploy automatically on push to main

## Development Workflow

### Using MCPs (Model Context Protocol)

The project supports MCP workflows in Cursor:
- **Firecrawl MCP**: For web scraping and content extraction
- **Perplexity MCP**: For research and content generation

See `MCP_SETUP_GUIDE.md` and `MCP_WORKFLOW_GUIDE.md` for details.

### Testing Endpoints

Use the provided test scripts:
```bash
./test_all_endpoints.sh
./test_prospecting.sh
./test_linkedin_search.sh
```

## Next Steps & Roadmap

### Planned Features
- [ ] Audio transcription + OCR pipelines for richer ingestion
- [ ] Authentication middleware to secure API endpoints
- [ ] Dedicated vector database (Pinecone/Weaviate) for faster search at scale
- [ ] Real-time collaboration features
- [ ] Advanced analytics dashboard
- [ ] Email integration for outreach automation
- [ ] CRM integrations (HubSpot, Salesforce)

### Known Limitations
- Local embeddings may not be as powerful as OpenAI/Cohere embeddings for large corpora
- Prospect discovery relies on publicly available information
- LinkedIn post scraping is limited to publicly accessible posts

## Documentation

- `QUICK_START.md` - Quick start guide
- `AI_JUMPSTART_PLAYBOOK.md` - Full playbook details
- `PROSPECTING_WORKFLOW_API_DOCS.md` - Complete prospecting API docs
- `MCP_SETUP_GUIDE.md` - MCP configuration
- `LINKEDIN_SEARCH_SETUP.md` - LinkedIn integration setup
- `ENVIRONMENT_VARIABLES.md` - Environment variable reference

## Contributing

This is a private project, but contributions and improvements are welcome. Please ensure:
- Code follows existing patterns
- New features include API documentation
- Environment variables are documented
- Tests are added for new endpoints

## License

Private project - All rights reserved.

---

**Built with ❤️ following the AI Advantage Jumpstart Playbook philosophy**
