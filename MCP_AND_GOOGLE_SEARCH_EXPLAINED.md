# MCP (Perplexity & Firecrawl) + Google Search API Architecture

## Overview

Your system uses **three different search/scraping mechanisms** that work together:

1. **MCP Perplexity** - Runs in Cursor IDE (not in backend)
2. **MCP Firecrawl** - Runs in Cursor IDE (not in backend)  
3. **Google Custom Search API** - Runs in backend (Python service)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CURSOR IDE (Your Local Machine)          │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Perplexity MCP  │         │ Firecrawl MCP    │          │
│  │                 │         │                  │          │
│  │ - Research      │         │ - Scrape URLs    │          │
│  │ - Search web    │         │ - Extract content│          │
│  │ - Get sources   │         │ - Crawl sites   │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                              │
│  Configured in: cursor_mcp_config.json                      │
│  Runs: Directly in Cursor (no HTTP, no timeouts)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (You manually trigger via chat)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              BACKEND (Railway/Python FastAPI)               │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Google Search   │         │ Firecrawl Client │          │
│  │ API Client      │         │ (Python)         │          │
│  │                 │         │                  │          │
│  │ - Find companies│         │ - Scrape pages   │          │
│  │ - Search web    │         │ - Extract data   │          │
│  │ - Get URLs      │         │ - Used in /discover│        │
│  └──────────────────┘         └──────────────────┘          │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Perplexity      │         │ Firestore        │          │
│  │ Client (Python) │         │                  │          │
│  │                 │         │ - Store research │          │
│  │ - Research topic│         │ - Store prospects│          │
│  │ - Used in /trigger│       │ - Store insights │          │
│  └──────────────────┘         └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## 1. MCP (Model Context Protocol) - Perplexity & Firecrawl

### What is MCP?

MCP is a protocol that allows AI assistants (like Cursor) to directly access external tools and services. Instead of making HTTP requests from your backend, MCPs run **directly in Cursor IDE**.

### Configuration

Your MCPs are configured in `cursor_mcp_config.json`:

```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "fc-ce10579f6df4449c84b31c0dbc69a949"
      }
    },
    "perplexity-mcp": {
      "command": "perplexity-mcp",
      "args": [
        "--model",
        "sonar",
        "--reasoning-model",
        "sonar-reasoning"
      ],
      "env": {
        "PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE"
      }
    }
  }
}
```

### How MCPs Work

**Key Point:** MCPs are **NOT** part of your backend code. They run in Cursor IDE when you ask me (the AI assistant) to use them.

**Example:**
```
You: "Research SaaS companies using Perplexity MCP"
Me: [Uses Perplexity MCP directly in Cursor]
    [Returns research results to you]
```

**Benefits:**
- ✅ No HTTP timeouts (runs locally in Cursor)
- ✅ Interactive (you guide the research)
- ✅ No backend API calls needed
- ✅ Can take as long as needed

### Perplexity MCP

**Location:** Runs in Cursor IDE (not backend)

**What it does:**
- Searches the web using Perplexity's AI-powered search
- Returns comprehensive research with sources
- Can answer complex questions with citations

**When you use it:**
- In Cursor chat: "Use Perplexity MCP to research..."
- I call the MCP directly (not your backend)
- Results come back to you in chat

**Example workflow:**
```
You: Research "AI coding tools for developers" using Perplexity MCP

Me: [Calls Perplexity MCP]
    [Gets research results]
    [Shows you: summary, sources, insights]
```

### Firecrawl MCP

**Location:** Runs in Cursor IDE (not backend)

**What it does:**
- Scrapes web pages (single URLs or entire sites)
- Extracts content in markdown/HTML
- Can crawl multiple pages

**When you use it:**
- In Cursor chat: "Use Firecrawl MCP to scrape..."
- I call the MCP directly (not your backend)
- Results come back to you in chat

**Example workflow:**
```
You: Scrape https://example.com/team using Firecrawl MCP

Me: [Calls Firecrawl MCP]
    [Gets scraped content]
    [Shows you: page content, links, metadata]
```

## 2. Google Custom Search API (Backend)

### What it is

Google Custom Search API is a **backend service** that searches the web using Google's search engine. It's different from MCPs because:

- ❌ It runs in your **backend** (Python FastAPI)
- ❌ It makes HTTP requests to Google's API
- ❌ It's subject to HTTP timeouts
- ✅ It's automated (no manual interaction needed)

### Configuration

**Location:** `backend/app/services/search_client.py`

**Environment Variables:**
- `GOOGLE_CUSTOM_SEARCH_API_KEY` - Your Google API key
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` - Your Custom Search Engine ID

### How it works

**1. Client Initialization:**
```python
# backend/app/services/search_client.py
class GoogleCustomSearchClient:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
```

**2. Search Function:**
```python
def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
    # Makes HTTP request to Google API
    # Returns: title, link, snippet, display_link
```

**3. Used in Prospect Discovery:**
```python
# backend/app/routes/prospects.py
@router.post("/discover")
async def discover_prospects(request: ProspectDiscoveryRequest):
    search_client = get_search_client()
    
    # Step 1: Search for companies
    search_results = search_client.search_companies(
        industry=request.industry,
        location=request.location,
        max_results=request.max_results,
    )
    
    # Step 2: Scrape results with Firecrawl (backend client)
    for result in search_results:
        scraped = firecrawl.scrape_url(result.link)
        # Extract prospect info...
```

## 3. How They Work Together

### Two Separate Workflows

#### Workflow A: MCP Research (Interactive in Cursor)

```
1. You ask in Cursor: "Research SaaS companies using Perplexity MCP"
2. I use Perplexity MCP directly (in Cursor)
3. You get research results in chat
4. You can refine: "Get more details on pricing"
5. I use Perplexity MCP again
6. You get refined results
7. You store results via: POST /api/research/store
```

**Files involved:**
- `cursor_mcp_config.json` - MCP configuration
- `backend/app/routes/research.py` - `/store` endpoint to save MCP results

#### Workflow B: Automated Prospect Discovery (Backend)

```
1. Frontend calls: POST /api/prospects/discover
2. Backend uses Google Search API to find companies
3. Backend uses Firecrawl Client (Python) to scrape pages
4. Backend extracts prospect info
5. Backend stores in Firestore
6. Returns prospects to frontend
```

**Files involved:**
- `backend/app/services/search_client.py` - Google Search client
- `backend/app/services/firecrawl_client.py` - Firecrawl Python client
- `backend/app/routes/prospects.py` - `/discover` endpoint

### Key Differences

| Feature | MCP (Cursor) | Backend Services |
|---------|-------------|------------------|
| **Location** | Runs in Cursor IDE | Runs in backend (Railway) |
| **Trigger** | You ask in chat | API endpoint call |
| **Timeouts** | None (local) | HTTP timeouts (Railway) |
| **Interaction** | Interactive | Automated |
| **Use Case** | Research, exploration | Production workflows |
| **Google Search** | ❌ Not available as MCP | ✅ Available as API |

### Why Two Firecrawl Implementations?

You have **two** Firecrawl implementations:

1. **Firecrawl MCP** (`cursor_mcp_config.json`)
   - Runs in Cursor IDE
   - Used when you manually ask me to scrape
   - No timeouts, interactive

2. **Firecrawl Client** (`backend/app/services/firecrawl_client.py`)
   - Runs in backend
   - Used in automated workflows (e.g., `/prospects/discover`)
   - Subject to HTTP timeouts

**Why both?**
- MCP: For interactive research in Cursor
- Backend Client: For automated prospect discovery

## 4. Complete Data Flow Examples

### Example 1: Research Workflow (MCP)

```
┌─────────┐
│  You    │
└────┬────┘
     │ "Research SaaS companies using Perplexity MCP"
     ▼
┌─────────────────┐
│  Cursor IDE     │
│  (Me - Auto)    │
└────┬────────────┘
     │ Calls Perplexity MCP
     ▼
┌─────────────────┐
│ Perplexity API  │
│ (via MCP)       │
└────┬────────────┘
     │ Returns research
     ▼
┌─────────────────┐
│  Cursor Chat    │
│  (Shows you)    │
└────┬────────────┘
     │ You copy results
     ▼
┌─────────────────┐
│ POST /research/ │
│ store           │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│  Firestore      │
│  (Stored)       │
└─────────────────┘
```

### Example 2: Prospect Discovery (Backend)

```
┌─────────┐
│Frontend │
└────┬────┘
     │ POST /api/prospects/discover
     ▼
┌─────────────────┐
│  Backend        │
│  (Railway)      │
└────┬────────────┘
     │
     ├─► Google Search API
     │   (Finds company URLs)
     │
     ├─► Firecrawl Client (Python)
     │   (Scrapes URLs)
     │
     └─► Extract prospect info
         │
         ▼
┌─────────────────┐
│  Firestore      │
│  (Stored)       │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│  Response       │
│  (Prospects)    │
└─────────────────┘
```

## 5. When to Use What

### Use MCP (Perplexity/Firecrawl in Cursor) when:
- ✅ You want to do research interactively
- ✅ You need to refine queries based on results
- ✅ You're exploring a topic
- ✅ You want to avoid timeout issues
- ✅ You're manually guiding the process

### Use Backend Services (Google Search/Firecrawl Client) when:
- ✅ You need automated workflows
- ✅ Frontend needs to trigger searches
- ✅ You're building production features
- ✅ You need consistent, repeatable processes

### Use Google Search API (Backend) when:
- ✅ You need to find companies/websites
- ✅ You need structured search results
- ✅ You're doing prospect discovery
- ✅ You need pagination (up to 100 results)

## 6. Configuration Summary

### MCP Configuration (Cursor)
**File:** `cursor_mcp_config.json`
- Perplexity MCP: Uses `PERPLEXITY_API_KEY`
- Firecrawl MCP: Uses `FIRECRAWL_API_KEY`
- **Runs:** In Cursor IDE (local)

### Backend Configuration (Railway)
**Files:** 
- `backend/app/services/perplexity_client.py` - Uses `PERPLEXITY_API_KEY`
- `backend/app/services/firecrawl_client.py` - Uses `FIRECRAWL_API_KEY`
- `backend/app/services/search_client.py` - Uses `GOOGLE_CUSTOM_SEARCH_API_KEY` + `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`

**Runs:** In backend (Railway server)

## 7. Important Notes

1. **MCPs are NOT in your backend code** - They're tools I use when you ask me in Cursor chat
2. **Google Search has no MCP** - Only available as backend API
3. **Two Firecrawl implementations** - One for MCP (Cursor), one for backend (Python)
4. **MCP results need to be stored** - Use `/api/research/store` to save MCP research
5. **Backend services are automated** - Called via API endpoints from frontend

## 8. Quick Reference

### To research a topic:
```
In Cursor: "Use Perplexity MCP to research [topic]"
Then: Store results via POST /api/research/store
```

### To discover prospects:
```
Frontend: POST /api/prospects/discover
Backend: Uses Google Search → Firecrawl → Extract → Store
```

### To scrape a URL:
```
Option 1 (MCP): "Use Firecrawl MCP to scrape [URL]"
Option 2 (Backend): Use firecrawl_client.py in your code
```

---

**Summary:** MCPs run in Cursor for interactive research, while Google Search API runs in backend for automated prospect discovery. They complement each other but serve different purposes!

