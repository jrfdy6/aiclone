# MCP Pivot Summary

## What Changed

**Before:** Perplexity and Firecrawl called via Railway backend API (timeout issues)

**After:** Perplexity and Firecrawl used directly via MCPs in Cursor (no timeout issues)

## New Architecture

```
┌─────────────────┐
│  Cursor (MCPs)  │
│  - Perplexity   │──┐
│  - Firecrawl    │  │
└─────────────────┘  │
                     │ Research/Scrape Data
                     ▼
┌─────────────────────────────────┐
│  Backend API (Railway)          │
│  POST /api/research/store       │──┐
└─────────────────────────────────┘  │
                                     │ Store
                                     ▼
┌─────────────────────────────────┐
│  Firestore                      │
│  - research_insights            │
│  - prospects                    │
└─────────────────────────────────┘
                                     │ Use
                                     ▼
┌─────────────────────────────────┐
│  Backend Endpoints              │
│  - /api/prospects/score         │
│  - /api/outreach/manual/...     │
└─────────────────────────────────┘
```

## New Endpoint

### `POST /api/research/store`

**Purpose:** Store research data generated via MCPs in Cursor

**Request:**
```json
{
  "user_id": "your-user-id",
  "title": "SaaS companies serving SMBs",
  "industry": "SaaS",
  "summary": "Research summary from Perplexity MCP...",
  "keywords": ["saas", "smb", "b2b"],
  "job_titles": ["VP Sales", "Director of Revenue"],
  "trending_pains": ["scaling", "efficiency"],
  "industry_trends": ["automation", "ai"],
  "sources": [
    {"url": "https://...", "title": "..."}
  ]
}
```

**Response:**
```json
{
  "success": true,
  "research_id": "research_1234567890",
  "status": "success",
  "summary": {...}
}
```

## Workflow

### 1. Research in Cursor (MCP)
```
Use Perplexity MCP to research "SaaS companies serving SMBs"
```

### 2. Store Research (Backend API)
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/research/store \
  -H "Content-Type: application/json" \
  -d @research_data.json
```

### 3. Use Research (Existing Endpoints)
- `/api/prospects/score` - Automatically uses stored research
- `/api/outreach/manual/prompts/generate` - Uses research for angles

## Benefits

✅ **No Timeout Issues** - MCPs run in Cursor, not Railway
✅ **Interactive Research** - Guide the process in real-time
✅ **Cost Optimized** - Use MCPs only when needed
✅ **Better Quality** - Human-in-the-loop refinement

## What Stays the Same

- ✅ Firestore storage
- ✅ Prospect scoring
- ✅ Outreach generation
- ✅ Metrics tracking
- ✅ Learning loop
- ✅ Google Custom Search (backend)

## What Changed

- ✅ Research generation: Backend API → MCP in Cursor
- ✅ Scraping: Backend API → MCP in Cursor (optional)
- ✅ New endpoint: `/api/research/store` for MCP data

## Legacy Endpoint

`/api/research/trigger` still works but is now **deprecated** for new workflows.

Use MCPs in Cursor + `/api/research/store` instead.

## Next Steps

1. ✅ MCPs configured in `cursor_mcp_config.json`
2. ✅ New `/api/research/store` endpoint created
3. ✅ Workflow guide created (`MCP_WORKFLOW_GUIDE.md`)
4. ⏭️ Test MCPs in Cursor
5. ⏭️ Test storing research via new endpoint
6. ⏭️ Update frontend (if needed) to use new workflow

---

**Ready to test?** See `MCP_WORKFLOW_GUIDE.md` for step-by-step instructions.

