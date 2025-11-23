# Quick Start - Vibe Marketing Implementation

Get started with implementing vibe marketing strategies in 5 minutes.

## Step 1: Set Up MCPs (2 minutes)

1. **Install Firecrawl MCP**:
   ```bash
   npm install -g @mcp/firecrawl
   ```
   Get API key from [firecrawl.dev](https://firecrawl.dev)

2. **Install Perplexity MCP**:
   ```bash
   npm install -g @modelcontextprotocol/server-perplexity
   ```
   Get API key from [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)

3. **Add to Cursor Settings**:
   - Open Cursor → Settings → General → MCP
   - Add configurations (see `MCP_SETUP_GUIDE.md` for details)

## Step 2: Create Custom Modes (1 minute)

1. Open Cursor Settings → Modes
2. Create these modes (see `CURSOR_CUSTOM_MODES.md` for prompts):
   - **PRD Generator** (Gemini 2.5)
   - **Marketing Expert** (Claude 3.7)
   - **Deep Researcher** (Claude 3.5)

## Step 3: Fill in LLM.ext (1 minute)

1. Open `LLM.ext` file
2. Fill in your product information
3. Save it - agents will use this for context

## Step 4: Test the Workflows (1 minute)

### Option A: Use Frontend UI
1. Start your backend: `cd backend && uvicorn app.main:app --reload`
2. Start your frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:3002/content-marketing`
4. Try the "Content Research" tab

### Option B: Use Cursor Directly
1. Open Cursor
2. Switch to "Marketing Expert" mode
3. Create file: `article_research.mmd`
4. Prompt: "Use Perplexity MCP and Firecrawl MCP to research 'best AI tools 2025'. Put output in article_research.mmd"

## Your First Workflow

### Content Research → Article Creation

1. **Research** (in Cursor):
   ```
   Mode: Marketing Expert
   Prompt: Use Perplexity MCP and Firecrawl MCP to research [your topic]. 
   Create comprehensive article with comparison tables. 
   Put output in article_research.mmd
   ```

2. **Add Product Context**:
   ```
   Based on LLM.ext and article_research.mmd, add [your product] 
   as a comparison and optimize for keywords: [keyword1, keyword2]
   ```

3. **Review & Publish**:
   - Review for accuracy
   - Check keyword optimization
   - Publish to your CMS

## Common Commands

### Content Research
```bash
curl -X POST http://localhost:8080/api/content/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "your topic", "num_results": 10}'
```

### Internal Linking
```bash
curl -X POST http://localhost:8080/api/content/internal-linking \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://yoursite.com", "num_articles": 10}'
```

### Generate Micro Tool
```bash
curl -X POST http://localhost:8080/api/content/micro-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "UTM Generator",
    "tool_description": "Generate UTM links",
    "target_audience": ["marketer", "business owner"]
  }'
```

## Next Steps

1. ✅ MCPs set up
2. ✅ Custom modes created
3. ✅ LLM.ext filled in
4. ✅ First workflow tested

**Now you can**:
- Create content at scale
- Analyze internal linking
- Generate micro tools
- Build PRDs for features

## Need Help?

- **Detailed MCP Setup**: See `MCP_SETUP_GUIDE.md`
- **Custom Modes**: See `CURSOR_CUSTOM_MODES.md`
- **Full Implementation**: See `IMPLEMENTATION_GUIDE.md`
- **All Highlights**: See `CURSOR_VIBE_MARKETING_HIGHLIGHTS.md`

---

**Pro Tip**: Start with one workflow, master it, then expand. Don't try to do everything at once!



