# MCP Workflow Guide - Research & Prospecting

## Overview

This system now uses **MCPs (Model Context Protocol) directly in Cursor** for Perplexity research and Firecrawl scraping, eliminating Railway timeout issues and enabling interactive workflows.

## Architecture

```
Cursor (with MCPs) → Research/Scrape → Store in Firestore → Backend uses for scoring/outreach
```

**Benefits:**
- ✅ No HTTP timeout limits (MCPs run directly in Cursor)
- ✅ Interactive research (you guide the process)
- ✅ Cost-optimized (use MCPs only when needed)
- ✅ Better control over research quality

## Setup

### 1. MCPs Already Configured

Your `cursor_mcp_config.json` has:
- ✅ **Perplexity MCP** - Research and search
- ✅ **Firecrawl MCP** - Web scraping and crawling

### 2. Verify MCPs Work in Cursor

Open Cursor and test:
```
Use Perplexity MCP to search for "best SaaS tools for SMBs"
```

If it works, you're ready!

## Workflow: Research → Store → Use

### Step 1: Research with Perplexity MCP (in Cursor)

**In Cursor chat:**
```
Research "SaaS companies serving SMBs" using Perplexity MCP. 
Provide:
1. Industry trends
2. Top companies/tools
3. Key pain points
4. Job titles that matter
5. Referral partner opportunities

Format the output as JSON with these fields:
- summary
- keywords
- job_titles
- trending_pains
- industry_trends
- sources (array of URLs)
```

**MCP will:**
- Search Perplexity (no timeout issues!)
- Return comprehensive research
- You can refine the query interactively

### Step 2: Scrape Sources with Firecrawl MCP (Optional)

**In Cursor chat:**
```
Using Firecrawl MCP, scrape these URLs from the research:
[list of URLs from Perplexity results]

Extract key insights and add to the research summary.
```

**MCP will:**
- Scrape each URL
- Extract content
- No timeout issues!

### Step 3: Store Research in Firestore

**Option A: Use Backend API (Recommended)**
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/research/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id",
    "title": "SaaS companies serving SMBs",
    "industry": "SaaS",
    "summary": "[research summary from MCP]",
    "keywords": ["saas", "smb", ...],
    "job_titles": ["VP Sales", ...],
    "sources": [{"url": "...", "title": "..."}]
  }'
```

**Option B: Store via Cursor (if you have Firestore MCP)**
- Use Firestore MCP to directly store research

### Step 4: Use Research for Prospect Scoring

Once stored, the existing backend endpoints will use it:
- `/api/prospects/score` - Uses stored research for scoring
- `/api/outreach/manual/prompts/generate` - Uses research for outreach angles

## Workflow: Prospect Discovery

### Step 1: Find Prospects with Google Custom Search (Backend)

**Still use backend for Google Custom Search:**
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id",
    "industry": "SaaS",
    "location": "San Francisco",
    "max_results": 10
  }'
```

### Step 2: Enrich Prospects with Firecrawl MCP (Optional)

**In Cursor chat:**
```
Using Firecrawl MCP, scrape the company websites for these prospects:
[list of prospect URLs]

Extract:
- Company description
- Key products/services
- Recent news/updates
- Team page info
```

### Step 3: Store Enriched Data

Update prospects in Firestore with enriched data.

## Complete Example Workflow

### 1. Research Phase (MCP in Cursor)

```
You: Research "AI coding tools for developers" using Perplexity MCP.
     Focus on: tools, pricing, key features, target audience.

Cursor: [Uses Perplexity MCP, returns comprehensive research]
```

### 2. Store Research (Backend API)

```bash
# Copy research from Cursor, format as JSON, store via API
curl -X POST https://aiclone-production-32dc.up.railway.app/api/research/store \
  -H "Content-Type: application/json" \
  -d @research_data.json
```

### 3. Discover Prospects (Backend API)

```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id",
    "industry": "AI Tools",
    "max_results": 20
  }'
```

### 4. Enrich Prospects (MCP in Cursor - Optional)

```
You: Using Firecrawl MCP, scrape company pages for these prospects:
     [prospect URLs]
     
     Extract company info, recent news, team structure.
```

### 5. Score & Outreach (Backend API)

```bash
# Score uses stored research automatically
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospects/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id",
    "prospect_ids": ["prospect-1", "prospect-2"]
  }'

# Generate outreach using research insights
curl -X POST https://aiclone-production-32dc.up.railway.app/api/outreach/manual/prompts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prospect_id": "prospect-1",
    "user_id": "your-user-id"
  }'
```

## Advantages of MCP Approach

1. **No Timeout Issues**
   - MCPs run in Cursor, not Railway
   - No HTTP request timeouts
   - Can take as long as needed

2. **Interactive Control**
   - Guide research in real-time
   - Refine queries based on results
   - Better quality research

3. **Cost Optimization**
   - Use MCPs only when you need them
   - No background API calls
   - Pay per use

4. **Better Results**
   - You can iterate on research
   - Combine multiple MCP calls
   - Human-in-the-loop quality control

## What Stays in Backend

- ✅ Firestore storage/retrieval
- ✅ Prospect scoring (uses stored research)
- ✅ Outreach generation (uses stored research)
- ✅ Metrics tracking
- ✅ Learning loop
- ✅ Google Custom Search (no MCP available)

## What Moves to MCP

- ✅ Perplexity research (MCP in Cursor)
- ✅ Firecrawl scraping (MCP in Cursor)
- ✅ Research refinement (interactive in Cursor)

## Next Steps

1. Test MCPs in Cursor (verify they work)
2. Create `/api/research/store` endpoint (if not exists)
3. Update workflow documentation
4. Test end-to-end: MCP research → Store → Use in scoring

---

**Ready to start?** Open Cursor and try:
```
Use Perplexity MCP to research "SaaS companies serving SMBs"
```

