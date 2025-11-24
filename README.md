# AI Clone

A comprehensive AI-powered platform combining knowledge management, prospecting automation, content marketing, and learning systems. Built with FastAPI + Next.js, designed for CustomGPT Actions integration, and aligned with the AI Advantage Jumpstart Playbook philosophy.

## Overview

AI Clone is a hybrid system that serves as:
- **Personal Knowledge Base**: Ingest, search, and retrieve from your documents (Google Drive, PDFs, presentations)
- **Prospecting Assistant**: Semi-autonomous workflow for research → discovery → scoring → outreach
- **Content Marketing Engine**: Research, analyze, and optimize content using AI-powered tools
- **Learning System**: Pattern recognition and continuous improvement from engagement data
- **LinkedIn Intelligence**: Search and analyze high-performing LinkedIn posts for content inspiration
- **AI-Powered Intelligence**: Advanced ML predictions, recommendations, and content optimization
- **Business Intelligence**: Executive dashboards, advanced reporting, and predictive insights
- **Multi-Format Content Generation**: Blogs, emails, video scripts, white papers

## Project Structure

```
aiclone/
  backend/       # FastAPI service (Railway deploy target)
    app/
      models/   # Pydantic models for requests/responses
      routes/   # API route handlers
      services/ # Business logic and external API clients
      utils/    # Utilities (chunking, etc.)
      middleware/ # Security, rate limiting, logging
  frontend/      # Next.js 14 app router frontend (Railway deploy target)
    app/         # Pages and routes
    components/  # React components
    lib/         # API clients and utilities
```

## Core Features

### 1. Knowledge Management
- **Document Ingestion**: Google Drive integration (Docs, Slides, PDFs, PPT/PPTX)
- **Local File Upload**: Direct file upload with automatic text extraction
- **Semantic Search**: Cosine similarity search over embedded chunks
- **Provenance Tracking**: Full metadata (file ID, folder, timestamps, tags)

### 2. Prospecting Workflow (Phases 1-2, Enhanced in Phase 4)
- **Research Trigger**: Industry/topic research using Perplexity + Firecrawl
- **Prospect Discovery**: Google Custom Search + web scraping for contact discovery
- **Hybrid Scoring**: Multi-dimensional fit scoring (fit_score, referral_capacity, signal_strength)
- **Outreach Generation**: Personalized outreach angles based on research insights
- **Learning Loop**: Pattern recognition from engagement data to improve targeting

### 2a. Outreach Engine & Automation (Phase 4)
- **Prospect Segmentation**: Automatic segmentation by audience type (Private school admins, EdTech leaders, Stealth founders)
- **Outreach Sequences**: Automated multi-step sequences (connection requests, DMs, follow-ups)
- **Message Personalization**: Segment-specific message variations with pain point targeting
- **Engagement Tracking**: Comprehensive tracking of outreach response rates and conversions
- **Calendar & Cadence**: Weekly outreach cadence management and follow-up scheduling

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

### 7. Advanced AI & Machine Learning (Phase 6)
- **Predictive Analytics**: 
  - Prospect conversion prediction with confidence scores
  - Content engagement forecasting
  - Optimal posting time recommendations
- **Recommendation Engine**: 
  - Smart prospect suggestions based on fit scores
  - Content topic recommendations from research insights
  - Outreach angle recommendations
  - Hashtag recommendations based on performance
- **Content Optimization**: 
  - Multi-factor content quality scoring (A-D grades)
  - A/B test variant generation and tracking
  - Sentiment analysis integration
- **Advanced NLP**: 
  - Intent detection (6 intent types)
  - Entity extraction (companies, people, industries)
  - Text summarization
  - Sentiment analysis

### 8. Advanced Analytics & Business Intelligence (Phase 6)
- **Executive Dashboard**: High-level KPIs, conversion funnel, trends analysis
- **Custom Dashboard Builder**: Create personalized dashboards
- **Advanced Reporting**: Period-over-period comparative analytics
- **Predictive Insights**: Revenue forecasting, pipeline forecasting, anomaly detection

### 9. Advanced Content Generation (Phase 6)
- **Multi-Format Generation**: 
  - Blog posts (short/medium/long, multiple tones)
  - Professional emails (multiple purposes and tones)
  - Video scripts (short/medium/long, multiple styles)
  - White papers (comprehensive, structured)
- **Content Library**: 
  - Version-controlled content repository
  - Approval workflows
  - Multi-platform publishing support
- **Cross-Platform Analytics**: Unified performance tracking across all publishing platforms

### 10. Intelligence Layer (Phase 3)
- **AI Research Task Manager**: Automated research with task queue
- **Playbooks Library**: Browsable AI-powered playbooks
- **Automations Builder**: Zapier-style trigger-action workflows
- **Global Activity Feed**: Real-time timeline of all system events
- **Templates Gallery**: Content and outreach templates
- **AI Knowledge Vault**: Structured research insights repository
- **AI Personas**: Configurable AI behavior and communication styles
- **System Logs & Debug Panel**: User-facing error tracking and debugging

### 11. Real-Time Features (Phase 5)
- **WebSocket Support**: Real-time activity streaming
- **Live Notifications**: Instant system updates
- **Task Status Updates**: Real-time progress tracking

### 12. Security & Authentication (Phase 5)
- **JWT Authentication**: Secure user authentication
- **Rate Limiting**: API abuse prevention
- **Audit Logging**: Complete action history
- **RBAC**: Role-based access control (structure ready)

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
- `JWT_SECRET_KEY` – Secret key for JWT tokens (default: auto-generated)
- `REDIS_URL` – Redis URL for caching (optional)

#### Frontend (Railway/Vercel)
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
  ├── research_tasks/{taskId}           # Research task queue
  ├── research_results/{resultId}       # Research execution results
  ├── prospects/{prospectId}            # Discovered prospects
  ├── learning_patterns/{patternId}     # Learned patterns (industry, job_title, etc.)
  ├── metrics/{metricId}                # Weekly/monthly KPIs
  ├── content_drafts/{draftId}          # LinkedIn content drafts
  ├── content_library/{contentId}       # Multi-format content with versioning
  ├── content_calendar/{calendarId}     # Scheduled posts
  ├── linkedin_metrics/{metricsId}      # Post engagement metrics
  ├── outreach/{outreachId}             # Outreach messages and sequences
  ├── templates/{templateId}            # Content and outreach templates
  ├── knowledge_vault/{itemId}          # Research knowledge vault items
  ├── personas/{personaId}              # AI personas configuration
  ├── automations/{automationId}        # Automation workflows
  ├── playbooks/{playbookId}            # AI playbooks
  ├── dashboards/{dashboardId}          # Custom dashboards
  ├── custom_reports/{reportId}         # Custom reports
  ├── ab_tests/{testId}                 # A/B test results
  ├── system_logs/{logId}               # System logs and errors
  ├── activity/{activityId}             # Global activity feed
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
- `status` (ascending)
- `user_id` (ascending)

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

#### `POST /api/prospects/discover`
Discover prospects using search + scraping.

#### `POST /api/prospects/score`
Score prospects using hybrid approach.

### Content Marketing

#### `POST /api/content/research`
Research topic with comparison tables.

#### `POST /api/content/internal-linking`
Analyze website for internal linking opportunities.

#### `POST /api/content/micro-tool`
Generate HTML/JS/CSS micro tool.

#### `POST /api/content/prd`
Generate Product Requirements Document.

### LinkedIn Intelligence

#### `POST /api/linkedin/search`
Search for LinkedIn posts.

#### `GET /api/linkedin/industry/{industry}/insights`
Get industry-specific insights.

### LinkedIn Content Management (PACER Strategy)

#### `POST /api/linkedin/content/drafts/generate`
Generate LinkedIn post drafts based on PACER pillars.

#### `POST /api/linkedin/content/calendar/schedule`
Schedule a content draft for publishing.

#### `POST /api/linkedin/content/outreach/generate`
Generate personalized outreach (connection requests, DMs).

### Phase 6: Advanced AI & Machine Learning

#### Predictive Analytics
- `POST /api/predictive/predict` - Make predictions (conversion, engagement, timing)
- `POST /api/predictive/prospect/{id}/predict-conversion` - Prospect conversion prediction
- `GET /api/predictive/optimal-posting-time` - Get optimal posting times

#### Recommendations
- `GET /api/recommendations/prospects` - Get prospect recommendations
- `GET /api/recommendations/content-topics` - Get content topic recommendations
- `GET /api/recommendations/outreach-angles` - Get outreach angle recommendations
- `GET /api/recommendations/hashtags` - Get hashtag recommendations

#### NLP Services
- `POST /api/nlp/detect-intent` - Detect text intent
- `POST /api/nlp/extract-entities` - Extract entities from text
- `POST /api/nlp/summarize` - Summarize text
- `POST /api/nlp/analyze-sentiment` - Analyze sentiment

#### Content Optimization
- `POST /api/content-optimization/score` - Score content quality
- `POST /api/content-optimization/ab-test/variants` - Create A/B test variants
- `POST /api/content-optimization/ab-test/{id}/track` - Track A/B test results
- `GET /api/content-optimization/ab-test/{id}/winner` - Get A/B test winner

### Phase 6: Business Intelligence

#### `GET /api/bi/executive-dashboard`
Get executive dashboard with KPIs, funnel, and trends.

**Query Parameters:**
- `user_id` (required)
- `days` (default: 30)

#### `POST /api/bi/custom-dashboard`
Create a custom dashboard.

#### `POST /api/reporting/comparative`
Generate comparative report between two periods.

#### `GET /api/predictive-insights/forecast/revenue`
Forecast revenue based on pipeline data.

#### `GET /api/predictive-insights/anomalies`
Detect anomalies in metrics.

### Phase 6: Advanced Content Generation

#### `POST /api/content/generate/blog`
Generate a blog post.

**Request:**
```json
{
  "topic": "AI in Education",
  "length": "medium",
  "tone": "professional"
}
```

#### `POST /api/content/generate/email`
Generate an email.

#### `POST /api/content/generate/video-script`
Generate a video script.

#### `POST /api/content/generate/white-paper`
Generate a white paper.

#### Content Library
- `POST /api/content-library` - Create content
- `GET /api/content-library` - List content (filterable by format, status)
- `GET /api/content-library/{id}` - Get content
- `PUT /api/content-library/{id}` - Update content
- `POST /api/content-library/{id}/approve` - Approve content
- `POST /api/content-library/{id}/publish` - Publish to platforms
- `DELETE /api/content-library/{id}` - Delete content

#### `GET /api/analytics/cross-platform/unified`
Get unified performance metrics across all platforms.

### Phase 3: Intelligence Layer

#### Research Tasks
- `GET /api/research-tasks` - List research tasks
- `POST /api/research-tasks` - Create research task
- `GET /api/research-tasks/{id}` - Get task details
- `POST /api/research-tasks/{id}/run` - Execute research task
- `GET /api/research-tasks/{id}/insights` - Get research insights

#### Activity Feed
- `GET /api/activity` - List activity events
- `POST /api/activity` - Create activity event

#### Templates
- `GET /api/templates` - List templates
- `POST /api/templates` - Create template
- `POST /api/templates/{id}/favorite` - Toggle favorite
- `POST /api/templates/{id}/use` - Use template

#### Knowledge Vault
- `GET /api/vault` - List vault items
- `GET /api/vault/topics/clusters` - Get topic clusters
- `GET /api/vault/trendlines` - Get trendlines

#### Personas
- `GET /api/personas` - List personas
- `GET /api/personas/default` - Get default persona
- `POST /api/personas` - Create persona

#### Automations
- `GET /api/automations` - List automations
- `POST /api/automations` - Create automation
- `POST /api/automations/{id}/activate` - Activate automation

#### Playbooks
- `GET /api/playbooks` - List playbooks
- `POST /api/playbooks/{id}/run` - Run playbook

### Phase 5: Real-Time & Security

#### WebSocket
- `WS /api/ws` - WebSocket connection for real-time updates

#### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

#### Webhooks
- `GET /api/webhooks` - List webhooks
- `POST /api/webhooks` - Create webhook

### Health & Status

#### `GET /health`
Health check for Railway.

#### `GET /api/docs`
OpenAPI/Swagger documentation.

## Testing

### Phase 6 API Tests

Run the comprehensive test suite to verify all Phase 6 endpoints:

```bash
cd frontend
./test-phase6-simple.sh
```

This tests:
- ✅ Predictive Analytics (1 endpoint)
- ✅ Recommendations (3 endpoints)
- ✅ NLP Services (3 endpoints)
- ✅ Content Optimization (1 endpoint)
- ✅ Business Intelligence (1 endpoint)
- ✅ Content Generation (2 endpoints)
- ✅ Content Library (1 endpoint)
- ✅ Cross-Platform Analytics (1 endpoint)

**Total:** 13 endpoints tested

See `frontend/README_TESTING.md` for detailed testing documentation.

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
- `/dashboard` - Unified workspace with widgets
- `/prospecting` - Prospecting workflow interface
- `/prospects` - Prospect management with filtering and sorting
- `/outreach` - Outreach automation panel
- `/calendar` - Follow-up calendar with drag-and-drop
- `/content-marketing` - Content marketing tools
- `/research-tasks` - AI Research Task Manager
- `/activity` - Global activity feed timeline
- `/playbooks` - Playbooks library
- `/automations` - Automations builder
- `/templates` - Templates gallery
- `/vault` - AI Knowledge Vault
- `/personas` - AI Personas configuration
- `/system/logs` - System logs and debug panel
- `/jumpstart` - AI Jumpstart Playbook interface

## Deployment

### Backend (Railway)
1. Connect GitHub repository
2. Set environment variables in Railway dashboard
3. Deploy automatically on push to main
4. API available at: `https://your-backend.up.railway.app`
5. API documentation at: `/api/docs`

### Frontend (Railway)
1. Connect GitHub repository
2. Set `NEXT_PUBLIC_API_URL` environment variable
3. Deploy automatically on push to main

## Implementation Phases

### ✅ Phase 1-2: Core Features
- Knowledge management
- Prospecting workflow
- Content marketing tools
- LinkedIn integration

### ✅ Phase 3: Intelligence Layer
- Research task management
- Activity timeline
- Templates gallery
- Knowledge vault
- AI personas
- Automations builder
- Playbooks library
- System logs

### ✅ Phase 4: Outreach Engine & Metrics
- **Prospect Segmentation**: Divide audience into segments (Private school admins/mental health/referral network, EdTech/AI-savvy leaders, Stealth founder/early adopters)
- **Outreach Sequences**: Semi-automated DMs, connection requests, and follow-up sequences with variations per segment
- **Scoring & Prioritization**: Multi-dimensional scoring (Fit, Referral capacity, Signal strength)
- **Engagement Metrics**: Track LinkedIn posts & reels engagement, prospect & outreach metrics
- **Learning Patterns**: Pattern recognition from engagement data to improve targeting

### ✅ Phase 5: Production Excellence
- WebSocket real-time features
- JWT authentication
- Rate limiting
- Webhooks
- Advanced analytics
- API documentation (OpenAPI/Swagger)
- Performance optimizations

### ✅ Phase 6: Advanced AI & Intelligence
- Predictive analytics engine
- Recommendation system
- Content optimization (A/B testing, scoring)
- Advanced NLP capabilities
- Business intelligence dashboards
- Advanced reporting
- Predictive insights
- Multi-format content generation
- Content library with version control
- Cross-platform analytics

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
- **WebSocket Manager**: Real-time communication
- **Authentication Service**: JWT-based auth
- **Analytics Service**: Advanced analytics and reporting

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

## Development Workflow

### Using MCPs (Model Context Protocol)

The project supports MCP workflows in Cursor:
- **Firecrawl MCP**: For web scraping and content extraction
- **Perplexity MCP**: For research and content generation

See `MCP_SETUP_GUIDE.md` and `MCP_WORKFLOW_GUIDE.md` for details.

## Documentation

### Core Documentation
- `QUICK_START.md` - Quick start guide
- `AI_JUMPSTART_PLAYBOOK.md` - Full playbook details
- `PROSPECTING_WORKFLOW_API_DOCS.md` - Complete prospecting API docs
- `LINKEDIN_PACER_INTEGRATION.md` - LinkedIn PACER strategy guide

### Phase Documentation
- `PHASE_3_COMPLETE.md` - Intelligence Layer implementation
- `PHASE_4_COMPLETE.md` - Outreach Engine & Metrics
- `PHASE_5_COMPLETE.md` - Production Excellence
- `PHASE_6_IMPLEMENTATION_COMPLETE.md` - Advanced AI & Intelligence
- `PHASE_6_TEST_RESULTS.md` - Phase 6 test results

### Setup & Configuration
- `MCP_SETUP_GUIDE.md` - MCP configuration
- `LINKEDIN_SEARCH_SETUP.md` - LinkedIn integration setup
- `ENVIRONMENT_VARIABLES.md` - Environment variable reference
- `RAILWAY_SETUP.md` - Railway deployment guide

### Testing
- `frontend/README_TESTING.md` - Testing documentation
- `PHASE_6_TEST_RESULTS.md` - Phase 6 test results

## Next Steps & Roadmap

### Completed ✅
- [x] Core knowledge management
- [x] Prospecting workflow
- [x] Content marketing tools
- [x] LinkedIn integration
- [x] Intelligence layer (Phase 3)
- [x] Outreach engine & metrics (Phase 4)
- [x] Production excellence (Phase 5)
- [x] Advanced AI & intelligence (Phase 6)

### Planned Features
- [ ] Audio transcription + OCR pipelines for richer ingestion
- [ ] CRM integrations (HubSpot, Salesforce)
- [ ] Email integration for outreach automation
- [ ] Advanced ML models for better predictions
- [ ] Multi-language support
- [ ] Mobile app

### Known Limitations
- Local embeddings may not be as powerful as OpenAI/Cohere embeddings for large corpora
- Prospect discovery relies on publicly available information
- LinkedIn post scraping is limited to publicly accessible posts

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

**Status:** ✅ **Production Ready** - All phases complete, fully tested, and deployed.
