# AI Clone: Workflows & Standard Operating Procedures

**Date:** 2025  
**Source:** Multiple documentation files (`PROSPECT_DISCOVERY_PIPELINE.md`, `TOPIC_INTELLIGENCE_GUIDE.md`, `README.md`, deployment docs)  
**Purpose:** Complete workflows and SOPs for key aiclone processes

---

## 1. Content Generation Workflow

### Objective
Generate authentic, voice-matched content using persona data and knowledge base examples.

### Prerequisites
- Persona data ingested into knowledge base
- Example content available
- OpenAI API key configured

### The Process

1. **User Request**
   - Topic, context, content type (LinkedIn post, email, DM, Instagram)
   - Category (value, sales, personal)
   - Audience (general, education, tech, fashion, leadership, neurodivergent, entrepreneurs)
   - Optional: PACER elements, tone

2. **Weighted Retrieval**
   - Query: `"persona voice style {topic} {category} content writing"`
   - Fetch top 7 persona chunks (organized by tag)
   - Fetch top 3 example chunks
   - System automatically prioritizes relevant tags for content type

3. **Prompt Building**
   - Combine anti-AI writing rules
   - Add channel-specific prompt
   - Include persona chunks (tagged sections)
   - Add example content
   - Add audience guidance
   - Add category guidance (9/1/1 formula)
   - Add PACER elements (if requested)
   - Add narrative arc structure
   - Add anti-hallucination rules
   - Add voice markers

4. **Content Generation**
   - System message: Ghostwriter instructions
   - User message: Complete mega-prompt
   - OpenAI API call (GPT-4 or GPT-3.5-turbo)
   - Generate 3 content options

5. **Output**
   - Return 3 options separated by "---OPTION---"
   - Each option has different hook/angle
   - All options match voice and use real stories

### Definition of Done
- [ ] Content matches voice patterns from persona
- [ ] No generic AI writing patterns
- [ ] Uses real stories, not fabricated ones
- [ ] Follows narrative arc (hook → challenge → reflection)
- [ ] Appropriate for channel (LinkedIn, email, etc.)
- [ ] Appropriate for audience
- [ ] Appropriate for category (value/sales/personal)
- [ ] 3 distinct options with varying hooks

---

## 2. Prospect Discovery Pipeline

### Objective
Discover and extract prospect information from web sources (Psychology Today, doctor directories, treatment centers, etc.)

### Prerequisites
- Firecrawl API key (for scraping)
- Google Custom Search API key (for finding URLs)
- Perplexity API key (optional, for AI-assisted discovery)
- Firebase configured

### The Process

1. **Category Selection**
   - User selects prospect category (psychologists, doctors, treatment centers, etc.)
   - System loads category-specific extractor

2. **Search Strategy**
   - **Free Search:** Use Google Custom Search to find relevant URLs
   - **AI Search:** Use Perplexity for AI-assisted discovery
   - **Direct Scraping:** Scrape known directories

3. **Extraction**
   - Scrape URLs using Firecrawl or BeautifulSoup fallback
   - Extract: name, organization, contact info, specialties
   - Validate: name format, organization format, contact validity

4. **Scoring**
   - Calculate influence score (0-100)
   - Factors: organization size, role, contact availability, relevance

5. **Saving**
   - Validate prospect meets criteria
   - Check for duplicates
   - Save to Firestore: `users/{userId}/prospects/{prospectId}`
   - Store discovery metadata

6. **Results**
   - Return list of discovered prospects
   - Include metadata (source, confidence, score)

### Definition of Done
- [ ] Prospects extracted with valid name and organization
- [ ] Contact information validated
- [ ] Duplicates filtered
- [ ] Influence scores calculated
- [ ] Saved to Firestore with proper structure
- [ ] Discovery metadata stored

---

## 3. Topic Intelligence Workflow

### Objective
Research a topic using MCP (Model Context Protocol) tools and store findings in knowledge base.

### Prerequisites
- MCP configured (Firecrawl, Perplexity)
- Knowledge base access
- User ID for storage

### The Process

1. **Topic Input**
   - User provides topic/query
   - System determines research approach

2. **Research Execution**
   - Use MCP tools to search web
   - Use Firecrawl to scrape relevant pages
   - Use Perplexity for AI-assisted research
   - Aggregate findings

3. **Synthesis**
   - Organize findings by theme
   - Extract key insights
   - Identify patterns

4. **Storage**
   - Chunk findings
   - Generate embeddings
   - Store in Firestore: `users/{userId}/topic_intelligence/{researchId}`
   - Tag with topic and date

5. **Retrieval**
   - Findings available for future queries
   - Can be retrieved via `/api/knowledge` endpoint

### Definition of Done
- [ ] Research completed using MCP tools
- [ ] Findings synthesized and organized
- [ ] Stored in knowledge base with proper tags
- [ ] Retrievable via knowledge search
- [ ] Metadata includes topic, date, sources

---

## 4. LinkedIn Intelligence Workflow

### Objective
Search LinkedIn posts, analyze industry insights, and extract intelligence.

### Prerequisites
- Firecrawl API key (for LinkedIn scraping)
- LinkedIn access (may require authentication)

### The Process

1. **Search Request**
   - User provides search query
   - System formats for LinkedIn search

2. **Scraping**
   - Use Firecrawl to scrape LinkedIn posts
   - Extract: post content, author, engagement, date
   - Handle rate limits and anti-bot measures

3. **Analysis**
   - Extract themes and insights
   - Identify industry patterns
   - Calculate engagement metrics

4. **Storage**
   - Store posts in Firestore
   - Tag with industry, date, author
   - Link to user's intelligence collection

5. **Retrieval**
   - Available via `/api/linkedin/industry/{industry}/insights`
   - Can be used for content inspiration

### Definition of Done
- [ ] LinkedIn posts scraped successfully
- [ ] Content and metadata extracted
- [ ] Stored in Firestore
- [ ] Accessible via API endpoints
- [ ] Industry insights available

---

## 5. Knowledge Ingestion Workflow

### Objective
Ingest documents (files or Google Drive) into knowledge base for retrieval.

### Prerequisites
- Firebase configured
- Embedding service available
- Google Drive API key (for Drive ingestion)

### The Process

#### File Upload

1. **Upload**
   - User uploads file (PDF, DOCX, TXT, MD, etc.)
   - System validates file type and size

2. **Processing**
   - Extract text from file
   - Chunk text (overlapping windows)
   - Generate embeddings for each chunk
   - Extract metadata (filename, date, type)

3. **Storage**
   - Store chunks in Firestore: `users/{userId}/memory_chunks/{chunkId}`
   - Store metadata
   - Store embeddings for similarity search

4. **Completion**
   - Return job status
   - Chunks available for retrieval

#### Google Drive Ingestion

1. **Folder Selection**
   - User provides Google Drive folder ID
   - System authenticates with Drive API

2. **File Discovery**
   - List all files in folder
   - Filter by supported types
   - Process each file

3. **Batch Processing**
   - For each file: extract, chunk, embed, store
   - Track progress
   - Handle errors gracefully

4. **Completion**
   - Return summary (files processed, chunks created)
   - All chunks available for retrieval

### Definition of Done
- [ ] Files processed and text extracted
- [ ] Text chunked appropriately
- [ ] Embeddings generated
- [ ] Stored in Firestore with proper structure
- [ ] Metadata preserved
- [ ] Retrievable via `/api/chat` or `/api/knowledge`

---

## 6. Deployment Workflow (Railway)

### Objective
Deploy backend and frontend to Railway production environment.

### Prerequisites
- Railway account
- GitHub repository connected
- Environment variables configured

### The Process

#### Backend Deployment

1. **Preparation**
   - Ensure `Procfile` exists: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Set environment variables in Railway:
     - `FIREBASE_SERVICE_ACCOUNT` (stringified JSON)
     - `FIRECRAWL_API_KEY` (optional)
     - `PERPLEXITY_API_KEY` (optional)
     - `GOOGLE_CUSTOM_SEARCH_API_KEY` (optional)
     - `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` (optional)

2. **Deployment**
   - Push to main branch
   - Railway auto-deploys
   - Monitor build logs

3. **Verification**
   - Check health endpoint: `https://your-backend.railway.app/health`
   - Check Swagger docs: `https://your-backend.railway.app/api/docs`
   - Test key endpoints

#### Frontend Deployment

1. **Preparation**
   - Ensure `Procfile` exists: `web: npm start`
   - Set environment variables:
     - `NEXT_PUBLIC_API_URL` (backend URL)

2. **Deployment**
   - Push to main branch
   - Railway auto-deploys
   - Monitor build logs

3. **Verification**
   - Visit frontend URL
   - Test key workflows
   - Verify API connection

### Definition of Done
- [ ] Backend deployed and accessible
- [ ] Frontend deployed and accessible
- [ ] Health endpoints responding
- [ ] API endpoints functional
- [ ] Environment variables configured
- [ ] CORS configured correctly

---

## 7. Testing Workflow

### Objective
Test key functionality before and after deployment.

### Prerequisites
- Local environment set up
- Test data available
- API keys configured

### The Process

1. **Unit Tests**
   - Test individual functions
   - Test extractors
   - Test validators

2. **Integration Tests**
   - Test API endpoints
   - Test database operations
   - Test external API calls

3. **End-to-End Tests**
   - Test complete workflows
   - Test user journeys
   - Test error handling

4. **Production Tests**
   - Test deployed endpoints
   - Test real-world scenarios
   - Monitor for errors

### Definition of Done
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] End-to-end tests passing
- [ ] Production tests successful
- [ ] No critical errors
- [ ] Performance acceptable

---

## Workflow Summary Table

| Workflow | Input | Output | Key Steps |
|----------|-------|--------|-----------|
| Content Generation | Topic, context, type, category, audience | 3 content options | Retrieval → Prompt Building → Generation |
| Prospect Discovery | Category, search query | List of prospects | Search → Extract → Validate → Score → Save |
| Topic Intelligence | Topic/query | Research findings | Research → Synthesize → Store |
| LinkedIn Intelligence | Search query | LinkedIn posts & insights | Search → Scrape → Analyze → Store |
| Knowledge Ingestion | Files or Drive folder | Chunked knowledge base | Extract → Chunk → Embed → Store |
| Deployment | Code changes | Deployed app | Prepare → Deploy → Verify |
| Testing | Test cases | Test results | Unit → Integration → E2E → Production |

---

**These workflows are production-ready and have been tested in the aiclone project.**
